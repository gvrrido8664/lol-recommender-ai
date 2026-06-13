"""Funciones y datos puros reutilizados por la UI.

Extraido de app.py sin cambios de comportamiento:
- clear_layout: limpieza recursiva de layouts Qt.
- Configuracion de usuario: DEFAULT_SETTINGS, cargar_settings, guardar_settings.
- Datos de campeones: STAT_SHARDS, SKILL_ORDERS.
- Pathing de jungla: JUNGLA_ESTILO, _jungla_estilo, sugerir_pathing_jungla.
- Runas adaptativas: ajustar_shards_adaptativos.
- Tips de matchup: MATCHUP_TIPS, obtener_tip_matchup, obtener_tips_matchup.
"""

import os
import json

from src.paths import BASE_DIR, CONFIG_DIR


# ─── SHARDS DE ESTADISTICAS ───────────────────────────────────────────────
STAT_SHARDS = {
    "5008": ("Fuerza Adapt.", "#e74c3c"),
    "5005": ("Vel. Ataque", "#f1c40f"),
    "5007": ("Acel. Hab.", "#9b59b6"),
    "5009": ("Vel. Mov.", "#1abc9c"),
    "5001": ("Prog. Vida", "#2ecc71"),
    "5010": ("Vida Plana", "#27ae60"),
    "5011": ("Vida", "#16a085"),
    "5013": ("Tenacidad", "#34495e"),
    "5002": ("Armadura", "#e67e22"),
    "5003": ("Res. Mágica", "#3498db"),
}

