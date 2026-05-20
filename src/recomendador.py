import sqlite3
import os
import json
from .db_manager import obtener_conexion, DATA_DIR
from .riot_api import cargar_objetos, cargar_runas, cargar_campeones

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

def obtener_campeones_por_rol(rol_api, min_partidas=10):
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

def obtener_counters(carril, enemigo, min_partidas=5):
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
        WHERE p1.champion = ?
          AND p1.team_position = ?
          AND p2.team_position = p1.team_position
          AND p1.team != p2.team
        GROUP BY p2.champion
        HAVING COUNT(*) >= ?
        ORDER BY winrate DESC
        LIMIT 50
    """

    cur.execute(consulta, (enemigo, carril, min_partidas))
    resultados = [
        (row["counter_champ"], row["winrate"], row["partidas"])
        for row in cur.fetchall()
        if row["counter_champ"] in campeones_validos
    ]

    conn.close()
    return resultados

def obtener_peores_matchups(campeon, carril, min_partidas=5):
    """Devuelve los campeones que tienen mayor winrate CONTRA el campeón del usuario"""
    conn = obtener_conexion()
    cur = conn.cursor()

    consulta = """
        SELECT
            p2.champion AS counter_champ,
            ROUND(SUM(p2.win) * 100.0 / COUNT(*), 1) AS enemy_winrate,
            COUNT(*) AS partidas
        FROM participantes p1
        JOIN participantes p2 ON p1.match_id = p2.match_id
        WHERE p1.champion = ? 
          AND p1.team_position = ?
          AND p2.team_position = p1.team_position 
          AND p1.team != p2.team
        GROUP BY p2.champion
        HAVING COUNT(*) >= ?
        ORDER BY enemy_winrate DESC
        LIMIT 10
    """

    cur.execute(consulta, (campeon, carril, min_partidas))
    resultados = [
        (row["counter_champ"], row["enemy_winrate"], row["partidas"])
        for row in cur.fetchall()
    ]

    conn.close()
    return resultados

def obtener_top_items(campeon, carril):
    conn = obtener_conexion()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT items, win
        FROM participantes
        WHERE champion = ? AND team_position = ? AND items != ''
        """,
        (campeon, carril),
    )
    filas = cur.fetchall()

    if not filas:
        cur.execute(
            """
            SELECT items, win
            FROM participantes
            WHERE champion = ? AND items != ''
            """,
            (campeon,),
        )
        filas = cur.fetchall()

    if not filas:
        conn.close()
        return ["1055", "2003", "2003"], []

    core_count = {}
    botas_count = {}
    supp_final_count = {}
    starters_count = {}

    for row in filas:
        items_lista = [i.strip() for i in row["items"].split(",") if i and i.strip() != "0"]
        is_win = bool(row["win"])
        peso = 2 if is_win else 1 

        for i in items_lista:
            i = str(i).strip()
            info = ITEMS_DATA.get(i, {}) or (ITEMS_DATA.get(int(i), {}) if i.isdigit() else {})
            tags = info.get("tags", [])
            costo = info.get("oro", 0)

            if "Consumable" in tags or "Vision" in tags or "Trinket" in tags:
                continue

            es_bota = "Boots" in tags
            es_supp_final = i in ITEMS_SUPP_FINAL

            if es_bota:
                if i not in ("1001", "2422"):
                    botas_count[i] = botas_count.get(i, 0) + peso
            elif es_supp_final:
                supp_final_count[i] = supp_final_count.get(i, 0) + peso
            elif costo <= 500 and i not in ("2003", "2031", "2033"):
                starters_count[i] = starters_count.get(i, 0) + peso
            else:
                if costo >= 1500 or (costo == 0 and not info.get("avanza_a")):
                    core_count[i] = core_count.get(i, 0) + peso

    # Determinar starter
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
    pociones = max(0, (500 - costo_base) // 50)
    for _ in range(pociones):
        combo_starters.append("2003")

    build_final = []

    # Botas
    if campeon != "Cassiopeia":
        if not botas_count:
            cur.execute(
                """
                SELECT items FROM participantes 
                WHERE team_position = ? AND items != ''
                """, (carril,)
            )
            filas_rol = cur.fetchall()
            for row in filas_rol:
                ids = [x.strip() for x in row["items"].split(",") if x and x.strip() != "0"]
                for iid in ids:
                    tags = ITEMS_DATA.get(iid, {}).get("tags", [])
                    if "Boots" in tags and "Consumable" not in tags and "Vision" not in tags and iid not in ("1001", "2422"):
                        botas_count[iid] = botas_count.get(iid, 0) + 1
                        
        if botas_count:
            bota = max(botas_count, key=botas_count.get)
            build_final.append(bota)

    # Item Support Final
    item_supp_mejorado = None
    if carril == "UTILITY":
        cur.execute(
            """
            SELECT items FROM participantes 
            WHERE champion = ? AND team_position = 'UTILITY' AND items != ''
            """, (campeon,)
        )
        supp_count_champ = {}
        for row in cur.fetchall():
            ids = [x.strip() for x in row["items"].split(",") if x and x.strip() != "0"]
            for iid in ids:
                if iid in ITEMS_SUPP_FINAL:
                    supp_count_champ[iid] = supp_count_champ.get(iid, 0) + 1

        if supp_count_champ:
            item_supp_mejorado = max(supp_count_champ, key=supp_count_champ.get)
        else:
            cur.execute("SELECT items FROM participantes WHERE team_position = 'UTILITY' AND items != ''")
            global_supp = {}
            for row in cur.fetchall():
                ids = [x.strip() for x in row["items"].split(",") if x and x.strip() != "0"]
                for iid in ids:
                    if iid in ITEMS_SUPP_FINAL:
                        global_supp[iid] = global_supp.get(iid, 0) + 1
            if global_supp:
                item_supp_mejorado = max(global_supp, key=global_supp.get)

        if item_supp_mejorado:
            build_final.append(item_supp_mejorado)

    # Core items restantes
    limite = 7 if carril == "BOTTOM" else 6
    espacios_restantes = max(0, limite - len(build_final))

    if core_count and espacios_restantes > 0:
        core_ordenado = sorted(core_count, key=core_count.get, reverse=True)[:espacios_restantes]
        build_final.extend(core_ordenado)

    if espacios_restantes > 0:
        tail = build_final[-espacios_restantes:]
        tail_ordenada = sorted(tail, key=lambda x: ITEMS_DATA.get(x, {}).get("oro", 0))
        build_final = build_final[:-espacios_restantes] + tail_ordenada

    conn.close()
    return combo_starters, build_final

def obtener_top_runas(campeon, carril):
    conn = obtener_conexion()
    cur = conn.cursor()

    cur.execute(
        "SELECT runes FROM participantes WHERE champion = ? AND team_position = ? AND runes != ''",
        (campeon, carril)
    )
    filas = cur.fetchall()

    if not filas:
        cur.execute(
            "SELECT runes FROM participantes WHERE champion = ? AND runes != ''",
            (campeon,)
        )
        filas = cur.fetchall()

    conn.close()

    if not filas:
        return []

    conteo_principal = {}
    conteo_shard_ofensivo = {}
    conteo_shard_flex = {}
    conteo_shard_defensivo = {}

    for row in filas:
        partes = [r.strip() for r in row["runes"].split(",") if r.strip()]

        if len(partes) >= 8:
            main_runes = ",".join(partes[:8])
            conteo_principal[main_runes] = conteo_principal.get(main_runes, 0) + 1

        if len(partes) >= 11:
            defensa = partes[-3]
            flex = partes[-2]
            ofensivo = partes[-1]

            conteo_shard_ofensivo[ofensivo] = conteo_shard_ofensivo.get(ofensivo, 0) + 1
            conteo_shard_flex[flex] = conteo_shard_flex.get(flex, 0) + 1
            conteo_shard_defensivo[defensa] = conteo_shard_defensivo.get(defensa, 0) + 1

    mejor_principal = max(conteo_principal, key=conteo_principal.get) if conteo_principal else ""
    runas_finales = mejor_principal.split(",") if mejor_principal else []

    if conteo_shard_ofensivo:
        runas_finales.append(max(conteo_shard_ofensivo, key=conteo_shard_ofensivo.get))
    else:
        runas_finales.append("5008") 

    if conteo_shard_flex:
        runas_finales.append(max(conteo_shard_flex, key=conteo_shard_flex.get))
    else:
        runas_finales.append("5008") 

    if conteo_shard_defensivo:
        runas_finales.append(max(conteo_shard_defensivo, key=conteo_shard_defensivo.get))
    else:
        runas_finales.append("5011") 

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
        sp_str = row["spells"]
        partes = sorted([s for s in sp_str.split(",") if s])
        if len(partes) == 2:
            llave = f"{partes[0]},{partes[1]}"
            conteo[llave] = conteo.get(llave, 0) + 1

    if not conteo: return ["4", "14"]
    return max(conteo, key=conteo.get).split(",")

def obtenermejoresbaneos(carril, min_partidas=5):
    conn = obtener_conexion()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            champion,
            ROUND(COUNT(*) * 100.0 / (
                SELECT COUNT(*)
                FROM participantes
                WHERE team_position = ?
            ), 1) AS banrate,
            COUNT(*) AS partidas
        FROM participantes
        WHERE team_position = ?
        GROUP BY champion
        HAVING COUNT(*) >= ?
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """, (carril, carril, min_partidas))

    resultados = [
        (row["champion"], row["banrate"], row["partidas"])
        for row in cur.fetchall()
    ]

    conn.close()
    return resultados

def analizar_composicion(aliados):
    ruta_tags = os.path.join(DATA_DIR, "champion_data.json")
    tags_data = {}
    if os.path.exists(ruta_tags):
        with open(ruta_tags, "r", encoding="utf-8") as f: 
            tags_data = json.load(f)

    ap_count = 0.0
    ad_count = 0.0
    tank_count = 0

    for aliado in aliados:
        tags = tags_data.get(aliado, {}).get("tags", [])
        es_ap = "Mage" in tags or "Support" in tags
        es_ad = "Marksman" in tags or "Assassin" in tags or "Fighter" in tags
        es_tank = "Tank" in tags or "Fighter" in tags

        if es_ap and not es_ad: 
            ap_count += 1
        elif es_ad and not es_ap: 
            ad_count += 1
        elif es_ap and es_ad: 
            ap_count += 0.5
            ad_count += 0.5
            
        if es_tank: 
            tank_count += 1

    total_dmg = ad_count + ap_count
    if total_dmg > 0:
        pct_ad = min(100, int((ad_count / total_dmg) * 100))
        pct_ap = min(100, int((ap_count / total_dmg) * 100))
    else:
        pct_ad = 50
        pct_ap = 50

    return pct_ad, pct_ap, tank_count, tags_data

def recomendar_picks_vivo(rol, aliados, enemigos):
    conn = obtener_conexion()
    cur = conn.cursor()
    campeones_rol = obtener_campeones_por_rol(rol, min_partidas=10)
    if not campeones_rol: return {}

    pct_ad, pct_ap, tank_count, tags_data = analizar_composicion(aliados)
    candidatos = {"Sinergia/Balance": [], "Falta Daño Mágico (AP)": [], "Falta Daño Físico (AD)": [], "Falta Tanque/Engage": []}
    
    for c in campeones_rol:
        tags = tags_data.get(c, {}).get("tags", [])
        es_ap = "Mage" in tags or "Support" in tags
        es_tank = "Tank" in tags or "Fighter" in tags 
        es_ad = "Marksman" in tags or "Assassin" in tags or "Fighter" in tags

        wr = 50.0
        if enemigos:
            placeholders = ",".join(["?"]*len(enemigos))
            query = f"""
                SELECT ROUND(SUM(p1.win)*100.0/COUNT(*),1), COUNT(*) 
                FROM participantes p1 
                JOIN participantes p2 ON p1.match_id = p2.match_id 
                WHERE p1.champion = ? AND p1.team_position = ? 
                  AND p2.champion IN ({placeholders}) AND p1.team != p2.team
            """
            cur.execute(query, [c, rol] + enemigos)
            row = cur.fetchone()
            
            if row and row[0]: 
                wr_enemigos = row[0]
                partidas_vs = row[1]
                # Suavizado bayesiano para evitar falsos 100% o 0% si hay pocas partidas
                if partidas_vs < 5:
                    wr = (wr_enemigos * partidas_vs + 50.0 * (5 - partidas_vs)) / 5
                else:
                    wr = wr_enemigos
            
        if pct_ad >= 60 and es_ap: 
            candidatos["Falta Daño Mágico (AP)"].append((c, wr, "Aporta AP"))
        elif pct_ap >= 60 and es_ad: 
            candidatos["Falta Daño Físico (AD)"].append((c, wr, "Aporta AD"))
        elif tank_count == 0 and es_tank: 
            candidatos["Falta Tanque/Engage"].append((c, wr, "Frontlane"))
        else: 
            candidatos["Sinergia/Balance"].append((c, wr, "Fuerte en Meta"))

    conn.close()
    
    finales = {}
    for cat, champs in candidatos.items():
        if champs:
            champs.sort(key=lambda x: x[1], reverse=True)
            finales[cat] = champs[:4] # Devolvemos hasta 4 para cuadricula 2x2
            
    return finales

def calcular_winrate_5v5(aliados, enemigos):
    if len(aliados) != 5 or len(enemigos) != 5: return 50.0
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
        if row and row[0]: total_wr.append(row[0])
        
    conn.close()
    return round(sum(total_wr)/len(total_wr), 1) if total_wr else 50.0