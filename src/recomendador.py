import sqlite3
import os
import json
from .db_manager import obtener_conexion, DATA_DIR
from .riot_api import cargar_objetos, cargar_runas

ITEMS_DATA = cargar_objetos()
RUNAS_DATA = cargar_runas()

def obtener_campeones_por_rol(rol_api, porcentaje_minimo=0.01):
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM participantes WHERE team_position = ?", (rol_api,))
    total_partidas = cur.fetchone()["total"]
    
    if total_partidas == 0:
        conn.close()
        return []

    min_partidas_reales = total_partidas * porcentaje_minimo
    cur.execute("""
        SELECT champion
        FROM participantes
        WHERE team_position = ?
        GROUP BY champion
        HAVING COUNT(*) >= ?
        ORDER BY COUNT(*) DESC
    """, (rol_api, min_partidas_reales))
    
    resultados = [row["champion"] for row in cur.fetchall()]
    conn.close()
    return resultados

def obtener_counters(carril, enemigo, min_partidas=3):
    conn = obtener_conexion()
    cur = conn.cursor()
    campeones_validos = obtener_campeones_por_rol(carril)

    consulta = """
        SELECT 
            p2.champion AS counter_champ,
            ROUND(SUM(p2.win) * 100.0 / COUNT(*), 1) AS winrate,
            COUNT(*) AS partidas
        FROM participantes p1
        JOIN participantes p2 ON p1.match_id = p2.match_id
        WHERE p1.champion = ? AND p1.team_position = ? AND p2.team_position = p1.team_position AND p1.team != p2.team
        GROUP BY p2.champion
        HAVING partidas >= ?
        ORDER BY winrate DESC
        LIMIT 50
    """
    cur.execute(consulta, (enemigo, carril, min_partidas))
    resultados_brutos = cur.fetchall()
    conn.close()
    
    resultados = []
    for row in resultados_brutos:
        if row["counter_champ"] in campeones_validos:
            resultados.append((row["counter_champ"], row["winrate"], row["partidas"]))
    
    return resultados

def obtener_top_items(campeon, carril):
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("SELECT items FROM participantes WHERE champion = ? AND win = 1 AND team_position = ? AND items != ''", (campeon, carril))
    filas = cur.fetchall()
    conn.close()

    conteo = {}
    for row in filas:
        for i in row["items"].split(","):
            if i: conteo[i] = conteo.get(i, 0) + 1

    starters_count = {}
    finales_count = {}

    for item_id, count in conteo.items():
        info = ITEMS_DATA.get(item_id)
        if not info: continue
        
        costo = info.get("oro", 0)
        tags = info.get("tags", [])
        if "Consumable" in tags or "Vision" in tags or "Trinket" in tags: continue

        es_bota = "Boots" in tags
        es_bota_mejorada = es_bota and costo > 300
        
        # Filtramos pociones de los starters base para calcular la matemática exacta
        if costo <= 500 and not es_bota_mejorada and int(item_id) not in [2003, 2031, 2033]:
            starters_count[item_id] = count
        else:
            if es_bota_mejorada or (costo >= 1500 and not info.get("avanza_a")) or (costo == 0 and not info.get("avanza_a")):
                finales_count[item_id] = count

    # --- 1. LÓGICA DE STARTER (Ítem Base + Pociones Reales) ---
    starter_principal = None
    for item_id in sorted(starters_count, key=starters_count.get, reverse=True):
        starter_principal = item_id
        break # Tomamos el más popular
        
    combo_starters = []
    if starter_principal:
        combo_starters.append(starter_principal)
        info = ITEMS_DATA.get(starter_principal, {})
        costo = info.get("oro", 0)
        oro_restante = 500 - costo
        pociones = oro_restante // 50  # Cada poción estándar cuesta 50g
        
        for _ in range(pociones):
            combo_starters.append("2003") # ID de Poción de Vida
    else:
        # Fallback seguro por línea si la base de datos es pequeña
        if carril == "JUNGLE": combo_starters = ["1102", "2003"]
        elif carril == "BOTTOM": combo_starters = ["1055", "2003"]
        elif carril == "UTILITY": combo_starters = ["3865", "2003", "2003"]
        else: combo_starters = ["1056", "2003", "2003"]

    # --- 2. LÓGICA DE BUILD FINAL (1 Bota + X Objetos) ---
    bota = None
    otros = []
    for item in sorted(finales_count, key=finales_count.get, reverse=True):
        info = ITEMS_DATA.get(item)
        if "Boots" in info.get("tags", []):
            if not bota: bota = item
        else:
            otros.append(item)
        
    limite_otros = 6 if carril == "BOTTOM" else 5
    build_final_limpia = []
    if bota: build_final_limpia.append(bota)
    build_final_limpia.extend(otros[:limite_otros])
    build_final_limpia.sort(key=lambda x: ITEMS_DATA.get(x, {}).get("oro", 0))

    return combo_starters, build_final_limpia