# ─── RUTAS DE HABILIDADES (skill order) ───
# Formato: "Q>W>E" = maxear Q primero, luego W, luego E. R siempre al 6/11/16.
SKILL_ORDERS = {
    "Aatrox": "Q>E>W", "Ahri": "Q>W>E", "Akali": "Q>E>W", "Akshan": "Q>E>W",
    "Alistar": "Q>W>E", "Amumu": "E>Q>W", "Anivia": "E>Q>W", "Annie": "Q>W>E",
    "Aphelios": "Q>W>E", "Ashe": "W>Q>E", "AurelionSol": "Q>W>E", "Azir": "Q>W>E",
    "Bardo": "Q>W>E", "Blitzcrank": "Q>E>W", "Brand": "W>Q>E", "Braum": "Q>E>W",
    "Caitlyn": "Q>W>E", "Camille": "Q>E>W", "Chogath": "Q>W>E", "Corki": "Q>E>W",
    "Darius": "Q>E>W", "Diana": "Q>W>E", "Draven": "Q>W>E", "DrMundo": "Q>E>W",
    "Ekko": "Q>E>W", "Elise": "Q>W>E", "Evelynn": "Q>E>W", "Ezreal": "Q>E>W",
    "Fiora": "Q>E>W", "Fizz": "E>W>Q", "Galio": "Q>W>E", "Garen": "E>Q>W",
    "Gnar": "Q>W>E", "Gragas": "Q>E>W", "Graves": "Q>E>W", "Gwen": "Q>E>W",
    "Hecarim": "Q>E>W", "Illaoi": "E>Q>W", "Irelia": "Q>E>W", "Janna": "E>W>Q",
    "JarvanIV": "Q>E>W", "Jax": "W>Q>E", "Jayce": "Q>W>E", "Jhin": "Q>W>E",
    "Jinx": "Q>W>E", "Kaisa": "Q>E>W", "Kalista": "E>Q>W", "Karma": "Q>E>W",
    "Karthus": "Q>E>W", "Kassadin": "Q>W>E", "Katarina": "Q>E>W", "Kayle": "Q>E>W",
    "Kayn": "Q>W>E", "Kennen": "Q>W>E", "Khazix": "Q>W>E", "Kindred": "Q>W>E",
    "Kled": "Q>W>E", "Leblanc": "W>Q>E", "LeeSin": "Q>W>E", "Leona": "W>E>Q",
    "Lillia": "Q>W>E", "Lissandra": "Q>W>E", "Lucian": "Q>E>W", "Lulu": "E>W>Q",
    "Lux": "E>Q>W", "Malphite": "Q>E>W", "Malzahar": "E>Q>W", "Maokai": "Q>W>E",
    "MasterYi": "Q>E>W", "MissFortune": "Q>W>E", "Mordekaiser": "Q>E>W",
    "Morgana": "Q>W>E", "Nami": "W>E>Q", "Nasus": "Q>W>E", "Nautilus": "Q>W>E",
    "Neeko": "Q>E>W", "Nidalee": "Q>E>W", "Nocturne": "Q>E>W", "Olaf": "Q>E>W",
    "Orianna": "Q>W>E", "Ornn": "W>Q>E", "Pantheon": "Q>E>W", "Poppy": "Q>E>W",
    "Pyke": "Q>E>W", "Qiyana": "Q>E>W", "Quinn": "W>Q>E", "Rakan": "W>E>Q",
    "Rammus": "Q>E>W", "RekSai": "Q>W>E", "Rell": "W>E>Q", "Renata": "E>W>Q",
    "Renekton": "Q>E>W", "Rengar": "Q>E>W", "Riven": "Q>E>W", "Rumble": "Q>E>W",
    "Ryze": "Q>E>W", "Samira": "Q>E>W", "Sejuani": "W>Q>E", "Senna": "Q>W>E",
    "Seraphine": "Q>E>W", "Sett": "Q>W>E", "Shaco": "E>Q>W", "Shen": "Q>E>W",
    "Shyvana": "W>Q>E", "Singed": "Q>E>W", "Sion": "Q>W>E", "Sivir": "Q>W>E",
    "Skarner": "Q>W>E", "Sona": "Q>W>E", "Soraka": "W>Q>E", "Swain": "Q>W>E",
    "Sylas": "W>E>Q", "Syndra": "Q>E>W", "TahmKench": "Q>W>E", "Taliyah": "Q>E>W",
    "Talon": "W>Q>E", "Taric": "E>Q>W", "Teemo": "E>Q>W", "Thresh": "Q>W>E",
    "Tristana": "Q>E>W", "Trundle": "Q>W>E", "Tryndamere": "Q>E>W",
    "TwistedFate": "Q>W>E", "Twitch": "E>Q>W", "Udyr": "Q>E>W", "Urgot": "W>Q>E",
    "Varus": "Q>W>E", "Vayne": "Q>W>E", "Veigar": "Q>E>W", "Velkoz": "Q>W>E",
    "Vex": "Q>E>W", "Vi": "Q>E>W", "Viego": "Q>E>W", "Viktor": "E>Q>W",
    "Vladimir": "Q>E>W", "Volibear": "W>Q>E", "Warwick": "Q>W>E",
    "Wukong": "Q>E>W", "Xayah": "E>W>Q", "Xerath": "Q>W>E",
    "Yasuo": "Q>E>W", "Yone": "Q>E>W", "Yorick": "Q>E>W", "Yuumi": "E>Q>W",
    "Zac": "E>W>Q", "Zed": "Q>E>W", "Zeri": "Q>W>E", "Ziggs": "Q>E>W",
    "Zilean": "Q>E>W", "Zoe": "Q>E>W", "Zyra": "E>Q>W",
    "Naafiri": "Q>E>W", "Belveth": "Q>E>W", "Briar": "Q>E>W",
    "Milio": "E>W>Q", "Smolder": "Q>W>E", "Hwei": "Q>E>W", "Aurora": "Q>E>W",
    "Mel": "Q>E>W", "Ambessa": "Q>E>W",
}

# ─── PATHING DE JUNGLA ───────────────────────────────────────
JUNGLA_ESTILO = {
    "early_gank": {
        "champs": {"Amumu", "Vi", "JarvanIV", "Sejuani", "Zac", "Rell", "Nocturne",
                   "Rammus", "Volibear", "Warwick", "Hecarim", "Nunu", "Skarner",
                   "Pantheon", "Briar", "Trundle", "Udyr"},
        "label": "⚡ GANKERO TEMPRANO",
        "color": "{GREEN_SUCCESS}",
        "inicio": "Empieza en el buff mas cercano a la linea aliada con mas CC.",
        "ruta": "3 campamentos → gank a nivel 3 → continua clear y repite.",
        "prioridad_gank": "Busca carriles donde tu aliado tenga CC o una ventaja de level.",
    },
    "farm": {
        "champs": {"MasterYi", "Karthus", "Lillia", "Kindred", "Nasus", "Shyvana",
                   "DrMundo", "Viego", "BelVeth", "Belveth", "Mordekaiser"},
        "label": "🌾 FARMEADOR / ESCALADA",
        "color": "#2dd4bf",
        "inicio": "Empieza en el buff que te permita full-clear mas rapido.",
        "ruta": "Full clear de la jungla → nivel 6 con ult → ganks selectivos.",
        "prioridad_gank": "Evita ganks tempranos si van mal. Llega al 6 y entonces actua.",
    },
    "invade": {
        "champs": {"LeeSin", "Graves", "Shaco", "Rengar", "Khazix", "KhaZix",
                   "Nidalee", "Elise", "Ekko", "Kayn", "Evelynn", "Talon",
                   "Qiyana", "RekSai"},
        "label": "🗡️ CONTRA-JUNGLA / DUELISTA",
        "color": "#e63946",
        "inicio": "Empieza en el lado OPUESTO al buff de inicio del rival para invadir a nivel 2.",
        "ruta": "3 campamentos → roba campamento enemigo → gank o continue invadiendo.",
        "prioridad_gank": "Rastrear al jungla rival y tomar sus campamentos vale mas que gankar ciegamente.",
    },
}


