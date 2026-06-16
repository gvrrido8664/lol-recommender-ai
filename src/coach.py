# -*- coding: utf-8 -*-

from .riot_api import cargar_mapeo_ids
from .theme import (
    GREEN_SUCCESS,
    PURPLE_LIGHT,
    PURPLE_VIOLET,
    RED_DANGER,
    TEAL_EMERALD,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_SUBTLE,
)

TEXT_GOLD = "#f8fafc"
ACCENT_TEAL = "#2dd4bf"

_CHAMP_ID_TO_NAME = None


def _id_to_champ(cid):
    global _CHAMP_ID_TO_NAME
    if _CHAMP_ID_TO_NAME is None:
        _CHAMP_ID_TO_NAME = cargar_mapeo_ids()
    name = _CHAMP_ID_TO_NAME.get(str(cid), None)
    if name == "MonkeyKing":
        return "Wukong"
    return name or f"Champ{cid}"


def _generar_filosofia_juego(nombre, nivel, wr, avg_d, total):
    """Genera la sección de filosofía de juego basada en los 6 principios del coach.

    Principios del curso:
    1. Eres el único factor constante — tu progreso depende de ti
    2. La mala suerte es real — enfócate en lo que puedes controlar
    3. Siempre hay algo para aprender — nunca rendirse, cada partida enseña
    4. Disfrute del proceso, no del resultado — el placer viene de mejorar
    5. El entorno es competitivo y tóxico — ajustar expectativas
    6. No uses el juego como escape — juega con cabeza limpia
    """
    # Personalizar cada principio según el nivel del jugador
    principios = []

    # Principio 1: Factor constante
    if nivel == "inicial":
        p1 = "<b>🧠 Tú eres el único factor constante.</b> De 10 personas en cada ranked, 9 cambian. El único que siempre está eres tú. A largo plazo, <b>tu progreso depende de lo que tú haces</b>, no de tus compañeros."
    elif nivel == "medio":
        p1 = "<b>🧠 Tú eres la constante.</b> Ya tienes fundamentos sólidos. Ahora la diferencia la marca tu consistencia: mismo enfoque, mismas decisiones, misma mentalidad partida tras partida."
    else:
        p1 = "<b>🧠 Eres el factor diferencial.</b> A tu nivel, el impacto individual es enorme. Cada decisión que tomas inclina la balanza. Los mejores jugadores no dependen de la suerte para ganar."

    # Principio 2: Mala suerte
    if wr < 45:
        p2 = "<b>🍀 La mala suerte existe, pero no define tu elo.</b> AFKs, trolls, LoserQ... todo eso pasa. Hasta Faker lo vive a diario. La diferencia está en <b>qué haces con lo que sí depende de ti</b> y cómo reaccionas ante las injusticias."
    else:
        p2 = "<b>🍀 No desperdicies energía en lo incontrolable.</b> Trolleos, AFKs, mala conexión... existen y siempre van a existir. Si te enfocas en eso, pones tu energía en algo que no puedes cambiar. <b>Juega tu juego.</b>"

    # Principio 3: Aprender siempre
    if nivel == "inicial":
        p3 = "<b>📝 Todas las partidas son útiles.</b> Incluso las peores. Decisiones, posicionamiento, hábitos, muertes: <b>siempre hay algo para revisar y mejorar</b>. Rendirse o jugar mal a propósito NO ahorra tiempo, solo cultiva una mentalidad tóxica."
    else:
        p3 = "<b>📝 Nunca se deja de aprender.</b> Hasta los mejores jugadores del mundo aprenden en cada partida. Rendirse JAMÁS: solo pierdes oportunidades de mejorar y cultivas una mentalidad que te daña a ti y a tu equipo."

    # Principio 4: Proceso vs Resultado
    if wr < 48:
        p4 = "<b>🎯 Disfruta del proceso, no solo del resultado.</b> Si tu disfrute depende solo de ganar, el LoL te va a frustrar. El verdadero placer está en <b>entender, aprender y mejorar de a poco</b>. Las victorias llegan solas cuando mejoras."
    else:
        p4 = "<b>🎯 El proceso es el premio.</b> Ganar es consecuencia de mejorar. Cuando tu motivación viene de aprender y perfeccionar tu juego —no solo de los LP—, la frustración desaparece y la mejora se acelera."

    # Principio 5: Entorno competitivo
    p5 = "<b>⚔️ Ajusta tus expectativas.</b> Estás en uno de los juegos más competitivos del mundo. No esperes partidas perfectas, compañeros ideales ni cero toxicidad. <b>Ser realista no es ser negativo, es protegerte.</b>"

    # Principio 6: Escape
    p6 = "<b>🧘 Juega con la cabeza limpia.</b> Si entras a jugar para escapar de problemas, vas a rendir peor, frustrarte más fácil y los problemas van a seguir ahí. El LoL no resuelve lo que evitas. <b>Juega porque realmente quieres jugar.</b>"

    # Títulos cortos de cada principio (para subencabezar cada bloque)
    titulos = [
        "1 · Eres la constante",
        "2 · Lo que no controlas",
        "3 · Aprender siempre",
        "4 · Proceso sobre resultado",
        "5 · Expectativas realistas",
        "6 · Cabeza limpia",
    ]
    principios = [p1, p2, p3, p4, p5, p6]

    # Se muestran TODOS los principios (visión completa de la mentalidad),
    # ordenados para empezar por el más relevante según el perfil del jugador.
    if nivel == "inicial":
        orden = [0, 1, 2, 3, 4, 5]
    elif nivel == "medio":
        orden = [0, 2, 3, 4, 1, 5]
    else:
        orden = [0, 2, 4, 5, 3, 1]

    bgs = ["#1a1030", "#1a1520", "#102530", "#1a2010", "#201810", "#151020"]
    partes_html = ""
    for idx in orden:
        partes_html += f"""
        <div style="background:{bgs[idx]}; border-radius:6px; padding:10px 14px; margin:6px 0;">
        <p style="font-size:12px; color:{PURPLE_LIGHT}; margin:0 0 4px 0; letter-spacing:0.5px;">{titulos[idx]}</p>
        <p style="font-size:12px; color:{TEXT_SECONDARY}; margin:0; line-height:1.55;">{principios[idx]}</p>
        </div>"""

    # Cierre accionable, distinto según el nivel
    if nivel == "inicial":
        cierre = (
            "Empieza por uno solo: <b>antes de cada partida, recuérdate que tú eres la constante</b>. "
            "Eso ya cambia cómo reaccionas cuando algo sale mal. La mentalidad no se arregla de golpe, "
            "se entrena partida a partida, igual que el last-hit."
        )
    elif nivel == "medio":
        cierre = (
            "Ya tienes mecánica; el siguiente salto es mental. Elige <b>un</b> principio de arriba para esta semana "
            "y obsérvate: ¿lo cumpliste hoy? Llevar la cuenta de tu mentalidad rinde más LP que un counterpick perfecto."
        )
    else:
        cierre = (
            "A tu nivel la diferencia es casi toda mental: tilt, fatiga y expectativas. "
            "Los mejores no son los que nunca fallan, sino los que <b>vuelven al plan más rápido</b> tras un error. "
            "Tu consistencia emocional es tu mayor ventaja competitiva."
        )

    return f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;line-height:1.6;">
    <p style="font-size:12px;color:{PURPLE_VIOLET};margin:0 0 6px 0;"><b>Antes de los números: cómo pensar el juego</b></p>
    <p style="font-size:12px;color:{TEXT_SECONDARY};margin:0 0 10px 0;">
    El 90% de lo que frena a un jugador no es la mecánica, es la cabeza. Estos seis principios
    son la base mental sobre la que se construye todo lo demás. No son frases motivacionales:
    son hábitos de pensamiento que puedes comprobar tú mismo, partida a partida.
    </p>
    {partes_html}
    <div style="background:#15131c; border-left:3px solid {PURPLE_VIOLET}; border-radius:6px; padding:10px 14px; margin:10px 0 0 0;">
    <p style="font-size:12px;color:{TEXT_SECONDARY};margin:0;line-height:1.55;">🧭 <b>Cómo aplicarlo:</b> {cierre}</p>
    </div>
    <p style="font-size:12px;color:{TEXT_SUBTLE};margin:10px 0 0 0;font-style:italic;">
    "Cuando cambia tu forma de pensar el LoL, cambia todo lo demás."
    </p>
    </div>"""


def _generar_practica_deliberada(nombre, nivel, avg_cs, avg_d, avg_vision):
    """Genera un ejercicio de práctica deliberada basado en la peor estadística.
    Principio del curso: aislar UNA habilidad, aprender teoría, aplicar, revisar."""

    # Determinar qué habilidad practicar según la peor métrica
    if avg_cs < 5:
        habilidad = "Farmear bajo presión"
        teoria = "Mira un video sobre wave management y last-hitting bajo torre (YouTube: SkillCapped o Znorux)."
        practica = "Entra a Practice Tool 10 min al día. Solo last-hits, sin habilidades. Apunta a 36 CS a los 5 min."
        revision = "Después de cada partida, fíjate en tu CS al minuto 10. ¿Mejoró respecto a la anterior?"
    elif avg_d > 6:
        habilidad = "Posicionamiento y supervivencia"
        teoria = "Mira un video sobre 'trading' y 'positioning' en teamfights para tu rol."
        practica = "En tus próximas 5 partidas, tu ÚNICO objetivo es morir 3 veces o menos. No importa ganar o perder."
        revision = "Al final de cada partida, revisa cada muerte: ¿era evitable? ¿Qué información te faltó?"
    elif avg_vision > 0 and avg_vision < 1.0:
        habilidad = "Control de visión"
        teoria = "Aprende los mejores spots de wards para tu rol (río, jungla enemiga, objetivos)."
        practica = "Cada vez que vuelvas a base, compra 1 Control Ward. Usa el trinket NI BIEN se recarga."
        revision = "Cuenta cuántos wards colocaste esta partida vs la anterior. ¿Subió?"
    else:
        habilidad = "Trading en early game"
        teoria = "Mira un video sobre 'trading patterns' para tu campeón principal."
        practica = "En tus próximas 5 partidas, enfócate SOLO en tradear cuando el enemigo va a last-hitear."
        revision = "Después de cada partida, pregúntate: ¿gané más trades de los que perdí en early?"

    return f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;">
    <p style="font-size:14px;color:{PURPLE_LIGHT};margin:0 0 8px 0;"><b>🦾 Tu ejercicio de práctica deliberada</b></p>
    <p style="font-size:12px;color:{TEXT_SECONDARY};margin:0 0 8px 0;">
    {nombre}, la <b>práctica deliberada</b> es aislar UNA habilidad y trabajarla con intención.
    No se trata de jugar más partidas: se trata de que cada una tenga un propósito claro.
    Jugar en automático no enseña. Jugar con foco en algo específico, sí.
    </p>
    <p style="font-size:12px;color:{TEXT_PRIMARY};margin:0 0 4px 0;"><b>🎯 Esta semana practica: {habilidad}</b></p>
    <div style="background:#1a1525;border-radius:6px;padding:10px 14px;margin:8px 0;">
    <p style="font-size:12px;color:{PURPLE_LIGHT};margin:0 0 4px 0;"><b>📚 1. Aprende la teoría</b></p>
    <p style="font-size:12px;color:{TEXT_SECONDARY};margin:0 0 8px 0;">{teoria}</p>
    <p style="font-size:12px;color:{PURPLE_LIGHT};margin:0 0 4px 0;"><b>🎮 2. Aplica activamente</b></p>
    <p style="font-size:12px;color:{TEXT_SECONDARY};margin:0 0 8px 0;">{practica}</p>
    <p style="font-size:12px;color:{PURPLE_LIGHT};margin:0 0 4px 0;"><b>🔍 3. Revisa y ajusta</b></p>
    <p style="font-size:12px;color:{TEXT_SECONDARY};margin:0 0 0 0;">{revision}</p>
    </div>
    <p style="font-size:12px;color:{TEXT_SUBTLE};margin:8px 0 0 0;">
    💡 Dato: jugar 3 partidas con foco en UNA habilidad enseña más que 15 partidas en automático.
    El cerebro aprende cuando prestas atención, no cuando repites sin pensar.
    </p>
    </div>"""


