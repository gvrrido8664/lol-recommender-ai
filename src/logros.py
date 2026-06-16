LOGROS_DEFINICIONES = [
    {"id": "hot_streak", "nombre": "En Rachaaa", "emoji": "\U0001f525",
     "desc": "5 victorias seguidas"},
    {"id": "solido", "nombre": "Solido", "emoji": "\U0001f451",
     "desc": "KDA > 4 en 5 de las ultimas 10 partidas"},
    {"id": "pentakiller", "nombre": "Pentakiller", "emoji": "\u2694\ufe0f",
     "desc": "Consigue un pentakill"},
    {"id": "inmortal", "nombre": "Inmortal", "emoji": "\U0001f6e1\ufe0f",
     "desc": "0 muertes en una partida"},
    {"id": "farmer", "nombre": "Granjero", "emoji": "\U0001f33e",
     "desc": "10 CS por minuto en una partida (+20 min)"},
    {"id": "versatil", "nombre": "Versatil", "emoji": "\U0001f4da",
     "desc": "7 campeones distintos con 2 o mas partidas cada uno"},
    {"id": "otp", "nombre": "One Trick Pony", "emoji": "\U0001f984",
     "desc": "Mismo campeon en 10 de las ultimas 15 partidas"},
    {"id": "sin_fronteras", "nombre": "Sin Fronteras", "emoji": "\U0001f30d",
     "desc": "Jugar en los 5 roles"},
    {"id": "sanguinario", "nombre": "Sanguinario", "emoji": "\U0001f480",
     "desc": "15 o mas kills en una partida"},
    {"id": "rey_grieta", "nombre": "Rey de la Grieta", "emoji": "\U0001f3c6",
     "desc": "60%+ winrate en 15+ partidas"},
    {"id": "relampago", "nombre": "Relampago", "emoji": "\u26a1",
     "desc": "Victoria en menos de 20 minutos"},
    {"id": "precision", "nombre": "Precision", "emoji": "\U0001f3af",
     "desc": "10+ kills y 0 muertes en una partida"},
    {"id": "resiliente", "nombre": "Resiliente", "emoji": "\U0001f504",
     "desc": "Ganar justo despues de 3 derrotas seguidas"},
    {"id": "en_crecimiento", "nombre": "En Crecimiento", "emoji": "\U0001f331",
     "desc": "Mejorar tu KDA promedio: 10 recientes vs 10 anteriores"},
    {"id": "triple_oro", "nombre": "Triple Oro", "emoji": "\U0001f3c5",
     "desc": "Consigue un triple kill"},
]


def _extraer_stats(g):
    """Normaliza una partida del formato anidado de LCU a un dict plano."""
    part = g.get("participants", [{}])
    p0 = part[0] if part else {}
    stats = p0.get("stats", {})

    champion_id = str(p0.get("championId", "0"))
    champion_name = g.get("championName") or p0.get("championName") or champion_id

    return {
        "win": stats.get("win", g.get("win", False)),
        "kills": stats.get("kills", g.get("kills", 0)),
        "deaths": stats.get("deaths", g.get("deaths", 0)),
        "assists": stats.get("assists", g.get("assists", 0)),
        "pentaKills": stats.get("pentaKills", g.get("pentaKills", 0)),
        "tripleKills": stats.get("tripleKills", g.get("tripleKills", 0)),
        "totalMinionsKilled": stats.get("totalMinionsKilled", g.get("totalMinionsKilled", 0)),
        "neutralMinionsKilled": stats.get("neutralMinionsKilled", g.get("neutralMinionsKilled", 0)),
        "gameDuration": g.get("gameDuration", 0),
        "championName": champion_name,
        "role": p0.get("teamPosition", p0.get("role", g.get("role", g.get("lane", "")))),
        "lane": p0.get("teamPosition", p0.get("lane", g.get("lane", g.get("role", "")))),
    }