def _jungla_estilo(champ_name: str) -> dict:
    """Devuelve el dict de estilo de jungla para el campeon dado."""
    sanitized = (champ_name or "").replace(" ", "").replace("'", "")
    for estilo, data in JUNGLA_ESTILO.items():
        if sanitized in data["champs"] or champ_name in data["champs"]:
            return data
    # Inferencia por tags si el campeon no esta en ningun set
    from src.tags_champions import es_asesino, obtener_nivel_cc
    if es_asesino(sanitized):
        return JUNGLA_ESTILO["invade"]
    if obtener_nivel_cc(sanitized) >= 2:
        return JUNGLA_ESTILO["early_gank"]
    return JUNGLA_ESTILO["farm"]


def sugerir_pathing_jungla(mi_champ: str, enemy_jungler: str, aliados: list, enemigos: list) -> dict:
    """Genera recomendacion de pathing para jungla.
    Returns dict con: label, color, inicio, ruta, prioridad_gank, vs_jungla."""
    from src.tags_champions import obtener_nivel_cc
    mi_estilo = _jungla_estilo(mi_champ)
    enemy_estilo = _jungla_estilo(enemy_jungler) if enemy_jungler else None

    # Prioridad de gank segun CC aliado por carril (posicion 0=top,1=jg,2=mid,3=bot,4=sup)
    gank_tips = []
    for nombre in aliados:
        cc = obtener_nivel_cc(nombre.replace(" ", "").replace("'", ""))
        if cc >= 3:
            gank_tips.append(f"Tu aliado {nombre} tiene mucho CC — gankea su carril primero.")
            break

    # Consejo contra el jungla rival
    vs_tip = ""
    if enemy_jungler:
        emy = enemy_estilo or {}
        if emy.get("label", "").startswith("⚡"):
            vs_tip = f"⚠️ {enemy_jungler} es agresivo temprano — wards en entradas de jungla y juega seguro en nivel 1-3."
        elif emy.get("label", "").startswith("🌾"):
            vs_tip = f"✅ {enemy_jungler} farmea. Toma ventaja gankeando antes de que llegue al 6."
        elif emy.get("label", "").startswith("🗡️"):
            vs_tip = f"⚠️ {enemy_jungler} puede invadir. Pon ward en tus buffs y juega lejos de su lado de inicio."

    resultado = dict(mi_estilo)
    if gank_tips:
        resultado["prioridad_gank"] = gank_tips[0]
    resultado["vs_jungla"] = vs_tip
    resultado["enemy_jungler"] = enemy_jungler or ""
    return resultado


# ─── RUNAS ADAPTATIVAS ───────────────────────────────────────
# Shards: slot 8 = row 1 (adaptive/att speed/haste), slot 9 = row 2 (adaptive/armor/mr), slot 10 = row 3 (health/tenacity/haste)
_SHARD_ADAPTIVE   = "5008"  # Fuerza Adaptativa
_SHARD_ATT_SPEED  = "5005"  # Velocidad de Ataque
_SHARD_HASTE      = "5007"  # Aceleracion de Habilidades
_SHARD_ARMOR      = "5002"  # Armadura
_SHARD_MR         = "5003"  # Resistencia Magica
_SHARD_HEALTH     = "5001"  # Prog. Vida
_SHARD_TENACITY   = "5013"  # Tenacidad

