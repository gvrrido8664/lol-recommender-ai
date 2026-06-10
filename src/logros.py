LOGROS_DEFINICIONES = [
    {"id": "first_blood", "nombre": "Primera Sangre", "emoji": "🩸",
     "desc": "Analiza tu primera partida", "check": lambda gs: len(gs) >= 1},
    {"id": "penta", "nombre": "5 Partidas", "emoji": "✋",
     "desc": "Completa 5 partidas", "check": lambda gs: len(gs) >= 5},
    {"id": "decena", "nombre": "Doble Digito", "emoji": "🔟",
     "desc": "Completa 10 partidas", "check": lambda gs: len(gs) >= 10},
    {"id": "veintena", "nombre": "Veinteava", "emoji": "🎯",
     "desc": "Completa 20 partidas", "check": lambda gs: len(gs) >= 20},
    {"id": "centenario", "nombre": "Centenario", "emoji": "💯",
     "desc": "100 partidas analizadas", "check": lambda gs: len(gs) >= 100},
    {"id": "hot_streak", "nombre": "En Rachaaa", "emoji": "🔥",
     "desc": "5 victorias seguidas"},
    {"id": "godlike", "nombre": "Intocable", "emoji": "👑",
     "desc": "KDA > 5 en 3 partidas seguidas"},
    {"id": "maraton", "nombre": "Maratoniano", "emoji": "⏱️",
     "desc": "10 partidas en un solo dia"},
    {"id": "bibliotecario", "nombre": "Bibliotecario", "emoji": "📚",
     "desc": "Juega 20 campeones distintos"},
    {"id": "otp", "nombre": "One Trick Pony", "emoji": "🦄",
     "desc": "Juega el mismo campeon 15 veces"},
    {"id": "roamer", "nombre": "Trota Mundos", "emoji": "🌍",
     "desc": "Juega en 3 roles distintos"},
    {"id": "pentakiller", "nombre": "Pentakiller", "emoji": "⚔️",
     "desc": "Consigue un pentakill"},
    {"id": "inmortal", "nombre": "Inmortal", "emoji": "🛡️",
     "desc": "0 muertes en una partida"},
    {"id": "farmer", "nombre": "Granjero", "emoji": "🌾",
     "desc": "10 CS/min en una partida"},
    {"id": "early_riser", "nombre": "Madrugador", "emoji": "🌅",
     "desc": "First Blood en los primeros 5 minutos"},
]


def evaluar_logros(games, daily_counts=None):
    logros = {}
    for lg in LOGROS_DEFINICIONES:
        lid = lg["id"]
        if "check" in lg:
            logros[lid] = lg["check"](games)
    if len(games) >= 5:
        wins = [1 if g.get("win") else 0 for g in games[:20]]
        streak = 0; max_streak = 0
        for w in wins:
            if w: streak += 1
            else: streak = 0
            max_streak = max(max_streak, streak)
        logros["hot_streak"] = max_streak >= 5
    if len(games) >= 3:
        kda_streak = 0
        max_kda_streak = 0
        for g in games[:20]:
            k = g.get("kills", 0) or 0
            d = max(1, g.get("deaths", 0) or 0)
            a = g.get("assists", 0) or 0
            if (k + a) / d > 5:
                kda_streak += 1
            else:
                kda_streak = 0
            max_kda_streak = max(max_kda_streak, kda_streak)
        logros["godlike"] = max_kda_streak >= 3
    champs = set()
    roles = set()
    otp_counts = {}
    for g in games:
        c = g.get("championName", "")
        if c: 
            champs.add(c)
            otp_counts[c] = otp_counts.get(c, 0) + 1
        r = (g.get("role") or g.get("lane") or "").upper()
        if r:
            roles.add(r)
    logros["bibliotecario"] = len(champs) >= 20
    logros["otp"] = any(v >= 15 for v in otp_counts.values())
    logros["roamer"] = len(roles) >= 3
    if daily_counts:
        logros["maraton"] = max(daily_counts.values()) >= 10 if daily_counts else False
    for g in games[:50]:
        if g.get("pentaKills", 0):
            logros["pentakiller"] = True
        if g.get("deaths", 1) == 0:
            logros["inmortal"] = True
        if g.get("neutralMinionsKilled", 0) >= 100:
            logros["farmer"] = True
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
