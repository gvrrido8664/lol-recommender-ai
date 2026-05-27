import sqlite3
import os
import json
from .db_manager import obtener_conexion, DATA_DIR
from .riot_api import cargar_objetos, cargar_runas, cargar_campeones
from .tags_champions import (
    obtener_dano, es_tanque, es_mago, es_tirador, es_asesino, es_luchador, es_soporte,
    obtener_nivel_cc, obtener_subrol_soporte, obtener_tag, es_botas_estaticas, obtener_bota_estatica
)
from .itemizador_dinamico import recomendar_bota, recomendar_item_defensivo
from .razonador import razonar_pick, razonar_hechizos, razonar_botas, razonar_runas, razonar_objeto

ITEMS_DATA = cargar_objetos()
RUNAS_DATA = cargar_runas()

# Ítems especiales por rol
ITEMS_JUNGLA = ["1101", "1102", "1103"]
ITEM_SUPP_BASE = "3865"
ITEMS_SUPP_FINAL = ["3866", "3867", "3869", "3870", "3871", "3873", "3874"]
SUPPORT_STARTERS = ["3865", "3850", "3851", "3854", "3855"]
BOTASREALES = {
    1001, 2422, 3006, 3009, 3020, 3047,
    3111, 3117, 3158, 3301, 3302, 3303,
    3156, 3173, 3174
}

# FIX: Diccionario de excepciones para el cálculo AD/AP perfecto
AP_EXCEPTIONS = {"Sylas", "Akali", "Diana", "Ekko", "Evelynn", "Fizz", "Gwen", "Katarina", 
                 "Mordekaiser", "Nidalee", "Rumble", "Shaco", "Singed", "Vladimir", "Zac", 
                 "Gragas", "Elise", "Volibear", "Kennen", "Teemo", "Azir", "Kassadin", "Leblanc"}

# Tanques que hacen daño AP (para el cálculo AD/AP)
AP_TANKS = {"Amumu", "ChoGath", "Galio", "Malphite", "Maokai", "Nunu", "Ornn",
            "Rammus", "Sejuani", "Shen", "Sion", "Zac", "Skarner"}

# Campeones con tag "Fighter" que NO son frontlane (asesinos, duelistas frágiles)
FRONTLANE_EXCLUDE = {"Fizz", "KhaZix", "MasterYi", "Quinn", "Rengar", "Shaco",
                     "Tryndamere", "Yasuo", "Yone", "Fiora", "Gwen", "Irelia",
                     "Kayn", "LeeSin", "Nidalee", "Riven", "Viego", "BelVeth",
                     "Elise", "Evelynn", "Katarina", "Akali", "Sylas", "Diana",
                     "Ekko", "Kassadin", "Leblanc"}

def obtener_campeones_por_rol(rol_api, min_partidas=20):
    conn = obtener_conexion()
    cur = conn.cursor()

    cur.execute("""
        SELECT champion
        FROM participantes
        WHERE team_position = ?
        GROUP BY champion
        HAVING COUNT(*) >= ?
        ORDER BY COUNT(*) DESC
        LIMIT 45
    """, (rol_api, min_partidas))

    resultados = [row["champion"] for row in cur.fetchall()]
    conn.close()
    return resultados

def obtener_counters(carril, enemigo, min_partidas=20):
    conn = obtener_conexion()
    cur = conn.cursor()
    campeones_validos = obtener_campeones_por_rol(carril, min_partidas=min_partidas)

    consulta = """
        SELECT
            p2.champion AS counter_champ,
            ROUND(SUM(p2.win) * 100.0 / COUNT(*), 1) AS winrate,
            COUNT(*) AS partidas
        FROM participantes p1
        JOIN participantes p2 ON p1.match_id = p2.match_id
        WHERE p1.champion = ? AND p1.team_position = ? AND p2.team_position = p1.team_position AND p1.team != p2.team
        GROUP BY p2.champion
        HAVING COUNT(*) >= ?
        ORDER BY winrate DESC
        LIMIT 50
    """
    cur.execute(consulta, (enemigo, carril, min_partidas))
    resultados = [(row["counter_champ"], row["winrate"], row["partidas"]) for row in cur.fetchall() if row["counter_champ"] in campeones_validos]
    conn.close()
    return resultados

