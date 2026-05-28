"""
GVRRIDO — Analizador de Perfil de Jugador
═══════════════════════════════════════════════════════
Analiza el historial de partidas (LCU) y la base de datos
para generar:
  1. Perfil de Personalidad (agresivo, escalado, control)
  2. Detección de Hábitos y Fortalezas
  3. Objetivos Semanales personalizados

Autor: Sello Gvrrido
"""
from collections import defaultdict
from .tags_champions import (
    obtener_tag, obtener_dano, es_tanque, es_mago, es_tirador,
    es_asesino, es_luchador, es_soporte, obtener_nivel_cc
)

# ═══════════════════════════════════════════════════════════════
# 1. PERFIL DE PERSONALIDAD
# ═══════════════════════════════════════════════════════════════

def analizar_personalidad(historial_games: list) -> dict:
    """
    Analiza el historial para clasificar al jugador.
    
    Retorna:
        {
            "perfil": str (descripción de personalidad),
            "estilo": str (AGRESIVO / CONSISTENTE / CONTROL),
            "detalles": dict con métricas de respaldo
        }
    """
    if not historial_games:
        return {"perfil": "Sin datos suficientes", "estilo": "NEUTRAL", "detalles": {}}

    total_games = 0
    kills_total = 0
    deaths_total = 0
    assists_total = 0
    champ_classes = defaultdict(int)
    early_snowball = 0  # partidas donde KDA early es muy alto
    safe_games = 0       # partidas con pocas muertes
    
    for g in historial_games:
        part = g.get("participants", [{}])[0]
        stats = part.get("stats", {})
        k = stats.get("kills", 0)
        d = stats.get("deaths", 0)
        a = stats.get("assists", 0)
        champ_id = str(part.get("championId", "0"))
        
        if k == 0 and d == 0 and a == 0:
            continue  # skip incomplete data
            
        total_games += 1
        kills_total += k
        deaths_total += d
        assists_total += a
        
        # Clasificar al campeón usado (desde tags)
        tag = obtener_tag(champ_id) if champ_id != "0" else {}
        clase = tag.get("champion_class", "")
        if clase:
            champ_classes[clase] += 1
        
        # Detectar partidas agresivas (mucho K+A, pocas muertes)
        if k + a >= 15:
            early_snowball += 1
        if d <= 3 and k + a >= 8:
            safe_games += 1

    if total_games == 0:
        return {"perfil": "Sin datos suficientes", "estilo": "NEUTRAL", "detalles": {}}

    avg_k = round(kills_total / total_games, 1)
    avg_d = round(deaths_total / total_games, 1)
    avg_a = round(assists_total / total_games, 1)
    kda = round((kills_total + assists_total) / max(1, deaths_total), 2)
    
    # Determinar clase predominante
    clase_pred = max(champ_classes, key=champ_classes.get) if champ_classes else "Balanceado"
    pct_agresivo = round(early_snowball / total_games * 100)
    pct_seguro = round(safe_games / total_games * 100)
    
    # LÓGICA DE CLASIFICACIÓN
    if avg_k >= 8 and avg_d >= 5:
        estilo = "AGRESIVO"
        perfil = "Jugador agresivo orientado a skirmishes. Busca peleas constantemente, prioriza el daño sobre la supervivencia."
    elif avg_d <= 3.5 and kda >= 3.5:
        estilo = "CONSISTENTE"
        perfil = "Jugador consistente y seguro. Excelente gestión de riesgos, evita muertes innecesarias y capitaliza ventajas."
    elif avg_a >= 7:
        estilo = "CONTROL"
        perfil = "Prefiere utilidad y control de mapa. Destaca por habilitar a su equipo con CC, visión y juego macro."
    elif clase_pred in ("Mage", "Marksman") and avg_d <= 4:
        estilo = "CONSISTENTE"
        perfil = "Jugador de escalado metódico. Prefiere campeones de late-game, farmea eficientemente y brilla en teamfights tardías."
    elif clase_pred in ("Assassin", "Fighter") and avg_k >= 6:
        estilo = "AGRESIVO"
        perfil = "Jugador agresivo con mentalidad de carry. Busca outplays constantes y genera ventaja desde early game."
    else:
        estilo = "BALANCEADO"
        perfil = "Jugador versátil y adaptativo. Combina agresividad calculada con buena lectura de mapa."

    return {
        "perfil": perfil,
        "estilo": estilo,
        "detalles": {
            "avg_kda": f"{avg_k}/{avg_d}/{avg_a}",
            "kda_ratio": kda,
            "clase_predominante": clase_pred,
            "pct_agresivo": pct_agresivo,
            "pct_seguro": pct_seguro,
            "total_games": total_games,
        }
    }


# ═══════════════════════════════════════════════════════════════
# 2. DETECCIÓN DE HÁBITOS Y FORTALEZAS
# ═══════════════════════════════════════════════════════════════