def _generar_tips_salud():
    """Genera tips de salud mental y fisiología basados en el curso del coach.
    6 tareas simples: contenido salud mental, movimiento, entorno, descanso vista, manos, hidratación."""
    return f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;">
    <p style="font-size:14px;color:{TEAL_EMERALD};margin:0 0 8px 0;"><b>💚 6 hábitos simples que mejoran tu juego</b></p>
    <p style="font-size:12px;color:{TEXT_SECONDARY};margin:0 0 8px 0;">
    Tu rendimiento no depende solo de cómo juegas, sino de <b>cómo estás</b>.
    Estos micro-hábitos son fáciles de empezar hoy y tienen impacto real en tu concentración.
    </p>
    <div style="background:#0d1f17;border-radius:6px;padding:10px 14px;margin:8px 0;">
    <p style="font-size:12px;color:{TEXT_SECONDARY};margin:2px 0;"><b>🌱 Día a día</b></p>
    <p style="font-size:12px;color:{TEXT_MUTED};margin:0 0 2px 12px;">• 5 min de contenido sobre salud mental (puede ser un video, un artículo).</p>
    <p style="font-size:12px;color:{TEXT_MUTED};margin:0 0 2px 12px;">• 6 min de movimiento físico diario (mejor poco y constante que nada).</p>
    <p style="font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 2px;"><b>🎓 Antes de jugar</b></p>
    <p style="font-size:12px;color:{TEXT_MUTED};margin:0 0 2px 12px;">• Elimina distracciones: silencia notificaciones, aleja el celular, cierra redes sociales.</p>
    <p style="font-size:12px;color:{TEXT_MUTED};margin:0 0 2px 12px;">• Prepara tu espacio: escritorio limpio, agua cerca, periféricos cómodos.</p>
    <p style="font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 2px;"><b>🧾 Durante el juego</b></p>
    <p style="font-size:12px;color:{TEXT_MUTED};margin:0 0 2px 12px;">• Cada 10-15 min: suelta mouse/teclado, estira los dedos y las muñecas.</p>
    <p style="font-size:12px;color:{TEXT_MUTED};margin:0 0 2px 12px;">• En momentos tranquilos: mira a lo lejos unos segundos para descansar la vista.</p>
    </div>
    <p style="font-size:12px;color:{TEXT_SUBTLE};margin:8px 0 0 0;">
    💡 No se trata de hacer todo perfecto. Se trata de <b>pequeños cambios sostenibles</b>.
    Dormir 7-9 horas con horarios regulares ya mejora tu rendimiento más que muchas otras cosas.
    </p>
    </div>"""


def generar_reporte_coach(
    historial_games, nombre_invocador="Invocador", datos_perfil=None, datos_fatiga=None, maestrias=None, lp_history=None
):
    if not historial_games or len(historial_games) < 3:
        return {
            "secciones": [],
            "resumen": "Necesito al menos 3 partidas para analizar tu juego. Juega un par mas y vuelve!",
        }

    nombre = nombre_invocador or "Invocador"
    all_games = historial_games
    recent = historial_games[:20]
    total = len(recent)
    total_all = len(all_games)
    secciones = []

    champ_games = {}
    all_k = []
    all_d = []
    all_a = []
    all_cs = []
    all_dur = []
    all_vision = []
    all_dmg = []
    all_gold = []
    all_turrets = []
    all_dragons = []
    all_barons = []
    all_cc = []
    all_pink = []
    wins_count = 0
    primer_sangre = 0

    for g in all_games:
        part = g.get("participants", [{}])[0]
        stats = part.get("stats", {})
        cid = str(part.get("championId", "0"))
        win = stats.get("win", False)
        k = stats.get("kills", 0)
        d = stats.get("deaths", 0)
        a = stats.get("assists", 0)
        cs = stats.get("totalMinionsKilled", 0) + stats.get("neutralMinionsKilled", 0)
        dur = g.get("gameDuration", 0)
        vision = stats.get("visionScore", 0) or stats.get("wardsPlaced", 0)
        fb = stats.get("firstBloodKill", False)
        dmg = stats.get("totalDamageDealtToChampions", 0)
        gold = stats.get("goldEarned", 0)
        turrets = stats.get("turretKills", 0)
        dragons = stats.get("dragonKills", 0)
        barons = stats.get("baronKills", 0)
        cc = stats.get("timeCCingOthers", 0)
        pink = stats.get("visionWardsBoughtInGame", 0)

        if cid not in champ_games:
            champ_games[cid] = {
                "wins": 0,
                "games": 0,
                "kills": 0,
                "deaths": 0,
                "assists": 0,
                "cs": 0,
                "dmg": 0,
                "gold": 0,
            }
        cg = champ_games[cid]
        cg["games"] += 1
        if win:
            cg["wins"] += 1
        cg["kills"] += k
        cg["deaths"] += d
        cg["assists"] += a
        cg["cs"] += cs
        cg["dmg"] += dmg
        cg["gold"] += gold

        all_k.append(k)
        all_d.append(d)
        all_a.append(a)
        if dur > 0:
            if cs > 0:
                all_cs.append(cs / (dur / 60))
            if dmg > 0:
                all_dmg.append(dmg / (dur / 60))
            if gold > 0:
                all_gold.append(gold / (dur / 60))
            all_dur.append(dur)
        if vision > 0:
            all_vision.append(vision / (dur / 60))
        if win:
            wins_count += 1
        if fb:
            primer_sangre += 1
        if turrets > 0:
            all_turrets.append(turrets)
        if dragons > 0:
            all_dragons.append(dragons)
        if barons > 0:
            all_barons.append(barons)
        if cc > 0:
            all_cc.append(cc / (dur / 60)) if dur > 0 else None
        if pink > 0:
            all_pink.append(pink)

    avg_k = sum(all_k) / total_all if total_all else 0
    avg_d = sum(all_d) / total_all if total_all else 0
    avg_a = sum(all_a) / total_all if total_all else 0
    avg_cs = sum(all_cs) / len(all_cs) if all_cs else 0
    avg_vision = sum(all_vision) / len(all_vision) if all_vision else 0
    avg_dmg = sum(all_dmg) / len(all_dmg) if all_dmg else 0
    avg_gold = sum(all_gold) / len(all_gold) if all_gold else 0
    avg_turrets = sum(all_turrets) / total_all if total_all else 0
    avg_dragons = sum(all_dragons) / total_all if total_all else 0
    avg_barons = sum(all_barons) / total_all if total_all else 0
    avg_cc = sum(all_cc) / len(all_cc) if all_cc else 0
    avg_pink = sum(all_pink) / total_all if total_all else 0
    wr = (wins_count / total_all * 100) if total_all else 0
    kda = (sum(all_k) + sum(all_a)) / max(1, sum(all_d))

    sorted_champs = sorted(champ_games.items(), key=lambda x: x[1]["games"], reverse=True)
    top3 = sorted_champs[:3]
    unique_champs = len(champ_games)

    # Daño a campeones por oro generado: se calcula con TOTALES crudos (no con
    # listas por-minuto de distinta longitud, que daban un ratio sin sentido).
    total_dmg_raw = sum(cg["dmg"] for cg in champ_games.values())
    total_gold_raw = sum(cg["gold"] for cg in champ_games.values())
    dmg_ratio = (total_dmg_raw / total_gold_raw) if total_gold_raw else 0
    dmg_vs_taken = sum(
        stats.get("totalDamageDealtToChampions", 0)
        for g in all_games
        for stats in [g.get("participants", [{}])[0].get("stats", {})]
    )
    dmg_taken_total = sum(
        stats.get("totalDamageTaken", 0)
        for g in all_games
        for stats in [g.get("participants", [{}])[0].get("stats", {})]
    )
    dmg_eff = dmg_vs_taken / max(1, dmg_taken_total)

    # ── Métricas POR PARTIDA (más concretas que por-minuto para daño/oro/visión) ──
    total_cs_raw = sum(cg["cs"] for cg in champ_games.values())
    total_vision_raw = sum(
        (stats.get("visionScore", 0) or stats.get("wardsPlaced", 0))
        for g in all_games
        for stats in [g.get("participants", [{}])[0].get("stats", {})]
    )
    avg_cs_game = total_cs_raw / total_all if total_all else 0
    avg_dmg_game = total_dmg_raw / total_all if total_all else 0
    avg_gold_game = total_gold_raw / total_all if total_all else 0
    avg_vision_game = total_vision_raw / total_all if total_all else 0

    # ═══════════════════════════════════════════════════
    # SECCIÓN 0: SALUDO Y RESUMEN GENERAL
    # ═══════════════════════════════════════════════════
    estado_mental = ""
    if datos_fatiga:
        estado = datos_fatiga.get("estado", "")
        if estado == "fresh":
            estado_mental = (
                "🔥 Estás fresco y enfocado. Es un buen momento para jugar ranked. Aprovecha tu mejor versión."
            )
        elif estado == "tired":
            estado_mental = "🥱 Parece que estás un poco cansado. Considera jugar normals o descansar. El LoL no es un escape: juega solo cuando tengas la cabeza limpia."
        elif estado == "tilted":
            estado_mental = "💢 Estás en zona de tilt. Mi recomendación sincera: descansa 30 min o cambia de juego un rato. La mala suerte existe, pero jugar tilted la empeora."
        else:
            estado_mental = "⚖️ Estado neutral. Vigila cómo te sientes tras cada partida. Recuerda: tú eres el factor constante en tu progreso."

    # Determinar rango aproximado según KDA y CS para personalizar tono
    if avg_cs >= 7 and kda >= 3.5:
        nivel = "alto"
    elif avg_cs >= 5 and kda >= 2.0:
        nivel = "medio"
    else:
        nivel = "inicial"

    if nivel == "alto":
        tono = f"Eres un jugador sólido, {nombre}. Tus números muestran que entiendes bien el juego."
    elif nivel == "medio":
        tono = f"Vas por buen camino, {nombre}. Tienes fundamentos sólidos y margen de mejora claro."
    else:
        tono = f"{nombre}, veo que estás en fase de aprendizaje. No te preocupes, todo jugador pasó por aquí. Vamos paso a paso."

    resumen_html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7;">
    <p style="font-size: 14px; color: {TEXT_PRIMARY}; margin: 0 0 8px 0;"><b>👋 Hola, {nombre}!</b></p>
    <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 12px 0;">{tono}</p>
    <p style="font-size: 12px; color: {TEXT_MUTED}; margin: 0 0 4px 0;">
    📊 <b>{total_all}</b> partidas analizadas · WR <b style="color:{GREEN_SUCCESS if wr >= 50 else RED_DANGER};">{wr:.0f}%</b> ·
    KDA <b>{avg_k:.1f}/{avg_d:.1f}/{avg_a:.1f}</b> ({kda:.2f}) · CS/min <b>{avg_cs:.1f}</b>
    </p>
    <p style="font-size: 12px; color: {TEXT_MUTED}; margin: 0 0 4px 0;">
    ⚡ Daño/partida <b>{avg_dmg_game:,.0f}</b> · Oro/partida <b>{avg_gold_game:,.0f}</b> · Visión/partida <b>{avg_vision_game:.0f}</b>
    </p>
    <p style="font-size: 12px; color: {TEXT_MUTED}; margin: 0 0 0 0;">{estado_mental}</p>
    </div>
    """

    # ── Métricas adicionales ──
    top3_wr = sum(c["wins"] for _, c in top3) / max(1, sum(c["games"] for _, c in top3)) * 100
    rest = sorted_champs[3:]
    rest_wr = sum(c["wins"] for _, c in rest) / max(1, sum(c["games"] for _, c in rest)) * 100 if rest else 0
    top3_ids = [cid for cid, _ in top3]

    racha_actual = 0
    racha_tipo = None
    for g in recent:
        win = g.get("participants", [{}])[0].get("stats", {}).get("win", False)
        if racha_tipo is None:
            racha_tipo = "W" if win else "L"
            racha_actual = 1
        elif (win and racha_tipo == "W") or (not win and racha_tipo == "L"):
            racha_actual += 1
        else:
            break

    metricas = {
        "nombre": nombre, "nivel": nivel, "total_all": total_all,
        "wr": wr, "kda": kda, "avg_k": avg_k, "avg_d": avg_d, "avg_a": avg_a,
        "avg_cs": avg_cs, "avg_vision": avg_vision, "avg_vision_game": avg_vision_game,
        "avg_dmg": avg_dmg, "avg_dmg_game": avg_dmg_game,
        "avg_gold": avg_gold, "avg_gold_game": avg_gold_game,
        "avg_turrets": avg_turrets, "avg_dragons": avg_dragons, "avg_barons": avg_barons,
        "avg_cc": avg_cc, "avg_pink": avg_pink,
        "dmg_eff": dmg_eff, "dmg_ratio": dmg_ratio,
        "unique_champs": unique_champs,
        "top3": [{"cid": cid, "wins": c["wins"], "games": c["games"],
                  "kills": c["kills"], "deaths": c["deaths"],
                  "assists": c["assists"], "cs": c["cs"],
                  "dmg": c["dmg"], "gold": c["gold"]} for cid, c in top3],
        "top3_ids": top3_ids, "top3_wr": top3_wr, "rest_wr": rest_wr,
        "primer_sangre_pct": (primer_sangre / total_all * 100) if total_all else 0,
        "racha_actual": racha_actual, "racha_tipo": racha_tipo,
        "datos_fatiga": datos_fatiga, "maestrias": maestrias, "lp_history": lp_history,
    }

    from .rules_coach import REGLAS_COACH

    for regla in REGLAS_COACH:
        sec = regla.evaluar(metricas)
        if sec is not None:
            secciones.append(sec)

    secciones.sort(key=lambda s: s["prioridad"])

    if nivel == "inicial":
        consejo_final = f"Recuerda, {nombre}: League of Legends es un maratón, no un sprint. Cada partida —incluso las que pierdes— es una oportunidad de aprender algo nuevo. No te castigues por los errores: TODO jugador pasó por donde estás tú ahora. Enfócate en mejorar un 1% cada día y los resultados van a llegar solos. Y si algún día te frustras, vuelve a leer la sección de Filosofía de Juego. 💜"
    elif nivel == "medio":
        consejo_final = f"{nombre}, estás en un punto donde pequeños cambios producen grandes resultados. Elige UN área de las que te mostré y enfócate en ella esta semana. No intentes mejorar todo a la vez. Y lo más importante: disfruta del proceso. Cuando tu motivación viene de aprender y no solo de ganar, la mejora se acelera. Confía en ti: eres el factor constante en tu progreso."
    else:
        consejo_final = f"Tu nivel es alto, {nombre}. La diferencia entre tú y el siguiente escalón está en los detalles: consistencia, gestión emocional y liderazgo en el mapa. Pero no te olvides de lo fundamental: incluso Faker sigue aprendiendo en cada partida. Mantén la cabeza limpia, ajusta tus expectativas y sigue refinando. El elo es consecuencia, no objetivo."

    return {
        "secciones": secciones,
        "resumen": resumen_html,
        "consejo_final": consejo_final,
        "nivel": nivel,
        "metricas": {
            "wr": wr, "kda": kda, "avg_cs": avg_cs, "avg_d": avg_d,
            "avg_k": avg_k, "avg_a": avg_a, "avg_vision": avg_vision,
            "unique_champs": unique_champs, "top3_wr": top3_wr, "nivel": nivel,
            "avg_dmg": avg_dmg, "avg_gold": avg_gold,
            "avg_cs_game": avg_cs_game, "avg_dmg_game": avg_dmg_game,
            "avg_gold_game": avg_gold_game, "avg_vision_game": avg_vision_game,
            "avg_turrets": avg_turrets, "avg_dragons": avg_dragons, "avg_barons": avg_barons,
            "avg_cc": avg_cc, "avg_pink": avg_pink,
            "dmg_eff": dmg_eff, "total_all": total_all,
            "primer_sangre_pct": (primer_sangre / total_all * 100) if total_all else 0,
        },
    }
