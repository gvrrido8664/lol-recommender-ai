"""
Motor de Razonamiento Educativo (Pilar 4).

Genera explicaciones breves, modulares y reutilizables para cada decisión
de la app: picks, hechizos, runas, botas e ítems.

Cada función devuelve un dict con:
- "recomendacion": str (texto corto para UI)
- "razon": str (explicación educativa)
- "icono": str (emoji temático)
"""
from .tags_champions import (
    obtener_tag, obtener_dano, es_tanque, es_mago, es_tirador,
    es_asesino, es_luchador, es_soporte, obtener_nivel_cc,
    obtener_subrol_soporte, obtener_escalado, obtener_poder_temprano,
    es_botas_estaticas, obtener_bota_estatica
)

# ─── CONSTANTES ─────────────────────────────────────────────────────
BOTA_NAMES = {
    "3047": "Botas de Acero Reforzado",
    "3111": "Botas de Mercurio",
    "3020": "Botas de Hechicero",
    "3006": "Grebas de Berserker",
    "3158": "Botas de Lucidez (Ionias)",
    "3009": "Botas de Rapidez",
    "3005": "Botas de Movilidad",
}

SPELL_NAMES = {
    "1": "Limpiar",
    "3": "Extenuación",
    "4": "Flash",
    "6": "Agotamiento",
    "7": "Curar",
    "11": "Aplastar",
    "12": "Teleportar",
    "13": "Claridad",
    "14": "Ignite",
    "21": "Barrera",
    "30": "Recall",
}

SPELL_REASONING = {
    "14": ("Ignite", "reduce las curaciones enemigas y asegura kills en early"),
    "4":  ("Flash", "esencial para reposicionarse, escapar o iniciar jugadas"),
    "12": ("Teleportar", "permite volver rápido a línea y rotar a otras líneas en mid-game"),
    "6":  ("Agotamiento", "anula a campeones de daño sostenido y asesinos en teamfights"),
    "3":  ("Extenuación", "reduce el daño de un enemigo clave y lo ralentiza"),
    "7":  ("Curar", "da sustain en línea y una pequeña velocidad de escape"),
    "11": ("Aplastar", "obligatorio en jungla para asegurar objetivos"),
    "21": ("Barrera", "escudo reactivo contra burst enemigo"),
    "1":  ("Limpiar", "elimina CC enemigo, clave contra composiciones con mucho control"),
}

ROLE_PLAYSTYLE = {
    "TOP": "control de línea y presión lateral",
    "JUNGLE": "presencia en el mapa y control de objetivos",
    "MIDDLE": "prioridad de línea y roaming para impactar otras líneas",
    "BOTTOM": "DPS consistente y posicionamiento seguro en teamfights",
    "UTILITY": "visión, peel para el ADC e iniciación de peleas",
}


