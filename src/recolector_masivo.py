import requests
import time
import random
import json
import os
from concurrent.futures import ThreadPoolExecutor
from collections import deque

from .db_manager import obtener_conexion, inicializar_db
from .riot_api import cargar_objetos  # usamos el mismo loader de items que el recomendador

# ============================================================================
# VERSIÓN / PARCHE ACTUAL (desde Data Dragon)
# ============================================================================

def obtener_parche_actual_desde_riot():
    """
    Consulta https://ddragon.leagueoflegends.com/api/versions.json
    y devuelve (parche_major_minor, version_completa), por ejemplo:
      ("26.1", "26.1.3")
    """
    try:
        url = "https://ddragon.leagueoflegends.com/api/versions.json"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        version_completa = resp.json()[0]  # primer elemento = versión live
    except Exception as e:
        print(f"❌ Error al consultar la versión de Riot: {e}")
        version_completa = "14.4.1"  # fallback seguro

    partes = version_completa.split(".")
    parche = ".".join(partes[:2]) if len(partes) >= 2 else "0.0"
    return parche, version_completa


# =============================================================================
# CONFIGURACIÓN PRO
# =============================================================================

# Cargar la API Key dinámicamente desde config.json
try:
    with open("config.json", "r") as config_file:
        config = json.load(config_file)
        API_KEY = config.get("API_KEY", "")
except FileNotFoundError:
    print("❌ Error: No se encontró el archivo config.json en el directorio actual.")
    API_KEY = ""

# Match-V5 para Américas (NA, BR, LAN, LAS)
REGION_ROUTING = "americas"

# Plataformas que usaremos como semilla (Challenger/GM/Master)
PLATFORMS = ["la2", "la1", "na1", "br1"]  # LAS, LAN, NA, BR

HEADERS = {"X-Riot-Token": API_KEY}

# Diccionario de ítems de Data Dragon
ITEMS_DATA = cargar_objetos()

# Ítems finales de misión de support (igual que en recomendador.py)
ITEMS_SUPP_FINAL = {"3866", "3867", "3869", "3870", "3871", "3873", "3874"}

# Cola de jugadores pendientes y set de control para no repetir
cola_exploracion = deque()
jugadores_visitados = set()

# Parche actual (major.minor), ej: "26.1"
PARCHE_ACTUAL, VERSION_COMPLETA = obtener_parche_actual_desde_riot()
print(f"🛈 Recolector configurado para parche: {PARCHE_ACTUAL} (versión completa {VERSION_COMPLETA})")


# =============================================================================
# HELPERS DE ITEMS
# =============================================================================

def es_bota(item_id: str) -> bool:
    """True si el ítem es una bota real (tag 'Boots', sin ser consumible/trinket)."""
    data = ITEMS_DATA.get(item_id, {})
    tags = data.get("tags", [])
    if not tags:
        return False
    if "Consumable" in tags or "Vision" in tags or "Trinket" in tags:
        return False
    return "Boots" in tags


def es_item_supp_final(item_id: str) -> bool:
    """True si es el ítem final de misión de support."""
    return item_id in ITEMS_SUPP_FINAL


# =============================================================================
# LÓGICA DE PETICIONES
# =============================================================================

def peticion_segura(url):
    """Maneja los límites de Riot (429) y errores de red de forma automática."""
    while True:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                espera = int(resp.headers.get("Retry-After", 10))
                print(f"⏳ Límite alcanzado. Esperando {espera}s...")
                time.sleep(espera)
            elif resp.status_code in [500, 502, 503, 504]:
                time.sleep(5)
            else:
                print(f"⚠️ Error HTTP {resp.status_code} al consultar la API.")
                try:
                    print(f"Detalle de Riot: {resp.json()}")
                except Exception:
                    pass
                return None
        except Exception:
            time.sleep(2)
            continue