def obtener_peores_matchups(campeon, carril, min_partidas=20):
    conn = obtener_conexion()
    cur = conn.cursor()
    consulta = """
        SELECT
            p2.champion AS counter_champ,
            ROUND(SUM(p2.win) * 100.0 / COUNT(*), 1) AS enemy_winrate,
            COUNT(*) AS partidas
        FROM participantes p1
        JOIN participantes p2 ON p1.match_id = p2.match_id
        WHERE p1.champion = ? AND p1.team_position = ? AND p2.team_position = p1.team_position AND p1.team != p2.team
        GROUP BY p2.champion
        HAVING COUNT(*) >= ?
        ORDER BY enemy_winrate DESC
        LIMIT 10
    """
    cur.execute(consulta, (campeon, carril, min_partidas))
    resultados = [(row["counter_champ"], row["enemy_winrate"], row["partidas"]) for row in cur.fetchall()]
    conn.close()
    return resultados

def _recomendar_botas_inteligentes(botas_count, enemigos, campeon, carril):
    """Decide la bota optima segun el draft enemigo usando el itemizador dinamico.
    La recomendacion del sistema SIEMPRE tiene prioridad sobre la estadistica,
    porque los datos historicos estan sesgados (la mayoria de partidas son AD vs AD)."""
    if not enemigos:
        return max(botas_count, key=botas_count.get) if botas_count else None

    try:
        bota_id, razon, es_estatica = recomendar_bota(campeon, enemigos, botas_count)
        if bota_id:
            return bota_id  # <-- El sistema decide, sin importar stats
    except Exception:
        pass

    return max(botas_count, key=botas_count.get) if botas_count else None