def razonar_pick(campeon: str, rol: str, aliados: list, enemigos: list) -> dict:
    """
    Explica por qué pickear este campeón en esta situación.
    """
    tag = obtener_tag(campeon)
    dano = tag.get("damage_type", "AD")
    clase = tag.get("champion_class", "")
    scaling = tag.get("scaling", "mid")
    early = tag.get("early_power", "neutral")
    cc = tag.get("cc_level", 0)

    # Contar daño enemigo
    ap_enemigos = sum(1 for e in enemigos if obtener_dano(e) in ("AP", "HYBRID"))
    ad_enemigos = sum(1 for e in enemigos if obtener_dano(e) == "AD")
    cc_enemigo_total = sum(obtener_nivel_cc(e) for e in enemigos)

    razones = []

    # 1. Razón del pick según su clase
    if clase == "Tank":
        if cc_enemigo_total >= 8:
            razones.append("Absorbe el CC enemigo masivo y protege a tu backline")
        else:
            razones.append("Frontlane sólido que inicia peleas y absorbe presión")
    elif clase == "Mage":
        if scaling in ("late", "hyper"):
            razones.append("Escalado seguro: carry AP con potencial de oneshot en late game")
        else:
            razones.append("Control de mapa con daño mágico en área y prio de línea")
    elif clase == "Assassin":
        if ad_enemigos <= 2:
            razones.append("Flanqueo letal contra backline enemigo vulnerable")
        else:
            razones.append("Eliminación rápida de carries enemigos en teamfights")
    elif clase == "Marksman":
        if scaling in ("late", "hyper"):
            razones.append("Hipercarry de daño físico: tu seguro de victoria en late game")
        else:
            razones.append("DPS constante desde backline con rango seguro")
    elif clase == "Fighter":
        if scaling in ("late", "hyper"):
            razones.append("Duelista de split push imparable en late game")
        else:
            razones.append("Bruiser versátil con daño y aguante para peleas extendidas")
    elif clase == "Support":
        subrol = obtener_subrol_soporte(campeon) or ""
        if "engage" in subrol:
            razones.append("Engage decisivo para iniciar peleas cuando tu equipo lo necesita")
        elif "peel" in subrol:
            razones.append("Protección máxima para tu ADC: peel, escudos y control de zona")
        elif "sustain" in subrol:
            razones.append("Sustain en línea que permite a tu ADC farmear seguro y escalar")
        elif "poke" in subrol:
            razones.append("Presión constante en línea con poke que desgasta al enemigo")
        else:
            razones.append("Utilidad versátil que se adapta a las necesidades del equipo")

    # 2. Razón por tipo de daño (balance de composición)
    ap_aliados = sum(1 for a in aliados if obtener_dano(a) in ("AP", "HYBRID"))
    ad_aliados = sum(1 for a in aliados if obtener_dano(a) == "AD")
    if dano == "AP" and ap_aliados <= 1:
        razones.append("Aporta el daño mágico que le falta a tu composición")
    elif dano == "AD" and ad_aliados <= 1:
        razones.append("Aporta el daño físico que necesita tu equipo")

    # 3. Razón por early/late
    if early == "strong":
        razones.append("Domina el early game y puede snowballear la partida rápido")
    elif scaling in ("late", "hyper"):
        razones.append("Tu equipo escalará mejor: este campeón brilla en late game")

    # 4. Razón por CC
    if cc >= 3 and cc_enemigo_total <= 5:
        razones.append("Aporta CC en área que el equipo enemigo no iguala")

    return {
        "recomendacion": f"Pick recomendado por {razones[0].lower()}",
        "razon": " | ".join(razones),
        "icono": _icono_clase(clase),
    }


def razonar_hechizos(campeon: str, rol: str, enemigos: list, spells: list) -> dict:
    """
    Explica por qué estos hechizos de invocador.
    """
    razones = []
    iconos = []

    for s in spells:
        info = SPELL_REASONING.get(s)
        if info:
            iconos.append(f"✨{info[0]}")
            # Personalizar razón según contexto
            if s == "14":  # Ignite
                curaciones = _contar_curaciones(enemigos)
                if curaciones >= 2:
                    razones.append(f"Ignite porque el equipo enemigo tiene {curaciones} fuentes de curación")
                else:
                    razones.append(info[1])
            elif s == "1":  # Cleanse
                cc_total = sum(obtener_nivel_cc(e) for e in enemigos)
                if cc_total >= 10:
                    razones.append("Limpiar porque el equipo enemigo tiene CC masivo")
                else:
                    razones.append(info[1])
            elif s == "12":  # TP
                if rol == "TOP":
                    razones.append("Teleportar indispensable en top para no perder oleadas y rotar a dragones")
                else:
                    razones.append(info[1])
            elif s == "11":  # Smite
                razones.append("Aplastar obligatorio en jungla para asegurar Barón y Dragones")
            else:
                razones.append(info[1])

    if not razones:
        razones.append("Combinación estándar más usada en este rol")

    return {
        "recomendacion": " + ".join([SPELL_REASONING.get(s, (f"Hechizo {s}",))[0] for s in spells]),
        "razon": " | ".join(razones),
        "icono": "🔮",
    }


