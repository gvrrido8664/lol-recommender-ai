"""
Reglas modulares para generar_reporte_coach — patrón Strategy.

Cada regla recibe un dict de métricas precomputadas y devuelve
una sección (dict con titulo, icono, color, html, prioridad) o None
si la condición no se cumple.
"""

from src.coach import _generar_filosofia_juego, _generar_practica_deliberada, _generar_tips_salud, _id_to_champ

RED_DANGER = "#ef4444"
YELLOW_WARNING = "#f59e0b"
GREEN_SUCCESS = "#22c55e"
PURPLE_LIGHT = "#c084fc"
INDIGO = "#818cf8"
VIOLET = "#a78bfa"
GOLD = "#f0b232"
TEXT_SECONDARY = "#94a3b8"
TEXT_SUBTLE = "#64748b"
TEXT_WHITE = "#f8fafc"
BG_DARK = "#0d0b10"
BG_PANEL = "#16131c"


class ReglaCoach:
    """Clase base para reglas de coaching."""

    def evaluar(self, m: dict) -> dict | None:
        raise NotImplementedError


# ─── Sección 0.5: Filosofía de juego ─────────────────────────────────────────

class ReglaFilosofiaJuego(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        html = _generar_filosofia_juego(m["nombre"], m["nivel"], m["wr"], m["avg_d"], m["total_all"])
        return {
            "titulo": "FILOSOFÍA DE JUEGO — Tu Mentalidad",
            "icono": "🧠",
            "color": PURPLE_LIGHT,
            "html": html,
            "prioridad": 0,
        }


# ─── Sección 1: Auditoría de Champion Pool ───────────────────────────────────

class ReglaAuditoriaChampion(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        top3 = m["top3"]
        unique = m["unique_champs"]
        is_wide = unique > 5

        if is_wide:
            color = YELLOW_WARNING
            icono = "⚠️"
            prio = 1
            titulo = "AUDITORÍA DE CHAMPION POOL — Demasiados Campeones"
        else:
            color = GREEN_SUCCESS
            icono = "✅"
            prio = 3
            titulo = "AUDITORÍA DE CHAMPION POOL — Pool Enfocado"

        rows = ""
        for ci, cd in enumerate(top3):
            name = _id_to_champ(cd["cid"])
            wr_local = cd["wins"] / max(1, cd["games"]) * 100
            k_total = cd["kills"] + cd["assists"]
            d = max(1, cd["deaths"])
            kda_local = (k_total) / d
            rows += (
                f'<tr style="border-bottom:1px solid #1e293b;">'
                f'<td style="padding:8px 12px;color:{TEXT_WHITE};font-weight:600;">{ci + 1}. {name}</td>'
                f'<td style="padding:8px 12px;text-align:center;color:{"#22c55e" if wr_local >= 50 else "#f59e0b"};font-weight:700;">{wr_local:.0f}% WR</td>'
                f'<td style="padding:8px 12px;text-align:center;color:{TEXT_SECONDARY};">{kda_local:.1f} KDA</td>'
                f'<td style="padding:8px 12px;text-align:center;color:{TEXT_SUBTLE};">{cd["games"]} part.</td>'
                f"</tr>"
            )

        if is_wide:
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:12px 0 8px 0;'>Juegas <b>{unique} campeones distintos</b>. "
                f"Para subir de ELO, enfócate en <b>2-3 como máximo</b>. "
                f"La especialización multiplica tu impacto porque automatizas mecánicas y liberas mente para el macro.</p>"
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:4px 0 0 0;'>Tus 3 mejores por WR están arriba. "
                f"Reduce el resto a práctica en normal/flex.</p>"
            )
        else:
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:12px 0 0 0;'>Buena señal: mantienes un pool enfocado de <b>{unique} campeones</b>. "
                f"La especialización consistente es la base del crecimiento real.</p>"
            )

        top3_wr = m["top3_wr"]
        rest_wr = m.get("rest_wr", 0)
        if is_wide and top3_wr > 0 and rest_wr > 0 and top3_wr > rest_wr:
            advice += (
                f"<p style='font-size:12px;color:{TEXT_SUBTLE};margin:8px 0 0 0;'>"
                f"WR con tu top 3: <b style='color:{GREEN_SUCCESS};'>{top3_wr:.0f}%</b> "
                f"vs WR con el resto: <b style='color:{YELLOW_WARNING};'>{rest_wr:.0f}%</b>. "
                f"Los números confirman: céntrate en lo que ya dominas.</p>"
            )

        html = (
            f"<div style=\"font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;\">"
            f'<table style="width:100%;border-collapse:collapse;margin:8px 0 0 0;">{rows}</table>'
            f"{advice}"
            f"</div>"
        )
        return {"titulo": titulo, "icono": icono, "color": color, "html": html, "prioridad": prio}


