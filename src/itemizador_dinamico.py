"""
Itemizador Dinámico — botas adaptativas e ítems situacionales.

Flujo:
  recomendar_bota(campeon, enemigos) → (bota_id, razon, es_estatica)
  recomendar_items_situacionales(campeon, carril, enemigos) → list[dict]
      Cada dict: {id, razon, categoria, prioridad}
      categorias: "anti_heal" | "anti_shield" | "anti_cc" | "anti_ap" |
                  "anti_ad" | "anti_tank" | "penetracion" | "supervivencia"
      prioridad:  1 = CRÍTICO, 2 = RECOMENDADO, 3 = OPCIONAL
"""
from .tags_champions import (
    obtener_tag, obtener_dano, es_tanque, es_tirador,
    es_asesino, es_mago, es_botas_estaticas, obtener_bota_estatica,
    obtener_nivel_cc, es_soporte, es_luchador,
)

# ─── BOTAS ──────────────────────────────────────────────────────
BOTA_STEELCAPS  = "3047"
BOTA_MERCURY    = "3111"
BOTA_SORCERER   = "3020"
BOTA_BERSERKER  = "3006"
BOTA_IONIAN     = "3158"
BOTA_SWIFTNESS  = "3009"
BOTA_MOBIS      = "3117"

# ─── CATÁLOGO DE ÍTEMS SITUACIONALES ────────────────────────────

# Heridas Graves (GW)
GW_AP       = "3165"   # Morellonomicon
GW_AD_MID   = "6609"   # Espada Chempunk
GW_AD_CHEAP = "3123"   # Llamado del Verdugo
GW_TANK     = "3075"   # Coraza de Espinas
GW_MORTAL   = "3033"   # Recordatorio Mortal (GW + armor pen, ADC)

# Anti-hechizo (escudo mágico activo — útil para AD vs burst AP)
EDGE_OF_NIGHT = "3814"  # Filo de la Noche — escudo de hechizo + letal para asesinos AD

# Anti-CC
QSS         = "3140"   # Quitarrunas
MIKAELS     = "3222"   # Bendición de Mikael (soporte)

# Defensivos AP
FORCE_NATURE  = "4401"  # Fuerza de la Naturaleza
SPIRIT_VISAGE = "3065"  # Rostro Espiritual
BANSHE        = "3102"  # Velo de Banshee
ZHONYA        = "3157"  # Reloj de Arena de Zhonya
MAW           = "3156"  # Quijada de Malmortius

# Defensivos AD
RANDUIN      = "3143"   # Runas de Randuin
FROZEN_HEART = "3110"   # Corazón Helado
THORNMAIL    = "3075"   # Coraza de Espinas
GARGOYLE     = "3193"   # Gárgola Pétrea

# Anti-tanque / penetración
LORD_DOMINIK = "3036"   # Recuerdos de Lord Dominik
BORK         = "3153"   # Hoja del Rey Arruinado

# Penetración mágica
VOID_STAFF   = "3135"   # Bastón del Vacío

# Sustain / anti-poke
WARMOGS      = "3083"   # Armadura de Warmog

# ─── SETS DE CAMPEONES ──────────────────────────────────────────

_HEALING_CHAMPS = {
    "Aatrox", "DrMundo", "Ekko", "Fiora", "Gangplank",
    "Irelia", "Kayn", "Nunu", "Olaf", "Riven",
    "Samira", "Senna", "Soraka", "Sylas", "TahmKench",
    "Vladimir", "Warwick", "Yuumi", "Swain", "Mordekaiser",
    "Nilah", "Gragas", "Nami", "Seraphine",
}

_SHIELD_CHAMPS = {
    "Janna", "Lulu", "Karma", "Orianna", "Seraphine",
    "Sona", "Thresh", "Braum", "Renata", "Taric",
    "Ivern", "Rakan", "Lux",
}

_SUPPRESS_CHAMPS = {
    "Malzahar", "Warwick", "Mordekaiser", "Skarner", "Urgot",
    "Camille",  # E deja atrapado en zona
}

