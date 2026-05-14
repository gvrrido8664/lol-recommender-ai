import sqlite3
import os
import json
from .db_manager import obtener_conexion, DATA_DIR
from .riot_api import cargar_objetos, cargar_runas, cargar_campeones

ITEMS_DATA = cargar_objetos()
RUNAS_DATA = cargar_runas()

# Ítems especiales por rol
ITEMS_JUNGLA = ["1101", "1102", "1103"]

# Starter base de support (por si no hay estadísticas)
ITEM_SUPP_BASE = "3865"

# Evoluciones finales de support (objeto de misión mejorado)
ITEMS_SUPP_FINAL = ["3866", "3867", "3869", "3870", "3871", "3873", "3874"]

# Starters posibles de support (dependen del parche, ajusta si hace falta)
SUPPORT_STARTERS = ["3865", "3850", "3851", "3854", "3855"]

# Botas reales (solo boots, sin colar items core tipo Maw, etc.)
BOTAS_REALES = [
    "1001",  # Botas básicas
    "3006",  # Grebas de berserker
    "3009",  # Botas de rapidez
    "3020",  # Zapatos del hechicero
    "3047",  # Tabi
    "3111",  # Mercurial
    "3117",  # Movilidad
    "3158",  # Lucidez
]

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
        SELECT champion FROM participantes WHERE team_position = ?
        GROUP BY champion HAVING COUNT(*) >= ? ORDER BY COUNT(*) DESC
    """, (rol_api, min_partidas_reales))
    resultados = [row["champion"] for row in cur.fetchall()]
    conn.close()
    return resultados

def obtener_counters(carril, enemigo, min_partidas=3):
    conn = obtener_conexion()
    cur = conn.cursor()
    campeones_validos = obtener_campeones_por_rol(carril)
    consulta = """
        SELECT p2.champion AS counter_champ, ROUND(SUM(p2.win) * 100.0 / COUNT(*), 1) AS winrate, COUNT(*) AS partidas
        FROM participantes p1 JOIN participantes p2 ON p1.match_id = p2.match_id
        WHERE p1.champion = ? AND p1.team_position = ? AND p2.team_position = p1.team_position AND p1.team != p2.team
        GROUP BY p2.champion HAVING partidas >= ? ORDER BY winrate DESC LIMIT 50
    """
    cur.execute(consulta, (enemigo, carril, min_partidas))
    resultados = [(row["counter_champ"], row["winrate"], row["partidas"]) for row in cur.fetchall() if row["counter_champ"] in campeones_validos]
    conn.close()
    return resultados

def obtener_top_items(campeon, carril):
    """
    Devuelve:
      - combo_starters: lista de IDs de ítems de inicio (starter + pociones)
      - build_final: lista de 7 ítems para ADC (BOTTOM) o 6 para el resto.

    Reglas especiales:
      - ADC (BOTTOM): siempre 1 bota (slot extra de misión) + 6 core.
      - Supports (UTILITY): siempre 1 ítem de misión final (ITEMS_SUPP_FINAL),
        si hay datos; si no hay datos ni a nivel campeón ni global, no lo mete.
    Todo se basa en estadísticas de la tabla 'participantes'; si el campeón
    no tiene datos, se usan estadísticas globales del rol.
    """
    conn = obtener_conexion()
    cur = conn.cursor()

    # 1) Traer todas las partidas del campeón en ese rol
    cur.execute(
        """
        SELECT items, win
        FROM participantes
        WHERE champion = ? AND team_position = ? AND items != ''
        """,
        (campeon, carril),
    )
    filas = cur.fetchall()

    # Si no hay suficientes datos para ese rol, usar cualquier posición del campeón
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

    # Fallback extremo: nada de datos del campeón -> starter por defecto y build vacía
    if not filas:
        conn.close()
        # Starter genérico de AP/AD + 2 pociones, build vacía
        return ["1055", "2003", "2003"], []

    core_count = {}
    botas_count = {}
    supp_final_count = {}
    starters_count = {}

    for row in filas:
        items_lista = [i.strip() for i in row["items"].split(",") if i and i.strip() != "0"]
        is_win = bool(row["win"])
        peso = 2 if is_win else 1  # victorias pesan doble

        for i in items_lista:
            info = ITEMS_DATA.get(i, {})
            tags = info.get("tags", [])
            costo = info.get("oro", 0)

            # Excluir consumibles, wards, trinkets, etc.
            if "Consumable" in tags or "Vision" in tags or "Trinket" in tags:
                continue

            es_bota = "Boots" in tags
            es_supp_final = i in ITEMS_SUPP_FINAL

            if es_bota:
                # No queremos recomendar botas básicas como ítem final
                if i not in ("1001", "2422"):
                    botas_count[i] = botas_count.get(i, 0) + peso
            elif es_supp_final:
                supp_final_count[i] = supp_final_count.get(i, 0) + peso
            elif costo <= 500 and i not in ("2003", "2031", "2033"):
                starters_count[i] = starters_count.get(i, 0) + peso
            else:
                # Core: míticos/legendarios o ítems que no avanzan a nada
                if costo >= 1500 or (costo == 0 and not info.get("avanza_a")):
                    core_count[i] = core_count.get(i, 0) + peso

    # 2) Elegir starter por rol (estadístico)
    SUPPORT_STARTERS = ["3865", "3850", "3851", "3854", "3855"]

    if carril == "JUNGLE":
        jg = {k: v for k, v in starters_count.items() if k in ITEMS_JUNGLA}
        starter_principal = max(jg, key=jg.get) if jg else "1102"
    elif carril == "UTILITY":
        ss = {k: v for k, v in starters_count.items() if k in SUPPORT_STARTERS}
        starter_principal = max(ss, key=ss.get) if ss else "3865"
    else:
        starter_principal = (
            max(starters_count, key=starters_count.get)
            if starters_count
            else "1055"
        )

    combo_starters = [starter_principal]
    costo_base = ITEMS_DATA.get(starter_principal, {}).get("oro", 0)
    pociones = max(0, (500 - costo_base) // 50)
    for _ in range(pociones):
        combo_starters.append("2003")

    build_final = []

    # 3) Botas: slot extra de ADC + botas normales para otros roles
    if campeon != "Cassiopeia":
        # Si el campeón apenas tiene botas, usamos distribución global por rol
        if not botas_count:
            cur.execute(
                """
                SELECT items
                FROM participantes
                WHERE team_position = ? AND items != ''
                """,
                (carril,),
            )
            filas_rol = cur.fetchall()
            botas_global = {}
            for row in filas_rol:
                ids = [x.strip() for x in row["items"].split(",") if x and x.strip() != "0"]
                for iid in ids:
                    info = ITEMS_DATA.get(iid, {})
                    tags = info.get("tags", [])
                    if "Boots" not in tags:
                        continue
                    if "Consumable" in tags or "Vision" in tags or "Trinket" in tags:
                        continue
                    if iid in ("1001", "2422"):  # no contar botas básicas para slot final
                        continue
                    botas_global[iid] = botas_global.get(iid, 0) + 1
            botas_count = botas_global

        if botas_count:
            bota = max(botas_count, key=botas_count.get)
            build_final.append(bota)

    # 4) Ítem de misión final de support
        # 4) Ítem de misión final de support
    item_supp_mejorado = None

    if carril == "UTILITY":
        # Recontar ÍTEMS_SUPP_FINAL para ESTE campeón a partir de la BD
        cur.execute(
            """
            SELECT items
            FROM participantes
            WHERE champion = ? AND team_position = 'UTILITY' AND items != ''
            """,
            (campeon,),
        )
        filas_champ = cur.fetchall()

        supp_count_champ = {}
        for row in filas_champ:
            ids = [x.strip() for x in row["items"].split(",") if x and x.strip() != "0"]
            for iid in ids:
                if iid in ITEMS_SUPP_FINAL:
                    supp_count_champ[iid] = supp_count_champ.get(iid, 0) + 1

        if supp_count_champ:
            # Si el campeón tiene datos de misión, usamos eso (Thresh -> 3869)
            item_supp_mejorado = max(supp_count_champ, key=supp_count_champ.get)
        else:
            # Fallback global: mirar TODOS los supports del rol UTILITY
            cur.execute(
                """
                SELECT items
                FROM participantes
                WHERE team_position = 'UTILITY' AND items != ''
                """
            )
            filas_supp = cur.fetchall()

            global_supp = {}
            for row in filas_supp:
                ids = [x.strip() for x in row["items"].split(",") if x and x.strip() != "0"]
                for iid in ids:
                    if iid in ITEMS_SUPP_FINAL:
                        global_supp[iid] = global_supp.get(iid, 0) + 1

            if global_supp:
                item_supp_mejorado = max(global_supp, key=global_supp.get)

        if item_supp_mejorado:
            build_final.append(item_supp_mejorado)

    # 5) Core: rellenar hasta 7 (BOTTOM) o 6 (resto)
    limite = 7 if carril == "BOTTOM" else 6
    espacios_restantes = max(0, limite - len(build_final))

    if core_count and espacios_restantes > 0:
        core_ordenado = sorted(core_count, key=core_count.get, reverse=True)[:espacios_restantes]
        build_final.extend(core_ordenado)

    # 6) Ordenar solo el core por coste, manteniendo botas/supp al frente
    if espacios_restantes > 0:
        tail = build_final[-espacios_restantes:]
        tail_ordenada = sorted(tail, key=lambda x: ITEMS_DATA.get(x, {}).get("oro", 0))
        build_final = build_final[:-espacios_restantes] + tail_ordenada

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

    conteo_principal = {}
    conteo_shards_1 = {}
    conteo_shards_2 = {}
    conteo_shards_3 = {}

    for row in filas:
        partes = [r for r in row["runes"].split(",") if r]
        if len(partes) >= 8:
            main_runes = ",".join(partes[:8])
            conteo_principal[main_runes] = conteo_principal.get(main_runes, 0) + 1
        
        if len(partes) >= 11:
            s1, s2, s3 = partes[8], partes[9], partes[10]
            conteo_shards_1[s1] = conteo_shards_1.get(s1, 0) + 1
            conteo_shards_2[s2] = conteo_shards_2.get(s2, 0) + 1
            conteo_shards_3[s3] = conteo_shards_3.get(s3, 0) + 1

    mejor_principal = max(conteo_principal, key=conteo_principal.get) if conteo_principal else ""
    runas_finales = mejor_principal.split(",")

    if conteo_shards_1: runas_finales.append(max(conteo_shards_1, key=conteo_shards_1.get))
    else: runas_finales.append("5008")
    
    if conteo_shards_2: runas_finales.append(max(conteo_shards_2, key=conteo_shards_2.get))
    else: runas_finales.append("5008")
    
    if conteo_shards_3: runas_finales.append(max(conteo_shards_3, key=conteo_shards_3.get))
    else: runas_finales.append("5011")

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

def obtener_mejores_baneos(rol, limite=5):
    conn = obtener_conexion()
    cur = conn.cursor()
    campeones_validos = obtener_campeones_por_rol(rol)
    if not campeones_validos: return []
    placeholders = ",".join(["?"] * len(campeones_validos))
    query = f"""
        SELECT champion, ROUND(SUM(win) * 100.0 / COUNT(*), 1) AS winrate, COUNT(*) AS partidas
        FROM participantes WHERE team_position = ? AND champion IN ({placeholders})
        GROUP BY champion HAVING partidas >= 15 ORDER BY winrate DESC, partidas DESC LIMIT ?
    """
    cur.execute(query, [rol] + campeones_validos + [limite])
    resultados = [row["champion"] for row in cur.fetchall()]
    conn.close()
    return resultados

def analizar_composicion(aliados):
    ruta_tags = os.path.join(DATA_DIR, "champion_data.json")
    tags_data = {}
    if os.path.exists(ruta_tags):
        with open(ruta_tags, "r", encoding="utf-8") as f: tags_data = json.load(f)

    ap_count = 0.0
    ad_count = 0.0
    tank_count = 0
    total_aliados = len(aliados) if aliados else 1

    for aliado in aliados:
        tags = tags_data.get(aliado, {}).get("tags", [])
        es_ap = "Mage" in tags or "Support" in tags
        es_ad = "Marksman" in tags or "Assassin" in tags or "Fighter" in tags
        es_tank = "Tank" in tags or "Fighter" in tags

        if es_ap and not es_ad: ap_count += 1
        elif es_ad and not es_ap: ad_count += 1
        elif es_ap and es_ad: ap_count += 0.5; ad_count += 0.5
        if es_tank: tank_count += 1

    pct_ad = min(100, int((ad_count / total_aliados) * 100))
    pct_ap = min(100, int((ap_count / total_aliados) * 100))
    return pct_ad, pct_ap, tank_count, tags_data

def recomendar_picks_vivo(rol, aliados, enemigos):
    conn = obtener_conexion()
    cur = conn.cursor()
    campeones_rol = obtener_campeones_por_rol(rol)
    if not campeones_rol: return {}

    pct_ad, pct_ap, tank_count, tags_data = analizar_composicion(aliados)
    candidatos = {"Sinergia/Balance": [], "Falta Daño Mágico (AP)": [], "Falta Daño Físico (AD)": [], "Falta Tanque/Engage": []}
    
    for c in campeones_rol:
        tags = tags_data.get(c, {}).get("tags", [])
        es_ap = "Mage" in tags or "Support" in tags
        es_tank = "Tank" in tags
        es_ad = "Marksman" in tags or "Assassin" in tags or "Fighter" in tags

        wr = 50.0
        if enemigos:
            placeholders = ",".join(["?"]*len(enemigos))
            query = f"SELECT ROUND(SUM(p1.win)*100.0/COUNT(*),1) FROM participantes p1 JOIN participantes p2 ON p1.match_id = p2.match_id WHERE p1.champion = ? AND p1.team_position = ? AND p2.champion IN ({placeholders}) AND p1.team != p2.team"
            cur.execute(query, [c, rol] + enemigos)
            row = cur.fetchone()
            if row and row[0]: wr = row[0]
            
        if pct_ad >= 60 and es_ap: candidatos["Falta Daño Mágico (AP)"].append((c, wr, "Aporta AP necesario"))
        elif pct_ap >= 60 and es_ad: candidatos["Falta Daño Físico (AD)"].append((c, wr, "Aporta AD necesario"))
        elif tank_count == 0 and es_tank: candidatos["Falta Tanque/Engage"].append((c, wr, "Falta Frontlane"))
        else: candidatos["Sinergia/Balance"].append((c, wr, "Balance y Sinergia"))

    conn.close()
    finales = {}
    for cat, champs in candidatos.items():
        if champs:
            champs.sort(key=lambda x: x[1], reverse=True)
            finales[cat] = champs[:2]
    return finales

def calcular_winrate_5v5(aliados, enemigos):
    if len(aliados) != 5 or len(enemigos) != 5: return 50.0
    conn = obtener_conexion()
    cur = conn.cursor()
    total_wr = []
    for aliado in aliados:
        placeholders = ",".join(["?"]*len(enemigos))
        query = f"SELECT SUM(p1.win)*100.0/COUNT(*) FROM participantes p1 JOIN participantes p2 ON p1.match_id = p2.match_id WHERE p1.champion = ? AND p2.champion IN ({placeholders}) AND p1.team != p2.team"
        cur.execute(query, [aliado] + enemigos)
        row = cur.fetchone()
        if row and row[0]: total_wr.append(row[0])
    conn.close()
    return round(sum(total_wr)/len(total_wr), 1) if total_wr else 50.0