def sembrar_desde_high_elo():
    """
    Obtiene jugadores aleatorios de Challenger, Grandmaster y Master
    para arrancar el crawler, usando varias plataformas (LAS, LAN, NA, BR).
    """
    puuids_semilla = []

    ligas = {
        "CHALLENGER": "challengerleagues",
        "GRANDMASTER": "grandmasterleagues",
        "MASTER": "masterleagues",
    }
    queue = "RANKED_SOLO_5x5"

    for platform in PLATFORMS:
        for nombre_liga, endpoint in ligas.items():
            print(f"🏆 Buscando {nombre_liga} en {platform.upper()}...")
            url = (
                f"https://{platform}.api.riotgames.com/lol/league/v4/"
                f"{endpoint}/by-queue/{queue}"
            )
            datos_liga = peticion_segura(url)

            if not datos_liga or "entries" not in datos_liga:
                print(f"❌ No se pudo obtener {nombre_liga} en {platform.upper()}.")
                continue

            # Hasta 10 jugadores por liga/plataforma para no abusar del rate limit
            entradas = random.sample(
                datos_liga["entries"],
                min(10, len(datos_liga["entries"]))
            )
            print(
                f"🔍 {platform.upper()} {nombre_liga}: "
                f"extrayendo PUUIDs de {len(entradas)} jugadores..."
            )

            for entrada in entradas:
                puuid = entrada.get("puuid")
                if puuid:
                    puuids_semilla.append(puuid)

    if not puuids_semilla:
        print("❌ No se encontraron PUUIDs válidos en ninguna plataforma/liga.")
        return False

    unicos = 0
    for puuid in puuids_semilla:
        if puuid not in jugadores_visitados:
            jugadores_visitados.add(puuid)
            cola_exploracion.append(puuid)
            unicos += 1

    print(
        f"✅ Semilla High-Elo lista. {unicos} jugadores únicos en cola "
        f"desde {len(PLATFORMS)} plataformas y 3 ligas (Challenger/GM/Master)."
    )
    return True


def procesar_jugador(puuid):
    """
    Descarga el historial de un jugador y procesa sus partidas.

    Objetivo: si el jugador tiene partidas del parche actual,
    intentar capturar TODAS las que encontremos entre sus últimas N.
    """
    url_historial = (
        f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/"
        f"by-puuid/{puuid}/ids?queue=420&start=0&count=50"
    )
    match_ids = peticion_segura(url_historial)

    if not match_ids:
        return 0

    partidas_nuevas = 0
    for m_id in match_ids:
        # descargar_partida ya filtra por duración y PARCHE_ACTUAL
        if descargar_partida(m_id):
            partidas_nuevas += 1

    return partidas_nuevas