def razonar_botas(campeon: str, rol: str, enemigos: list, bota_id: str) -> dict:
    """
    Explica por qué estas botas específicas.
    """
    nombre_bota = BOTA_NAMES.get(bota_id, f"Botas {bota_id}")
    tag = obtener_tag(campeon)

    # Si son botas estáticas (core del campeón)
    if es_botas_estaticas(campeon):
        static = obtener_bota_estatica(campeon)
        if static == bota_id:
            razon = _razon_bota_estatica(bota_id, tag)
            return {
                "recomendacion": nombre_bota,
                "razon": f"{razon} — Son las botas óptimas para {campeon} en casi todas las partidas",
                "icono": "👢",
            }

    # Si es adaptativo, explicar según amenazas
    ad = sum(1 for e in enemigos if obtener_dano(e) == "AD")
    ap = sum(1 for e in enemigos if obtener_dano(e) == "AP")
    cc_total = sum(obtener_nivel_cc(e) for e in enemigos)
    tiradores = sum(1 for e in enemigos if es_tirador(e))

    razon = ""
    if bota_id == "3047":  # Steelcaps
        if tiradores >= 2:
            razon = f"Reduce el daño de {tiradores} tiradores enemigos y autoataques"
        else:
            razon = f"Mitiga el daño físico de {ad} campeones AD enemigos"
    elif bota_id == "3111":  # Mercury
        if cc_total >= 10:
            razon = f"Tenacidad vital contra {cc_total} puntos de CC enemigo acumulado"
        else:
            razon = f"Resistencia mágica y tenacidad contra {ap} amenazas AP con CC"
    elif bota_id == "3020":  # Sorcerer
        razon = f"Penetración mágica plana: esencial para maximizar tu daño AP"
    elif bota_id == "3006":  # Berserker
        razon = "Velocidad de ataque para maximizar tu DPS como tirador"
    elif bota_id == "3158":  # Ionian
        razon = "Aceleración de habilidad para lanzar más hechizos y summoners"
    elif bota_id == "3009":  # Swiftness
        razon = "Velocidad de movimiento y resistencia a ralentizaciones para kiteo"
    else:
        razon = "Botas recomendadas según tu build óptimo"

    return {
        "recomendacion": nombre_bota,
        "razon": razon,
        "icono": "👟",
    }


def razonar_runas(campeon: str, rol: str, enemigos: list) -> dict:
    """
    Explica la elección de la rama de runas.
    """
    tag = obtener_tag(campeon)
    dano = tag.get("damage_type", "AD")
    clase = tag.get("champion_class", "")

    # Inferir rama según clase
    if clase == "Mage" or dano == "AP":
        rama = "Brujería/Dominación"
        razon = "Maximiza el burst mágico y la presión en línea con poke y electrocute"
    elif clase == "Marksman":
        rama = "Precisión"
        razon = "Optimiza el DPS con velocidad de ataque y daño consistente"
    elif clase == "Assassin":
        rama = "Dominación"
        razon = "Electrocute o Cosecha Oscura para asegurar eliminaciones rápidas"
    elif clase == "Tank":
        rama = "Valor"
        razon = "Aftershock o Garras para resistir e iniciar peleas con seguridad"
    elif clase == "Fighter":
        rama = "Precisión/Conquistador"
        razon = "Conquistador da curación y daño adaptativo en peleas extendidas"
    elif clase == "Support":
        subrol = obtener_subrol_soporte(campeon) or ""
        if "sustain" in subrol or "peel" in subrol:
            rama = "Inspiración/Brujería"
            razon = "Potencia escudos y curaciones para mantener vivo a tu equipo"
        else:
            rama = "Valor/Dominación"
            razon = "Aftershock para resistir al engagear o electrocute para poke"
    else:
        rama = "Precisión"
        razon = "Runas adaptadas al estilo de juego del campeón"

    return {
        "recomendacion": f"Rama: {rama}",
        "razon": razon,
        "icono": "📜",
    }