def detectar_habitos(historial_games: list) -> list:
    """
    Detecta patrones en el historial y devuelve insights accionables.
    
    Retorna lista de strings con hallazgos.
    """
    if not historial_games or len(historial_games) < 5:
        return ["⚠️ Necesitas al menos 5 partidas para detectar patrones."]

    insights = []
    total = len(historial_games)
    
    # ─── Análisis de rachas ───
    wins = 0
    losses = 0
    streak_data = []  # [(win_bool, k, d, a), ...]
    derrotas_seguidas = 0
    max_derrotas = 0
    
    for g in historial_games:
        part = g.get("participants", [{}])[0]
        stats = part.get("stats", {})
        win = stats.get("win", False)
        k = stats.get("kills", 0)
        d = stats.get("deaths", 0)
        a = stats.get("assists", 0)
        
        streak_data.append((win, k, d, a))
        if win:
            wins += 1
            derrotas_seguidas = 0
        else:
            losses += 1
            derrotas_seguidas += 1
            max_derrotas = max(max_derrotas, derrotas_seguidas)

    wr_general = round(wins / total * 100)
    
    # ─── Winrate después de derrotas ───
    post_loss_wins = 0
    post_loss_total = 0
    for i in range(1, len(streak_data)):
        if not streak_data[i-1][0]:  # partida anterior fue derrota
            post_loss_total += 1
            if streak_data[i][0]:
                post_loss_wins += 1
    
    if post_loss_total >= 3:
        wr_post_loss = round(post_loss_wins / post_loss_total * 100)
        if wr_post_loss < wr_general - 10:
            insights.append(f"⚠️ Tu winrate cae de {wr_general}% a {wr_post_loss}% después de una derrota. Considera tomar un descanso tras perder.")
        elif wr_post_loss > wr_general + 5:
            insights.append(f"💪 Te recuperas bien tras derrotas: WR post-derrota = {wr_post_loss}% (vs {wr_general}% general).")

    # ─── Rendimiento desde ventaja/desventaja ───
    # (aproximación: kills > deaths = ventaja temprana)
    ahead_wins = 0
    ahead_total = 0
    for win, k, d, a in streak_data:
        if k > d:  # positivos en KDA
            ahead_total += 1
            if win:
                ahead_wins += 1
    
    if ahead_total >= 4:
        wr_ahead = round(ahead_wins / ahead_total * 100)
        if wr_ahead >= 70:
            insights.append(f"✅ Excelente jugando desde ventaja: cierras el {wr_ahead}% de partidas donde vas positivo en kills.")
        elif wr_ahead < 55:
            insights.append(f"⚠️ Te cuesta cerrar partidas: solo ganas el {wr_ahead}% cuando vas positivo en KDA. Trabaja en el macro y objetivos.")

    # ─── Análisis de CS ───
    cs_values = []
    durations = []
    for g in historial_games:
        part = g.get("participants", [{}])[0]
        stats = part.get("stats", {})
        cs = stats.get("totalMinionsKilled", 0) + stats.get("neutralMinionsKilled", 0)
        dur = g.get("gameDuration", 0)
        if dur > 0 and cs > 0:
            cs_values.append(cs)
            durations.append(dur)
    
    if len(cs_values) >= 3:
        # Calcular CS/min promedio
        cs_per_min = [cs / (dur / 60) for cs, dur in zip(cs_values, durations)]
        avg_cs_min = round(sum(cs_per_min) / len(cs_per_min), 1)
        
        # Detectar si CS baja en partidas largas (>25min)
        cs_early = []
        cs_late = []
        for cs, dur in zip(cs_values, durations):
            cspm = cs / (dur / 60)
            if dur < 1500:
                cs_early.append(cspm)
            else:
                cs_late.append(cspm)
        
        if cs_early and cs_late:
            avg_early = round(sum(cs_early) / len(cs_early), 1)
            avg_late = round(sum(cs_late) / len(cs_late), 1)
            drop = avg_early - avg_late
            if drop > 1.5:
                insights.append(f"📉 Tu CS baja de {avg_early}/min (early) a {avg_late}/min (late). Enfócate en mantener el farm en mid-late game.")
        
        if avg_cs_min < 5:
            insights.append(f"🎯 CS promedio bajo: {avg_cs_min}/min. Practica last-hitting en practice tool 10 min al día.")
        elif avg_cs_min > 7.5:
            insights.append(f"👑 Excelente farm: {avg_cs_min} CS/min promedio. Tu economía es sólida.")

    # ─── Muertes excesivas ───
    avg_deaths = round(sum(d for _, _, d, _ in streak_data) / total, 1)
    if avg_deaths > 6:
        insights.append(f"🛡️ Promedio de muertes alto: {avg_deaths}/partida. Revisa tu posicionamiento y visión en el mapa.")
    
    # ─── Max derrotas seguidas ───
    if max_derrotas >= 4:
        insights.append(f"🔴 Rachas de hasta {max_derrotas} derrotas seguidas detectadas. Programa descansos cada 2-3 partidas.")

    if not insights:
        insights.append("✅ No se detectaron patrones negativos claros. ¡Buen trabajo!")

    return insights


# ═══════════════════════════════════════════════════════════════
# 3. OBJETIVOS SEMANALES
# ═══════════════════════════════════════════════════════════════