# Burst AP que eliminan en 1 combo (Zhonya's/Banshee's muy útiles)
_BURST_AP_CHAMPS = {
    "Syndra", "Lissandra", "Annie", "Veigar", "Leblanc",
    "Fizz", "Elise", "Kennen", "Cassiopeia", "Katarina",
    "Akali", "Ekko", "Diana", "Qiyana",
}

# Asesinos AD que matan mages en 1 combo (Zhonya's clave)
_AD_ASSASSINS = {
    "Zed", "Talon", "Qiyana", "Naafiri", "Nocturne",
    "Kha'Zix", "KhaZix", "Rengar", "Pyke", "Shaco",
}

# Campeones de poke a distancia sostenido
_POKE_CHAMPS = {
    "Lux", "Ezreal", "Jayce", "Nidalee", "Ziggs",
    "Xerath", "Karma", "Varus", "Hwei", "Caitlyn",
    "Gangplank", "Corki",
}

# Slows significativos
_SLOW_CHAMPS = {
    "Ashe", "Bard", "Brand", "Cassiopeia", "Chogath", "DrMundo",
    "Gangplank", "Garen", "Gnar", "Hecarim", "Heimerdinger",
    "Janna", "Karma", "Kayle", "Kindred", "Lillia", "Lulu", "Lux",
    "Malphite", "MissFortune", "Morgana", "Nami", "Nasus",
    "Nautilus", "Nunu", "Olaf", "Orianna", "Rammus", "Rumble",
    "Sejuani", "Seraphine", "Singed", "Sion", "Sivir", "Skarner",
    "Sona", "Soraka", "Swain", "Taliyah", "Teemo", "Thresh",
    "Trundle", "Tryndamere", "Twitch", "Udyr", "Varus",
    "Velkoz", "Viktor", "Volibear", "Warwick", "Zilean", "Zyra",
}

# Críticos (Randuin's)
_CRIT_CHAMPS = {
    "Aphelios", "Ashe", "Caitlyn", "Draven", "Gangplank",
    "Jhin", "Jinx", "KaiSa", "Kaisa", "Lucian", "MissFortune",
    "Nilah", "Samira", "Senna", "Sivir", "Smolder",
    "Tristana", "Twitch", "Vayne", "Xayah", "Yasuo",
    "Yone", "Zeri", "Akshan", "Kindred", "Kalista",
}


# ─── BOTAS ──────────────────────────────────────────────────────

def recomendar_bota(campeon: str, enemigos: list, botas_data: dict = None) -> tuple:
    """Devuelve (bota_id, razon, es_estatica)."""
    if not enemigos:
        fallback = max(botas_data, key=botas_data.get) if botas_data else None
        return (fallback, "Sin datos de draft", False)

    if es_botas_estaticas(campeon):
        bota = obtener_bota_estatica(campeon)
        if bota:
            tag = obtener_tag(campeon)
            clase = tag.get("champion_class", "")
            sub = tag.get("sub_class", "")
            if clase == "Mage" or sub == "Artillery":
                razon = "Botas de Hechicero — penetración mágica core de magos"
            elif clase == "Marksman":
                razon = "Grebas de Berserker — velocidad de ataque core de tiradores"
            elif sub == "Enchanter":
                razon = "Botas de Lucidez — más hechizos y summoners, core de encantadores"
            else:
                razon = f"Botas fijas de {campeon} — parte esencial de su build"
            return (bota, razon, True)

    return _calcular_bota_adaptativa(campeon, enemigos, botas_data)


