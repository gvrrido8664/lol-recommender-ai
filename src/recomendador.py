import sqlite3
from .db_manager import obtener_conexion
from .riot_api import cargar_objetos

# Cargamos el diccionario de objetos una sola vez en memoria al importar el módulo
# Esto hace que las consultas sean rapidísimas
ITEMS_DATA = cargar_objetos()

BOTAS_IDS = {3006, 3009, 3020, 3158, 3111, 3047, 3117, 3302, 3303}
# IDs de los items con los que se sale de base
STARTERS_IDS = {1054, 1055, 1056, 1082, 1083, 1101, 1102, 1103, 3865, 3070} 
# IDs de baratijas, pociones y wards
WARDS_CONSUMIBLES = {2003, 2031, 2033, 2055, 3340, 3363, 3364}
def obtener_campeones_por_rol(rol_api, porcentaje_minimo=0.01):
    """
    Devuelve los campeones que representan al menos el 'porcentaje_minimo' (ej. 1%) 
    de todas las partidas jugadas en ese rol. ¡Filtra automáticamente los picks troll!
    """
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
    """
    Busca enfrentamientos directos en una línea y devuelve los campeones
    que más le ganan al 'enemigo' seleccionado.
    """
    conn = obtener_conexion()
    cur = conn.cursor()

    consulta = """
        SELECT 
            p2.champion AS counter_champ,
            ROUND(SUM(p2.win) * 100.0 / COUNT(*), 1) AS winrate,
            COUNT(*) AS partidas
        FROM participantes p1
        JOIN participantes p2 ON p1.match_id = p2.match_id
        WHERE p1.champion = ?
          AND p1.team_position = ?
          AND p2.team_position = p1.team_position
          AND p1.team != p2.team
        GROUP BY p2.champion
        HAVING partidas >= ?
        ORDER BY winrate DESC
        LIMIT 50
    """
    cur.execute(consulta, (enemigo, carril, min_partidas))
    resultados = [(row["counter_champ"], row["winrate"], row["partidas"]) for row in cur.fetchall()]
    conn.close()
    return resultados

def obtener_top_items(campeon, carril):
    """
    Separa analíticamente los items iniciales de la build completa (6 items).
    Filtra wards, pociones y componentes a medio armar.
    """
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT items
        FROM participantes
        WHERE champion = ? AND win = 1 AND team_position = ? AND items != ''
    """, (campeon, carril))
    filas = cur.fetchall()
    conn.close()

    starters_count = {}
    finales_count = {}

    for row in filas:
        if not row["items"]: continue
        ids = row["items"].split(",")
        for i in ids:
            if not i: continue
            str_id = str(int(i))
            
            item_info = ITEMS_DATA.get(str_id)
            if not item_info: continue

            tags = item_info.get("tags", [])
            id_int = int(str_id)
            
            # 1. BLOQUEAR Wards, Consumibles y Baratijas
            if id_int in WARDS_CONSUMIBLES or "Consumable" in tags or "Vision" in tags or "Trinket" in tags:
                continue

            # 2. SEPARAR Items Iniciales
            if id_int in STARTERS_IDS:
                starters_count[str_id] = starters_count.get(str_id, 0) + 1
                continue

            # 3. IDENTIFICAR Build Completa
            es_bota = id_int in BOTAS_IDS
            # La regla de oro: Cuesta más de 1500g y NO se puede evolucionar en nada más (avanza_a vacío)
            es_final = item_info.get("oro", 0) >= 1500 and len(item_info.get("avanza_a", [])) == 0

            if es_bota or es_final:
                finales_count[str_id] = finales_count.get(str_id, 0) + 1

    # Extraemos el Top 2 de iniciales
    top_starters = sorted(starters_count, key=starters_count.get, reverse=True)[:2]

    # Extraemos el Top 6 de la build final (limitando a 1 bota máximo)
    top_finales = []
    bota_encontrada = False
    for id_item in sorted(finales_count, key=finales_count.get, reverse=True):
        if int(id_item) in BOTAS_IDS:
            if bota_encontrada: continue
            bota_encontrada = True
        top_finales.append(id_item)
        if len(top_finales) == 6:
            break

    # Retorna dos listas separadas
    return top_starters, top_finales

def obtener_winrate_5v5(lista_aliados, lista_enemigos):
    """
    Busca partidas donde se enfrenten exactamente esas dos composiciones de 5.
    """
    if len(lista_aliados) != 5 or len(lista_enemigos) != 5:
        return 0, 0

    conn = obtener_conexion()
    cur = conn.cursor()

    # Aliados en el mismo equipo
    cur.execute("""
        SELECT match_id, team
        FROM participantes
        WHERE champion IN ({})
        GROUP BY match_id, team
        HAVING COUNT(DISTINCT champion) = 5
    """.format(','.join(['?']*len(lista_aliados))), lista_aliados)
    matches_aliados = cur.fetchall()

    if not matches_aliados:
        conn.close()
        return 0, 0

    # Enemigos en el mismo equipo
    cur.execute("""
        SELECT match_id, team
        FROM participantes
        WHERE champion IN ({})
        GROUP BY match_id, team
        HAVING COUNT(DISTINCT champion) = 5
    """.format(','.join(['?']*len(lista_enemigos))), lista_enemigos)
    matches_enemigos = cur.fetchall()

    if not matches_enemigos:
        conn.close()
        return 0, 0

    # Cruzar por match_id con equipos diferentes
    victorias = 0
    total = 0
    for match_al in matches_aliados:
        for match_en in matches_enemigos:
            if match_al["match_id"] == match_en["match_id"] and match_al["team"] != match_en["team"]:
                cur.execute("""
                    SELECT win FROM participantes
                    WHERE match_id = ? AND team = ? LIMIT 1
                """, (match_al["match_id"], match_al["team"]))
                row = cur.fetchone()
                if row and row["win"] == 1:
                    victorias += 1
                total += 1
                break
                
    conn.close()
    if total == 0:
        return 0, 0
    return round(victorias * 100.0 / total, 1), total