def evaluar_logros(games, daily_counts=None):
    logros = {lg["id"]: False for lg in LOGROS_DEFINICIONES}
    if not games:
        return logros

    flat_games = [_extraer_stats(g) for g in games]
    recent = list(reversed(flat_games))

    # 1. En Rachaaa: 5 wins in a row
    max_streak = 0
    cur_streak = 0
    for g in recent:
        if g.get("win"):
            cur_streak += 1
            max_streak = max(max_streak, cur_streak)
        else:
            cur_streak = 0
    logros["hot_streak"] = max_streak >= 5

    # 2. Sólido: KDA > 4 in 5 of last 10 games
    last_10 = recent[-10:]
    if len(last_10) >= 5:
        solid = 0
        for g in last_10:
            k = g.get("kills", 0) or 0
            d = max(1, g.get("deaths", 0) or 0)
            a = g.get("assists", 0) or 0
            if (k + a) / d > 4:
                solid += 1
        logros["solido"] = solid >= 5

    # 3. Pentakiller
    logros["pentakiller"] = any(g.get("pentaKills", 0) for g in recent)

    # 4. Inmortal: 0 deaths in a game
    logros["inmortal"] = any((g.get("deaths", 1) or 0) == 0 for g in recent)

    # 5. Granjero: 10 CS/min in a game lasting 20+ min
    for g in recent:
        dur = g.get("gameDuration", 0) or 0
        cs_val = (g.get("totalMinionsKilled", 0) or 0) + (g.get("neutralMinionsKilled", 0) or 0)
        if dur >= 1200 and dur > 0:
            cs_min = cs_val / (dur / 60)
            if cs_min >= 10:
                logros["farmer"] = True
                break

    # 6. Versátil: 7 champs with 2+ games each
    champ_counts = {}
    for g in recent:
        c = g.get("championName", "")
        if c:
            champ_counts[c] = champ_counts.get(c, 0) + 1
    versatiles = sum(1 for cnt in champ_counts.values() if cnt >= 2)
    logros["versatil"] = versatiles >= 7

    # 7. OTP: same champ in 10 of last 15
    last_15 = recent[-15:]
    if len(last_15) >= 10:
        otp_counts = {}
        for g in last_15:
            c = g.get("championName", "")
            if c:
                otp_counts[c] = otp_counts.get(c, 0) + 1
        logros["otp"] = any(v >= 10 for v in otp_counts.values())

    # 8. Sin Fronteras: all 5 roles
    roles = set()
    for g in recent:
        r = (g.get("role") or g.get("lane") or "").upper()
        if r in ("TOP", "JUNGLE", "JUNGLA", "MIDDLE", "MID", "BOTTOM", "BOT", "ADC", "UTILITY", "SUPPORT"):
            roles.add(r)
    role_groups = set()
    for r in roles:
        if r in ("TOP",): role_groups.add("TOP")
        elif r in ("JUNGLE", "JUNGLA"): role_groups.add("JUNGLE")
        elif r in ("MIDDLE", "MID"): role_groups.add("MIDDLE")
        elif r in ("BOTTOM", "BOT", "ADC"): role_groups.add("BOTTOM")
        elif r in ("UTILITY", "SUPPORT"): role_groups.add("UTILITY")
    logros["sin_fronteras"] = len(role_groups) >= 5

    # 9. Sanguinario: 15+ kills in a game
    logros["sanguinario"] = any((g.get("kills", 0) or 0) >= 15 for g in recent)

    # 10. Rey de la Grieta: 60%+ WR in 15+ games
    total_wr_games = len(recent)
    if total_wr_games >= 15:
        wins = sum(1 for g in recent if g.get("win"))
        logros["rey_grieta"] = (wins / total_wr_games) >= 0.6

    # 11. Relámpago: win in < 20 min
    logros["relampago"] = any(
        g.get("win") and (g.get("gameDuration", 9999) or 9999) < 1200
        for g in recent
    )

    # 12. Precisión: 10+ kills and 0 deaths
    logros["precision"] = any(
        (g.get("kills", 0) or 0) >= 10 and (g.get("deaths", 1) or 0) == 0
        for g in recent
    )

    # 13. Resiliente: win right after 3 consecutive losses (chronological: L,L,L,W)
    if len(flat_games) >= 4:
        for i in range(3, len(flat_games)):
            if (not flat_games[i - 3].get("win", True) and
                not flat_games[i - 2].get("win", True) and
                not flat_games[i - 1].get("win", True) and
                flat_games[i].get("win", False)):
                logros["resiliente"] = True
                break

    # 14. En Crecimiento: better KDA in last 10 vs previous 10
    if len(recent) >= 20:
        def _avg_kda(gs):
            total = 0
            count = 0
            for g in gs:
                k = g.get("kills", 0) or 0
                d = max(1, g.get("deaths", 0) or 0)
                a = g.get("assists", 0) or 0
                total += (k + a) / d
                count += 1
            return total / max(1, count)
        new_kda = _avg_kda(recent[:10])
        old_kda = _avg_kda(recent[10:20])
        logros["en_crecimiento"] = new_kda > old_kda

    # 15. Triple Oro: triple kill
    logros["triple_oro"] = any(g.get("tripleKills", 0) for g in recent)

    return logros