# ─── Sección 2: Fase de Líneas ───────────────────────────────────────────────

class ReglaFaseLineas(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        avg_cs = m["avg_cs"]
        if avg_cs < 4.5:
            verdict = "🔴 Tu farm está por debajo de lo necesario para ser consistente."
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 4px 0;'>Con <b>{avg_cs:.1f} CS/min</b>, pierdes ~{(7.0 - avg_cs) * 10:.0f} oro por minuto "
                f"respecto al estándar de 7 CS/min. Una diferencia de 1500+ oro a los 15 min.</p>"
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:4px 0 0 0;'><b>Ejercicio:</b> 10 min diarios en Practice Tool, solo last-hitting, sin items. "
                f"Luego 5 min farmeando bajo torre. Repítelo 5 días. El farm es la habilidad más rentable del juego.</p>"
            )
            color = RED_DANGER
            prio = 0
        elif avg_cs < 6.5:
            verdict = "🟡 Tu farmeo es decente pero tiene margen de mejora."
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 4px 0;'><b>{avg_cs:.1f} CS/min</b> está bien. "
                f"Para dar el salto, trabaja el farm bajo presión (trades + last-hits simultáneos).</p>"
            )
            color = YELLOW_WARNING
            prio = 2
        else:
            verdict = "🟢 Tu farmeo es excelente. Buen trabajo."
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 4px 0;'><b>{avg_cs:.1f} CS/min</b> es nivel alto. "
                f"Ahora el foco pasa a negarle farm al rival mientras mantienes el tuyo (trading + wave management).</p>"
            )
            color = GREEN_SUCCESS
            prio = 2

        html = (
            f"<div style=\"font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;\">"
            f"<p style='font-size:14px;color:{TEXT_WHITE};margin:0 0 4px 0;'>{verdict}</p>"
            f"{advice}"
        )

        if m.get("primer_sangre_pct", 0) >= 30:
            html += (
                f"<p style='font-size:12px;color:{GREEN_SUCCESS};margin:12px 0 0 0;'>⚔️ Consigues First Blood en el <b>{m['primer_sangre_pct']:.0f}%</b> de tus partidas. "
                f"Excelente agresividad temprana. Usala con cabeza: si estás en matchup favorable, forzá el nivel 2 primero.</p>"
            )

        html += "</div>"
        return {"titulo": "RENDIMIENTO EN FASE DE LÍNEAS", "icono": "🌾", "color": color, "html": html, "prioridad": prio}


# ─── Sección 3: Supervivencia ────────────────────────────────────────────────

