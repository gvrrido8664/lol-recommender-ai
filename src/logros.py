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


def evaluar_logros(games, daily_counts=None):
    logros = {lg["id"]: False for lg in LOGROS_DEFINICIONES}
    if not games:
        return logros

    recent = list(reversed(games))  # oldest first, newest last

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
        cs_val = g.get("totalMinionsKilled") or g.get("neutralMinionsKilled", 0) or 0
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
    if len(games) >= 4:
        for i in range(3, len(games)):
            if (not games[i - 3].get("win", True) and
                not games[i - 2].get("win", True) and
                not games[i - 1].get("win", True) and
                games[i].get("win", False)):
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
