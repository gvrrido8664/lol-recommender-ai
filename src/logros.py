from .riot_api import cargar_mapeo_ids

_ID_TO_CHAMP = None


def _resolver_champ(cid):
    global _ID_TO_CHAMP
    if _ID_TO_CHAMP is None:
        _ID_TO_CHAMP = cargar_mapeo_ids()
    name = _ID_TO_CHAMP.get(str(cid), None)
    if name == "MonkeyKing":
        return "Wukong"
    return name or f"Champ{cid}"


LOGROS_DEFINICIONES = [
    {"id": "hot_streak", "nombre": "En Rachaaa", "emoji": "\U0001f525", "desc": "5 victorias seguidas"},
    {"id": "solido", "nombre": "Solido", "emoji": "\U0001f451", "desc": "KDA > 4 en 5 de las ultimas 10 partidas"},
    {"id": "pentakiller", "nombre": "Pentakiller", "emoji": "\u2694\ufe0f", "desc": "Consigue un pentakill"},
    {"id": "inmortal", "nombre": "Inmortal", "emoji": "\U0001f6e1\ufe0f", "desc": "0 muertes en una partida"},
    {"id": "farmer", "nombre": "Granjero", "emoji": "\U0001f33e", "desc": "10 CS por minuto en una partida (+20 min)"},
    {
        "id": "versatil",
        "nombre": "Versatil",
        "emoji": "\U0001f4da",
        "desc": "7 campeones distintos con 2 o mas partidas cada uno",
    },
    {
        "id": "otp",
        "nombre": "One Trick Pony",
        "emoji": "\U0001f984",
        "desc": "Mismo campeon en 10 de las ultimas 15 partidas",
    },
    {"id": "sin_fronteras", "nombre": "Sin Fronteras", "emoji": "\U0001f30d", "desc": "Jugar en los 5 roles"},
    {"id": "sanguinario", "nombre": "Sanguinario", "emoji": "\U0001f480", "desc": "15 o mas kills en una partida"},
    {"id": "rey_grieta", "nombre": "Rey de la Grieta", "emoji": "\U0001f3c6", "desc": "60%+ winrate en 15+ partidas"},
    {"id": "relampago", "nombre": "Relampago", "emoji": "\u26a1", "desc": "Victoria en menos de 20 minutos"},
    {"id": "precision", "nombre": "Precision", "emoji": "\U0001f3af", "desc": "10+ kills y 0 muertes en una partida"},
    {
        "id": "resiliente",
        "nombre": "Resiliente",
        "emoji": "\U0001f504",
        "desc": "Ganar justo despues de 3 derrotas seguidas",
    },
    {
        "id": "en_crecimiento",
        "nombre": "En Crecimiento",
        "emoji": "\U0001f331",
        "desc": "Mejorar tu KDA promedio: 10 recientes vs 10 anteriores",
    },
    {"id": "triple_oro", "nombre": "Triple Oro", "emoji": "\U0001f3c5", "desc": "Consigue un triple kill"},
]


def _extraer_stats(g):
    """Normaliza una partida del formato anidado de LCU a un dict plano."""
    part = g.get("participants", [{}])
    p0 = part[0] if part else {}
    stats = p0.get("stats", {})

    champion_id = str(p0.get("championId", "0"))
    champion_name = g.get("championName") or p0.get("championName") or _resolver_champ(champion_id)

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
        "gameCreation": g.get("gameCreation", 0),
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
        if r in ("TOP",):
            role_groups.add("TOP")
        elif r in ("JUNGLE", "JUNGLA"):
            role_groups.add("JUNGLE")
        elif r in ("MIDDLE", "MID"):
            role_groups.add("MIDDLE")
        elif r in ("BOTTOM", "BOT", "ADC"):
            role_groups.add("BOTTOM")
        elif r in ("UTILITY", "SUPPORT"):
            role_groups.add("UTILITY")
    logros["sin_fronteras"] = len(role_groups) >= 5

    # 9. Sanguinario: 15+ kills in a game
    logros["sanguinario"] = any((g.get("kills", 0) or 0) >= 15 for g in recent)

    # 10. Rey de la Grieta: 60%+ WR in 15+ games
    total_wr_games = len(recent)
    if total_wr_games >= 15:
        wins = sum(1 for g in recent if g.get("win"))
        logros["rey_grieta"] = (wins / total_wr_games) >= 0.6

    # 11. Relámpago: win in < 20 min
    logros["relampago"] = any(g.get("win") and (g.get("gameDuration", 9999) or 9999) < 1200 for g in recent)

    # 12. Precisión: 10+ kills and 0 deaths
    logros["precision"] = any((g.get("kills", 0) or 0) >= 10 and (g.get("deaths", 1) or 0) == 0 for g in recent)

    # 13. Resiliente: win right after 3 consecutive losses (chronological: L,L,L,W)
    if len(flat_games) >= 4:
        for i in range(3, len(flat_games)):
            if (
                not flat_games[i - 3].get("win", True)
                and not flat_games[i - 2].get("win", True)
                and not flat_games[i - 1].get("win", True)
                and flat_games[i].get("win", False)
            ):
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
# INSIGHTS ESTILO POROFESSOR — 20 patrones, top 5 por relevancia
# ═══════════════════════════════════════════════════════════════