def descargar_partida(match_id):
    """
    Descarga y guarda la partida, alimentando la cola de exploración.

    - Solo guarda partidas del parche actual (PARCHE_ACTUAL).
    - Reconstruye botas e item de misión de supp usando el TIMELINE.
    """
    conn = obtener_conexion()
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM matches WHERE match_id = ?", (match_id,))
    if cur.fetchone():
        conn.close()
        return False

    # Match principal
    url_match = (
        f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    )
    data = peticion_segura(url_match)

    if not data or "info" not in data:
        conn.close()
        return False

    info = data["info"]

    # Filtrar partidas muy cortas
    if info.get("gameDuration", 0) < 600:
        conn.close()
        return False

    # Filtrar por parche (major.minor)
    version = info.get("gameVersion", "0")
    parts = version.split(".")
    patch = ".".join(parts[:2]) if len(parts) >= 2 else "0.0"

    if patch != PARCHE_ACTUAL:
        # No guardamos partidas de parches viejos para mantener la BD limpia
        conn.close()
        return False

    # Timeline para detectar botas / supp quest (slot extra)
    url_timeline = (
        f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/"
        f"{match_id}/timeline"
    )
    timeline = peticion_segura(url_timeline)

    boots_por_participante = {}
    supp_por_participante = {}

    if timeline and "info" in timeline:
        frames = timeline["info"].get("frames", [])
        for frame in frames:
            for ev in frame.get("events", []):
                if ev.get("type") != "ITEM_PURCHASED":
                    continue
                pid = ev.get("participantId")
                item_id = str(ev.get("itemId", 0))
                if not pid or item_id == "0":
                    continue

                if es_bota(item_id):
                    # última bota comprada (incluye upgrades)
                    boots_por_participante[pid] = item_id
                elif es_item_supp_final(item_id):
                    supp_por_participante[pid] = item_id

    try:
        # Guardar match
        cur.execute(
            """
            INSERT INTO matches (match_id, game_version, game_duration, patch)
            VALUES (?, ?, ?, ?)
            """,
            (match_id, version, info.get("gameDuration", 0), patch),
        )

        # Guardar participantes
        for p in info.get("participants", []):
            p_puuid = p.get("puuid")
            if p_puuid and p_puuid not in jugadores_visitados:
                jugadores_visitados.add(p_puuid)
                cola_exploracion.append(p_puuid)

            raw_name = p.get("championName")
            champ = raw_name if raw_name != "MonkeyKing" else "Wukong"

            # Inventario final (item0..item6)
            items_ids = [
                str(p.get(f"item{i}", 0))
                for i in range(7)
                if p.get(f"item{i}", 0) != 0
            ]

            # Detectar si ya hay botas / supp quest en el inventario final
            tiene_bota = any(es_bota(i) for i in items_ids)
            tiene_supp_final = any(es_item_supp_final(i) for i in items_ids)

            pid = p.get("participantId")
            team_position = p.get("teamPosition", "")

            # Inyectar bota si sólo aparece en el timeline (slot de misión ADC)
            if not tiene_bota and pid in boots_por_participante:
                items_ids.append(boots_por_participante[pid])

            # Inyectar item de misión final de supp si sólo aparece en el timeline
            if team_position == "UTILITY" and not tiene_supp_final and pid in supp_por_participante:
                items_ids.append(supp_por_participante[pid])

            items = ",".join(items_ids)

            # --- RUNAS + SHARDS ---
            styles = p.get("perks", {}).get("styles", [])
            runas_lista = []
            for style in styles:
                runas_lista.append(str(style.get("style")))
                for seleccion in style.get("selections", []):
                    runas_lista.append(str(seleccion.get("perk")))

            statPerks = p.get("perks", {}).get("statPerks", {})
            if statPerks:
                runas_lista.append(str(statPerks.get("defense", "")))
                runas_lista.append(str(statPerks.get("flex", "")))
                runas_lista.append(str(statPerks.get("offense", "")))

            runas_str = ",".join([r for r in runas_lista if r])

            # --- HECHIZOS Y KDA ---
            spells = f"{p.get('summoner1Id', 0)},{p.get('summoner2Id', 0)}"
            kills = p.get("kills", 0)
            deaths = p.get("deaths", 0)
            assists = p.get("assists", 0)

            cur.execute(
                """
                INSERT INTO participantes
                    (match_id, champion, team_position, team, win,
                     items, runes, spells, kills, deaths, assists)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    champ,
                    team_position,
                    p.get("teamId", 0),
                    1 if p.get("win") else 0,
                    items,
                    runas_str,
                    spells,
                    kills,
                    deaths,
                    assists,
                ),
            )

        conn.commit()
        return True

    except Exception as e:
        print(f"Error guardando en BD: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def ejecutar_recoleccion_masiva(meta=5000):
    """Orquestador multihilo."""
    print("🌟 Iniciando gran recolección automatizada High-Elo")

    if not sembrar_desde_high_elo():
        print("❌ Error crítico: No se pudo obtener la semilla. Revisa tu API Key.")
        return

    total_descargado = 0

    with ThreadPoolExecutor(max_workers=3) as executor:
        while total_descargado < meta and cola_exploracion:
            actual = cola_exploracion.popleft()

            futuro = executor.submit(procesar_jugador, actual)
            resultado = futuro.result()

            total_descargado += resultado
            print(
                f"📈 Total partidas en BD: {total_descargado} / {meta} "
                f"(En cola: {len(cola_exploracion)})"
            )

            # No ponemos sleep fijo: dejamos que el manejo de 429 nos regule


if __name__ == "__main__":
    inicializar_db()
    ejecutar_recoleccion_masiva(meta=20000)