class ReglaSupervivencia(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        avg_d = m["avg_d"]
        kda = m["kda"]
        if avg_d > 7:
            verdict = "🔴 Mueres demasiado. Cada muerte te saca del mapa ~40s y regala 300+ oro."
            gold_gifted = int(avg_d * 300)
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 4px 0;'><b>{avg_d:.1f} muertes</b> por partida "
                f"equivalen a regalar ~{gold_gifted} de oro al equipo rival.</p>"
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:4px 0 0 0;'><b>Regla de 2:</b> antes de cada engage, "
                f"preguntate: ¿veo a 5 enemigos en el mapa? ¿Mi equipo me sigue? Si alguna es NO, no entres. "
                f"Revisa tus deaths en el replay: ¿cuántas eran evitables?</p>"
            )
            color = RED_DANGER
            prio = 0
        elif avg_d > 5:
            verdict = "🟡 Tus muertes son mejorables. Cada muerte que ahorres es oro y presencia."
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'><b>{avg_d:.1f} muertes/partida</b>. "
                f"Bajá a 4 o menos y vas a notar la diferencia en tu WR. "
                f"Tips: wardear antes de pushear, mirar el minimapa entre cada CS, y no perseguir kills sin visión.</p>"
            )
            color = YELLOW_WARNING
            prio = 1
        else:
            verdict = "🟢 Buen control de muertes. Sigue así."
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'><b>{avg_d:.1f} muertes/partida</b> "
                f"con <b>{kda:.1f} KDA</b>. Mueres poco y generas impacto. "
                f"Para el siguiente nivel: revisa si tus muertes ocurren en momentos clave (objetivos, late game).</p>"
            )
            color = GREEN_SUCCESS
            prio = 3

        html = (
            f"<div style=\"font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;\">"
            f"<p style='font-size:14px;color:{TEXT_WHITE};margin:0 0 4px 0;'>{verdict}</p>"
            f"{advice}"
            f"</div>"
        )
        return {"titulo": "TOMA DE DECISIONES Y SUPERVIVENCIA", "icono": "🛡️", "color": color, "html": html, "prioridad": prio}


# ─── Sección 4: Visión ───────────────────────────────────────────────────────

class ReglaVision(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        avg_vision = m["avg_vision_game"]
        if avg_vision <= 0:
            return None
        if avg_vision < 15:
            verdict = "🔴 Tu visión es muy baja. Estás jugando a ciegas."
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'><b>{avg_vision:.0f} de visión/partida</b>. "
                f"Compra un Control Ward en CADA base. Ponlo en un arbusto de río o en la entrada de tu jungla. "
                f"Una ward bien puesta vale más que 300 de oro.</p>"
            )
            color = RED_DANGER
            prio = 2
        elif avg_vision < 28:
            verdict = "🟡 Visión aceptable. Con pequeños ajustes, mejorás mucho."
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'><b>{avg_vision:.0f} de visión/partida</b>. "
                f"Buen hábito. Wardea con intención: ¿qué objetivo viene? Wardea 45s antes. "
                f"Si eres support, mira si tu equipo tiene visión en el próximo objetivo.</p>"
            )
            color = YELLOW_WARNING
            prio = 3
        else:
            verdict = "🟢 Excelente control de visión. Eres los ojos de tu equipo."
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'><b>{avg_vision:.0f} de visión/partida</b>. "
                f"Nivel alto. Ahora el desafío es negar visión rival: compra Oracle Lens si no lo haces, "
                f"y despeja visión enemiga antes de objetivos.</p>"
            )
            color = GREEN_SUCCESS
            prio = 3

        html = (
            f"<div style=\"font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;\">"
            f"<p style='font-size:14px;color:{TEXT_WHITE};margin:0 0 4px 0;'>{verdict}</p>"
            f"{advice}"
            f"</div>"
        )
        return {"titulo": "CONTROL DE VISIÓN", "icono": "👁️", "color": color, "html": html, "prioridad": prio}


# ─── Sección 5: Fatiga ───────────────────────────────────────────────────────