# Campeones que se benefician de Velocidad de Ataque (slot 8) — AA-heavy pero no ADC
_AA_HEAVY = {"Jax", "Tryndamere", "MasterYi", "Kayle", "Warwick", "Volibear",
             "Shyvana", "Udyr", "Garen", "Hecarim", "Viego", "Kalista",
             "Vayne", "Draven", "Jinx", "Caitlyn", "Ashe", "Ezreal", "Tristana"}
# Campeones que prefieren Haste (slot 8) — casters sin AA
_HASTE_PREF = {"Karthus", "Lux", "Xerath", "Ziggs", "Syndra", "Cassiopeia",
               "Anivia", "Viktor", "Swain", "Malzahar", "Azir", "Brand",
               "Veigar", "Velkoz", "Hwei", "Seraphine"}


def ajustar_shards_adaptativos(ids_runas: list, mi_champ: str, enemigo_lane: str, picks_en: list) -> list:
    """Reemplaza los 3 shards (indices 8-10) con elecciones adaptativas.
    No modifica el resto de las runas. Si no hay suficientes datos, devuelve la lista sin cambios."""
    if not ids_runas or len(ids_runas) < 11:
        return ids_runas

    from src.tags_champions import obtener_dano, obtener_nivel_cc, es_mago, es_tirador

    champ_sanitized = (mi_champ or "").replace(" ", "").replace("'", "")
    enemy_sanitized = (enemigo_lane or "").replace(" ", "").replace("'", "")

    result = list(ids_runas)

    # Shard 8 (row 1): adaptive / att speed / haste
    if champ_sanitized in _HASTE_PREF or es_mago(champ_sanitized):
        result[8] = _SHARD_HASTE
    elif champ_sanitized in _AA_HEAVY or es_tirador(champ_sanitized):
        result[8] = _SHARD_ATT_SPEED
    else:
        result[8] = _SHARD_ADAPTIVE

    # Shard 9 (row 2): adaptive / armor / MR segun dano del rival de linea
    if enemy_sanitized:
        dmg = obtener_dano(enemy_sanitized)
        if dmg == "AP":
            result[9] = _SHARD_MR
        elif dmg == "AD":
            result[9] = _SHARD_ARMOR
        else:
            result[9] = _SHARD_ADAPTIVE
    # Si no hay rival conocido, mantener el shard original

    # Shard 10 (row 3): tenacity si hay mucho CC enemigo, si no salud
    total_cc = sum(obtener_nivel_cc((c or "").replace(" ", "").replace("'", "")) for c in picks_en)
    result[10] = _SHARD_TENACITY if total_cc >= 8 else _SHARD_HEALTH

    return result