def obtener_top_items(campeon, carril, enemigos=None):
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("SELECT items, win FROM participantes WHERE champion = ? AND team_position = ? AND items != ''", (campeon, carril))
    filas = cur.fetchall()
    
    if not filas:
        cur.execute("SELECT items, win FROM participantes WHERE champion = ? AND items != ''", (campeon,))
        filas = cur.fetchall()

    if not filas:
        conn.close()
        return ["1055", "2003", "2003"], []

    core_count, botas_count, supp_final_count, starters_count = {}, {}, {}, {}

    for row in filas:
        items_lista = [i.strip() for i in row["items"].split(",") if i and i.strip() != "0"]
        peso = 2 if bool(row["win"]) else 1 

        for i in items_lista:
            i = str(i).strip()
            info = ITEMS_DATA.get(i, {}) or (ITEMS_DATA.get(int(i), {}) if i.isdigit() else {})
            tags = info.get("tags", [])
            costo = info.get("oro", 0)

            if "Consumable" in tags or "Vision" in tags or "Trinket" in tags: continue
            es_bota = "Boots" in tags
            es_supp_final = i in ITEMS_SUPP_FINAL

            if es_bota:
                if i not in ("1001", "2422"): botas_count[i] = botas_count.get(i, 0) + peso
            elif es_supp_final: supp_final_count[i] = supp_final_count.get(i, 0) + peso
            elif costo <= 500 and i not in ("2003", "2031", "2033"): starters_count[i] = starters_count.get(i, 0) + peso
            else:
                if costo >= 1500 or (costo == 0 and not info.get("avanza_a")): core_count[i] = core_count.get(i, 0) + peso

    if carril == "JUNGLE":
        jg = {k: v for k, v in starters_count.items() if k in ITEMS_JUNGLA}
        starter_principal = max(jg, key=jg.get) if jg else "1102"
    elif carril == "UTILITY":
        ss = {k: v for k, v in starters_count.items() if k in SUPPORT_STARTERS}
        starter_principal = max(ss, key=ss.get) if ss else "3865"
    else:
        starter_principal = max(starters_count, key=starters_count.get) if starters_count else "1055"

    combo_starters = [starter_principal]
    costo_base = ITEMS_DATA.get(starter_principal, {}).get("oro", 0)
    for _ in range(max(0, (500 - costo_base) // 50)): combo_starters.append("2003")

    build_final = []
    if not botas_count:
        cur.execute("SELECT items FROM participantes WHERE team_position = ? AND items != ''", (carril,))
        for row in cur.fetchall():
            ids = [x.strip() for x in row["items"].split(",") if x and x.strip() != "0"]
            for iid in ids:
                tags = ITEMS_DATA.get(iid, {}).get("tags", [])
                if "Boots" in tags and "Consumable" not in tags and "Vision" not in tags and iid not in ("1001", "2422"):
                    botas_count[iid] = botas_count.get(iid, 0) + 1
    if botas_count:
        if enemigos:
            bota_inteligente = _recomendar_botas_inteligentes(botas_count, enemigos, campeon, carril)
            build_final.append(bota_inteligente if bota_inteligente else max(botas_count, key=botas_count.get))
        else:
            build_final.append(max(botas_count, key=botas_count.get))

    item_supp_mejorado = None
    if carril == "UTILITY":
        cur.execute("SELECT items FROM participantes WHERE champion = ? AND team_position = 'UTILITY' AND items != ''", (campeon,))
        supp_count_champ = {}
        for row in cur.fetchall():
            for iid in [x.strip() for x in row["items"].split(",") if x and x.strip() != "0"]:
                if iid in ITEMS_SUPP_FINAL: supp_count_champ[iid] = supp_count_champ.get(iid, 0) + 1
        if supp_count_champ: item_supp_mejorado = max(supp_count_champ, key=supp_count_champ.get)
        if item_supp_mejorado: build_final.append(item_supp_mejorado)

    espacios_restantes = max(0, (7 if carril == "BOTTOM" else 6) - len(build_final))
    if core_count and espacios_restantes > 0:
        core_ordenado = sorted(core_count, key=core_count.get, reverse=True)[:espacios_restantes]
        build_final.extend(core_ordenado)

    conn.close()
    return combo_starters, build_final

def obtener_top_runas(campeon, carril):
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("SELECT runes FROM participantes WHERE champion = ? AND team_position = ? AND runes != ''", (campeon, carril))
    filas = cur.fetchall()
    if not filas:
        cur.execute("SELECT runes FROM participantes WHERE champion = ? AND runes != ''", (campeon,))
        filas = cur.fetchall()
    conn.close()
    if not filas: return []

    conteo_principal, conteo_shard_ofensivo, conteo_shard_flex, conteo_shard_defensivo = {}, {}, {}, {}
    for row in filas:
        partes = [r.strip() for r in row["runes"].split(",") if r.strip()]
        if len(partes) >= 8: conteo_principal[",".join(partes[:8])] = conteo_principal.get(",".join(partes[:8]), 0) + 1
        if len(partes) >= 11:
            conteo_shard_defensivo[partes[-3]] = conteo_shard_defensivo.get(partes[-3], 0) + 1
            conteo_shard_flex[partes[-2]] = conteo_shard_flex.get(partes[-2], 0) + 1
            conteo_shard_ofensivo[partes[-1]] = conteo_shard_ofensivo.get(partes[-1], 0) + 1

    mejor_principal = max(conteo_principal, key=conteo_principal.get) if conteo_principal else ""
    runas_finales = mejor_principal.split(",") if mejor_principal else []
    runas_finales.append(max(conteo_shard_ofensivo, key=conteo_shard_ofensivo.get) if conteo_shard_ofensivo else "5008") 
    runas_finales.append(max(conteo_shard_flex, key=conteo_shard_flex.get) if conteo_shard_flex else "5008") 
    runas_finales.append(max(conteo_shard_defensivo, key=conteo_shard_defensivo.get) if conteo_shard_defensivo else "5011") 
    return runas_finales

def obtener_top_hechizos(campeon, carril):
    conn = obtener_conexion()
    cur = conn.cursor()
    try:
        cur.execute("SELECT spells FROM participantes WHERE champion = ? AND team_position = ? AND spells != ''", (campeon, carril))
        filas = cur.fetchall()
        if not filas:
            cur.execute("SELECT spells FROM participantes WHERE champion = ? AND spells != ''", (campeon,))
            filas = cur.fetchall()
    except:
        conn.close()
        return ["4", "14"]
    conn.close()

    conteo = {}
    for row in filas:
        partes = sorted([s for s in row["spells"].split(",") if s])
        if len(partes) == 2:
            llave = f"{partes[0]},{partes[1]}"
            conteo[llave] = conteo.get(llave, 0) + 1
    return max(conteo, key=conteo.get).split(",") if conteo else ["4", "14"]

def obtenermejoresbaneos(carril, min_partidas=20):
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT champion, ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM participantes WHERE team_position = ?), 1) AS banrate, COUNT(*) AS partidas
        FROM participantes WHERE team_position = ? GROUP BY champion HAVING COUNT(*) >= ? ORDER BY COUNT(*) DESC LIMIT 10
    """, (carril, carril, min_partidas))
    resultados = [(row["champion"], row["banrate"], row["partidas"]) for row in cur.fetchall()]
    conn.close()
    return resultados

def _clasificar_dano(champ, tags=None):
    """Devuelve 'AD', 'AP' o 'HYBRID' usando el nuevo sistema de tags (Pilar 5)."""
    return obtener_dano(champ)

def _es_frontlane(champ, tags=None):
    """Determina si un campeon puede hacer de frontlane (absorber dano/engagear).
    Los Skirmishers (Yasuo, Yone, Yi, etc.) NO son frontlane aunque sean Fighters."""
    if es_tanque(champ):
        return True
    if es_luchador(champ):
        tag = obtener_tag(champ)
        # Solo Divers y Juggernauts son frontlane; Skirmishers no
        return tag.get("sub_class") in ("Diver", "Juggernaut")
    return False

def analizar_composicion(aliados):
    ad_count, ap_count, tank_count = 0.0, 0.0, 0

    for aliado in aliados:
        dano = obtener_dano(aliado)
        if dano == "AP":
            ap_count += 1.0
        elif dano == "AD":
            ad_count += 1.0
        else:  # HYBRID
            ad_count += 0.5
            ap_count += 0.5

        if _es_frontlane(aliado):
            tank_count += 1

    total_dmg = ad_count + ap_count
    if total_dmg > 0:
        pct_ad = min(100, int((ad_count / total_dmg) * 100))
        pct_ap = min(100, int((ap_count / total_dmg) * 100))
    else:
        pct_ad, pct_ap = 50, 50

    return pct_ad, pct_ap, tank_count

def recomendar_picks_vivo(rol, aliados, enemigos):
    conn = obtener_conexion()
    cur = conn.cursor()
    campeones_rol = obtener_campeones_por_rol(rol, min_partidas=20)
    if not campeones_rol: return {}

    pct_ad, pct_ap, tank_count = analizar_composicion(aliados)
    candidatos = {"Sinergia/Balance": [], "Falta Daño Mágico (AP)": [], "Falta Daño Físico (AD)": [], "Falta Tanque/Engage": []}
    
    for c in campeones_rol:
        dano = obtener_dano(c)
        es_tank = _es_frontlane(c)
        es_ap = dano in ("AP", "HYBRID")
        es_ad = dano in ("AD", "HYBRID")

        wr = 50.0
        if enemigos:
            placeholders = ",".join(["?"]*len(enemigos))
            cur.execute(f"SELECT ROUND(SUM(p1.win)*100.0/COUNT(*),1), COUNT(*) FROM participantes p1 JOIN participantes p2 ON p1.match_id = p2.match_id WHERE p1.champion = ? AND p1.team_position = ? AND p2.champion IN ({placeholders}) AND p1.team != p2.team", [c, rol] + enemigos)
            row = cur.fetchone()
            if row and row[0]:
                n = row[1]
                wr_raw = row[0]
                if n < 3:
                    # Suavizado bayesiano ligero: prior de la BD global (no 50% fijo)
                    cur.execute("SELECT ROUND(SUM(win)*100.0/COUNT(*),1) FROM participantes WHERE champion=?", (c,))
                    prior_row = cur.fetchone()
                    prior = float(prior_row[0]) if prior_row and prior_row[0] else 50.0
                    wr = round((wr_raw * n + prior * (3 - n)) / 3, 1)
                else:
                    wr = wr_raw
            
        if pct_ad >= 60 and es_ap: candidatos["Falta Daño Mágico (AP)"].append((c, wr, "Aporta AP"))
        elif pct_ap >= 60 and es_ad: candidatos["Falta Daño Físico (AD)"].append((c, wr, "Aporta AD"))
        elif tank_count == 0 and es_tank: candidatos["Falta Tanque/Engage"].append((c, wr, "Frontlane"))
        else: candidatos["Sinergia/Balance"].append((c, wr, "Fuerte en Meta"))

    conn.close()
    finales = {}
    for cat, champs in candidatos.items():
        if champs: finales[cat] = sorted(champs, key=lambda x: x[1], reverse=True)[:4]
    return finales

def calcular_winrate_5v5(aliados, enemigos, pos_aliados=None, pos_enemigos=None):
    """Calcula el winrate estimado de un equipo 5v5 usando matchups por línea.
    Empareja cada aliado con su enemigo de misma posición para mayor precisión.
    """
    if len(aliados) != 5 or len(enemigos) != 5:
        return 50.0
    
    conn = obtener_conexion()
    cur = conn.cursor()
    
    # Asignar posiciones por defecto si no vienen del draft
    if not pos_aliados:
        pos_aliados = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
    if not pos_enemigos:
        pos_enemigos = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
    
    # Crear diccionario aliado → posición
    al_pos = dict(zip(aliados, pos_aliados))
    en_pos = dict(zip(enemigos, pos_enemigos))
    
    # Mapa de posiciones equivalentes para emparejar
    pos_equivalentes = {
        "TOP": "TOP", "JUNGLE": "JUNGLE", "JUNGLA": "JUNGLE",
        "MIDDLE": "MIDDLE", "MID": "MIDDLE",
        "BOTTOM": "BOTTOM", "ADC": "BOTTOM",
        "UTILITY": "UTILITY", "SUPPORT": "UTILITY",
    }
    
    wr_por_lane = []
    
    for aliado, pos_al in al_pos.items():
        # Buscar enemigo en la misma posición
        pos_norm = pos_equivalentes.get(pos_al.upper(), pos_al.upper())
        enemigo_lane = None
        for en, pos_en in en_pos.items():
            if pos_equivalentes.get(pos_en.upper(), pos_en.upper()) == pos_norm:
                enemigo_lane = en
                break
        
        if enemigo_lane:
            # WR específico del matchup por línea
            cur.execute("""
                SELECT ROUND(SUM(p1.win)*100.0/COUNT(*), 1) as wr, COUNT(*) as partidas
                FROM participantes p1
                JOIN participantes p2 ON p1.match_id = p2.match_id
                WHERE p1.champion = ? AND p1.team_position = ?
                  AND p2.champion = ? AND p2.team_position = ?
                  AND p1.team != p2.team
            """, (aliado, pos_al, enemigo_lane, pos_norm))
            row = cur.fetchone()
            if row and row["wr"] is not None:
                # Suavizar con prior (50% WR) si hay pocas partidas
                n = row["partidas"]
                wr = (row["wr"] * n + 50.0 * max(0, 5 - n)) / max(5, n)
                wr_por_lane.append(wr)
            else:
                wr_por_lane.append(50.0)
        else:
            wr_por_lane.append(50.0)
    
    conn.close()
    
    if wr_por_lane:
        return round(sum(wr_por_lane) / len(wr_por_lane), 1)
    return 50.0