class ReglaFatiga(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        fatiga = m.get("datos_fatiga")
        if not fatiga:
            return None
        sesiones = fatiga.get("sesiones", [])
        if not sesiones:
            return None
        ultima = sesiones[-1]
        total_sesion = ultima.get("total", 0)
        if total_sesion < 4:
            return None
        wr_sesion = ultima.get("wr", 0)
        partidas_hoy = fatiga.get("partidas_hoy", 0)

        if wr_sesion < 40:
            titulo = "GESTIÓN DE SESIONES — Fatiga Detectada"
            icono = "😫"
            color = RED_DANGER
            prio = 1
            verdict = f"🔴 Tu última sesión ({total_sesion} partidas) tuvo solo <b>{wr_sesion:.0f}% WR</b>."
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 4px 0;'>Esto es señal de fatiga. "
                f"El rendimiento cognitivo cae significativamente después de 3-4 partidas seguidas. "
                f"La ciencia del juego muestra que jugar en bloques de 3 con pausas de 10 min duplica la calidad.</p>"
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:4px 0 0 0;'><b>Plan:</b> máximo 3 partidas, "
                f"luego pausa de 10 min (levántate, toma agua, estira). Si pierdes 2 seguidas, corta la sesión.</p>"
            )
        elif wr_sesion >= 60:
            titulo = "GESTIÓN DE SESIONES — Buen Momento"
            icono = "🔥"
            color = GREEN_SUCCESS
            prio = 3
            verdict = f"🟢 Tu última sesión tuvo <b>{wr_sesion:.0f}% WR</b> en {total_sesion} partidas."
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'>Estás en racha positiva. "
                f"Para mantenerla: no caigas en el «una más» cuando estás ganando. "
                f"Cerrá la sesión en un pico de concentración, no cuando empiece a bajar.</p>"
            )
        else:
            titulo = "GESTIÓN DE SESIONES — Estable"
            icono = "⚖️"
            color = YELLOW_WARNING
            prio = 3
            verdict = f"🟡 Tu última sesión tuvo <b>{wr_sesion:.0f}% WR</b> en {total_sesion} partidas."
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'>Estás estable. "
                f"Para inclinar la balanza, revisá si hay un patrón en tus derrotas "
                f"(¿primeras partidas? ¿últimas? ¿contra cierto tipo de campeón?).</p>"
            )

        if partidas_hoy:
            advice += (
                f"<p style='font-size:12px;color:{TEXT_SUBTLE};margin:12px 0 0 0;'>Hoy llevás <b>{partidas_hoy}</b> partidas.</p>"
            )

        html = (
            f"<div style=\"font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;\">"
            f"<p style='font-size:14px;color:{TEXT_WHITE};margin:0 0 4px 0;'>{verdict}</p>"
            f"{advice}"
            f"</div>"
        )
        return {"titulo": titulo, "icono": icono, "color": color, "html": html, "prioridad": prio}


# ─── Sección 5.5: Rachas ─────────────────────────────────────────────────────