def _calcular_bota_adaptativa(campeon: str, enemigos: list, botas_data: dict = None) -> tuple:
    ad_score = ap_score = total_cc = aa_score = slow_count = 0.0

    for e in enemigos:
        dano = obtener_dano(e)
        clase = obtener_tag(e).get("champion_class", "")
        if dano == "AD":
            ad_score += 1
        elif dano == "AP":
            ap_score += 1
        else:
            ad_score += 0.5; ap_score += 0.5
        total_cc += obtener_nivel_cc(e)
        if clase in ("Marksman", "Fighter", "Assassin"):
            aa_score += 1
        if e in _SLOW_CHAMPS:
            slow_count += 1

    n = len(enemigos)
    ad_dom = ad_score >= n * 0.6
    ap_dom = ap_score >= n * 0.6
    cc_heavy = total_cc >= 10
    aa_heavy = aa_score >= 4

    tag_yo = obtener_tag(campeon)
    if tag_yo.get("support_subrole") == "roam":
        return (BOTA_MOBIS, "Botas de Movilidad — roaming support, llega antes a objetivos", False)

    if es_asesino(campeon) and sum(1 for e in enemigos if e in _SHIELD_CHAMPS) >= 2:
        return (BOTA_SWIFTNESS, "Botas de Rapidez — kite y seguimiento vs escudos enemigos", False)

    if aa_heavy or (ad_dom and sum(1 for e in enemigos if e in _CRIT_CHAMPS) >= 2):
        return (BOTA_STEELCAPS,
                f"Placas de Acero — {int(aa_score)}/{n} enemigos dependen de autoataques. Reduce daño físico el 12%.", False)
    if cc_heavy:
        return (BOTA_MERCURY,
                f"Botas de Mercurio — {int(total_cc)} pts de CC. Tenacidad reduce su duración el 30%.", False)
    if ad_dom and ad_score >= 3:
        return (BOTA_STEELCAPS,
                f"Placas de Acero — {int(ad_score)}/{n} campeones hacen daño físico.", False)
    if ap_dom and total_cc >= 6:
        return (BOTA_MERCURY,
                f"Botas de Mercurio — {int(ap_score)} amenazas AP con CC. RM + tenacidad.", False)
    if total_cc >= 7:
        return (BOTA_MERCURY,
                f"Botas de Mercurio — {int(total_cc)} pts de CC. Tenacidad invaluable.", False)
    if ad_score >= 3 and aa_score >= 3:
        return (BOTA_STEELCAPS,
                f"Placas de Acero — {int(ad_score)} AD y {int(aa_score)} AA. Mejor valor defensivo.", False)
    if slow_count >= 3:
        return (BOTA_SWIFTNESS,
                f"Botas de Rapidez — {int(slow_count)} enemigos con slows. Reduce ralentizaciones el 25%.", False)
    if ap_dom:
        return (BOTA_MERCURY,
                f"Botas de Mercurio — comp AP dominante. RM + tenacidad.", False)
    if botas_data:
        mejor = max(botas_data, key=botas_data.get)
        return (mejor, "Composición balanceada — bota con mejor rendimiento estadístico.", False)
    return (BOTA_MERCURY, "Composición balanceada — Mercury's ofrece la mejor utilidad general.", False)


# ─── ÍTEMS SITUACIONALES ────────────────────────────────────────