def razonar_objeto(item_id: str, campeon: str, rol: str, enemigos: list, items_dict: dict) -> dict:
    """
    Explica por qué este ítem es bueno en esta situación.
    """
    info = items_dict.get(item_id, {}) or items_dict.get(str(item_id), {})
    nombre = info.get("nombre", f"Ítem {item_id}")
    tags_item = info.get("tags", [])

    ad = sum(1 for e in enemigos if obtener_dano(e) == "AD")
    ap = sum(1 for e in enemigos if obtener_dano(e) == "AP")
    tanques = sum(1 for e in enemigos if es_tanque(e))

    razon = ""

    # Analizar por tags del ítem
    if "Armor" in tags_item and ad >= 3:
        razon = f"Armadura necesaria contra {ad} campeones AD enemigos"
    elif "SpellBlock" in tags_item and ap >= 3:
        razon = f"Resistencia mágica contra {ap} amenazas AP enemigas"
    elif "Health" in tags_item:
        razon = "Vida adicional para sobrevivir el burst enemigo en teamfights"
    elif "Damage" in tags_item:
        if ap >= 3:
            razon = "Daño para eliminar rápido a los carries AP enemigos"
        else:
            razon = "Item de daño core para maximizar tu potencial ofensivo"
    elif "CriticalStrike" in tags_item:
        razon = "Crítico para escalar tu DPS en late game"
    elif "AttackSpeed" in tags_item:
        razon = "Velocidad de ataque para aplicar daño por segundo más rápido"
    elif "SpellDamage" in tags_item:
        razon = "Potencia de habilidad para maximizar tu burst mágico"
    elif "Boots" in tags_item:
        return razonar_botas(campeon, rol, enemigos, item_id)
    elif "ArmorPenetration" in tags_item or "MagicPenetration" in tags_item:
        if tanques >= 3:
            razon = f"Penetración vital contra {tanques} tanques enemigos"
        else:
            razon = "Penetración para maximizar daño contra objetivos con resistencias"
    elif "Active" in tags_item:
        razon = "Activa de utilidad que puede cambiar el rumbo de una pelea"
    elif "Trinket" in tags_item:
        razon = "Visión esencial para controlar el mapa y evitar emboscadas"
    elif "Lane" in tags_item:
        razon = "Item de inicio para sustain en la fase de líneas"
    elif "Jungle" in tags_item:
        razon = "Item de jungla necesario para limpiar campamentos y asegurar objetivos"
    elif "GoldPer" in tags_item:
        razon = "Generación de oro pasiva para alcanzar tu build más rápido"
    else:
        # Fallback: usar descripción del ítem
        desc = info.get("descripcion", "")
        if desc:
            razon = f"Parte esencial de la build óptima de {campeon}"
        else:
            razon = f"Item estadísticamente más efectivo en {campeon}"

    return {
        "recomendacion": nombre,
        "razon": razon,
        "icono": "⚔️",
    }


# ─── HELPERS ─────────────────────────────────────────────────────────

def _icono_clase(clase: str) -> str:
    iconos = {
        "Tank": "🛡️", "Fighter": "⚔️", "Assassin": "🗡️",
        "Mage": "🔮", "Marksman": "🏹", "Support": "💚",
    }
    return iconos.get(clase, "✅")


def _contar_curaciones(enemigos: list) -> int:
    """Campeones con curación significativa en su kit."""
    curadores = {
        "Aatrox", "Briar", "Darius", "DrMundo", "Fiora", "Illaoi",
        "Kayn", "Maokai", "Nasus", "Olaf", "RedKayn", "Renekton",
        "Samira", "Soraka", "Swain", "Sylas", "Trundle", "Viego",
        "Vladimir", "Warwick", "Yone", "Yorick", "Zac",
    }
    return sum(1 for e in enemigos if e in curadores)


def _razon_bota_estatica(bota_id: str, tag: dict) -> str:
    """Explica por qué este campeón usa estas botas fijas."""
    clase = tag.get("champion_class", "")
    dano = tag.get("damage_type", "AD")

    if bota_id == "3006":  # Berserker
        if clase == "Marksman":
            return "Velocidad de ataque para maximizar DPS como tirador"
        return "Velocidad de ataque esencial para su patrón de daño"
    elif bota_id == "3020":  # Sorcerer
        if clase == "Mage":
            return "Penetración mágica plana para maximizar burst AP"
        return "Penetración mágica para amplificar su daño AP"
    elif bota_id == "3009":  # Swiftness
        return "Resistencia a ralentizaciones para mantener movilidad en peleas"
    elif bota_id == "3158":  # Ionian
        return "Aceleración de habilidad para rotar hechizos más rápido"
    elif bota_id == "3047":  # Steelcaps
        return "Reducción de daño de autoataques para duelos 1v1"
    return "Botas óptimas para este campeón"