def obtener_top_runas(campeon, carril):
    conn = obtener_conexion()
    cur = conn.cursor()
    try:
        cur.execute("SELECT runes FROM participantes WHERE champion = ? AND win = 1 AND team_position = ? AND runes IS NOT NULL AND runes != ''", (campeon, carril))
        filas = cur.fetchall()
    except:
        conn.close()
        return []
    conn.close()
    
    conteo = {}
    for row in filas:
        r_str = row["runes"]
        conteo[r_str] = conteo.get(r_str, 0) + 1
        
    if not conteo: return []
    mejor_set = max(conteo, key=conteo.get)
    return [r for r in mejor_set.split(",") if r]

def obtener_mejores_baneos(rol, limite=5):
    conn = obtener_conexion()
    cur = conn.cursor()
    campeones_validos = obtener_campeones_por_rol(rol)
    if not campeones_validos:
        conn.close()
        return []

    placeholders = ",".join(["?"] * len(campeones_validos))
    query = f"""
        SELECT champion,
               ROUND(SUM(win) * 100.0 / COUNT(*), 1) AS winrate,
               COUNT(*) AS partidas
        FROM participantes
        WHERE team_position = ? AND champion IN ({placeholders})
        GROUP BY champion
        HAVING partidas >= 15
        ORDER BY winrate DESC, partidas DESC
        LIMIT ?
    """
    
    params = [rol] + campeones_validos + [limite]
    cur.execute(query, params)
    
    resultados = [row["champion"] for row in cur.fetchall()]
    conn.close()
    return resultados

def recomendar_picks_vivo(rol, aliados, enemigos):
    """Evalúa la composición aliada para suplir faltas (Tanque, AP, AD) y contrarrestar al enemigo."""
    conn = obtener_conexion()
    cur = conn.cursor()
    campeones_rol = obtener_campeones_por_rol(rol)
    if not campeones_rol:
        conn.close()
        return []

    ruta_tags = os.path.join(DATA_DIR, "champion_data.json")
    tags_data = {}
    if os.path.exists(ruta_tags):
        with open(ruta_tags, "r", encoding="utf-8") as f:
            tags_data = json.load(f)

    tiene_ap = False
    tiene_ad = False
    tiene_tank = False

    for aliado in aliados:
        info = tags_data.get(aliado, {})
        tags = info.get("tags", [])
        if "Mage" in tags or "Support" in tags: tiene_ap = True
        if "Marksman" in tags or "Assassin" in tags or "Fighter" in tags: tiene_ad = True
        if "Tank" in tags or "Fighter" in tags: tiene_tank = True

    candidatos_filtrados = []
    for c in campeones_rol:
        info = tags_data.get(c, {})
        tags = info.get("tags", [])
        es_ap = "Mage" in tags or "Support" in tags
        es_tank = "Tank" in tags
        es_ad = "Marksman" in tags or "Assassin" in tags or "Fighter" in tags

        puntaje_sinergia = 0
        if not tiene_ap and es_ap: puntaje_sinergia += 2
        if not tiene_tank and es_tank: puntaje_sinergia += 2
        if not tiene_ad and es_ad: puntaje_sinergia += 1

        candidatos_filtrados.append((c, puntaje_sinergia))

    # Tomamos los 20 campeones que mejor completan la composición
    candidatos_filtrados.sort(key=lambda x: x[1], reverse=True)
    top_candidatos = [c[0] for c in candidatos_filtrados[:20]]

    resultados = []
    for champ in top_candidatos:
        if not enemigos:
            cur.execute("SELECT ROUND(SUM(win)*100.0/COUNT(*),1) FROM participantes WHERE champion=? AND team_position=?", (champ, rol))
            row = cur.fetchone()
            wr = row[0] if row and row[0] else 50.0
            resultados.append((champ, wr))
        else:
            # Evaluar el WR de este candidato contra la composición enemiga detectada
            placeholders = ",".join(["?"]*len(enemigos))
            query = f"""
                SELECT ROUND(SUM(p1.win)*100.0/COUNT(*),1)
                FROM participantes p1
                JOIN participantes p2 ON p1.match_id = p2.match_id
                WHERE p1.champion = ? AND p1.team_position = ?
                AND p2.champion IN ({placeholders}) AND p1.team != p2.team
            """
            cur.execute(query, [champ, rol] + enemigos)
            row = cur.fetchone()
            wr = row[0] if row and row[0] else 50.0
            resultados.append((champ, wr))

    conn.close()
    resultados.sort(key=lambda x: x[1], reverse=True)
    return [r[0] for r in resultados[:6]] # Retornamos los mejores 6

def calcular_winrate_5v5(aliados, enemigos):
    """Calcula el winrate promedio de los 5 aliados contra los 5 enemigos basándose en el historial."""
    if len(aliados) != 5 or len(enemigos) != 5:
        return 50.0
        
    conn = obtener_conexion()
    cur = conn.cursor()
    total_wr = []
    
    for aliado in aliados:
        placeholders = ",".join(["?"]*len(enemigos))
        query = f"""
            SELECT SUM(p1.win)*100.0/COUNT(*)
            FROM participantes p1
            JOIN participantes p2 ON p1.match_id = p2.match_id
            WHERE p1.champion = ? AND p2.champion IN ({placeholders}) AND p1.team != p2.team
        """
        cur.execute(query, [aliado] + enemigos)
        row = cur.fetchone()
        if row and row[0]:
            total_wr.append(row[0])
            
    conn.close()
    if total_wr:
        return round(sum(total_wr)/len(total_wr), 1)
    return 50.0