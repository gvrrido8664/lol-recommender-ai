import sqlite3
import os
import json
from .db_manager import obtener_conexion, DATA_DIR
from .riot_api import cargar_objetos, cargar_campeones
from .tags_champions import (
    obtener_dano, es_tanque, es_mago, es_tirador, es_asesino, es_luchador, es_soporte,
    obtener_nivel_cc, obtener_subrol_soporte, obtener_tag, es_botas_estaticas, obtener_bota_estatica
)
from .itemizador_dinamico import recomendar_bota, recomendar_items_situacionales
from .razonador import razonar_pick, razonar_hechizos, razonar_botas, razonar_runas, razonar_objeto

_ITEMS_DATA = None

def _get_items_data():
    global _ITEMS_DATA
    if _ITEMS_DATA is None:
        _ITEMS_DATA = cargar_objetos() or {}
    return _ITEMS_DATA

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
_BOTASREALES_STR = {str(b) for b in BOTASREALES}

# Ítems de soporte base/quest (van siempre en primer slot para UTILITY)
_SOPORTE_QUEST = {str(i) for i in ITEMS_SUPP_FINAL} | {"3865","3850","3851","3854","3855"}


def _ordenar_build_por_timing(build_final: list, items_data: dict) -> list:
    """Reordena el build en el orden real de compra:
      1. Ítem de soporte quest (si existe) — siempre primero para UTILITY
      2. Ítem más caro del core (primer power-spike)
      3. Botas
      4. Resto del core por coste descendente
      5. Ítems baratos (< 2000g) al final
    """
    if not build_final:
        return build_final

    def costo(iid) -> int:
        iid_s = str(iid)
        info = items_data.get(iid_s, {})
        if not info and iid_s.isdigit():
            info = items_data.get(int(iid_s), {})
        return (info.get("oro", 0) or 0) if isinstance(info, dict) else 0

    soporte_q  = [i for i in build_final if str(i) in _SOPORTE_QUEST]
    botas      = [i for i in build_final if str(i) in _BOTASREALES_STR and str(i) not in _SOPORTE_QUEST]
    core       = [i for i in build_final if str(i) not in _BOTASREALES_STR and str(i) not in _SOPORTE_QUEST]

    core_caro   = sorted([i for i in core if costo(i) >= 2000], key=costo, reverse=True)
    core_barato = sorted([i for i in core if costo(i) <  2000], key=costo, reverse=True)

    resultado = list(soporte_q)
    if core_caro:
        resultado.append(core_caro[0])
        resultado.extend(botas)
        resultado.extend(core_caro[1:])
    else:
        resultado.extend(botas)
    resultado.extend(core_barato)

    return resultado

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
        WHERE team_position = %s
        GROUP BY champion
        HAVING COUNT(*) >= %s
        ORDER BY COUNT(*) DESC
        LIMIT 45
    """, (rol_api, min_partidas))

    con_datos = [row["champion"] for row in cur.fetchall()]
    conn.close()

    # Fallback: incluir campeones del rol sin datos suficientes al final de la lista
    try:
        from .tags_champions import obtener_champs_rol_base
        con_datos_set = set(con_datos)
        sin_datos = [c for c in obtener_champs_rol_base(rol_api) if c not in con_datos_set]
        return con_datos + sin_datos
    except Exception:
        return con_datos

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
        WHERE p1.champion = %s AND p1.team_position = %s AND p2.team_position = p1.team_position AND p1.team != p2.team
        GROUP BY p2.champion
        HAVING COUNT(*) >= %s
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
        WHERE p1.champion = %s AND p1.team_position = %s AND p2.team_position = p1.team_position AND p1.team != p2.team
        GROUP BY p2.champion
        HAVING COUNT(*) >= %s
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


def obtener_top_items(campeon, carril, enemigos=None, conn=None):
    conn_owned = conn is None
    if conn_owned:
        conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("SELECT items, win FROM participantes WHERE champion = %s AND team_position = %s AND items != ''", (campeon, carril))
    filas = cur.fetchall()
    
    if not filas:
        cur.execute("SELECT items, win FROM participantes WHERE champion = %s AND items != ''", (campeon,))
        filas = cur.fetchall()

    if not filas:
        if conn_owned:
            conn.close()
        return ["1055", "2003", "2003"], []

    core_count, botas_count, supp_final_count, starters_count = {}, {}, {}, {}

    items_data = _get_items_data()
    for row in filas:
        items_lista = [i.strip() for i in row["items"].split(",") if i and i.strip() != "0"]
        peso = 2 if bool(row["win"]) else 1 

        for i in items_lista:
            i = str(i).strip()
            info = items_data.get(i, {}) or (items_data.get(int(i), {}) if i.isdigit() else {})
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
    costo_base = items_data.get(starter_principal, {}).get("oro", 0)
    for _ in range(max(0, (500 - costo_base) // 50)): combo_starters.append("2003")

    build_final = []
    if not botas_count:
        cur.execute("SELECT items FROM participantes WHERE team_position = %s AND items != ''", (carril,))
        for row in cur.fetchall():
            ids = [x.strip() for x in row["items"].split(",") if x and x.strip() != "0"]
            for iid in ids:
                tags = items_data.get(iid, {}).get("tags", [])
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
        cur.execute("SELECT items FROM participantes WHERE champion = %s AND team_position = 'UTILITY' AND items != ''", (campeon,))
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

    # Reordenar en secuencia de compra real: item de poder → botas → resto
    build_final = _ordenar_build_por_timing(build_final, items_data)

    if conn_owned:
        conn.close()
    return combo_starters, build_final


def obtener_items_situacionales(campeon: str, carril: str, enemigos: list,
                                excluir: list = None) -> list:
    """Devuelve lista de ítems situacionales enriquecidos con nombre y coste.

    Cada elemento: {id, nombre, coste, razon, categoria, prioridad}
    categorias: anti_heal | anti_shield | anti_cc | anti_ap |
                anti_ad   | anti_tank   | penetracion | supervivencia
    prioridad:  1=CRÍTICO, 2=RECOMENDADO, 3=OPCIONAL
    """
    if not enemigos or not campeon:
        return []
    try:
        items_sit = recomendar_items_situacionales(campeon, carril, enemigos)
        items_data = _get_items_data()
        excluir_str = {str(e) for e in (excluir or [])}
        resultado = []
        vistos = set()
        for sit in items_sit:
            iid = str(sit["id"])
            if iid in vistos or iid in excluir_str:
                continue
            vistos.add(iid)
            info = items_data.get(iid, {})
            resultado.append({
                **sit,
                "id": iid,
                "nombre": info.get("nombre", f"Ítem {iid}"),
                "coste": info.get("oro", 0) or 0,
            })
        return resultado
    except Exception as e:
        print(f"[ItemSit] Error: {e}")
        return []

def obtener_top_runas(campeon, carril, conn=None):
    conn_owned = conn is None
    if conn_owned:
        conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("SELECT runes FROM participantes WHERE champion = %s AND team_position = %s AND runes != ''", (campeon, carril))
    filas = cur.fetchall()
    if not filas:
        cur.execute("SELECT runes FROM participantes WHERE champion = %s AND runes != ''", (campeon,))
        filas = cur.fetchall()
    if conn_owned:
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

def obtener_top_hechizos(campeon, carril, conn=None):
    conn_owned = conn is None
    if conn_owned:
        conn = obtener_conexion()
    cur = conn.cursor()
    try:
        cur.execute("SELECT spells FROM participantes WHERE champion = %s AND team_position = %s AND spells != ''", (campeon, carril))
        filas = cur.fetchall()
        if not filas:
            cur.execute("SELECT spells FROM participantes WHERE champion = %s AND spells != ''", (campeon,))
            filas = cur.fetchall()
    except:
        if conn_owned:
            conn.close()
        return ["4", "14"]
    if conn_owned:
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
        SELECT champion, ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM participantes WHERE team_position = %s), 1) AS banrate, COUNT(*) AS partidas
        FROM participantes WHERE team_position = %s GROUP BY champion HAVING COUNT(*) >= %s ORDER BY COUNT(*) DESC LIMIT 10
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

def _score_pick(wr, es_ap, es_ad, es_tank, pct_ad, pct_ap, tank_count):
    """Convierte winrate y sinergia en una puntuacion 1.0-10.0.
    
    Base: WR mapeada al rango 1-10 (centrada en 50% = 5.0, minima 1.0).
    Bonus: hasta +1.0 si cubre una necesidad urgente del equipo.
    """
    # Mapeo WR -> score base: 30% -> 1.0, 50% -> 5.0, 70% -> 10.0
    base = max(1.0, min(10.0, 1.0 + (wr - 30.0) / 4.0))
    
    # Bonus de sinergia: cubrir lo que le falta al equipo (proporcional a la escala)
    bonus = 0.0
    if pct_ad >= 60 and es_ap:
        bonus = 0.8  # El equipo necesita AP urgente
    elif pct_ap >= 60 and es_ad:
        bonus = 0.8  # El equipo necesita AD urgente
    elif tank_count == 0 and es_tank:
        bonus = 1.0  # El equipo necesita frontlane urgente
    elif es_ap and pct_ad >= 50:
        bonus = 0.3  # Buen balance con AP extra
    elif es_ad and pct_ap >= 50:
        bonus = 0.3  # Buen balance con AD extra
    elif es_tank and tank_count <= 1:
        bonus = 0.4  # Refuerzo de frontlane
    
    return round(base + bonus, 1)

def recomendar_picks_vivo(rol, aliados, enemigos):
    conn = obtener_conexion()
    cur = conn.cursor()
    campeones_rol = obtener_campeones_por_rol(rol, min_partidas=20)
    if not campeones_rol: return {}

    # Filtrar campeones ya pickeados (aliados o enemigos) para no recomendarlos
    picks_existentes = set(aliados) | set(enemigos)
    campeones_rol = [c for c in campeones_rol if c not in picks_existentes]
    if not campeones_rol: return {}

    pct_ad, pct_ap, tank_count = analizar_composicion(aliados)
    candidatos = {"⭐ Sinergia/Balance": [], "🔮 Falta Daño Mágico (AP)": [], "⚔️ Falta Daño Físico (AD)": [], "🛡️ Falta Tanque/Engage": []}
    
    for c in campeones_rol:
        dano = obtener_dano(c)
        es_tank = _es_frontlane(c)
        es_ap = dano in ("AP", "HYBRID")
        es_ad = dano in ("AD", "HYBRID")

        wr = 50.0
        if enemigos:
            placeholders = ",".join(["%s"]*len(enemigos))
            
            # Query 1: WR vs enemigos en LA MISMA LÍNEA (lane-specific, mas preciso)
            cur.execute(
                f"SELECT ROUND(SUM(p1.win)*100.0/COUNT(*),1), COUNT(*) "
                f"FROM participantes p1 JOIN participantes p2 ON p1.match_id = p2.match_id "
                f"WHERE p1.champion = %s AND p1.team_position = %s "
                f"AND p2.champion IN ({placeholders}) AND p2.team_position = p1.team_position "
                f"AND p1.team != p2.team",
                [c, rol] + enemigos
            )
            row = cur.fetchone()
            
            # Fallback: si no hay datos de misma linea, usar query global (cualquier rol enemigo)
            if not row or not row[0] or (row[1] and row[1] < 3):
                cur.execute(
                    f"SELECT ROUND(SUM(p1.win)*100.0/COUNT(*),1), COUNT(*) "
                    f"FROM participantes p1 JOIN participantes p2 ON p1.match_id = p2.match_id "
                    f"WHERE p1.champion = %s AND p1.team_position = %s "
                    f"AND p2.champion IN ({placeholders}) AND p1.team != p2.team",
                    [c, rol] + enemigos
                )
                row = cur.fetchone()
            
            if row and row[0]:
                n = row[1]
                wr_raw = row[0]
                if n < 3:
                    # Suavizado bayesiano: prior del campeon en ese rol (no 50% fijo)
                    cur.execute(
                        "SELECT ROUND(SUM(win)*100.0/COUNT(*),1) FROM participantes "
                        "WHERE champion = %s AND team_position = %s", (c, rol))
                    prior_row = cur.fetchone()
                    prior = float(prior_row[0]) if prior_row and prior_row[0] else 50.0
                    wr = round((wr_raw * n + prior * (3 - n)) / 3, 1)
                else:
                    wr = wr_raw
        
        # Calcular puntuacion 1.0–10.0
        puntuacion = _score_pick(wr, es_ap, es_ad, es_tank, pct_ad, pct_ap, tank_count)
        
        # Determinar categoria y razon
        if pct_ad >= 60 and es_ap:
            candidatos["🔮 Falta Daño Mágico (AP)"].append((c, puntuacion, f"AP — {wr}% WR"))
        elif pct_ap >= 60 and es_ad:
            candidatos["⚔️ Falta Daño Físico (AD)"].append((c, puntuacion, f"AD — {wr}% WR"))
        elif tank_count == 0 and es_tank:
            candidatos["🛡️ Falta Tanque/Engage"].append((c, puntuacion, f"Front — {wr}% WR"))
        else:
            razon = "Fuerte en Meta"
            if puntuacion >= 8.0:
                razon = "🔥 Dominante"
            elif puntuacion >= 6.0:
                razon = "✅ Sólido"
            elif puntuacion >= 4.0:
                razon = "⚖️ Decente"
            candidatos["⭐ Sinergia/Balance"].append((c, puntuacion, f"{razon} — {wr}% WR"))

    conn.close()
    finales = {}
    for cat, champs in candidatos.items():
        if champs:
            finales[cat] = sorted(champs, key=lambda x: x[1], reverse=True)[:4]
    return finales

def calcular_winrate_5v5(aliados, enemigos, pos_aliados=None, pos_enemigos=None):
    """Calcula el winrate estimado de un equipo 5v5 usando matchups por línea
    + stats comparativas de composición (CC total, movilidad, escalado, daño).
    """
    if len(aliados) != 5 or len(enemigos) != 5:
        return 50.0
    
    conn = obtener_conexion()
    try:
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
                cur.execute("""
                    SELECT ROUND(SUM(p1.win)*100.0/COUNT(*), 1) as wr, COUNT(*) as partidas
                    FROM participantes p1
                    JOIN participantes p2 ON p1.match_id = p2.match_id
                    WHERE p1.champion = %s AND p1.team_position = %s
                      AND p2.champion = %s AND p2.team_position = %s
                      AND p1.team != p2.team
                """, (aliado, pos_al, enemigo_lane, pos_norm))
                row = cur.fetchone()
                if row and row["wr"] is not None:
                    n = row["partidas"]
                    if n >= 50:
                        wr_por_lane.append(row["wr"])
                    elif n >= 10:
                        wr_por_lane.append(row["wr"] * 0.7 + 50 * 0.3)
                else:
                    wr_por_lane.append(50.0)
            else:
                wr_por_lane.append(50.0)
    finally:
        conn.close()
    
    # ═══════ FEATURE ENGINEERING 5v5: stats de composición ═══════
    try:
        from .tags_champions import obtener_tag
        
        cc_aliado_total = sum(obtener_tag(c).get("cc_level", 1) for c in aliados)
        cc_enemigo_total = sum(obtener_tag(c).get("cc_level", 1) for c in enemigos)
        
        _EARLY = {"weak": 1, "neutral": 2, "strong": 3}
        _SCALE = {"early": 1, "mid": 2, "late": 3, "hyper": 4}
        early_aliado = sum(_EARLY.get(obtener_tag(c).get("early_power", "neutral"), 2) for c in aliados)
        early_enemigo = sum(_EARLY.get(obtener_tag(c).get("early_power", "neutral"), 2) for c in enemigos)
        scale_aliado = sum(_SCALE.get(obtener_tag(c).get("scaling", "mid"), 2) for c in aliados)
        scale_enemigo = sum(_SCALE.get(obtener_tag(c).get("scaling", "mid"), 2) for c in enemigos)
        
        tanks_aliado = sum(1 for c in aliados if obtener_tag(c).get("champion_class") == "Tank")
        tanks_enemigo = sum(1 for c in enemigos if obtener_tag(c).get("champion_class") == "Tank")
        
        ad_aliado = sum(1 for c in aliados if obtener_tag(c).get("damage_type") == "AD")
        ap_aliado = sum(1 for c in aliados if obtener_tag(c).get("damage_type") == "AP")
        ad_enemigo = sum(1 for c in enemigos if obtener_tag(c).get("damage_type") == "AD")
        ap_enemigo = sum(1 for c in enemigos if obtener_tag(c).get("damage_type") == "AP")
        
        # Ajustes de composición (pesos calibrados)
        ajuste_cc = min(5, (cc_aliado_total - cc_enemigo_total) * 0.8)
        ajuste_early = min(3, (early_aliado - early_enemigo) * 0.6)
        ajuste_scale = min(3, (scale_aliado - scale_enemigo) * 0.5)
        
        balance_aliado = 1.0 if (ad_aliado >= 2 and ap_aliado >= 2) else 0.0
        balance_enemigo = 1.0 if (ad_enemigo >= 2 and ap_enemigo >= 2) else 0.0
        ajuste_balance = (balance_aliado - balance_enemigo) * 1.5
        
        ajuste_tank = (tanks_aliado - tanks_enemigo) * 1.2
        
        ajuste_total = ajuste_cc + ajuste_early + ajuste_scale + ajuste_balance + ajuste_tank
        
        if wr_por_lane:
            wr_base = sum(wr_por_lane) / len(wr_por_lane)
            wr_final = max(35, min(65, wr_base + ajuste_total))
            return round(wr_final, 1)
    except Exception:
        pass
    
    if wr_por_lane:
        return round(sum(wr_por_lane) / len(wr_por_lane), 1)
    return 50.0