# ─── TIPS DE MATCHUP ────────────────────────────────────────
MATCHUP_TIPS = {
    "Zed":        ["Guarda tu dash/CC para despues de su R — actua cuando sale del shadow.",
                   "Warda el arbusto lateral antes del nivel 6 para evitar all-ins ciegos.",
                   "Itemiza Sello del Celemi o Temprana Hourglass si llegas al 10% vida."],
    "Darius":     ["No tradees cuando falle su Q — el borde cura y recarga rapido.",
                   "Matchup de desgaste: poke desde lejos y evita su E (gancho).",
                   "Bajo torre es donde mas pierde; hazle llegar ahi con 2 torres restantes."],
    "Yasuo":      ["Los champions con mucho poke pasan el early; evita caminar hacia el.",
                   "Su barrera de viento dura 4s — esperala antes de usar proyectiles CC.",
                   "Cuida su EQ (Q + empuje) que resetea; alejate despues de cada wave."],
    "Yone":       ["Su R te ancla al suelo — usa flash antes de que caiga, no despues.",
                   "Cuando entra en soul form pierde rango; kitele en esas ventanas.",
                   "Nivel 6 es su pico; juega defensivo sin ult propio."],
    "Lux":        ["Predice su Q en linea recta; los side-steps eliminan el 80% de su dano.",
                   "Cuando waste Q, entra y all-in — tiene la re-cast de E pero no Q.",
                   "Su ult tiene CD muy bajo con haste; no te confies despues de verlo una vez."],
    "Thresh":     ["Su Q (gancho) tiene 2 partes — dodge la primera con lateral.",
                   "No te arrimes a companeros aturdidos; Thresh hace cadena de CC.",
                   "Su E empuja/hala segun el lado que impacta; aprende el angulo correcto."],
    "Blitzcrank": ["Camina detras de minions en el carril — bloquean el gancho.",
                   "Si te hookea, flash inmediato antes del Q para romper la combinacion.",
                   "Su R silencia un area grande; ten cuidado de no estar agrupado."],
    "Zac":        ["Sus blobs (e-s) en el suelo le curan; destruyelos pisandolos antes.",
                   "Su E (salto) anuncia antes de saltar — escuchalo y escapa lateral.",
                   "Nivel 3 y 6 son sus picos de gank; wardea trinomio."],
    "Irelia":     ["No la dejes stackear pasiva — ataca minions para resetearla.",
                   "Q resetea si mata — alejate de minions bajos de vida en tu zona.",
                   "Su R bloquea proyectiles; usa tu CC durante las pausas de la ult."],
    "Lee Sin":    ["Wardea tus entradas de jungla nivel 2 — puede invadir muy pronto.",
                   "Su Q necesita segundo click — si no lo confirma, pierde la carga.",
                   "Post-6, no te pongas cerca de aliados o te usara de insec."],
    "Graves":     ["Sus perdigones hacen dano en cono — alejate en diagonal, no en linea.",
                   "Su dash no funciona hacia obstaculos (muros) — usalos para cortarle.",
                   "Evita el humo de E (W); reduce rango de vision y ralentiza."],
    "Kha'Zix":    ["Separarse del equipo lo hace mas peligroso — mantente agrupado.",
                   "Cada evo le da herramientas distintas; aprende que evoluciono primero.",
                   "Su W (salto largo) esta disponible sin minions cerca — no te confies en lane."],
    "Nasus":      ["Ralentizale el farmeo de Q con poke constante los primeros 10 min.",
                   "Post-15 min no pelee con el en un duel — escala infinitamente.",
                   "Su R tiene una duracion corta — kitalo o manda CC hasta que expire."],
    "Tryndamere": ["Su R dura 5s — CC y corre, no lo termines dentro de ult.",
                   "Nivel 11 (ult 2 veces) es su pico — juega cerca de tower.",
                   "Su furia (barrita) aumenta su CR; no lo dejes acumular sin pegarle."],
    "Fiora":      ["Sus Vitals cambian de lado 4 veces; aprende su patron para quitarlos.",
                   "Su R requiere golpear los 4 vitals — bordalo con cuerpo a cuerpo."],
    "Camille":    ["Su E (gancho + dash) tiene un gap de 0.75s entre las dos partes — evade el segundo.",
                   "Su R la encierra contigo sola — flash por la pared antes de que caiga."],
    "Renekton":   ["Matchup de rabia: cuando tenga barra llena (50+) no tradees.",
                   "Su W (combo de aturdimiento) requiere un hit previo — alejate cuando se active."],
    "Gangplank":  ["Sus barriles tienen 2 cargas por defecto — elimina el primero antes de que encadene.",
                   "Su E le quita CC activos — usalos durante su ult para el minimo dano."],
    "Malphite":   ["Full AP Malphite: tratalo como un mago disfrazado de tanque.",
                   "Su R tiene CC de area — no estes agrupado contra el en teamfights."],
    "Morgana":    ["Su W tiene un delay de 0.5s — side-step apenas lo empiece a lanzar.",
                   "Su escudo (E) bloquea CCs; no gastes tu CC hard mientras este activo."],
    "Leona":      ["No pelear cuando su Eclipse (W) esta activo — dura 3s.",
                   "Su Q (stun) requiere que su E haya llegado primero — ve el orden."],
    "Nautilus":   ["Su gancho Q marca — si falla, tiene un gran cooldown.",
                   "Su auto-ataque ancla (pasiva) — no autoataquees en trades cortos si son malos."],
    "Jinx":       ["Sin cargas de pasiva es un objetivo facil — matala antes de que empiece a resetear.",
                   "Sus minas (E) duran 5s en el suelo — camina por los lados de la wave."],
    "Caitlyn":    ["Sus trampas (W) se colocan tras stuns — ward los arbustos y no pases sobre ellas.",
                   "Su ult puede ser bloqueada por un aliado entre tu y ella."],
    "Ezreal":     ["Su E es su unico escape — forzalo con CC y luego all-in.",
                   "Su Q tiene rango muy largo — no hagas linea recta en poke wars."],
    "Orianna":    ["La pelota esta siempre en algun lugar — saber donde es el 80% del matchup.",
                   "Su R en pelota lanzada — alejarse del centro es la defensa mas efectiva."],
    "Syndra":     ["Sus bolas permanecen en el mapa — su R hace mas dano cuantas mas tenga.",
                   "Su E aturde si una bola esta detras del target — no te pongas entre bolas y ella."],
    "Ahri":       ["Puede hacer charm en W; el Q pasa dos veces — la vuelta hace mas dano.",
                   "Sin R (3 dashes) es muy vulnerable — countergankea post ult."],
    "Leblanc":    ["Su W deja un espejo — si no pone puntos en W empuja, si no regresa.",
                   "Con silencio le cortas la cadena de burst — usalo antes de su Q."],
    "Katarina":   ["Sus daggers en el suelo la resetean — evita quedarte cerca de ellas.",
                   "CC en el momento del dash la interrumpe completamente."],
    "Akali":      ["Su campo de humo (W) la hace invisible — usa AoE para forzarla a salir.",
                   "Su R primer dash no hace dano — el segundo si; flash tras el primero."],
    "Qiyana":     ["Sus elementos cambian su kit — el Q con rio aturde, con arbol hace dano extra.",
                   "Su R explota con colision de estructuras y rios; cuida los bordes del mapa."],
    "Rengar":     ["Ward los arbustos antes de que llegue al 6; predice de que arbusto sale.",
                   "Su pasiva (stack) aumenta su kit — hazle usar habilidades sin stacks completos."],
    "Evelynn":    ["Invisible post-6 salvo anti-invis — itemiza Oraculo de la Trampa (pink ward).",
                   "Su alurt aturde si la segunda parte impacta — sal del area con flash."],
    "Shaco":      ["Sus cajas (W) se activan por aparicion repentina — no entres en arbustos sin ward.",
                   "Puede clonar con R — el real tiene HP diferente en el numero del score."],
    "Nidalee":    ["Sus javelinas hacen mas dano a distancia — angulate para reducir la distancia.",
                   "En forma de puma su Q cura — activala cuando tenga vida baja."],
    "Hecarim":    ["Su fantasma de invocador sube su movespeed para E — no lo persiga en linea recta.",
                   "Su R tiene fear de area — agrupate lejos de walls para evitar el empuje."],
    "Warwick":    ["Su W (rastrear heridos) se activa en <50% HP — juega conservador en esa zona.",
                   "Su R es suppresion de canal — QSS lo rompe o flash pre-R."],
}


