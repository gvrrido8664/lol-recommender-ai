"""
Itemizador Dinámico (Pilar 5 — segunda parte).

Sistema de recomendación de botas que distingue entre:
- ESTÁTICAS: campeones con botas fijas (ej. ADC siempre Berserker, magos siempre Sorcerer)
- ADAPTATIVAS: campeones que cambian botas según el draft enemigo (ej. tanques, bruisers)

También incluye lógica de itemización situacional.
"""
from .tags_champions import (
    obtener_tag, obtener_dano, es_tanque, es_tirador,
    es_asesino, es_mago, es_botas_estaticas, obtener_bota_estatica,
    obtener_nivel_cc
)

# ─── CONSTANTES ─────────────────────────────────────────────────────
BOTA_STEELCAPS  = "3047"   # vs AD / autoataques
BOTA_MERCURY    = "3111"   # vs CC / AP
BOTA_SORCERER   = "3020"   # magic pen (AP fijo)
BOTA_BERSERKER  = "3006"   # attack speed (ADC fijo)
BOTA_IONIAN     = "3158"   # ability haste (soportes utilities)
BOTA_SWIFTNESS  = "3009"   # slow resist + MS (kiteadores)

BOTA_ORDER = [BOTA_STEELCAPS, BOTA_MERCURY, BOTA_SORCERER, BOTA_BERSERKER, BOTA_IONIAN, BOTA_SWIFTNESS]


def recomendar_bota(campeon: str, enemigos: list, botas_data: dict = None) -> tuple:
    """
    Recomienda la bota óptima para un campeón contra un equipo enemigo.

    Args:
        campeon: nombre del campeón
        enemigos: lista de nombres de campeones enemigos
        botas_data: dict {id_bota: frecuencia} de botas usadas estadísticamente (opcional)

    Returns:
        (bota_id, razon, es_estatica: bool)
    """
    if not enemigos:
        return (None, "Sin datos del equipo enemigo", False)

    # ── CASO 1: BOTAS ESTÁTICAS (core fijo del campeón) ──────────
    if es_botas_estaticas(campeon):
        bota = obtener_bota_estatica(campeon)
        if bota:
            tag = obtener_tag(campeon)
            clase = tag.get("champion_class", "")
            if clase == "Mage":
                razon = "Botas de Hechicero: penetración mágica fija, core absoluto de magos"
            elif clase == "Marksman":
                razon = "Grebas de Berserker: velocidad de ataque, core absoluto de tiradores"
            elif tag.get("sub_class") == "Enchanter":
                razon = "Botas de Lucidez: más hechizos y summoners, core de soportes de utilidad"
            else:
                razon = f"Botas fijas de {campeon}: parte esencial de su build"
            return (bota, razon, True)

    # ── CASO 2: BOTAS ADAPTATIVAS (calcular según amenazas) ───────
    return _calcular_bota_adaptativa(campeon, enemigos, botas_data)