class ReglaRacha(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        racha = m.get("racha_actual", 0)
        tipo = m.get("racha_tipo", "")
        if racha < 3:
            return None
        if tipo == "L":
            titulo = "RACHA Y RESILIENCIA — Mala Racha"
            icono = "📉"
            color = RED_DANGER
            prio = 1
            advice = (
                f"<p style='font-size:14px;color:{TEXT_WHITE};margin:0 0 8px 0;'>Llevás <b>{racha} derrotas seguidas</b>.</p>"
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 4px 0;'>Las rachas de pérdidas son normales: "
                f"incluso jugadores con 55% WR tienen rachas de 5+ derrotas una de cada 30 sesiones.</p>"
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:4px 0 0 0;'><b>Estrategia:</b> corta ya. "
                f"No intentes «recuperar» el ELO hoy. Mañana con la mente fresca, tus decisiones serán mejores. "
                f"Una partida en tilt = 2 partidas perdidas (la actual y la siguiente).</p>"
            )
        else:
            titulo = "RACHA Y RESILIENCIA — Buena Racha"
            icono = "📈"
            color = GREEN_SUCCESS
            prio = 4
            advice = (
                f"<p style='font-size:14px;color:{TEXT_WHITE};margin:0 0 8px 0;'>¡Llevás <b>{racha} victorias seguidas</b>!</p>"
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'>Disfrutalo. Es fruto de tu mejora. "
                f"Para mantenerlo: no cambies tu estilo ni champions ahora. "
                f"La consistencia es lo que construye la racha; la novedad la rompe.</p>"
            )

        html = (
            f"<div style=\"font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;\">"
            f"{advice}"
            f"</div>"
        )
        return {"titulo": titulo, "icono": icono, "color": color, "html": html, "prioridad": prio}


# ─── Sección 5.6: Bloques de 3 ───────────────────────────────────────────────

class ReglaBloques(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        html = (
            f"<div style=\"font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;\">"
            f"<p style='font-size:14px;color:{TEXT_WHITE};margin:0 0 8px 0;'><b>🎯 Jugar por Bloques de 3</b></p>"
            f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:4px 0 4px 0;'>El método más efectivo para escalar: "
            f"<b>3 partidas → revisión rápida → pausa</b>.</p>"
            f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:4px 0 4px 0;'>"
            f"<b>1.</b> Juega 3 partidas con foco total (sin música, sin stream, sin móvil).<br>"
            f"<b>2.</b> Al terminar el bloque, revisá 1 minuto: ¿qué hice bien? ¿qué repetí mal?<br>"
            f"<b>3.</b> Pausa de 10 min (levántate, muévete). Después decide si juegas otro bloque.</p>"
            f"<p style='font-size:12px;color:{TEXT_SUBTLE};margin:8px 0 0 0;'>Esto reduce el desgaste mental y mejora "
            f"la calidad de decisiones en cada partida.</p>"
            f"</div>"
        )
        return {"titulo": "JUGAR POR BLOQUES (3 PARTIDAS)", "icono": "📦", "color": INDIGO, "html": html, "prioridad": 4}


# ─── Sección 5.7: Práctica Deliberada ────────────────────────────────────────

class ReglaPracticaDeliberada(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        html = _generar_practica_deliberada(m["nombre"], m["nivel"], m["avg_cs"], m["avg_d"], m["avg_vision_game"])
        return {"titulo": "PRÁCTICA DELIBERADA", "icono": "🎯", "color": VIOLET, "html": html, "prioridad": 5}


# ─── Sección 5.8: Salud ──────────────────────────────────────────────────────

class ReglaSalud(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        html = _generar_tips_salud()
        return {"titulo": "SALUD MENTAL Y FISIOLOGÍA", "icono": "💚", "color": GOLD, "html": html, "prioridad": 6}


# ─── Sección 6: Daño ─────────────────────────────────────────────────────────

class ReglaDano(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        avg_dmg = m["avg_dmg_game"]
        if avg_dmg <= 0:
            return None
        if avg_dmg < 12000:
            verdict = "🔴 Tu daño por partida es bajo."
            color = RED_DANGER
            prio = 2
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'><b>{avg_dmg:.0f} de daño/partida</b>. "
                f"Posicionate más agresivo en teamfights: priorizá golpear al objetivo más cercano en vez de buscar al carry. "
                f"Daño constante &gt; daño espectacular.</p>"
            )
        elif avg_dmg < 22000:
            verdict = "🟡 Tu daño por partida es aceptable."
            color = YELLOW_WARNING
            prio = 3
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'><b>{avg_dmg:.0f} de daño/partida</b>. "
                f"Para mejorar: en teamfights, identifica UNA ventana de daño y comprométete a usarla. "
                f"No esperes la jugada perfecta.</p>"
            )
        else:
            verdict = "🟢 Excelente output de daño."
            color = GREEN_SUCCESS
            prio = 3
            advice = (
                f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'><b>{avg_dmg:.0f} de daño/partida</b>. "
                f"Muy bien. Ahora el foco: ¿ese daño se traduce en kills para tu carry? "
                f"Revisa tu daño a objetivos (torres, dragones) — eso gana partidas.</p>"
            )

        dmg_eff = m.get("dmg_eff", 1)
        if dmg_eff < 0.7:
            advice += (
                f"<p style='font-size:12px;color:{TEXT_SUBTLE};margin:8px 0 0 0;'>⚠️ Recibís más daño del que infligís "
                f"(ratio {dmg_eff:.1f}). Cuidá tu posicionamiento en teamfights.</p>"
            )

        html = (
            f"<div style=\"font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;\">"
            f"<p style='font-size:14px;color:{TEXT_WHITE};margin:0 0 4px 0;'>{verdict}</p>"
            f"{advice}"
            f"</div>"
        )
        return {"titulo": "DAÑO Y EFICIENCIA", "icono": "⚔️", "color": color, "html": html, "prioridad": prio}


# ─── Sección 7: Oro ──────────────────────────────────────────────────────────

class ReglaOro(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        avg_gold = m["avg_gold_game"]
        if avg_gold <= 0:
            return None
        if avg_gold < 9000:
            verdict = "🔴 Tu generación de oro es baja."
            advice = f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'><b>{avg_gold:.0f} oro/partida</b>. Foco en farm + plates + asistir a kills."
            color = RED_DANGER
        elif avg_gold < 12000:
            verdict = "🟡 Oro aceptable, con margen de mejora."
            advice = f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'><b>{avg_gold:.0f} oro/partida</b>. Buen ritmo. Optimiza backs y oleadas."
            color = YELLOW_WARNING
        else:
            verdict = "🟢 Excelente economía."
            advice = f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'><b>{avg_gold:.0f} oro/partida</b>. Asegúrate de gastarlo bien: items correctos según la partida."
            color = GREEN_SUCCESS

        html = (
            f"<div style=\"font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;\">"
            f"<p style='font-size:14px;color:{TEXT_WHITE};margin:0 0 4px 0;'>{verdict}</p>"
            f"{advice}"
            f"</div>"
        )
        return {"titulo": "ORO Y ECONOMÍA", "icono": "💰", "color": color, "html": html, "prioridad": 4}


# ─── Sección 8: Objetivos ────────────────────────────────────────────────────

class ReglaObjetivos(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        turrets = m["avg_turrets"]
        dragons = m["avg_dragons"]
        barons = m["avg_barons"]
        warning = ""
        if dragons < 0.5 and barons < 0.2:
            warning = (
                f"<p style='font-size:12px;color:{YELLOW_WARNING};margin:8px 0 0 0;'>⚠️ Tu participación en dragones y barones es baja. "
                f"Rota hacia objetivos 30s antes de que aparezcan. Wardea el río.</p>"
            )
        html = (
            f"<div style=\"font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;\">"
            f"<p style='font-size:14px;color:{TEXT_WHITE};margin:0 0 8px 0;'>🏰 <b>Participación en Objetivos</b></p>"
            f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:4px 0;'>Torres: <b>{turrets:.1f}</b> · Dragones: <b>{dragons:.1f}</b> · Barones: <b>{barons:.1f}</b></p>"
            f"{warning}"
            f"</div>"
        )
        return {"titulo": "CONTROL DE OBJETIVOS", "icono": "🏰", "color": INDIGO, "html": html, "prioridad": 4}


# ─── Sección 9: CC ───────────────────────────────────────────────────────────

class ReglaCC(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        avg_cc = m["avg_cc"]
        if avg_cc <= 0:
            return None
        if avg_cc > 30:
            verdict = "🟢 Excelente uso de CC. Mantienes al rival fuera de juego."
        elif avg_cc > 10:
            verdict = "🟡 Buen CC. Mejorable: apuntá a interrumpir canales clave (Katarina R, Miss Fortune R)."
        else:
            verdict = "🔵 CC bajo. Si tu campeón tiene CC, priorizá usarlo para peel, no solo para engage."
        html = (
            f"<div style=\"font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;\">"
            f"<p style='font-size:14px;color:{TEXT_WHITE};margin:0 0 4px 0;'>{verdict}</p>"
            f"</div>"
        )
        return {"titulo": "CONTROL DE MASAS (CC)", "icono": "⛓️", "color": GOLD, "html": html, "prioridad": 5}


# ─── Sección 10: Pinks ───────────────────────────────────────────────────────

class ReglaPinks(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        avg_pink = m["avg_pink"]
        if avg_pink < 0.5:
            verdict = "🔴 No estás comprando Control Wards. Son el item más infravalorado del juego."
        elif avg_pink < 2:
            verdict = "🟡 Compras pocos Pinks. Uno por base como mínimo."
        else:
            verdict = "🟢 Buen uso de Control Wards."
        html = (
            f"<div style=\"font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;\">"
            f"<p style='font-size:14px;color:{TEXT_WHITE};margin:0 0 4px 0;'>{verdict}</p>"
            f"</div>"
        )
        return {"titulo": "CONTROL WARDS (PINKS)", "icono": "🔮", "color": GOLD, "html": html, "prioridad": 5}


# ─── Sección 11: Maestría ────────────────────────────────────────────────────

class ReglaMaestria(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        maestrias = m.get("maestrias")
        if not maestrias:
            return None
        top3_ids = m.get("top3_ids", [])
        overlap = [cid for cid in top3_ids if cid in maestrias]
        if overlap:
            verdict = "🟢 Tus campeones más jugados tienen alta maestría. Bien alineado."
            color = GREEN_SUCCESS
        else:
            verdict = "🟡 Tus campeones con más maestría no son los que más juegas."
            color = YELLOW_WARNING
        html = (
            f"<div style=\"font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;\">"
            f"<p style='font-size:14px;color:{TEXT_WHITE};margin:0 0 4px 0;'>{verdict}</p>"
            f"</div>"
        )
        return {"titulo": "ARSENAL VS MAESTRÍA", "icono": "🏅", "color": color, "html": html, "prioridad": 3}


# ─── Sección 12: ELO ─────────────────────────────────────────────────────────

class ReglaProgresionELO(ReglaCoach):
    def evaluar(self, m: dict) -> dict | None:
        lp_history = m.get("lp_history")
        if not lp_history or len(lp_history) < 3:
            return None
        first = lp_history[0]
        last = lp_history[-1]
        lp_delta = last.get("lp_total", 0) - first.get("lp_total", 0)
        if lp_delta > 100:
            verdict = "📈 ¡Subiendo fuerte! +" + str(lp_delta) + " LP netos en el período."
        elif lp_delta > 0:
            verdict = "📈 Subiendo lento pero constante: +" + str(lp_delta) + " LP."
        elif lp_delta > -100:
            verdict = "📊 Estable / ligera bajada: " + str(lp_delta) + " LP."
        else:
            verdict = "📉 En caída: " + str(lp_delta) + " LP. Momento de pausar y revisar."

        tier_name = last.get("tier", "?").title()
        div = last.get("division", "?")
        lp_actual = last.get("lp", 0)

        html = (
            f"<div style=\"font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;\">"
            f"<p style='font-size:14px;color:{TEXT_WHITE};margin:0 0 4px 0;'>{verdict}</p>"
            f"<p style='font-size:12px;color:{TEXT_SECONDARY};margin:8px 0 0 0;'>"
            f"Actual: <b>{tier_name} {div} {lp_actual} LP</b></p>"
            f"</div>"
        )
        return {"titulo": "PROGRESIÓN DE ELO", "icono": "🏆", "color": INDIGO, "html": html, "prioridad": 4}


# ─── Registro de reglas ──────────────────────────────────────────────────────

REGLAS_COACH = [
    ReglaFilosofiaJuego(),
    ReglaAuditoriaChampion(),
    ReglaFaseLineas(),
    ReglaSupervivencia(),
    ReglaVision(),
    ReglaFatiga(),
    ReglaRacha(),
    ReglaBloques(),
    ReglaPracticaDeliberada(),
    ReglaSalud(),
    ReglaDano(),
    ReglaOro(),
    ReglaObjetivos(),
    ReglaCC(),
    ReglaPinks(),
    ReglaMaestria(),
    ReglaProgresionELO(),
]