def generar_objetivos_semanales(historial_games: list) -> list:
    """
    Genera 3 metas accionables basadas en las peores estadísticas.
    
    Retorna lista de strings con objetivos.
    """
    if not historial_games or len(historial_games) < 3:
        return ["🎯 Juega al menos 5 partidas para recibir objetivos personalizados."]

    objetivos = []
    total = len(historial_games)
    
    # Recolectar métricas
    kills = []
    deaths = []
    assists = []
    cs_list = []
    durs = []
    vision_list = []
    wins = 0
    
    for g in historial_games:
        part = g.get("participants", [{}])[0]
        stats = part.get("stats", {})
        k = stats.get("kills", 0)
        d = stats.get("deaths", 0)
        a = stats.get("assists", 0)
        cs = stats.get("totalMinionsKilled", 0) + stats.get("neutralMinionsKilled", 0)
        dur = g.get("gameDuration", 0)
        vision = stats.get("visionScore", 0) or stats.get("wardsPlaced", 0)
        win = stats.get("win", False)
        
        kills.append(k)
        deaths.append(d)
        assists.append(a)
        if cs > 0: cs_list.append(cs)
        if dur > 0: durs.append(dur)
        if vision > 0: vision_list.append(vision)
        if win: wins += 1

    avg_k = round(sum(kills) / total, 1)
    avg_d = round(sum(deaths) / total, 1)
    avg_a = round(sum(assists) / total, 1)
    wr = round(wins / total * 100)
    
    # Calcular CS/min
    if cs_list and durs:
        cs_per_min = [cs / (dur / 60) for cs, dur in zip(cs_list, durs)]
        avg_cs_min = round(sum(cs_per_min) / len(cs_per_min), 1)
    else:
        avg_cs_min = 0
    
    # Calcular visión/min
    if vision_list and durs:
        vis_per_min = [v / (dur / 60) for v, dur in zip(vision_list, durs)]
        avg_vis = round(sum(vis_per_min) / len(vis_per_min), 1)
    else:
        avg_vis = 0

    # ─── Priorizar los 3 peores aspectos ───
    issues = []
    
    if avg_d > 5:
        issues.append(("muertes", avg_d, f"🎯 Objetivo: Morir menos de 5 veces promedio (actual: {avg_d}). Enfócate en posicionamiento y wardear antes de pushear."))
    
    if avg_cs_min > 0 and avg_cs_min < 6:
        issues.append(("cs", avg_cs_min, f"🎯 Objetivo: Alcanzar 6.5+ CS/min (actual: {avg_cs_min}). Dedica 10 min diarios al practice tool."))
    
    if avg_k < 3 and avg_d < 4:
        issues.append(("impacto", avg_k, f"🎯 Objetivo: Aumentar tu impacto en teamfights. Busca participar en al menos 2 kills extra por partida (actual: {avg_k} kills)."))

    if wr < 45:
        issues.append(("wr", wr, f"🎯 Objetivo: Subir tu winrate a 50%+. Revisa tus counters y limita tu pool a 2-3 campeones principales (WR actual: {wr}%)."))

    if avg_vis > 0 and avg_vis < 0.5:
        issues.append(("vision", avg_vis, f"🎯 Objetivo: Mejorar visión a 0.8+/min (actual: {avg_vis}). Compra más pinks y usa el trinket en cooldown."))

    if avg_a < 3 and avg_k > 5:
        issues.append(("equipo", avg_a, f"🎯 Objetivo: Jugar más para el equipo. Promedio de asistencias bajo ({avg_a}) pese a buen KDA. Rotea más."))

    # Tomar los 3 más críticos (ordenados por severidad)
    issues.sort(key=lambda x: {
        "muertes": 0, "wr": 1, "cs": 2, "vision": 3, "impacto": 4, "equipo": 5
    }.get(x[0], 99))
    
    objetivos = [issue[2] for issue in issues[:3]]
    
    # Si no hay suficientes issues, agregar objetivos genéricos positivos
    while len(objetivos) < 3:
        genericos = [
            f"🎯 Objetivo: Mantener tu buen rendimiento. WR actual: {wr}%, KDA: {avg_k}/{avg_d}/{avg_a}.",
            f"🎯 Objetivo: Expandir tu pool de campeones en 1-2 picks nuevos esta semana.",
            f"🎯 Objetivo: Ver 1 replay propio por día para identificar errores de posicionamiento.",
        ]
        for g in genericos:
            if g not in objetivos and len(objetivos) < 3:
                objetivos.append(g)

    return objetivos


# ═══════════════════════════════════════════════════════════════
# 4. CRUCE EMOCIONAL (WINRATE POR ESTADO)
# ═══════════════════════════════════════════════════════════════

def analizar_emocional_vs_wr(historial_games: list) -> dict:
    """
    Cruza el estado emocional etiquetado con el winrate de la BD.
    
    Retorna dict con {estado: {'wr': %, 'partidas': N}}
    """
    from .db_manager import obtener_estadisticas_emocionales
    try:
        stats = obtener_estadisticas_emocionales()
        return stats
    except Exception as e:
        print(f"[analizar_emocional_vs_wr] Error: {e}")
        return {}