def _calcular_bota_adaptativa(campeon: str, enemigos: list, botas_data: dict = None) -> tuple:
    """
    Analiza el draft enemigo y decide la bota óptima.
    Ponderación: AD autoattacks > CC total > Daño mixto.
    """
    # ── Analizar amenazas ──────────────────────────────────────────
    ad_champs = 0
    ap_champs = 0
    total_cc = 0
    tiradores = 0
    autoattackers = 0  # campeones que dependen fuertemente de AA

    for enemigo in enemigos:
        dano = obtener_dano(enemigo)
        tag = obtener_tag(enemigo)
        clase = tag.get("champion_class", "")

        if dano == "AD":
            ad_champs += 1
        elif dano == "AP":
            ap_champs += 1
        else:  # HYBRID
            ad_champs += 0.5
            ap_champs += 0.5

        total_cc += obtener_nivel_cc(enemigo)

        if es_tirador(enemigo):
            tiradores += 1
            autoattackers += 1

        # Fighters y assassins también auto-atacan mucho
        if clase in ("Fighter", "Assassin"):
            autoattackers += 1

    # Redondear
    ad_champs = int(ad_champs)
    ap_champs = int(ap_champs)

    # ── Reglas de decisión ─────────────────────────────────────────
    # Regla 0: Pocos enemigos → decidir por tipo de daño directamente
    num_enemigos = len(enemigos)
    if num_enemigos <= 3:
        if ap_champs > ad_champs:
            bota = BOTA_MERCURY
            razon = (f"Botas de Mercurio: {ap_champs} de {num_enemigos} enemigos hacen daño AP. "
                     "Resistencia mágica + tenacidad.")
            return (bota, razon, False)
        elif ad_champs > ap_champs:
            bota = BOTA_STEELCAPS
            razon = (f"Botas de Acero: {ad_champs} de {num_enemigos} enemigos hacen daño AD. "
                     "Reduce el daño de autoataques en 12%.")
            return (bota, razon, False)
        # Si está balanceado (1 AP, 1 AD), decidir por CC
        if total_cc >= 4:
            bota = BOTA_MERCURY
            razon = (f"Botas de Mercurio: {total_cc} puntos de CC entre {num_enemigos} enemigos.")
            return (bota, razon, False)

    # Prioridad 1: Demasiados autoattackers → Steelcaps
    if autoattackers >= 4:
        bota = BOTA_STEELCAPS
        razon = (f"Botas de Acero: {autoattackers} enemigos dependen de autoataques "
                 f"({tiradores} tiradores). Reduce su daño físico en 12%.")
        return (bota, razon, False)

    # Prioridad 2: CC masivo → Mercury
    if total_cc >= 12:
        bota = BOTA_MERCURY
        razon = (f"Botas de Mercurio: el equipo enemigo suma {total_cc} puntos de CC. "
                 "La tenacidad reduce su duración un 30%.")
        return (bota, razon, False)

    # Prioridad 3: AD dominante → Steelcaps
    if ad_champs >= 4:
        bota = BOTA_STEELCAPS
        razon = (f"Botas de Acero: {ad_champs} campeones hacen daño físico. "
                 f"Reduce el daño de autoataques en 12%.")
        return (bota, razon, False)

    # Prioridad 4: AP dominante + CC → Mercury
    if ap_champs >= 3 and total_cc >= 8:
        bota = BOTA_MERCURY
        razon = (f"Botas de Mercurio: {ap_champs} amenazas AP con CC. "
                 "Resistencia mágica + tenacidad en una sola bota.")
        return (bota, razon, False)

    # Prioridad 5: CC moderado → Mercury
    if total_cc >= 8:
        bota = BOTA_MERCURY
        razon = (f"Botas de Mercurio: {total_cc} puntos de CC enemigo. "
                 "La tenacidad es invaluable contra composiciones con control.")
        return (bota, razon, False)

    # Prioridad 6: AD moderado → Steelcaps
    if ad_champs >= 3 and autoattackers >= 3:
        bota = BOTA_STEELCAPS
        razon = (f"Botas de Acero: {ad_champs} AD + {autoattackers} dependientes de AA. "
                 "Mejor valor defensivo por oro.")
        return (bota, razon, False)

    # Prioridad 7: Muchos slows → Swiftness
    slow_champs = _contar_slows(enemigos)
    if slow_champs >= 3:
        bota = BOTA_SWIFTNESS
        razon = (f"Botas de Rapidez: {slow_champs} enemigos aplican ralentizaciones. "
                 "Reduce slows un 25% y da MS extra.")
        return (bota, razon, False)

    # Prioridad 8: Equipo balanceado → usar datos estadísticos
    if botas_data:
        mejor_estadistica = max(botas_data, key=botas_data.get)
        razon = ("Composición enemiga balanceada. "
                 f"Se recomienda la bota con mejor rendimiento estadístico.")
        return (mejor_estadistica, razon, False)

    # Fallback: Mercury's (la más versátil)
    return (BOTA_MERCURY, "Composición balanceada: Mercury's ofrece la mejor utilidad general.", False)


def _contar_slows(enemigos: list) -> int:
    """Campeones con slows significativos en su kit."""
    slowers = {
        "Ashe", "Bard", "Brand", "Cassiopeia", "Chogath",
        "DrMundo", "Gangplank", "Garen", "Gnar", "Heimerdinger",
        "Janna", "Karma", "Kayle", "Lillia", "Lulu", "Lux",
        "Malphite", "MissFortune", "Morgana", "Nami", "Nasus",
        "Nunu", "Olaf", "Orianna", "Rumble", "Sejuani",
        "Seraphine", "Singed", "Sion", "Skarner", "Sona",
        "Soraka", "Swain", "Taliyah", "Teemo", "Thresh",
        "Trundle", "Tryndamere", "Twitch", "Udyr", "Varus",
        "Velkoz", "Viktor", "Zilean", "Zyra",
    }
    return sum(1 for e in enemigos if e in slowers)


# ─── ITEMIZACIÓN SITUACIONAL ────────────────────────────────────────

def recomendar_item_defensivo(campeon: str, enemigos: list) -> str | None:
    """
    Sugiere un ítem defensivo situacional según la composición enemiga.
    Retorna el ID del ítem o None si no aplica.
    """
    ad = sum(1 for e in enemigos if obtener_dano(e) == "AD")
    ap = sum(1 for e in enemigos if obtener_dano(e) in ("AP", "HYBRID"))
    cc = sum(obtener_nivel_cc(e) for e in enemigos)
    tanques = sum(1 for e in enemigos if es_tanque(e))

    # Mucha AP → Espíritu Visceral o Fuerza de la Naturaleza
    if ap >= 3:
        if cc >= 10:
            return "3065"  # Spirit Visage (más curación contra CC)
        return "4401"  # Force of Nature (anti-AP DPS)

    # Mucho AD + críticos → Randuin
    if ad >= 4 and _contar_criticos(enemigos) >= 2:
        return "3143"  # Randuin's Omen

    # Mucho AD puro → Coraza de Espinas
    if ad >= 4:
        return "3075"  # Thornmail

    # Mucha vida enemiga → Hoja del Rey
    if tanques >= 3:
        return "3153"  # Blade of the Ruined King

    return None


def _contar_criticos(enemigos: list) -> int:
    """Campeones que típicamente buildan crítico."""
    crit_champs = {
        "Aphelios", "Ashe", "Caitlyn", "Draven", "Gangplank",
        "Jhin", "Jinx", "KaiSa", "Lucian", "MissFortune",
        "Nilah", "Samira", "Senna", "Sivir", "Smolder",
        "Tristana", "Twitch", "Vayne", "Xayah", "Yasuo",
        "Yone", "Zeri", "Akshan", "Kindred",
    }
    return sum(1 for e in enemigos if e in crit_champs)
