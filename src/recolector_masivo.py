import requests
import time
import random
import json
import os
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from .db_manager import obtener_conexion, inicializar_db

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

REGION_ROUTING = "americas"
PLATFORM_ROUTING = "la2"
HEADERS = {"X-Riot-Token": API_KEY}

# Cola de jugadores pendientes y set de control para no repetir
cola_exploracion = deque()
jugadores_visitados = set()

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
        except Exception as e:
            time.sleep(2)
            continue

def sembrar_desde_high_elo():
    """Obtiene jugadores aleatorios de Challenger para arrancar el crawler."""
    print(f"🏆 Buscando élite Challenger en el servidor {PLATFORM_ROUTING.upper()}...")
    url_challenger = f"https://{PLATFORM_ROUTING}.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/RANKED_SOLO_5x5"
    datos_liga = peticion_segura(url_challenger)

    if not datos_liga or "entries" not in datos_liga:
        print("❌ No se pudo obtener la liga Challenger.")
        return False

    entradas = random.sample(datos_liga["entries"], min(10, len(datos_liga["entries"])))
    print(f"🔍 Extrayendo PUUIDs directamente de {len(entradas)} jugadores...")

    puuids_semilla = []
    for entrada in entradas:
        puuid = entrada.get("puuid")
        if puuid:
            puuids_semilla.append(puuid)

    if not puuids_semilla:
        print("❌ No se encontraron PUUIDs válidos.")
        return False

    for puuid in puuids_semilla:
        cola_exploracion.append(puuid)
        jugadores_visitados.add(puuid)

    print(f"✅ Semilla High-Elo lista. {len(puuids_semilla)} jugadores en cola.")
    return True

def procesar_jugador(puuid):
    """Descarga el historial de un jugador y procesa sus partidas."""
    url_historial = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start=0&count=10"
    match_ids = peticion_segura(url_historial)
    
    if not match_ids:
        return 0

    partidas_nuevas = 0
    for m_id in match_ids:
        if descargar_partida(m_id):
            partidas_nuevas += 1
    return partidas_nuevas

def descargar_partida(match_id):
    """Descarga y guarda la partida, alimentando la cola de exploración."""
    conn = obtener_conexion()
    cur = conn.cursor()
    
    cur.execute("SELECT 1 FROM matches WHERE match_id = ?", (match_id,))
    if cur.fetchone():
        conn.close()
        return False

    url_match = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    data = peticion_segura(url_match)
    
    if not data or "info" not in data:
        conn.close()
        return False

    info = data["info"]
    if info.get("gameDuration", 0) < 600:
        conn.close()
        return False

    try:
        version = info.get("gameVersion", "0")
        parts = version.split(".")
        patch = f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else "0.0"

        cur.execute("INSERT INTO matches (match_id, game_version, game_duration, patch) VALUES (?, ?, ?, ?)",
                    (match_id, version, info.get("gameDuration", 0), patch))

        for p in info.get("participants", []):
            p_puuid = p.get("puuid")
            if p_puuid and p_puuid not in jugadores_visitados:
                cola_exploracion.append(p_puuid)
                jugadores_visitados.add(p_puuid)

            champ = p.get("championName", "Wukong" if p.get("championName") == "MonkeyKing" else p.get("championName"))
            items = ",".join([str(p.get(f"item{i}", 0)) for i in range(7) if p.get(f"item{i}", 0) != 0])
            
            # --- LECTURA DE RUNAS Y SHARDS ---
            styles = p.get("perks", {}).get("styles", [])
            runas_lista = []
            for style in styles:
                runas_lista.append(str(style.get("style")))
                for seleccion in style.get("selections", []):
                    runas_lista.append(str(seleccion.get("perk")))
            
            # --- NUEVO: Extraer Mini Estadísticas ---
            statPerks = p.get("perks", {}).get("statPerks", {})
            if statPerks:
                runas_lista.append(str(statPerks.get("defense", "")))
                runas_lista.append(str(statPerks.get("flex", "")))
                runas_lista.append(str(statPerks.get("offense", "")))
                
            runas_str = ",".join([r for r in runas_lista if r])
            
            # --- LECTURA DE HECHIZOS Y KDA ---
            spells = f"{p.get('summoner1Id', 0)},{p.get('summoner2Id', 0)}"
            kills = p.get('kills', 0)
            deaths = p.get('deaths', 0)
            assists = p.get('assists', 0)
            
            # Insert con las nuevas columnas
            cur.execute("""
                INSERT INTO participantes (match_id, champion, team_position, team, win, items, runes, spells, kills, deaths, assists)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (match_id, champ, p.get("teamPosition", ""), p.get("teamId", 0), 1 if p.get("win") else 0, items, runas_str, spells, kills, deaths, assists))
        
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
            print(f"📈 Total partidas en BD: {total_descargado} / {meta} (En cola: {len(cola_exploracion)})")
            
            time.sleep(2)

if __name__ == "__main__":
    inicializar_db()  # <-- Construye las tablas si no existen
    ejecutar_recoleccion_masiva(meta=20000)