def obtener_logros_conseguidos(logros_dict):
    conseguidos = []
    for lg in LOGROS_DEFINICIONES:
        lid = lg["id"]
        if logros_dict.get(lid):
            conseguidos.append(lg)
    return conseguidos


def obtener_logros_faltantes(logros_dict):
    faltantes = []
    for lg in LOGROS_DEFINICIONES:
        lid = lg["id"]
        if not logros_dict.get(lid):
            faltantes.append(lg)
    return faltantes


# ═══════════════════════════════════════════════════════════════
# INSIGHTS ESTILO POROFESSOR — cards profesionales con stats reales
# ═══════════════════════════════════════════════════════════════

_EMOJIS = {
    "main_champ": "🎯", "kda": "📊", "cs": "🌾", "wr_trend": "📈",
    "kp": "🤝", "vision": "👁️", "fb": "⚡", "roles": "📚",
    "deaths": "🛡️", "tilt": "🧘", "racha": "🔥", "otp": "🦄",
}

_TIPOS_COLOR = {
    "positivo": ("#2ecc71", "#1a3a2a"),
    "neutral": ("#f1c40f", "#3a2f1a"),
    "warning": ("#e74c3c", "#3a1a1a"),
}


def generar_insights_jugador(games):
    """Genera insights estilo Porofessor a partir de las partidas del jugador.
    Devuelve lista de dicts con 'id', 'icono', 'titulo', 'mensaje', 'tipo', 'color_borde', 'color_fondo'.
    """
    if not games:
        return []
    flat = [_extraer_stats(g) for g in games]
    recent = list(reversed(flat))  # mas reciente primero
    insights = []

    if not any(g.get("championName") for g in flat):
        return insights

    # ── Main champion ──
    champ_stats = {}
    for g in flat:
        c = g.get("championName") or "SinNombre"
        if c not in champ_stats:
            champ_stats[c] = {"picks": 0, "wins": 0}
        champ_stats[c]["picks"] += 1
        if g.get("win"):
            champ_stats[c]["wins"] += 1
    main = max(champ_stats.items(), key=lambda x: x[1]["picks"])
    main_name, main_data = main
    main_wr = round(main_data["wins"] / main_data["picks"] * 100, 1) if main_data["picks"] > 0 else 0
    if main_data["picks"] >= 3:
        insights.append({
            "id": "main_champ", "icono": _EMOJIS["main_champ"],
            "titulo": f"Main {main_name}",
            "mensaje": f"{main_data['picks']} partidas — {main_wr}% WR",
            "tipo": "positivo" if main_wr >= 50 else "neutral", "color_borde": _TIPOS_COLOR["positivo" if main_wr >= 50 else "neutral"][0],
            "color_fondo": _TIPOS_COLOR["positivo" if main_wr >= 50 else "neutral"][1],
        })
    # Second main if player has two champs
    if len(champ_stats) >= 2:
        second = sorted(champ_stats.items(), key=lambda x: x[1]["picks"], reverse=True)[1]
        s_name, s_data = second
        s_wr = round(s_data["wins"] / s_data["picks"] * 100, 1) if s_data["picks"] > 0 else 0
        if s_data["picks"] >= 3:
            insights.append({
                "id": "main_champ", "icono": _EMOJIS["main_champ"],
                "titulo": f"Alternativa {s_name}",
                "mensaje": f"{s_data['picks']} partidas — {s_wr}% WR",
                "tipo": "positivo" if s_wr >= 50 else "neutral", "color_borde": _TIPOS_COLOR["positivo" if s_wr >= 50 else "neutral"][0],
                "color_fondo": _TIPOS_COLOR["positivo" if s_wr >= 50 else "neutral"][1],
            })

    # ── KDA ──
    kdas = []
    for g in flat:
        k = g.get("kills", 0) or 0
        d = max(1, g.get("deaths", 0) or 0)
        a = g.get("assists", 0) or 0
        kdas.append((k + a) / d)
    avg_kda = round(sum(kdas) / len(kdas), 1)
    tipo_kda = "positivo" if avg_kda >= 4 else ("neutral" if avg_kda >= 2.5 else "warning")
    label_kda = "Muy alto" if avg_kda >= 5 else ("Alto" if avg_kda >= 4 else ("Normal" if avg_kda >= 2.5 else "Bajo"))
    insights.append({
        "id": "kda", "icono": _EMOJIS["kda"],
        "titulo": f"KDA {label_kda}",
        "mensaje": f"KDA promedio de {avg_kda} en {len(flat)} partidas",
        "tipo": tipo_kda, "color_borde": _TIPOS_COLOR[tipo_kda][0],
        "color_fondo": _TIPOS_COLOR[tipo_kda][1],
    })

    # ── CS ──
    cs_vals = []
    for g in flat:
        dur = g.get("gameDuration", 0) or 0
        cs = (g.get("totalMinionsKilled", 0) or 0) + (g.get("neutralMinionsKilled", 0) or 0)
        if dur >= 600:
            cs_vals.append(cs / (dur / 60))
    if cs_vals:
        avg_cs = round(sum(cs_vals) / len(cs_vals), 1)
        tipo_cs = "positivo" if avg_cs >= 7 else ("neutral" if avg_cs >= 5 else "warning")
        label_cs = "Excelente" if avg_cs >= 8 else ("Bueno" if avg_cs >= 7 else ("Normal" if avg_cs >= 5 else "Bajo"))
        insights.append({
            "id": "cs", "icono": _EMOJIS["cs"],
            "titulo": f"Farm {label_cs}",
            "mensaje": f"{avg_cs} CS/min en tus últimas {len(cs_vals)} partidas",
            "tipo": tipo_cs, "color_borde": _TIPOS_COLOR[tipo_cs][0],
            "color_fondo": _TIPOS_COLOR[tipo_cs][1],
        })

    # ── Winrate trend (últimas 10 vs total) ──
    if len(flat) >= 15:
        last_10 = flat[:10]
        rest = flat[10:]
        wr_recent = round(sum(1 for g in last_10 if g.get("win")) / len(last_10) * 100, 1)
        wr_old = round(sum(1 for g in rest if g.get("win")) / len(rest) * 100, 1) if rest else 0
        diff = round(wr_recent - wr_old, 1)
        tipo_wr = "positivo" if diff > 3 else ("warning" if diff < -3 else "neutral")
        if diff > 0:
            msg = f"Subiendo: {wr_old}% → {wr_recent}% (+{diff}%)"
        elif diff < 0:
            msg = f"Bajando: {wr_old}% → {wr_recent}% ({diff}%)"
        else:
            msg = f"Estable en {wr_recent}%"
        insights.append({
            "id": "wr_trend", "icono": _EMOJIS["wr_trend"],
            "titulo": "Tendencia de WR",
            "mensaje": msg,
            "tipo": tipo_wr, "color_borde": _TIPOS_COLOR[tipo_wr][0],
            "color_fondo": _TIPOS_COLOR[tipo_wr][1],
        })

    # ── Muertes ──
    avg_deaths = round(sum((g.get("deaths", 0) or 0) for g in flat) / len(flat), 1)
    tipo_death = "positivo" if avg_deaths <= 4 else ("neutral" if avg_deaths <= 6 else "warning")
    label_death = "Muy pocas" if avg_deaths <= 3 else ("Controladas" if avg_deaths <= 4 else ("Normal" if avg_deaths <= 6 else "Altas"))
    insights.append({
        "id": "deaths", "icono": _EMOJIS["deaths"],
        "titulo": f"Muertes {label_death}",
        "mensaje": f"{avg_deaths} muertes/partida en promedio",
        "tipo": tipo_death, "color_borde": _TIPOS_COLOR[tipo_death][0],
        "color_fondo": _TIPOS_COLOR[tipo_death][1],
    })

    # ── Racha ──
    wins_streak = 0
    for g in recent:
        if g.get("win"):
            wins_streak += 1
        else:
            break
    if wins_streak >= 5:
        insights.append({
            "id": "racha", "icono": _EMOJIS["racha"],
            "titulo": "¡En racha!",
            "mensaje": f"{wins_streak} victorias consecutivas",
            "tipo": "positivo", "color_borde": _TIPOS_COLOR["positivo"][0],
            "color_fondo": _TIPOS_COLOR["positivo"][1],
        })
    else:
        loss_streak = 0
        for g in recent:
            if not g.get("win"):
                loss_streak += 1
            else:
                break
        if loss_streak >= 3:
            insights.append({
                "id": "racha", "icono": _EMOJIS["tilt"],
                "titulo": "Mala racha",
                "mensaje": f"{loss_streak} derrotas seguidas — considera un descanso",
                "tipo": "warning", "color_borde": _TIPOS_COLOR["warning"][0],
                "color_fondo": _TIPOS_COLOR["warning"][1],
            })

    # ── Flexibilidad de roles ──
    roles_set = set()
    for g in flat:
        r = (g.get("role") or g.get("lane") or "").upper()
        if r in ("TOP", "JUNGLE", "JUNGLA", "MIDDLE", "MID", "BOTTOM", "BOT", "ADC", "UTILITY", "SUPPORT"):
            if r in ("JUNGLA",): r = "JUNGLE"
            if r in ("MID",): r = "MIDDLE"
            if r in ("BOT", "ADC"): r = "BOTTOM"
            if r in ("SUPPORT",): r = "UTILITY"
            roles_set.add(r)
    if len(roles_set) >= 4:
        insights.append({
            "id": "roles", "icono": _EMOJIS["roles"],
            "titulo": "Jugador flexible",
            "mensaje": f"Juegas en {len(roles_set)} roles distintos",
            "tipo": "neutral", "color_borde": _TIPOS_COLOR["neutral"][0],
            "color_fondo": _TIPOS_COLOR["neutral"][1],
        })

    # ── OTP check ──
    if len(flat) >= 10:
        top_picks = max(champ_stats.values(), key=lambda x: x["picks"])
        if top_picks["picks"] >= len(flat) * 0.7:
            insights.append({
                "id": "otp", "icono": _EMOJIS["otp"],
                "titulo": "One Trick Pony",
                "mensaje": f"Juegas solo {len(champ_stats)} campeones distintos",
                "tipo": "neutral", "color_borde": _TIPOS_COLOR["neutral"][0],
                "color_fondo": _TIPOS_COLOR["neutral"][1],
            })

    return insights


def formatear_insight(insight: dict) -> str:
    """Version texto plano para debug / tooltip."""
    return f"{insight['icono']} {insight['titulo']}: {insight['mensaje']}"
