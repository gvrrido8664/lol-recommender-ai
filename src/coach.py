# -*- coding: utf-8 -*-
from .theme import (TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_SUBTLE, GREEN_SUCCESS, RED_DANGER, YELLOW_WARNING, PURPLE_LIGHT, PURPLE_VIOLET, TEAL_EMERALD, PURPLE_ACCENT)
import json

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
        p1 = f"<b>🧠 Tú eres el único factor constante.</b> De 10 personas en cada ranked, 9 cambian. El único que siempre está eres tú. A largo plazo, <b>tu progreso depende de lo que tú haces</b>, no de tus compañeros."
    elif nivel == "medio":
        p1 = f"<b>🧠 Tú eres la constante.</b> Ya tienes fundamentos sólidos. Ahora la diferencia la marca tu consistencia: mismo enfoque, mismas decisiones, misma mentalidad partida tras partida."
    else:
        p1 = f"<b>🧠 Eres el factor diferencial.</b> A tu nivel, el impacto individual es enorme. Cada decisión que tomas inclina la balanza. Los mejores jugadores no dependen de la suerte para ganar."
    
    # Principio 2: Mala suerte
    if wr < 45:
        p2 = f"<b>🍀 La mala suerte existe, pero no define tu elo.</b> AFKs, trolls, LoserQ... todo eso pasa. Hasta Faker lo vive a diario. La diferencia está en <b>qué haces con lo que sí depende de ti</b> y cómo reaccionas ante las injusticias."
    else:
        p2 = f"<b>🍀 No desperdicies energía en lo incontrolable.</b> Trolleos, AFKs, mala conexión... existen y siempre van a existir. Si te enfocas en eso, pones tu energía en algo que no puedes cambiar. <b>Juega tu juego.</b>"
    
    # Principio 3: Aprender siempre
    if nivel == "inicial":
        p3 = f"<b>📝 Todas las partidas son útiles.</b> Incluso las peores. Decisiones, posicionamiento, hábitos, muertes: <b>siempre hay algo para revisar y mejorar</b>. Rendirse o jugar mal a propósito NO ahorra tiempo, solo cultiva una mentalidad tóxica."
    else:
        p3 = f"<b>📝 Nunca se deja de aprender.</b> Hasta los mejores jugadores del mundo aprenden en cada partida. Rendirse JAMÁS: solo pierdes oportunidades de mejorar y cultivas una mentalidad que te daña a ti y a tu equipo."
    
    # Principio 4: Proceso vs Resultado
    if wr < 48:
        p4 = f"<b>🎯 Disfruta del proceso, no solo del resultado.</b> Si tu disfrute depende solo de ganar, el LoL te va a frustrar. El verdadero placer está en <b>entender, aprender y mejorar de a poco</b>. Las victorias llegan solas cuando mejoras."
    else:
        p4 = f"<b>🎯 El proceso es el premio.</b> Ganar es consecuencia de mejorar. Cuando tu motivación viene de aprender y perfeccionar tu juego —no solo de los LP—, la frustración desaparece y la mejora se acelera."
    
    # Principio 5: Entorno competitivo
    p5 = f"<b>⚔️ Ajusta tus expectativas.</b> Estás en uno de los juegos más competitivos del mundo. No esperes partidas perfectas, compañeros ideales ni cero toxicidad. <b>Ser realista no es ser negativo, es protegerte.</b>"
    
    # Principio 6: Escape
    p6 = f"<b>🧘 Juega con la cabeza limpia.</b> Si entras a jugar para escapar de problemas, vas a rendir peor, frustrarte más fácil y los problemas van a seguir ahí. El LoL no resuelve lo que evitas. <b>Juega porque realmente quieres jugar.</b>"
    
    principios = [p1, p2, p3, p4, p5, p6]
    
    # Elegir 3-4 principios más relevantes según perfil
    if nivel == "inicial":
        seleccion = [0, 1, 2, 3]  # Factor constante, mala suerte, aprender, proceso
    elif nivel == "medio":
        seleccion = [0, 2, 3, 4]  # Constante, aprender, proceso, expectativas
    else:
        seleccion = [0, 2, 4, 5]  # Constante, aprender, expectativas, cabeza limpia
    
    partes_html = ""
    for idx in seleccion:
        color_bg = ["#1a1030", "#1a1520", "#102530", "#1a2010", "#201810", "#151020"][idx]
        partes_html += f"""
        <div style="background:{color_bg}; border-radius:6px; padding:10px 14px; margin:6px 0;">
        <p style="font-size:11px; color:{TEXT_SECONDARY}; margin:0; line-height:1.5;">{principios[idx]}</p>
        </div>"""
    
    return f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;line-height:1.6;">
    <p style="font-size:12px;color:{PURPLE_VIOLET};margin:0 0 10px 0;">
    💡 <b>Antes de ver tus números, quiero compartirte algo importante.</b> 
    Estas ideas me ayudaron a mí y a cientos de jugadores a pensar mejor el juego. No son reglas rígidas, son principios que puedes comprobar tú mismo.
    </p>
    {partes_html}
    <p style="font-size:10px;color:{TEXT_SUBTLE};margin:10px 0 0 0;font-style:italic;">
    ✨ "Cuando cambia tu forma de pensar el LoL, cambia todo lo demás."
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
    <p style="font-size:11px;color:{PURPLE_LIGHT};margin:0 0 4px 0;"><b>📚 1. Aprende la teoría</b></p>
    <p style="font-size:11px;color:{TEXT_SECONDARY};margin:0 0 8px 0;">{teoria}</p>
    <p style="font-size:11px;color:{PURPLE_LIGHT};margin:0 0 4px 0;"><b>🎮 2. Aplica activamente</b></p>
    <p style="font-size:11px;color:{TEXT_SECONDARY};margin:0 0 8px 0;">{practica}</p>
    <p style="font-size:11px;color:{PURPLE_LIGHT};margin:0 0 4px 0;"><b>🔍 3. Revisa y ajusta</b></p>
    <p style="font-size:11px;color:{TEXT_SECONDARY};margin:0 0 0 0;">{revision}</p>
    </div>
    <p style="font-size:11px;color:{TEXT_SUBTLE};margin:8px 0 0 0;">
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
    <p style="font-size:11px;color:{TEXT_SECONDARY};margin:2px 0;"><b>🌱 Día a día</b></p>
    <p style="font-size:11px;color:{TEXT_MUTED};margin:0 0 2px 12px;">• 5 min de contenido sobre salud mental (puede ser un video, un artículo).</p>
    <p style="font-size:11px;color:{TEXT_MUTED};margin:0 0 2px 12px;">• 6 min de movimiento físico diario (mejor poco y constante que nada).</p>
    <p style="font-size:11px;color:{TEXT_SECONDARY};margin:8px 0 2px;"><b>🎓 Antes de jugar</b></p>
    <p style="font-size:11px;color:{TEXT_MUTED};margin:0 0 2px 12px;">• Elimina distracciones: silencia notificaciones, aleja el celular, cierra redes sociales.</p>
    <p style="font-size:11px;color:{TEXT_MUTED};margin:0 0 2px 12px;">• Prepara tu espacio: escritorio limpio, agua cerca, periféricos cómodos.</p>
    <p style="font-size:11px;color:{TEXT_SECONDARY};margin:8px 0 2px;"><b>🧾 Durante el juego</b></p>
    <p style="font-size:11px;color:{TEXT_MUTED};margin:0 0 2px 12px;">• Cada 10-15 min: suelta mouse/teclado, estira los dedos y las muñecas.</p>
    <p style="font-size:11px;color:{TEXT_MUTED};margin:0 0 2px 12px;">• En momentos tranquilos: mira a lo lejos unos segundos para descansar la vista.</p>
    </div>
    <p style="font-size:11px;color:{TEXT_SUBTLE};margin:8px 0 0 0;">
    💡 No se trata de hacer todo perfecto. Se trata de <b>pequeños cambios sostenibles</b>. 
    Dormir 7-9 horas con horarios regulares ya mejora tu rendimiento más que muchas otras cosas.
    </p>
    </div>"""


def generar_reporte_coach(historial_games, nombre_invocador="Invocador", datos_perfil=None, datos_fatiga=None):
    """
    COACHING PRO — Reporte completo y empático basado en datos reales.
    Analiza el historial y devuelve un dict con todas las secciones de coaching.
    
    Cada sección contiene:
      - "titulo": nombre de la sección
      - "icono": emoji
      - "color": color para el borde
      - "html": contenido en HTML para mostrar
      - "prioridad": número (menor = más urgente)
    """
    if not historial_games or len(historial_games) < 3:
        return {
            "secciones": [],
            "resumen": "Necesito al menos 3 partidas para analizar tu juego. ¡Juega un par más y vuelve! 🎮",
        }
    
    nombre = nombre_invocador or "Invocador"
    recent = historial_games[:20]
    total = len(recent)
    secciones = []
    
    # ═══════════════════════════════════════════════════
    # DATOS BASE
    # ═══════════════════════════════════════════════════
    champ_games = {}
    all_k = []; all_d = []; all_a = []; all_cs = []; all_dur = []
    all_vision = []
    wins_count = 0
    roles_count = {}
    primer_sangre = 0
    
    for g in recent:
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
        
        if cid not in champ_games:
            champ_games[cid] = {"wins": 0, "games": 0, "kills": 0, "deaths": 0, "assists": 0, "cs": 0}
        cg = champ_games[cid]
        cg["games"] += 1
        if win: cg["wins"] += 1
        cg["kills"] += k; cg["deaths"] += d; cg["assists"] += a; cg["cs"] += cs
        
        all_k.append(k); all_d.append(d); all_a.append(a)
        if dur > 0 and cs > 0:
            all_cs.append(cs / (dur / 60))
            all_dur.append(dur)
        if vision > 0: all_vision.append(vision / (dur / 60))
        if win: wins_count += 1
        if fb: primer_sangre += 1
    
    avg_k = sum(all_k) / total if total else 0
    avg_d = sum(all_d) / total if total else 0
    avg_a = sum(all_a) / total if total else 0
    avg_cs = sum(all_cs) / len(all_cs) if all_cs else 0
    avg_vision = sum(all_vision) / len(all_vision) if all_vision else 0
    wr = (wins_count / total * 100) if total else 0
    kda = (sum(all_k) + sum(all_a)) / max(1, sum(all_d))
    
    sorted_champs = sorted(champ_games.items(), key=lambda x: x[1]["games"], reverse=True)
    top3 = sorted_champs[:3]
    unique_champs = len(champ_games)
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 0: SALUDO Y RESUMEN GENERAL
    # ═══════════════════════════════════════════════════
    estado_mental = ""
    if datos_fatiga:
        estado = datos_fatiga.get("estado", "")
        if estado == "fresh": estado_mental = "🔥 Estás fresco y enfocado. Es un buen momento para jugar ranked. Aprovecha tu mejor versión."
        elif estado == "tired": estado_mental = "🥱 Parece que estás un poco cansado. Considera jugar normals o descansar. El LoL no es un escape: juega solo cuando tengas la cabeza limpia."
        elif estado == "tilted": estado_mental = "💢 Estás en zona de tilt. Mi recomendación sincera: descansa 30 min o cambia de juego un rato. La mala suerte existe, pero jugar tilted la empeora."
        else: estado_mental = "⚖️ Estado neutral. Vigila cómo te sientes tras cada partida. Recuerda: tú eres el factor constante en tu progreso."
    
    # Determinar rango aproximado según KDA y CS para personalizar tono
    if avg_cs >= 7 and kda >= 3.5: nivel = "alto"
    elif avg_cs >= 5 and kda >= 2.0: nivel = "medio"
    else: nivel = "inicial"
    
    if nivel == "alto":
        tono = f"Eres un jugador sólido, {nombre}. Tus números muestran que entiendes bien el juego."
    elif nivel == "medio":
        tono = f"Vas por buen camino, {nombre}. Tienes fundamentos sólidos y margen de mejora claro."
    else:
        tono = f"{nombre}, veo que estás en fase de aprendizaje. No te preocupes, todo jugador pasó por aquí. Vamos paso a paso."
    
    resumen_html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7;">
    <p style="font-size: 16px; color: {TEXT_PRIMARY}; margin: 0 0 8px 0;"><b>👋 ¡Hola, {nombre}!</b></p>
    <p style="font-size: 13px; color: {TEXT_SECONDARY}; margin: 0 0 12px 0;">{tono}</p>
    <p style="font-size: 12px; color: {TEXT_MUTED}; margin: 0 0 4px 0;">
    📊 <b>{total}</b> partidas analizadas · WR <b style="color:{'{GREEN_SUCCESS}' if wr >= 50 else '{RED_DANGER}'};">{wr:.0f}%</b> · 
    KDA <b>{avg_k:.0f}/{avg_d:.0f}/{avg_a:.0f}</b> · CS/min <b>{avg_cs:.1f}</b>
    </p>
    <p style="font-size: 12px; color: {TEXT_MUTED}; margin: 0 0 0 0;">{estado_mental}</p>
    </div>
    """
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 0.5: FILOSOFÍA DE JUEGO (basado en el curso del coach)
    # ═══════════════════════════════════════════════════
    filo_html = _generar_filosofia_juego(nombre, nivel, wr, avg_d, total)
    secciones.append({
        "titulo": "FILOSOFÍA DE JUEGO — Tu Mentalidad",
        "icono": "🧘",
        "color": "{PURPLE_VIOLET}",
        "html": filo_html,
        "prioridad": 0,  # Siempre primero
    })
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 1: CHAMPION POOL
    # ═══════════════════════════════════════════════════
    top3_wr = sum(c["wins"] for _, c in top3) / max(1, sum(c["games"] for _, c in top3)) * 100
    rest = sorted_champs[3:]
    rest_wr = sum(c["wins"] for _, c in rest) / max(1, sum(c["games"] for _, c in rest)) * 100 if rest else 0
    is_too_wide = unique_champs > 5
    
    cp_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
    
    if is_too_wide:
        cp_html += f"""
        <p style="font-size: 14px; color: {YELLOW_WARNING}; margin: 0 0 8px 0;"><b>⚠️ Estás jugando demasiados campeones ({unique_champs} en {total} partidas)</b></p>
        <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
        Esto es lo que pasa: tu cerebro gasta energía adaptándose a cada campeón en vez de enfocarse en el mapa. 
        <b style="color: {GREEN_SUCCESS};">Tu WR con tu top 3 es {top3_wr:.0f}%</b>, pero con el resto cae a 
        <b style="color: {RED_DANGER};">{rest_wr:.0f}%</b>. Esa diferencia son partidas que regalas.
        </p>
        <p style="font-size: 12px; color: {TEXT_PRIMARY}; margin: 0 0 4px 0;"><b>🎯 Plan de acción:</b></p>
        <ul style="margin: 4px 0; padding-left: 18px; color: {TEXT_SECONDARY}; font-size: 12px;">
        <li>Elige <b>2 campeones principales</b> y 1 de reserva. Juega solo esos durante 2 semanas.</li>
        <li>Tus picks deben <b>compartir estilo de juego</b> (coherencia mecánica): así las habilidades se transfieren y el aprendizaje se acumula.</li>
        <li>Idealmente, que <b>se cubran entre sí</b>: si te pickean tu main, que el otro sea una buena respuesta.</li>
        <li>Si quieres probar algo nuevo, hazlo en normals, no en ranked.</li>
        <li>La consistencia gana más partidas que el counterpick perfecto.</li>
        </ul>
        """
    else:
        cp_html += f"""
        <p style="font-size: 14px; color: {GREEN_SUCCESS}; margin: 0 0 8px 0;"><b>✅ Pool de campeones enfocada ({unique_champs} distintos)</b></p>
        <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
        Buena disciplina. Mantener un pool reducido y coherente te permite dominar matchups y concentrarte en el macro.
        Tus picks deben <b>compartir patrones de gameplay</b>: así las mecánicas se transfieren, el aprendizaje se acumula
        y cambiar de campeón se siente natural. Tu WR con tu top 3 es <b style="color: {GREEN_SUCCESS};">{top3_wr:.0f}%</b>. Así se construye el elo.
        </p>
        """
    
    # Mostrar top 3 con stats
    cp_html += '<p style="font-size: 12px; color: {TEXT_MUTED}; margin: 8px 0 4px 0;"><b>Tu top 3:</b></p>'
    for i, (champ_name, cs_data) in enumerate(top3):
        c_wr = (cs_data["wins"] / cs_data["games"] * 100) if cs_data["games"] > 0 else 0
        c_kda = (cs_data["kills"] + cs_data["assists"]) / max(1, cs_data["deaths"])
        c_cs = cs_data["cs"] / max(1, cs_data["games"])
        color_wr = "{GREEN_SUCCESS}" if c_wr >= 50 else "{RED_DANGER}"
        cp_html += f'<p style="font-size: 11px; color: {color_wr}; margin: 2px 0 2px 12px;">{i+1}. {champ_name} — {c_wr:.0f}% WR · KDA {c_kda:.1f} · {cs_data["games"]} partidas</p>'
    
    cp_html += '</div>'
    
    secciones.append({
        "titulo": "AUDITORÍA DE CHAMPION POOL",
        "icono": "📋",
        "color": "{YELLOW_WARNING}" if is_too_wide else "{GREEN_SUCCESS}",
        "html": cp_html,
        "prioridad": 1 if is_too_wide else 3,
    })
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 2: FASE DE LÍNEAS (CS + EARLY)
    # ═══════════════════════════════════════════════════
    cs_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
    
    if avg_cs < 4.5:
        cs_html += f"""
        <p style="font-size: 14px; color: {RED_DANGER}; margin: 0 0 8px 0;"><b>🔴 Tu farmeo necesita atención urgente: {avg_cs:.1f} CS/min</b></p>
        <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
        Mira, {nombre}, esto es lo más importante que puedes mejorar ahora mismo. Cada 15-20 CS equivalen a 
        <b>una kill en oro</b>. Si farmeas mejor, llegarás a tus objetos más rápido sin necesidad de arriesgarte en peleas.
        </p>
        <p style="font-size: 12px; color: {TEXT_PRIMARY}; margin: 0 0 4px 0;"><b>🎯 Ejercicio concreto:</b></p>
        <ul style="margin: 4px 0; padding-left: 18px; color: {TEXT_SECONDARY}; font-size: 12px;">
        <li>Entra al <b>Practice Tool</b> 10 minutos al día.</li>
        <li>Elige tu campeón principal, <b>sin objetos ni runas de daño</b>.</li>
        <li>Solo last-hit. Nada de habilidades. Apunta a 36 CS a los 5 min (6/min).</li>
        <li>Cuando llegues a 70 CS en 10 min consistentemente, empieza a añadir trades contra un bot.</li>
        </ul>
        <p style="font-size: 11px; color: {TEXT_SUBTLE}; margin: 8px 0 0 0;">💡 Dato: Un campeón con 150 CS a los 20 min tiene el mismo oro que uno con 50 CS y 5 kills. El CS es seguro, las kills no.</p>
        """
    elif avg_cs < 6.5:
        cs_html += f"""
        <p style="font-size: 14px; color: {YELLOW_WARNING}; margin: 0 0 8px 0;"><b>🟡 Farmeo decente pero con margen de mejora: {avg_cs:.1f} CS/min</b></p>
        <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
        No está mal, {nombre}, pero cada CS que pierdes es oro que dejas en la mesa. En partidas igualadas, 
        la diferencia entre 6 y 7.5 CS/min puede ser completar un objeto clave 3 minutos antes.
        </p>
        <p style="font-size: 12px; color: {TEXT_PRIMARY}; margin: 0 0 4px 0;"><b>🎯 Plan:</b></p>
        <ul style="margin: 4px 0; padding-left: 18px; color: {TEXT_SECONDARY}; font-size: 12px;">
        <li>En los primeros 10 min, prioriza <b>NO perder CS</b> sobre tradear.</li>
        <li>Aprende a farmear bajo torre: melé = 2 torre + 1 auto, caster = 1 auto + torre + 1 auto.</li>
        <li>En mid-late, no dejes que las oleadas mueran solas: rotan entre líneas para absorber oro.</li>
        </ul>
        """
    else:
        cs_html += f"""
        <p style="font-size: 14px; color: {GREEN_SUCCESS}; margin: 0 0 8px 0;"><b>🟢 Excelente farmeo: {avg_cs:.1f} CS/min</b></p>
        <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
        Esto es nivel alto, {nombre}. Tu economía early es sólida y llegas a tus poderes antes que el rival.
        Asegúrate de traducir esa ventaja de oro en presión en el mapa: rotaciones, visión agresiva y objetivos.
        </p>
        """
    
    # First blood
    if primer_sangre >= total * 0.3:
        cs_html += f'<p style="font-size: 11px; color: {GREEN_SUCCESS}; margin: 8px 0 0 0;">⚔️ Además, consigues First Blood en el {primer_sangre/total*100:.0f}% de tus partidas. ¡Agresividad bien ejecutada!</p>'
    
    cs_html += '</div>'
    
    secciones.append({
        "titulo": "RENDIMIENTO EN FASE DE LÍNEAS",
        "icono": "⚔️",
        "color": "{RED_DANGER}" if avg_cs < 5 else "{YELLOW_WARNING}" if avg_cs < 6.5 else "{GREEN_SUCCESS}",
        "html": cs_html,
        "prioridad": 0 if avg_cs < 5 else 2,
    })
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 3: SUPERVIVENCIA Y DECISIONES
    # ═══════════════════════════════════════════════════
    sv_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
    
    if avg_d > 7:
        sv_html += f"""
        <p style="font-size: 14px; color: {RED_DANGER}; margin: 0 0 8px 0;"><b>🔴 Mueres demasiado: {avg_d:.1f} muertes por partida</b></p>
        <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
        {nombre}, esta es la estadística que más te está frenando. Cada muerte le da <b>300g + asistencia</b> al enemigo. 
        En 20 partidas con {avg_d:.0f} muertes de media, has regalado aproximadamente <b>{int(avg_d * 300 * total)} de oro</b>.
        Eso son varios objetos completos.
        </p>
        <p style="font-size: 12px; color: {TEXT_PRIMARY}; margin: 0 0 4px 0;"><b>🎯 Reglas de oro:</b></p>
        <ul style="margin: 4px 0; padding-left: 18px; color: {TEXT_SECONDARY}; font-size: 12px;">
        <li><b>Regla de las 2 muertes:</b> si mueres 2 veces en lane, deja de tradear. Farma bajo torre y espera a tu jungla.</li>
        <li>Antes de pushear una línea lateral, pregúntate: ¿sé dónde están los 5 enemigos? Si la respuesta es no, no pases del río.</li>
        <li>Compra un <b>Control Ward</b> cada vez que vuelvas a base. 75g que te salvan de regalar 300g.</li>
        </ul>
        """
    elif avg_d > 5:
        sv_html += f"""
        <p style="font-size: 14px; color: {YELLOW_WARNING}; margin: 0 0 8px 0;"><b>🟡 Tus muertes son mejorables: {avg_d:.1f} por partida (KDA {kda:.1f})</b></p>
        <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
        No es dramático, {nombre}, pero reducir tus muertes a 4 o menos por partida puede subir tu WR 5-10% 
        sin cambiar nada más de tu juego.
        </p>
        <p style="font-size: 12px; color: {TEXT_PRIMARY}; margin: 0 0 4px 0;"><b>🎯 Claves:</b></p>
        <ul style="margin: 4px 0; padding-left: 18px; color: {TEXT_SECONDARY}; font-size: 12px;">
        <li>Wardea antes de pushear, no mientras.</li>
        <li>Si no ves al jungla enemigo en el mapa, asume que está en tu línea.</li>
        <li>En teamfights, identifica qué habilidad enemiga NO debes recibir y juega alrededor de eso.</li>
        </ul>
        """
    else:
        sv_html += f"""
        <p style="font-size: 14px; color: {GREEN_SUCCESS}; margin: 0 0 8px 0;"><b>🟢 Buen control de muertes: {avg_d:.1f} por partida (KDA {kda:.1f})</b></p>
        <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
        Muy bien, {nombre}. Mantener baja tu tasa de muertes es señal de buen juicio. 
        Cada muerte que evitas son 300g que no regalas. Sigue así.
        </p>
        """
    
    sv_html += '</div>'
    
    secciones.append({
        "titulo": "TOMA DE DECISIONES Y SUPERVIVENCIA",
        "icono": "🛡️",
        "color": "{RED_DANGER}" if avg_d > 7 else "{YELLOW_WARNING}" if avg_d > 5 else "{GREEN_SUCCESS}",
        "html": sv_html,
        "prioridad": 0 if avg_d > 6 else 1 if avg_d > 5 else 3,
    })
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 4: VISIÓN
    # ═══════════════════════════════════════════════════
    if avg_vision > 0:
        vis_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
        if avg_vision < 0.5:
            vis_html += f"""
            <p style="font-size: 14px; color: {RED_DANGER}; margin: 0 0 8px 0;"><b>🔴 Visión muy baja: {avg_vision:.1f}/min</b></p>
            <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
            La visión es información, y la información gana partidas. Con {avg_vision:.1f} de visión por minuto, 
            estás jugando a ciegas gran parte del tiempo. Cada ward es un "no me matan" potencial.
            </p>
            <p style="font-size: 12px; color: {TEXT_PRIMARY}; margin: 0 0 4px 0;"><b>🎯 Hábito a crear:</b></p>
            <ul style="margin: 4px 0; padding-left: 18px; color: {TEXT_SECONDARY}; font-size: 12px;">
            <li>Cada vez que vuelvas a base, compra al menos 1 Control Ward.</li>
            <li>Usa el trinket en cuanto esté disponible. No lo guardes.</li>
            <li>Mira el minimapa cada 5 segundos. Suena intenso, pero se convierte en hábito.</li>
            </ul>
            """
        elif avg_vision < 1.0:
            vis_html += f"""
            <p style="font-size: 14px; color: {YELLOW_WARNING}; margin: 0 0 8px 0;"><b>🟡 Visión aceptable: {avg_vision:.1f}/min</b></p>
            <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
            No está mal, pero los mejores jugadores suelen estar por encima de 1.5/min en soloQ. 
            Un buen objetivo es comprar 2-3 Control Wards por partida.
            </p>
            """
        else:
            vis_html += f"""
            <p style="font-size: 14px; color: {GREEN_SUCCESS}; margin: 0 0 8px 0;"><b>🟢 Buena visión: {avg_vision:.1f}/min</b></p>
            <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
            Excelente control de visión. Eso ayuda a tu equipo más de lo que crees. ¡Sigue así!
            </p>
            """
        vis_html += '</div>'
        
        secciones.append({
            "titulo": "CONTROL DE VISIÓN",
            "icono": "👁️",
            "color": "{RED_DANGER}" if avg_vision < 0.5 else "{YELLOW_WARNING}" if avg_vision < 1.0 else "{GREEN_SUCCESS}",
            "html": vis_html,
            "prioridad": 2 if avg_vision < 0.5 else 3,
        })
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 5: GESTIÓN DE SESIONES (FATIGA)
    # ═══════════════════════════════════════════════════
    if datos_fatiga:
        sesiones = datos_fatiga.get("sesiones", [])
        partidas_hoy = datos_fatiga.get("partidas_hoy", [])
        if sesiones:
            sesion_actual = sesiones[-1] if sesiones else []
            total_sesion = len(sesion_actual)
            
            if total_sesion >= 4:
                wins_sesion = sum(1 for p in sesion_actual if p.get("win", False))
                wr_sesion = (wins_sesion / total_sesion * 100) if total_sesion else 0
                
                fat_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
                
                if wr_sesion < 40:
                    fat_html += f"""
                    <p style="font-size: 14px; color: {RED_DANGER}; margin: 0 0 8px 0;"><b>🔴 Llevas {total_sesion} partidas en esta sesión con {wr_sesion:.0f}% WR</b></p>
                    <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
                    {nombre}, los datos son claros: tu rendimiento baja drásticamente en sesiones largas. 
                    Llevas {total_sesion} partidas seguidas. Tu cerebro está fatigado aunque no lo notes.
                    </p>
                    <p style="font-size: 12px; color: {TEXT_PRIMARY}; margin: 0 0 4px 0;"><b>🧠 Lo que dice la ciencia:</b></p>
                    <p style="font-size: 11px; color: {TEXT_MUTED}; margin: 0 0 8px 0;">
                    Después de 90-120 minutos de juego intenso, tu tiempo de reacción y toma de decisiones 
                    se degradan significativamente. Los jugadores profesionales rotan entre partidas y descansos por esto.
                    </p>
                    <p style="font-size: 12px; color: {TEXT_PRIMARY}; margin: 0 0 4px 0;"><b>🎯 Mi recomendación:</b></p>
                    <ul style="margin: 4px 0; padding-left: 18px; color: {TEXT_SECONDARY}; font-size: 12px;">
                    <li>Termina esta sesión ya. Levántate, hidrátate, descansa al menos 30 minutos.</li>
                    <li>Establece un límite: 3 partidas, luego pausa obligatoria de 15-30 min.</li>
                    <li>Si pierdes 2 seguidas, para. No hay recuperación milagrosa en la tercera.</li>
                    </ul>
                    """
                elif wr_sesion >= 60:
                    fat_html += f"""
                    <p style="font-size: 14px; color: {GREEN_SUCCESS}; margin: 0 0 8px 0;"><b>🔥 Buen momento: {wr_sesion:.0f}% WR en {total_sesion} partidas</b></p>
                    <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
                    Estás en racha, {nombre}. Pero recuerda: incluso en una buena sesión, 
                    tu concentración tiene un límite. Programa un descanso pronto para mantener el nivel.
                    </p>
                    """
                else:
                    fat_html += f"""
                    <p style="font-size: 14px; color: {TEXT_PRIMARY}; margin: 0 0 8px 0;"><b>⚖️ Sesión estable: {wr_sesion:.0f}% WR en {total_sesion} partidas</b></p>
                    <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
                    Rendimiento consistente. Vigila cómo te sientes y no dudes en parar si notas fatiga mental.
                    </p>
                    """
                
                if partidas_hoy:
                    wins_hoy = sum(1 for p in partidas_hoy if p.get("win", False))
                    wr_hoy = (wins_hoy / len(partidas_hoy) * 100) if partidas_hoy else 0
                    fat_html += f'<p style="font-size: 11px; color: {TEXT_SUBTLE}; margin: 8px 0 0 0;">📅 Hoy: {len(partidas_hoy)} partidas · {wr_hoy:.0f}% WR</p>'
                
                fat_html += '</div>'
                
                secciones.append({
                    "titulo": "GESTIÓN DE SESIONES Y FATIGA",
                    "icono": "🧠",
                    "color": "{RED_DANGER}" if wr_sesion < 40 else "{GREEN_SUCCESS}" if wr_sesion >= 60 else "{YELLOW_WARNING}",
                    "html": fat_html,
                    "prioridad": 1 if wr_sesion < 40 else 3,
                })
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 5.5: RACHA Y RESILIENCIA (Proceso vs Resultado)
    # ═══════════════════════════════════════════════════
    racha_actual = 0
    racha_tipo = None  # 'W' o 'L'
    for g in recent:
        win = g.get("participants", [{}])[0].get("stats", {}).get("win", False)
        if racha_tipo is None:
            racha_tipo = 'W' if win else 'L'
            racha_actual = 1
        elif (win and racha_tipo == 'W') or (not win and racha_tipo == 'L'):
            racha_actual += 1
        else:
            break
    
    if racha_actual >= 3:
        racha_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
        if racha_tipo == 'L':
            racha_html += f"""
            <p style="font-size: 14px; color: {RED_DANGER}; margin: 0 0 8px 0;"><b>🔴 Llevas {racha_actual} derrotas seguidas</b></p>
            <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
            {nombre}, esto es importante: <b>la mala suerte existe</b>. AFKs, trolls, malos matchups... 
            todo eso pasa y es real. Pero hay dos caminos: puedes enfocarte en lo que no controlas (y frustrarte) 
            o puedes enfocarte en <b>lo que sí depende de ti</b>.
            </p>
            <p style="font-size: 12px; color: {TEXT_PRIMARY}; margin: 0 0 4px 0;"><b>🎯 Qué hacer ahora:</b></p>
            <ul style="margin: 4px 0; padding-left: 18px; color: {TEXT_SECONDARY}; font-size: 12px;">
            <li><b>No juegues en automático.</b> Tómate 5 minutos para respirar antes de la siguiente.</li>
            <li>Pregúntate: ¿Hubo algo que YO podría haber hecho mejor? Incluso en partidas con AFK, siempre hay algo para revisar.</li>
            <li>Si perdiste 2 seguidas, para. No hay recuperación milagrosa en la tercera. Es la trampa más común del LoL.</li>
            </ul>
            <p style="font-size: 11px; color: {TEXT_SUBTLE}; margin: 8px 0 0 0;">📝 Recuerda: <b>todas las partidas son útiles</b>. Rendirse o jugar mal a propósito solo cultiva una mentalidad tóxica que te daña. Incluso en las peores derrotas, siempre hay algo para aprender.</p>
            """
        else:
            racha_html += f"""
            <p style="font-size: 14px; color: {GREEN_SUCCESS}; margin: 0 0 8px 0;"><b>🔥 ¡{racha_actual} victorias seguidas!</b></p>
            <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
            Excelente momento, {nombre}. Pero no te confíes: <b>el verdadero crecimiento viene de mantener la consistencia</b> 
            incluso cuando las cosas van bien. Disfruta la racha, pero no olvides que cada partida es una nueva oportunidad de aprender.
            </p>
            <p style="font-size: 11px; color: {TEXT_SUBTLE}; margin: 8px 0 0 0;">💡 Dato: los jugadores que más mejoran no son los que ganan más, sino los que <b>analizan tanto sus victorias como sus derrotas</b>.</p>
            """
        racha_html += '</div>'
        
        secciones.append({
            "titulo": "RACHA Y RESILIENCIA",
            "icono": "📈",
            "color": "{RED_DANGER}" if racha_tipo == 'L' else "{GREEN_SUCCESS}",
            "html": racha_html,
            "prioridad": 1 if racha_tipo == 'L' else 4,
        })
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 5.6: JUGAR POR BLOQUES (método de 3 partidas)
    # ═══════════════════════════════════════════════════
    bloques_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
    bloques_html += f"""
    <p style="font-size: 14px; color: {PURPLE_ACCENT}; margin: 0 0 8px 0;"><b>🧊 Juega por bloques de 3 partidas</b></p>
    <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">
    Tu concentración <b>tiene un límite</b>. Después de 3-4 partidas seguidas, tu cerebro entra en piloto automático 
    y tomas peores decisiones. No es falta de habilidad: es fatiga mental real.
    </p>
    <p style="font-size: 12px; color: {TEXT_PRIMARY}; margin: 0 0 4px 0;"><b>📊 El método simple:</b></p>
    <ul style="margin: 4px 0; padding-left: 18px; color: {TEXT_SECONDARY}; font-size: 12px;">
    <li>Juega <b>hasta 3 partidas</b> por bloque.</li>
    <li><b>Si pierdes 2 seguidas → corta el bloque.</b> No hay recuperación milagrosa en la tercera.</li>
    <li>Entre bloques: descansa sin LoL (30+ min). Levántate, camina, toma agua.</li>
    <li>Entre partidas: 2-5 min de pausa. Suelta el mouse, estira las manos, mira a lo lejos.</li>
    </ul>
    <p style="font-size: 11px; color: {TEXT_SUBTLE}; margin: 8px 0 0 0;">
    💡 Este sistema hace que tengas más días positivos que negativos. No es frenarte: es <b>administrar tu energía</b>. 
    Las ganas de jugar se acumulan y las aprovechas mejor cuando vuelves fresco.
    </p>
    """
    bloques_html += '</div>'
    
    secciones.append({
        "titulo": "JUGAR POR BLOQUES (3 partidas)",
        "icono": "🧊",
        "color": "{PURPLE_ACCENT}",
        "html": bloques_html,
        "prioridad": 4,
    })
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 5.7: PRÁCTICA DELIBERADA
    # ═══════════════════════════════════════════════════
    practica_html = _generar_practica_deliberada(nombre, nivel, avg_cs, avg_d, avg_vision)
    secciones.append({
        "titulo": "PRÁCTICA DELIBERADA",
        "icono": "🦾",
        "color": "{PURPLE_LIGHT}",
        "html": practica_html,
        "prioridad": 5,
    })
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 5.8: SALUD MENTAL Y FISIOLOGÍA
    # ═══════════════════════════════════════════════════
    salud_html = _generar_tips_salud()
    secciones.append({
        "titulo": "SALUD MENTAL Y FISIOLOGÍA",
        "icono": "💚",
        "color": "{TEAL_EMERALD}",
        "html": salud_html,
        "prioridad": 6,
    })
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 6: RECOMENDACIÓN FINAL
    # ═══════════════════════════════════════════════════
    # Identificar el área más urgente
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
            "avg_vision": avg_vision, "unique_champs": unique_champs,
            "top3_wr": top3_wr, "nivel": nivel
        }
    }