def recomendar_items_situacionales(campeon: str, carril: str, enemigos: list) -> list:
    """Devuelve lista de dicts {id, razon, categoria, prioridad} ordenada por prioridad."""
    if not enemigos:
        return []

    tag_yo      = obtener_tag(campeon)
    soy_tanque  = es_tanque(campeon)
    soy_mago    = es_mago(campeon)
    soy_tirador = es_tirador(campeon)
    soy_asesino = es_asesino(campeon)
    soy_support = es_soporte(campeon)
    soy_luch    = es_luchador(campeon)
    mobility    = tag_yo.get("mobility", 2)

    sugs = []

    def _add(item_id: str, razon: str, categoria: str, prioridad: int = 2):
        sugs.append({"id": item_id, "razon": razon,
                     "categoria": categoria, "prioridad": prioridad})

    # ── Conteos clave ─────────────────────────────────────────
    healers   = sum(1 for e in enemigos if _norm(e) in {_norm(h) for h in _HEALING_CHAMPS})
    shielders = sum(1 for e in enemigos if e in _SHIELD_CHAMPS)
    supresses = sum(1 for e in enemigos if e in _SUPPRESS_CHAMPS)
    burst_ap  = sum(1 for e in enemigos if e in _BURST_AP_CHAMPS)
    ad_assas  = sum(1 for e in enemigos if e in _AD_ASSASSINS)
    poke_cnt  = sum(1 for e in enemigos if e in _POKE_CHAMPS)
    tanques   = sum(1 for e in enemigos if es_tanque(e))
    ap_count  = sum(1 for e in enemigos if obtener_dano(e) in ("AP", "HYBRID"))
    ad_count  = sum(1 for e in enemigos if obtener_dano(e) == "AD")
    crit_cnt  = sum(1 for e in enemigos if e in _CRIT_CHAMPS)
    cc_total  = sum(obtener_nivel_cc(e) for e in enemigos)

    n = len(enemigos)

    # ── 1. HERIDAS GRAVES ─────────────────────────────────────
    if healers >= 1:
        prio = 1 if healers >= 2 else 2
        nombres_h = ", ".join(e for e in enemigos if _norm(e) in {_norm(h) for h in _HEALING_CHAMPS})[:50]
        if soy_tanque:
            _add(THORNMAIL,
                 f"{healers} sanadores ({nombres_h}) — Coraza de Espinas aplica Heridas Graves al atacar",
                 "anti_heal", prio)
        elif soy_mago:
            _add(GW_AP,
                 f"{healers} sanadores ({nombres_h}) — Morellonomicon aplica HG al hacer daño mágico",
                 "anti_heal", prio)
        elif soy_tirador:
            # ADC vs healing + armor → Mortal Reminder (HG + penetración)
            if tanques >= 2 or ad_count >= 3:
                _add(GW_MORTAL,
                     f"{healers} sanadores + {tanques} tanques — Recordatorio Mortal: HG y 30% penetración de armadura",
                     "anti_heal", prio)
            else:
                _add(GW_AD_CHEAP,
                     f"{healers} sanadores ({nombres_h}) — Llamado del Verdugo: HG barato, compra temprana eficiente",
                     "anti_heal", prio)
        elif soy_support:
            _add(MIKAELS,
                 f"{healers} sanadores enemigos — Bendición de Mikael: cura aliado y limpia CC",
                 "anti_heal", prio)
        else:
            _add(GW_AD_MID,
                 f"{healers} sanadores ({nombres_h}) — Espada Chempunk: HG + daño y letalidad para bruisers",
                 "anti_heal", prio)

    # ── 2. FILO DE LA NOCHE (escudo mágico) ──────────────────
    # Para asesinos y luchadores AD vs burst AP / CC puntual
    if soy_asesino and ap_count >= 2:
        _add(EDGE_OF_NIGHT,
             f"{ap_count} amenazas AP — Filo de la Noche: escudo mágico activo que bloquea el primer hechizo enemigo",
             "anti_ap", 2)

    # ── 3. ANTI-CC / SUPPRESS ────────────────────────────────
    if supresses >= 1:
        nombres_sup = ", ".join(e for e in enemigos if e in _SUPPRESS_CHAMPS)
        if soy_tirador or soy_asesino or soy_mago:
            _add(QSS,
                 f"Suppress de {nombres_sup} — Quitarrunas cancela cualquier CC incancelable al instante",
                 "anti_cc", 1)
        elif soy_support:
            _add(MIKAELS,
                 f"Suppress de {nombres_sup} — Bendición de Mikael limpia el CC de tu aliado",
                 "anti_cc", 1)
    elif cc_total >= 12 and not soy_tanque:
        _add(QSS,
             f"{cc_total} pts de CC enemigo — Quitarrunas limpia cualquier debuff y permite escapar",
             "anti_cc", 2)

    # ── 4. ANTI-BURST AP / PROTECCIÓN MAGO ───────────────────
    if burst_ap >= 1 and not soy_mago and not soy_tanque:
        nombres_b = ", ".join(e for e in enemigos if e in _BURST_AP_CHAMPS)[:50]
        if soy_tirador or soy_support or soy_asesino:
            _add(BANSHE,
                 f"Burst AP de {nombres_b} — Velo de Banshee bloquea el primer hechizo enemigo automáticamente",
                 "anti_ap", 1)
        elif soy_luch:
            _add(MAW,
                 f"Burst AP de {nombres_b} — Quijada de Malmortius genera escudo mágico al estar a baja vida",
                 "anti_ap", 1)

    # Zhonya's para magos vs asesinos AD
    if soy_mago and ad_assas >= 1:
        nombres_ad = ", ".join(e for e in enemigos if e in _AD_ASSASSINS)[:50]
        _add(ZHONYA,
             f"Asesino AD {nombres_ad} — Reloj de Arena de Zhonya: invulnerabilidad activa para sobrevivir el burst",
             "anti_ad", 1)

    # Void Staff para magos vs tanques/MR
    if soy_mago and (tanques >= 2 or ap_count >= 1):
        _add(VOID_STAFF,
             f"{tanques} tanques + {ad_count} AD que acumularán RM — Bastón del Vacío ignora el 40% de resistencia mágica",
             "penetracion", 2 if tanques >= 2 else 3)

    # ── 5. ANTI-AP COMP ───────────────────────────────────────
    # Solo para champs que realmente llevan defensivos: tanques, luchadores, supports
    if ap_count >= 3 and (soy_tanque or soy_luch or soy_support):
        if soy_tanque or soy_support:
            _add(SPIRIT_VISAGE,
                 f"{ap_count}/{n} amenazas AP — Rostro Espiritual: RM + amplifica tu curación propia",
                 "anti_ap", 2)
        elif mobility >= 3:
            _add(FORCE_NATURE,
                 f"{ap_count}/{n} amenazas AP — Fuerza de la Naturaleza: RM que crece cuanto más te muevas",
                 "anti_ap", 2)
        else:
            _add(SPIRIT_VISAGE,
                 f"{ap_count}/{n} amenazas AP — Rostro Espiritual: mejor ratio RM + curación por oro",
                 "anti_ap", 2)

    # Maw para luchadores vs AP
    if soy_luch and ap_count >= 2 and not any(s["id"] == MAW for s in sugs):
        _add(MAW,
             f"{ap_count} amenazas AP — Quijada de Malmortius: escudo mágico + AD y letalidad para fighters",
             "anti_ap", 3)

    # ── 6. ANTI-AD / CRIT ────────────────────────────────────
    if crit_cnt >= 2 and (soy_tanque or soy_luch or soy_support):
        nombres_c = ", ".join(e for e in enemigos if e in _CRIT_CHAMPS)[:50]
        _add(RANDUIN,
             f"{crit_cnt} campeones con críticos ({nombres_c}) — Runas de Randuin reduce el daño crítico el 20%",
             "anti_ad", 2)

    if ad_count >= 4 and soy_tanque:
        _add(FROZEN_HEART,
             f"{ad_count} campeones AD — Corazón Helado reduce la velocidad de ataque de enemigos cercanos",
             "anti_ad", 2)

    if soy_tanque and (crit_cnt >= 2 or ad_count >= 3):
        _add(GARGOYLE,
             f"Comp AD pesada — Gárgola Pétrea: activa para duplicar blindaje en teamfight",
             "supervivencia", 3)

    # ── 7. ANTI-TANQUE / PENETRACIÓN AD ──────────────────────
    if tanques >= 2 and not soy_tanque and not soy_mago:
        prio_tank = 1 if tanques >= 3 else 2
        if soy_tirador:
            if not any(s["id"] == GW_MORTAL for s in sugs):
                _add(LORD_DOMINIK,
                     f"{tanques} tanques — Lord Dominik: 35% penetración de armadura, más efectivo cuanta más vida tengan",
                     "anti_tank", prio_tank)
        elif soy_luch or soy_asesino:
            _add(BORK,
                 f"{tanques} tanques — Hoja del Rey Arruinado: daño % de vida máxima, ralentización activa",
                 "anti_tank", prio_tank)

    # ── 8. ANTI-POKE / SUSTAIN ───────────────────────────────
    if poke_cnt >= 2 and (soy_tanque or soy_luch):
        nombres_p = ", ".join(e for e in enemigos if e in _POKE_CHAMPS)[:50]
        _add(WARMOGS,
             f"{poke_cnt} poke ({nombres_p}) — Armadura de Warmog: regenera toda tu vida fuera de combate (5000+ HP req.)",
             "supervivencia", 3)

    # Ordenar por prioridad (1 primero) luego por categoría
    sugs.sort(key=lambda x: x["prioridad"])
    return sugs


def _norm(nombre: str) -> str:
    return (nombre or "").lower().replace(" ", "").replace("'", "").replace(".", "")