def obtener_tip_matchup(enemigo: str) -> str:
    """Devuelve el primer tip relevante para el matchup dado, o cadena vacia si no hay."""
    tips = MATCHUP_TIPS.get(enemigo, [])
    return tips[0] if tips else ""


def obtener_tips_matchup(enemigo: str) -> list:
    """Devuelve todos los tips para el matchup dado."""
    return MATCHUP_TIPS.get(enemigo, [])


def clear_layout(layout):
    if layout is not None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                clear_layout(item.layout())


# ─── CONFIGURACION DE USUARIO ───────────────────────────────────────
DEFAULT_SETTINGS = {
    "auto_deteccion": True,
    "mostrar_power_spikes": True,
    "mostrar_explicaciones": True,
    "frecuencia_radar": 1500,
    "sonidos": False,
    "modo_principiante": False,
    "modo_profesional": False,
    "recordatorios_partida": True,
    "mostrar_dificultad": True,
    "tooltips_grandes": False,
    "flash_en_d": True,
    "auto_runas": False,
    "auto_hechizos": False,
    "auto_habilidades": False,
    "auto_items": False,
    "auto_switch_radar": True,
    "overlay_ingame": False,
    "notificaciones_escritorio": True,
    "auto_aceptar": False,
}


def cargar_settings():
    try:
        with open(os.path.join(CONFIG_DIR, "config.json"), "r", encoding="utf-8") as f:
            saved = json.load(f)
            return {**DEFAULT_SETTINGS, **saved.get("user_settings", {})}
    except:
        # Fallback: leer desde BASE_DIR (bundled default config)
        try:
            with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
                saved = json.load(f)
                return {**DEFAULT_SETTINGS, **saved.get("user_settings", {})}
        except:
            return dict(DEFAULT_SETTINGS)


def guardar_settings(settings):
    try:
        config_path = os.path.join(CONFIG_DIR, "config.json")
        config = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        config["user_settings"] = settings
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False