_TIPOS_COLOR = {
    "positivo": ("#2ecc71", "#152a1a"),
    "neutral": ("#f1c40f", "#2a2510"),
    "warning": ("#e74c3c", "#2a1010"),
}


def _kda(g):
    k = g.get("kills", 0) or 0
    d = max(1, g.get("deaths", 0) or 0)
    a = g.get("assists", 0) or 0
    return (k + a) / d


def _cs_min(g):
    dur = g.get("gameDuration", 0) or 0
    if dur < 600:
        return None
    cs = (g.get("totalMinionsKilled", 0) or 0) + (g.get("neutralMinionsKilled", 0) or 0)
    return cs / (dur / 60)


def generar_insights_jugador(games):
    """Genera hasta 20 insights de patrones de juego, ordenados por relevancia.
    Retorna solo los top 5 con mas impacto sobre el jugador.
    Cada insight: { 'icono', 'texto', 'tipo', 'color', 'fondo', 'relevancia' }
    """
    if not games:
        return []
    flat = [_extraer_stats(g) for g in games]
    if len(flat) < 5:
        return []

    # Ordenar por fecha (mas reciente ultimo) y tomar ultimas 20
    flat.sort(key=lambda g: g.get("gameCreation", 0))
    flat = flat[-20:]
    wins = sum(1 for g in flat if g.get("win"))
    total = len(flat)
    wr_total = round(wins / total * 100, 1)
    recent = list(reversed(flat))

    # ── Stats por campeon ──
    champ_stats = {}
    for g in flat:
        c = g.get("championName") or "SinNombre"
        if c not in champ_stats:
            champ_stats[c] = {"p": 0, "w": 0}
        champ_stats[c]["p"] += 1
        if g.get("win"):
            champ_stats[c]["w"] += 1
    main_champ = max(champ_stats.items(), key=lambda x: x[1]["p"])
    mc_name, mc_data = main_champ
    mc_wr = round(mc_data["w"] / mc_data["p"] * 100, 1) if mc_data["p"] else 0

    # ── Stats por rol ──
    role_stats = {}
    for g in flat:
        r = (g.get("role") or g.get("lane") or "").upper()
        if r in ("JUNGLA",):
            r = "JUNGLE"
        if r in ("MID",):
            r = "MIDDLE"
        if r in ("BOT", "ADC"):
            r = "BOTTOM"
        if r in ("SUPPORT",):
            r = "UTILITY"
        if r not in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"):
            continue
        if r not in role_stats:
            role_stats[r] = {"p": 0, "w": 0}
        role_stats[r]["p"] += 1
        if g.get("win"):
            role_stats[r]["w"] += 1

    all_insights = []

    def _add(ins):
        """Añade insight con relevancia minima 1 para asegurar que se muestre."""
        if ins.get("relevancia", 0) < 1:
            ins["relevancia"] = 1
        all_insights.append(ins)

    # ────────────────────────────────────────────────
    # 1. POOL CONCENTRACION: main vs resto
    # ────────────────────────────────────────────────
    otros = {c: d for c, d in champ_stats.items() if c != mc_name}
    if otros and mc_data["p"] >= 3:
        otros_w = sum(d["w"] for d in otros.values())
        otros_p = sum(d["p"] for d in otros.values())
        otros_wr = round(otros_w / otros_p * 100, 1) if otros_p else 0
        gap = round(mc_wr - otros_wr, 1)
        if gap > 15 and otros_p >= 5:
            _add(
                {
                    "icono": "🎯",
                    "texto": f"Tu pool: {mc_name} {mc_wr}% vs resto {otros_wr}%",
                    "tipo": "warning",
                    "color": _TIPOS_COLOR["warning"][0],
                    "fondo": _TIPOS_COLOR["warning"][1],
                    "relevancia": abs(gap),
                }
            )
        elif gap < -10 and mc_data["p"] > otros_p / max(len(otros), 1):
            _add(
                {
                    "icono": "🎯",
                    "texto": f"Tu main {mc_name} rinde menos que tu pool",
                    "tipo": "warning",
                    "color": _TIPOS_COLOR["warning"][0],
                    "fondo": _TIPOS_COLOR["warning"][1],
                    "relevancia": abs(gap),
                }
            )
        elif len(champ_stats) <= 2 and mc_data["p"] >= total * 0.7:
            _add(
                {
                    "icono": "🎯",
                    "texto": f"{mc_name} OTP — {mc_wr}% en {mc_data['p']} partidas",
                    "tipo": "neutral",
                    "color": _TIPOS_COLOR["neutral"][0],
                    "fondo": _TIPOS_COLOR["neutral"][1],
                    "relevancia": 10,
                }
            )

    # ────────────────────────────────────────────────
    # 2. PROFUNDIDAD DE POOL
    # ────────────────────────────────────────────────
    buenos = sum(1 for d in champ_stats.values() if d["p"] >= 3 and d["w"] / d["p"] >= 0.5)
    if len(champ_stats) >= 4 and buenos >= 3:
        _add(
            {
                "icono": "📚",
                "texto": f"Pool sólido: {buenos} campeones con WR ≥50%",
                "tipo": "positivo",
                "color": _TIPOS_COLOR["positivo"][0],
                "fondo": _TIPOS_COLOR["positivo"][1],
                "relevancia": buenos * 3,
            }
        )
    elif len(champ_stats) >= 4 and buenos <= 1 and mc_data["p"] >= 5:
        _add(
            {
                "icono": "📚",
                "texto": f"Pool débil: solo {mc_name} tiene WR positivo",
                "tipo": "warning",
                "color": _TIPOS_COLOR["warning"][0],
                "fondo": _TIPOS_COLOR["warning"][1],
                "relevancia": 8,
            }
        )

    # ────────────────────────────────────────────────
    # 3. CS → WR
    # ────────────────────────────────────────────────
    cs_pares = [(_cs_min(g), g.get("win", False)) for g in flat if _cs_min(g) is not None]
    if len(cs_pares) >= 10:
        median_cs = sorted(cs for cs, _ in cs_pares)[len(cs_pares) // 2]
        hi = [(cs, w) for cs, w in cs_pares if cs >= median_cs]
        lo = [(cs, w) for cs, w in cs_pares if cs < median_cs]
        wr_hi = round(sum(1 for _, w in hi if w) / len(hi) * 100, 1) if hi else 0
        wr_lo = round(sum(1 for _, w in lo if w) / len(lo) * 100, 1) if lo else 0
        diff = round(wr_hi - wr_lo, 1)
        if diff > 15:
            _add(
                {
                    "icono": "🌾",
                    "texto": f"+{median_cs:.0f} CS/min → {wr_hi}% WR, bajo → {wr_lo}%",
                    "tipo": "positivo",
                    "color": _TIPOS_COLOR["positivo"][0],
                    "fondo": _TIPOS_COLOR["positivo"][1],
                    "relevancia": diff,
                }
            )

    # ────────────────────────────────────────────────
    # 4. TILT CASCADE: WR tras derrotas
    # ────────────────────────────────────────────────
    after_2loss = []  # partidas jugadas tras 2+ derrotas seguidas
    loss_run = 0
    for i, g in enumerate(recent):
        if i == 0:
            if not g.get("win"):
                loss_run = 1
            else:
                loss_run = 0
            continue
        if loss_run >= 2:
            after_2loss.append(g.get("win", False))
        if not g.get("win"):
            loss_run += 1
        else:
            loss_run = 0
    if len(after_2loss) >= 4:
        wr_tilt = round(sum(1 for w in after_2loss if w) / len(after_2loss) * 100, 1)
        diff_tilt = round(wr_total - wr_tilt, 1)
        if diff_tilt > 12:
            _add(
                {
                    "icono": "🧘",
                    "texto": f"Tras 2 derrotas tu WR baja a {wr_tilt}% (−{diff_tilt}%)",
                    "tipo": "warning",
                    "color": _TIPOS_COLOR["warning"][0],
                    "fondo": _TIPOS_COLOR["warning"][1],
                    "relevancia": diff_tilt,
                }
            )

    # ────────────────────────────────────────────────
    # 5. DEATH GAP: muertes en W vs L
    # ────────────────────────────────────────────────
    d_wins = [(g.get("deaths", 0) or 0) for g in flat if g.get("win")]
    d_loss = [(g.get("deaths", 0) or 0) for g in flat if not g.get("win")]
    if d_wins and d_loss:
        avg_dw = round(sum(d_wins) / len(d_wins), 1)
        avg_dl = round(sum(d_loss) / len(d_loss), 1)
        gap_death = round(avg_dl - avg_dw, 1)
        if gap_death >= 5:
            _add(
                {
                    "icono": "💀",
                    "texto": f"Mueres {avg_dl}x en L vs {avg_dw}x en W — juega seguro al perder",
                    "tipo": "warning",
                    "color": _TIPOS_COLOR["warning"][0],
                    "fondo": _TIPOS_COLOR["warning"][1],
                    "relevancia": gap_death * 2,
                }
            )
        elif avg_dw <= 3 and gap_death <= 2:
            _add(
                {
                    "icono": "🛡️",
                    "texto": f"Solo {avg_dw} muertes/partida en victorias",
                    "tipo": "positivo",
                    "color": _TIPOS_COLOR["positivo"][0],
                    "fondo": _TIPOS_COLOR["positivo"][1],
                    "relevancia": 6,
                }
            )

    # ────────────────────────────────────────────────
    # 6. COMEBACK
    # ────────────────────────────────────────────────
    behind = [g for g in flat if _kda(g) < 1.5]
    if behind and len(behind) >= 4:
        cb_w = sum(1 for g in behind if g.get("win"))
        cb_wr = round(cb_w / len(behind) * 100, 1)
        if cb_wr >= 40:
            _add(
                {
                    "icono": "🔄",
                    "texto": f"Buen comeback: {cb_wr}% WR partiendo de KDA <1.5",
                    "tipo": "positivo",
                    "color": _TIPOS_COLOR["positivo"][0],
                    "fondo": _TIPOS_COLOR["positivo"][1],
                    "relevancia": cb_wr,
                }
            )
        elif cb_wr <= 20:
            _add(
                {
                    "icono": "🔄",
                    "texto": f"Mal comeback: solo {cb_wr}% WR cuando vas mal",
                    "tipo": "warning",
                    "color": _TIPOS_COLOR["warning"][0],
                    "fondo": _TIPOS_COLOR["warning"][1],
                    "relevancia": 20 - cb_wr,
                }
            )

    # ────────────────────────────────────────────────
    # 7. CLOSER
    # ────────────────────────────────────────────────
    ahead = [g for g in flat if _kda(g) > 3.0]
    if ahead and len(ahead) >= 4:
        cl_w = sum(1 for g in ahead if g.get("win"))
        cl_wr = round(cl_w / len(ahead) * 100, 1)
        if cl_wr >= 85:
            _add(
                {
                    "icono": "🏆",
                    "texto": f"Buen closer: {cl_wr}% WR con KDA >3.0",
                    "tipo": "positivo",
                    "color": _TIPOS_COLOR["positivo"][0],
                    "fondo": _TIPOS_COLOR["positivo"][1],
                    "relevancia": cl_wr,
                }
            )
        elif cl_wr <= 65:
            _add(
                {
                    "icono": "🏆",
                    "texto": f"Mal closer: solo {cl_wr}% WR cuando vas bien",
                    "tipo": "warning",
                    "color": _TIPOS_COLOR["warning"][0],
                    "fondo": _TIPOS_COLOR["warning"][1],
                    "relevancia": 65 - cl_wr,
                }
            )

    # ────────────────────────────────────────────────
    # 8. MEJOR ROL
    # ────────────────────────────────────────────────
    if len(role_stats) >= 2:
        ranked = sorted(role_stats.items(), key=lambda x: x[1]["w"] / x[1]["p"] if x[1]["p"] else 0, reverse=True)
        best_r, best_d = ranked[0]
        worst_r, worst_d = ranked[-1]
        best_wr = round(best_d["w"] / best_d["p"] * 100, 1) if best_d["p"] else 0
        worst_wr = round(worst_d["w"] / worst_d["p"] * 100, 1) if worst_d["p"] else 0
        if best_wr - worst_wr > 15 and best_d["p"] >= 3:
            _add(
                {
                    "icono": "📍",
                    "texto": f"Mejor rol: {best_r} ({best_wr}%) vs {worst_r} ({worst_wr}%)",
                    "tipo": "neutral",
                    "color": _TIPOS_COLOR["neutral"][0],
                    "fondo": _TIPOS_COLOR["neutral"][1],
                    "relevancia": best_wr - worst_wr,
                }
            )

    # ────────────────────────────────────────────────
    # 9. RACHA ACTUAL
    # ────────────────────────────────────────────────
    streak = 0
    streak_w = recent[0].get("win", False) if recent else False
    for g in recent:
        if g.get("win") == streak_w:
            streak += 1
        else:
            break
    if streak >= 5 and streak_w:
        _add(
            {
                "icono": "🔥",
                "texto": f"¡En racha! {streak} victorias seguidas",
                "tipo": "positivo",
                "color": _TIPOS_COLOR["positivo"][0],
                "fondo": _TIPOS_COLOR["positivo"][1],
                "relevancia": streak * 3,
            }
        )
    elif streak >= 3 and not streak_w:
        _add(
            {
                "icono": "❄️",
                "texto": f"{streak} derrotas seguidas — toma un descanso",
                "tipo": "warning",
                "color": _TIPOS_COLOR["warning"][0],
                "fondo": _TIPOS_COLOR["warning"][1],
                "relevancia": streak * 3,
            }
        )

    # ────────────────────────────────────────────────
    # 10. INCONSISTENCIA KDA
    # ────────────────────────────────────────────────
    kdas = [_kda(g) for g in flat]
    avg_kda = sum(kdas) / len(kdas)
    var_kda = sum((k - avg_kda) ** 2 for k in kdas) / len(kdas)
    std_kda = round(var_kda**0.5, 1)
    if len(flat) >= 10:
        if std_kda > avg_kda * 0.9:
            _add(
                {
                    "icono": "🎢",
                    "texto": f"KDA muy irregular (σ={std_kda}) — días buenos y malos",
                    "tipo": "warning",
                    "color": _TIPOS_COLOR["warning"][0],
                    "fondo": _TIPOS_COLOR["warning"][1],
                    "relevancia": std_kda,
                }
            )
        elif std_kda < avg_kda * 0.4 and avg_kda >= 2.5:
            _add(
                {
                    "icono": "📏",
                    "texto": f"KDA muy consistente (σ={std_kda}) — rendimiento parejo",
                    "tipo": "positivo",
                    "color": _TIPOS_COLOR["positivo"][0],
                    "fondo": _TIPOS_COLOR["positivo"][1],
                    "relevancia": 7,
                }
            )

    # ────────────────────────────────────────────────
    # 11. WR TRAS VICTORIA (momentum)
    # ────────────────────────────────────────────────
    after_win = []
    for i, g in enumerate(recent):
        if i > 0 and recent[i - 1].get("win"):
            after_win.append(g.get("win", False))
    if len(after_win) >= 5:
        wr_aw = round(sum(1 for w in after_win if w) / len(after_win) * 100, 1)
        if wr_aw >= 65:
            _add(
                {
                    "icono": "⚡",
                    "texto": f"Momentum: {wr_aw}% WR tras una victoria",
                    "tipo": "positivo",
                    "color": _TIPOS_COLOR["positivo"][0],
                    "fondo": _TIPOS_COLOR["positivo"][1],
                    "relevancia": wr_aw - 50,
                }
            )

    # ────────────────────────────────────────────────
    # 12. PENTAKILL / TRIPLE
    # ────────────────────────────────────────────────
    penta = sum(1 for g in flat if g.get("pentaKills", 0))
    triple = sum(1 for g in flat if g.get("tripleKills", 0))
    if penta > 0:
        _add(
            {
                "icono": "⭐",
                "texto": f"¡{penta} pentakill{'s' if penta > 1 else ''}! — capacidad de carry",
                "tipo": "positivo",
                "color": _TIPOS_COLOR["positivo"][0],
                "fondo": _TIPOS_COLOR["positivo"][1],
                "relevancia": penta * 5 + 5,
            }
        )
    elif triple >= len(flat) * 0.3 and len(flat) >= 10:
        _add(
            {
                "icono": "⚔️",
                "texto": f"{triple} triple kills — buen teamfighter",
                "tipo": "positivo",
                "color": _TIPOS_COLOR["positivo"][0],
                "fondo": _TIPOS_COLOR["positivo"][1],
                "relevancia": 6,
            }
        )

    # ────────────────────────────────────────────────
    # 13. DEPENDENCIA: ¿carry o facilitador?
    # ────────────────────────────────────────────────
    high_kp = sum(1 for g in flat if _kda(g) >= 4.0)
    if len(flat) >= 10:
        pct_carry = round(high_kp / len(flat) * 100, 1)
        if pct_carry >= 50:
            _add(
                {
                    "icono": "👑",
                    "texto": f"Eres el carry en {pct_carry}% de tus partidas",
                    "tipo": "neutral",
                    "color": _TIPOS_COLOR["neutral"][0],
                    "fondo": _TIPOS_COLOR["neutral"][1],
                    "relevancia": 7,
                }
            )
        elif pct_carry <= 25 and wr_total >= 50:
            _add(
                {
                    "icono": "🤝",
                    "texto": f"Juegas para el equipo — carry solo en {pct_carry}% de games",
                    "tipo": "neutral",
                    "color": _TIPOS_COLOR["neutral"][0],
                    "fondo": _TIPOS_COLOR["neutral"][1],
                    "relevancia": 5,
                }
            )

    # ────────────────────────────────────────────────
    # 14. EARLY GAME vs LATE GAME
    # ────────────────────────────────────────────────
    short = [g for g in flat if (g.get("gameDuration", 0) or 0) < 25 * 60 and (g.get("gameDuration", 0) or 0) > 0]
    long_g = [g for g in flat if (g.get("gameDuration", 0) or 0) >= 35 * 60]
    if len(short) >= 4 and len(long_g) >= 4:
        wr_short = round(sum(1 for g in short if g.get("win")) / len(short) * 100, 1)
        wr_long = round(sum(1 for g in long_g if g.get("win")) / len(long_g) * 100, 1)
        if wr_short - wr_long > 20:
            _add(
                {
                    "icono": "⚡",
                    "texto": f"Early game: {wr_short}% vs late: {wr_long}% — cierra rápido",
                    "tipo": "positivo",
                    "color": _TIPOS_COLOR["positivo"][0],
                    "fondo": _TIPOS_COLOR["positivo"][1],
                    "relevancia": wr_short - wr_long,
                }
            )
        elif wr_long - wr_short > 20:
            _add(
                {
                    "icono": "🐢",
                    "texto": f"Late game: {wr_long}% vs early: {wr_short}% — juega seguro al inicio",
                    "tipo": "positivo",
                    "color": _TIPOS_COLOR["positivo"][0],
                    "fondo": _TIPOS_COLOR["positivo"][1],
                    "relevancia": wr_long - wr_short,
                }
            )

    # ────────────────────────────────────────────────
    # 15. CHAMPION MASTERY GAP
    # ────────────────────────────────────────────────
    if len(champ_stats) >= 2:
        sorted_cs = sorted(champ_stats.items(), key=lambda x: x[1]["p"], reverse=True)
        c1, c1d = sorted_cs[0]
        if len(sorted_cs) >= 2:
            c2, c2d = sorted_cs[1]
            if c1d["p"] >= 5 and c2d["p"] >= 3:
                wr1 = round(c1d["w"] / c1d["p"] * 100, 1)
                wr2 = round(c2d["w"] / c2d["p"] * 100, 1)
                if abs(wr1 - wr2) > 20:
                    _add(
                        {
                            "icono": "📉",
                            "texto": f"{c1} ({wr1}%) vs {c2} ({wr2}%) — gap de {abs(wr1 - wr2)}%",
                            "tipo": "warning",
                            "color": _TIPOS_COLOR["warning"][0],
                            "fondo": _TIPOS_COLOR["warning"][1],
                            "relevancia": abs(wr1 - wr2),
                        }
                    )

    # ────────────────────────────────────────────────
    # 16. FLEXIBILIDAD DE ROLES
    # ────────────────────────────────────────────────
    roles_set = set()
    for g in flat:
        r = (g.get("role") or g.get("lane") or "").upper()
        if r in ("JUNGLA",):
            r = "JUNGLE"
        if r in ("MID",):
            r = "MIDDLE"
        if r in ("BOT", "ADC"):
            r = "BOTTOM"
        if r in ("SUPPORT",):
            r = "UTILITY"
        if r in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"):
            roles_set.add(r)
    if len(roles_set) >= 4:
        _add(
            {
                "icono": "🎭",
                "texto": f"Juegas {len(roles_set)} roles — flex pick",
                "tipo": "neutral",
                "color": _TIPOS_COLOR["neutral"][0],
                "fondo": _TIPOS_COLOR["neutral"][1],
                "relevancia": len(roles_set) * 2,
            }
        )

    # ────────────────────────────────────────────────
    # 17. INMORTALIDAD
    # ────────────────────────────────────────────────
    immortal = sum(1 for g in flat if (g.get("deaths", 1) or 0) == 0)
    if immortal >= 2 and len(flat) >= 10:
        _add(
            {
                "icono": "😇",
                "texto": f"{immortal} partidas sin morir — buen posicionamiento",
                "tipo": "positivo",
                "color": _TIPOS_COLOR["positivo"][0],
                "fondo": _TIPOS_COLOR["positivo"][1],
                "relevancia": immortal * 2 + 5,
            }
        )

    # ────────────────────────────────────────────────
    # 18. SED DE SANGRE
    # ────────────────────────────────────────────────
    high_kill = sum(1 for g in flat if (g.get("kills", 0) or 0) >= 12)
    if high_kill >= len(flat) * 0.2 and len(flat) >= 10:
        _add(
            {
                "icono": "💢",
                "texto": f"{high_kill} partidas con 12+ kills — agresivo",
                "tipo": "neutral",
                "color": _TIPOS_COLOR["neutral"][0],
                "fondo": _TIPOS_COLOR["neutral"][1],
                "relevancia": 6,
            }
        )

    # ────────────────────────────────────────────────
    # 19. WR GENERAL BAJO / ALTO
    # ────────────────────────────────────────────────
    if total >= 15:
        if wr_total >= 65:
            _add(
                {
                    "icono": "🚀",
                    "texto": f"WR global: {wr_total}% — estás por encima del elo",
                    "tipo": "positivo",
                    "color": _TIPOS_COLOR["positivo"][0],
                    "fondo": _TIPOS_COLOR["positivo"][1],
                    "relevancia": wr_total,
                }
            )
        elif wr_total <= 40:
            _add(
                {
                    "icono": "📉",
                    "texto": f"WR global: {wr_total}% — necesitas ajustar algo",
                    "tipo": "warning",
                    "color": _TIPOS_COLOR["warning"][0],
                    "fondo": _TIPOS_COLOR["warning"][1],
                    "relevancia": 40 - wr_total + 10,
                }
            )

    # ────────────────────────────────────────────────
    # 20. FARM EN DERROTAS
    # ────────────────────────────────────────────────
    cs_loss = [_cs_min(g) for g in flat if not g.get("win") and _cs_min(g) is not None]
    cs_win = [_cs_min(g) for g in flat if g.get("win") and _cs_min(g) is not None]
    if cs_loss and cs_win and len(cs_loss) >= 3 and len(cs_win) >= 3:
        avg_cs_l = sum(cs_loss) / len(cs_loss)
        avg_cs_w = sum(cs_win) / len(cs_win)
        gap_cs = round(avg_cs_w - avg_cs_l, 1)
        if gap_cs > 2:
            _add(
                {
                    "icono": "🌾",
                    "texto": f"CS cae {gap_cs}/min al perder — no abandones el farm",
                    "tipo": "warning",
                    "color": _TIPOS_COLOR["warning"][0],
                    "fondo": _TIPOS_COLOR["warning"][1],
                    "relevancia": gap_cs * 3,
                }
            )

    # ── Ordenar por relevancia y tomar top 5 ──
    all_insights.sort(key=lambda x: x.get("relevancia", 0), reverse=True)
    top5 = all_insights[:5]
    # Solo devolver campos necesarios para el render
    return [{k: v for k, v in i.items() if k in ("icono", "texto", "tipo", "color", "fondo")} for i in top5]


def formatear_insight(insight: dict) -> str:
    """Version texto plano para debug / tooltip."""
    return f"{insight['icono']} {insight['texto']}"
