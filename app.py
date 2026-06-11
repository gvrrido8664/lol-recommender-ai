import json
import os
import requests
import threading
import time
from datetime import datetime, date
from io import BytesIO
from PIL import Image
import numpy as np
import joblib
import sys

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QGridLayout, QLabel, QPushButton, 
                               QComboBox, QTabWidget, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QFrame, QMessageBox, QAbstractItemView, QProgressBar, QCheckBox, QRadioButton, QDialog, QDialogButtonBox, QButtonGroup, QSlider, QSpinBox, QScrollArea, QSizePolicy, QSystemTrayIcon, QMenu, QStackedLayout, QGroupBox)
from PySide6.QtGui import QPixmap, QFont, QColor, QIcon, QAction, QPainter, QPen, QBrush
from PySide6.QtCore import Qt, QTimer, QSize, Signal, QPointF

from src.db_manager import DATA_DIR, obtener_conexion, inicializar_db
from src.db_manager import etiquetar_estado_emocional, obtener_estado_emocional, obtener_estadisticas_emocionales
from src.db_manager import registrar_lp, obtener_historial_lp
from src.db_manager import guardar_draft, completar_draft_resultado, obtener_historial_drafts
from src.riot_api import cargar_campeones, cargar_objetos, cargar_runas, cargar_mapeo_ids, cargar_hechizos, obtener_version_actual
from src.tags_champions import obtener_tag, obtener_nivel_cc, es_soporte, obtener_dano, es_tanque
from src.recomendador import (obtener_counters, obtener_top_items, obtener_campeones_por_rol,
                              obtener_top_runas, obtener_top_hechizos, obtenermejoresbaneos, obtener_peores_matchups,
                              recomendar_picks_vivo, calcular_winrate_5v5, analizar_composicion,
                              obtener_items_situacionales)
from src.lcu_api import LCUConnector
from src.analizador_fatiga import analizar_fatiga
from src.perfil_jugador import analizar_personalidad, detectar_habitos, generar_objetivos_semanales, analizar_emocional_vs_wr
from src.entrenador_ia import extraer_features_comparativas, interpretar_features
from src.overlay import OverlayWindow
from src.discord_rpc import iniciar_discord_rpc, detener_discord_rpc, actualizar_discord_rpc
from src.logros import evaluar_logros, obtener_logros_conseguidos, LOGROS_DEFINICIONES
from src.logger import init_logging, get_logger
from src.updater import check_for_update, set_current_version

init_logging()
log = get_logger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# PyInstaller: cuando es .exe, los datos están en _MEIPASS
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS

def _get_writable_dir():
    """Devuelve un directorio escribible para config/user data.
    En desarrollo: junto al script.
    En .exe frozen: %APPDATA%/LoLRecommender."""
    if getattr(sys, 'frozen', False):
        d = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'LoLRecommender')
    else:
        d = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(d, exist_ok=True)
    return d

ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# Cuando es .exe, los directorios de caché van a %APPDATA% (Program Files es solo lectura)
if getattr(sys, 'frozen', False):
    _CACHE_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'LoLRecommender', 'assets')
else:
    _CACHE_DIR = ASSETS_DIR

ITEMS_DIR = os.path.join(_CACHE_DIR, "items")
RUNAS_DIR = os.path.join(_CACHE_DIR, "runas")
CHAMPS_DIR = os.path.join(_CACHE_DIR, "champs")
SPELLS_DIR = os.path.join(_CACHE_DIR, "spells")
PROFILE_ICONS_DIR = os.path.join(_CACHE_DIR, "profile_icons")

for d in [ITEMS_DIR, RUNAS_DIR, CHAMPS_DIR, SPELLS_DIR, PROFILE_ICONS_DIR]:
    os.makedirs(d, exist_ok=True)

# Safe stdout/stderr for GUI mode (--windowed, sin consola) y encoding cp1252 en Windows
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

modelo_1v1 = {}
ruta_modelo = os.path.join(BASE_DIR, "data", "modelo_1v1.pkl")
if os.path.exists(ruta_modelo):
    try:
        modelo_1v1 = joblib.load(ruta_modelo)
        log.info("Modelo 1v1 cargado: %d roles", len(modelo_1v1))
    except Exception as e:
        log.warning("Error cargando modelo 1v1: %s", e)
else:
    log.warning("No se encuentra %s. El simulador 1v1 no funcionara.", ruta_modelo)
ITEMS_DICT = cargar_objetos()
RUNAS_DICT = cargar_runas()
SPELLS_DICT = cargar_hechizos()
MAPEO_IDS_CAMPEONES = cargar_mapeo_ids()

UI_ROLES = ["TOP", "JUNGLA", "MID", "ADC", "SUPPORT"]
ROL_TO_API = {"TOP": "TOP", "JUNGLA": "JUNGLE", "MID": "MIDDLE", "ADC": "BOTTOM", "SUPPORT": "UTILITY"}
API_TO_ROL = {"TOP": "TOP", "JUNGLE": "JUNGLA", "MIDDLE": "MID", "BOTTOM": "ADC", "UTILITY": "SUPPORT"}

# ═══════════════════════════════════════════════════════════════
# SELLO NEXUS — SISTEMA DE DISEÑO
# ═══════════════════════════════════════════════════════════════
BG_DARK = "#05080f"          # Fondo principal — negro azabache profundo
BG_PANEL = "#0c101a"         # Paneles — casi negro con un toque de azul
BG_CARD = "#111827"          # Tarjetas internas — gris azulado oscuro
BORDER_ACCENT = "#e63946"    # Borde acento — rojo carmesí agresivo (sello nexus)
BORDER_SUBTLE = "#1e293b"    # Borde sutil — gris pizarra para tarjetas
TEXT_WHITE = "#f1f5f9"       # Texto principal — blanco roto, legible
TEXT_MUTED = "#64748b"       # Texto secundario — gris medio
TEXT_GOLD = "#f8fafc"        # Texto destacado — casi blanco puro
ACCENT_RED = "#e63946"       # Acento principal — rojo nexus
ACCENT_TEAL = "#2dd4bf"      # Acento secundario — teal para datos/estadísticas
RED_WR = "#ef4444"           # Derrota — rojo intenso
GREEN_WR = "#22c55e"         # Victoria — verde esmeralda
YELLOW_WR = "#f59e0b"        # Advertencia — ámbar
ALLY_BG = "#0f172a"          # Aliados — azul muy oscuro
ENEMY_BG = "#1a0a0f"         # Enemigos — rojo muy oscuro
HOVER_GLOW = "#f43f5e"       # Hover — rosa-rojo para botones
FONT_FAMILY = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"

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

# ─── PATHING DE JUNGLA ──────────────────────────────────────────
JUNGLA_ESTILO = {
    "early_gank": {
        "champs": {"Amumu", "Vi", "JarvanIV", "Sejuani", "Zac", "Rell", "Nocturne",
                   "Rammus", "Volibear", "Warwick", "Hecarim", "Nunu", "Skarner",
                   "Pantheon", "Briar", "Trundle", "Udyr"},
        "label": "⚡ GANKERO TEMPRANO",
        "color": "#22c55e",
        "inicio": "Empieza en el buff más cercano a la línea aliada con más CC.",
        "ruta": "3 campamentos → gank a nivel 3 → continúa clear y repite.",
        "prioridad_gank": "Busca carriles donde tu aliado tenga CC o una ventaja de level.",
    },
    "farm": {
        "champs": {"MasterYi", "Karthus", "Lillia", "Kindred", "Nasus", "Shyvana",
                   "DrMundo", "Viego", "BelVeth", "Belveth", "Mordekaiser"},
        "label": "🌾 FARMEADOR / ESCALADA",
        "color": "#2dd4bf",
        "inicio": "Empieza en el buff que te permita full-clear más rápido.",
        "ruta": "Full clear de la jungla → nivel 6 con ult → ganks selectivos.",
        "prioridad_gank": "Evita ganks tempranos si van mal. Llega al 6 y entonces actúa.",
    },
    "invade": {
        "champs": {"LeeSin", "Graves", "Shaco", "Rengar", "Khazix", "KhaZix",
                   "Nidalee", "Elise", "Ekko", "Kayn", "Evelynn", "Talon",
                   "Qiyana", "RekSai"},
        "label": "🗡️ CONTRA-JUNGLA / DUELISTA",
        "color": "#e63946",
        "inicio": "Empieza en el lado OPUESTO al buff de inicio del rival para invadir a nivel 2.",
        "ruta": "3 campamentos → roba campamento enemigo → gank o continue invadiendo.",
        "prioridad_gank": "Rastrear al jungla rival y tomar sus campamentos vale más que gankar ciegamente.",
    },
}

def _jungla_estilo(champ_name: str) -> dict:
    """Devuelve el dict de estilo de jungla para el campeón dado."""
    sanitized = (champ_name or "").replace(" ", "").replace("'", "")
    for estilo, data in JUNGLA_ESTILO.items():
        if sanitized in data["champs"] or champ_name in data["champs"]:
            return data
    # Inferencia por tags si el campeón no está en ningún set
    from src.tags_champions import es_asesino, obtener_nivel_cc
    if es_asesino(sanitized):
        return JUNGLA_ESTILO["invade"]
    if obtener_nivel_cc(sanitized) >= 2:
        return JUNGLA_ESTILO["early_gank"]
    return JUNGLA_ESTILO["farm"]


def sugerir_pathing_jungla(mi_champ: str, enemy_jungler: str, aliados: list, enemigos: list) -> dict:
    """Genera recomendación de pathing para jungla.
    Returns dict con: label, color, inicio, ruta, prioridad_gank, vs_jungla."""
    from src.tags_champions import obtener_nivel_cc
    mi_estilo = _jungla_estilo(mi_champ)
    enemy_estilo = _jungla_estilo(enemy_jungler) if enemy_jungler else None

    # Prioridad de gank según CC aliado por carril (posición 0=top,1=jg,2=mid,3=bot,4=sup)
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


# ─── RUNAS ADAPTATIVAS ──────────────────────────────────────────
# Shards: slot 8 = row 1 (adaptive/att speed/haste), slot 9 = row 2 (adaptive/armor/mr), slot 10 = row 3 (health/tenacity/haste)
_SHARD_ADAPTIVE   = "5008"  # Fuerza Adaptativa
_SHARD_ATT_SPEED  = "5005"  # Velocidad de Ataque
_SHARD_HASTE      = "5007"  # Aceleración de Habilidades
_SHARD_ARMOR      = "5002"  # Armadura
_SHARD_MR         = "5003"  # Resistencia Mágica
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
    """Reemplaza los 3 shards (índices 8-10) con elecciones adaptativas.
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

    # Shard 9 (row 2): adaptive / armor / MR según daño del rival de línea
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


# ─── TIPS DE MATCHUP ────────────────────────────────────────────
MATCHUP_TIPS = {
    "Zed":        ["Guarda tu dash/CC para después de su R — actúa cuando sale del shadow.",
                   "Warda el arbusto lateral antes del nivel 6 para evitar all-ins ciegos.",
                   "Itemiza Sello del Celemí o Temprana Hourglass si llegas al 10% vida."],
    "Darius":     ["No tradees cuando falle su Q — el borde cura y recarga rápido.",
                   "Matchup de desgaste: poke desde lejos y evita su E (gancho).",
                   "Bajo torre es donde más pierde; hazle llegar ahí con 2 torres restantes."],
    "Yasuo":      ["Los champions con mucho poke pasan el early; evita caminar hacia él.",
                   "Su barrera de viento dura 4s — espérala antes de usar proyectiles CC.",
                   "Cuida su EQ (Q + empuje) que resetea; aléjate después de cada wave."],
    "Yone":       ["Su R te ancla al suelo — usa flash antes de que caiga, no después.",
                   "Cuando entra en soul form pierde rango; kítele en esas ventanas.",
                   "Nivel 6 es su pico; juega defensivo sin ult propio."],
    "Lux":        ["Predice su Q en línea recta; los side-steps eliminan el 80% de su daño.",
                   "Cuando waste Q, entra y all-in — tiene la re-cast de E pero no Q.",
                   "Su ult tiene CD muy bajo con haste; no te confíes después de verlo una vez."],
    "Thresh":     ["Su Q (gancho) tiene 2 partes — dodge la primera con lateral.",
                   "No te arrimes a compañeros aturdidos; Thresh hace cadena de CC.",
                   "Su E empuja/hala según el lado que impacta; aprende el ángulo correcto."],
    "Blitzcrank": ["Camina detrás de minions en el carril — bloquean el gancho.",
                   "Si te hookea, flash inmediato antes del Q para romper la combinación.",
                   "Su R silencia un área grande; ten cuidado de no estar agrupado."],
    "Zac":        ["Sus blobs (e-s) en el suelo le curan; destruyelos pisándolos antes.",
                   "Su E (salto) anuncia antes de saltar — escúchalo y escapa lateral.",
                   "Nivel 3 y 6 son sus picos de gank; wardea trinomio."],
    "Irelia":     ["No la dejes stackear pasiva — ataca minions para resetearla.",
                   "Q resetea si mata — aléjate de minions bajos de vida en tu zona.",
                   "Su R bloquea proyectiles; usa tu CC durante las pausas de la ult."],
    "Lee Sin":    ["Wardea tus entradas de jungla nivel 2 — puede invadir muy pronto.",
                   "Su Q necesita segundo click — si no lo confirma, pierde la carga.",
                   "Post-6, no te pongas cerca de aliados o te usará de insec."],
    "Graves":     ["Sus perdigones hacen daño en cono — aléjate en diagonal, no en línea.",
                   "Su dash no funciona hacia obstáculos (muros) — úsalos para cortarle.",
                   "Evita el humo de E (W); reduce rango de vision y ralentiza."],
    "Kha'Zix":    ["Separarse del equipo lo hace más peligroso — mantente agrupado.",
                   "Cada evo le da herramientas distintas; aprende qué evolucionó primero.",
                   "Su W (salto largo) está disponible sin minions cerca — no te confíes en lane."],
    "Nasus":      ["Ralentizale el farmeo de Q con poke constante los primeros 10 min.",
                   "Post-15 min no pelee con él en un duel — escala infinitamente.",
                   "Su R tiene una duración corta — kítalo o manda CC hasta que expire."],
    "Tryndamere": ["Su R dura 5s — CC y corre, no lo termines dentro de ult.",
                   "Nivel 11 (ult 2 veces) es su pico — juega cerca de tower.",
                   "Su furia (barrita) aumenta su CR; no lo dejes acumular sin pegarle."],
    "Fiora":      ["Sus Vitals cambian de lado 4 veces; aprende su patrón para quitarlos.",
                   "Su R requiere golpear los 4 vitals — bórdalo con cuerpo a cuerpo."],
    "Camille":    ["Su E (gancho + dash) tiene un gap de 0.75s entre las dos partes — evade el segundo.",
                   "Su R la encierra contigo sola — flash por la pared antes de que caiga."],
    "Renekton":   ["Matchup de rabia: cuando tenga barra llena (50+) no tradees.",
                   "Su W (combo de aturdimiento) requiere un hit previo — aléjate cuando se active."],
    "Gangplank":  ["Sus barriles tienen 2 cargas por defecto — elimina el primero antes de que encadene.",
                   "Su E le quita CC activos — úsalos durante su ult para el mínimo daño."],
    "Malphite":   ["Full AP Malphite: trátalo como un mago disfrazado de tanque.",
                   "Su R tiene CC de área — no estés agrupado contra él en teamfights."],
    "Morgana":    ["Su W tiene un delay de 0.5s — side-step apenas lo empiece a lanzar.",
                   "Su escudo (E) bloquea CCs; no gastes tu CC hard mientras esté activo."],
    "Leona":      ["No pelear cuando su Eclipse (W) está activo — dura 3s.",
                   "Su Q (stun) requiere que su E haya llegado primero — ve el orden."],
    "Nautilus":   ["Su gancho Q marca — si falla, tiene un gran cooldown.",
                   "Su auto-ataque ancla (pasiva) — no autoataquees en trades cortos si son malos."],
    "Jinx":       ["Sin cargas de pasiva es un objetivo fácil — mátala antes de que empiece a resetear.",
                   "Sus minas (E) duran 5s en el suelo — camina por los lados de la wave."],
    "Caitlyn":    ["Sus trampas (W) se colocan tras stuns — ward los arbustos y no pases sobre ellas.",
                   "Su ult puede ser bloqueada por un aliado entre tú y ella."],
    "Ezreal":     ["Su E es su único escape — fórzalo con CC y luego all-in.",
                   "Su Q tiene rango muy largo — no hagas línea recta en poke wars."],
    "Orianna":    ["La pelota está siempre en algún lugar — saber dónde es el 80% del matchup.",
                   "Su R en pelota lanzada — alejarse del centro es la defensa más efectiva."],
    "Syndra":     ["Sus bolas permanecen en el mapa — su R hace más daño cuantas más tenga.",
                   "Su E aturde si una bola está detrás del target — no te pongas entre bolas y ella."],
    "Ahri":       ["Puede hacer charm en W; el Q pasa dos veces — la vuelta hace más daño.",
                   "Sin R (3 dashes) es muy vulnerable — countergankea post ult."],
    "Leblanc":    ["Su W deja un espejo — si no pone puntos en W empuja, si no regresa.",
                   "Con silencio le cortas la cadena de burst — úsalo antes de su Q."],
    "Katarina":   ["Sus daggers en el suelo la resetean — evita quedarte cerca de ellas.",
                   "CC en el momento del dash la interrumpe completamente."],
    "Akali":      ["Su campo de humo (W) la hace invisible — usa AoE para forzarla a salir.",
                   "Su R primer dash no hace daño — el segundo sí; flash tras el primero."],
    "Qiyana":     ["Sus elementos cambian su kit — el Q con río aturde, con árbol hace daño extra.",
                   "Su R explota con colisión de estructuras y ríos; cuida los bordes del mapa."],
    "Rengar":     ["Ward los arbustos antes de que llegue al 6; predice de qué arbusto sale.",
                   "Su pasiva (stack) aumenta su kit — hazle usar habilidades sin stacks completos."],
    "Evelynn":    ["Invisible post-6 salvo anti-invis — itemiza Oráculo de la Trampa (pink ward).",
                   "Su alurt aturde si la segunda parte impacta — sal del área con flash."],
    "Shaco":      ["Sus cajas (W) se activan por aparición repentina — no entres en arbustos sin ward.",
                   "Puede clonar con R — el real tiene HP diferente en el número del score."],
    "Nidalee":    ["Sus javelinas hacen más daño a distancia — ángulate para reducir la distancia.",
                   "En forma de puma su Q cura — actívala cuando tenga vida baja."],
    "Hecarim":    ["Su fantasma de invocador sube su movespeed para E — no lo persiga en línea recta.",
                   "Su R tiene fear de área — agrúpate lejos de walls para evitar el empuje."],
    "Warwick":    ["Su W (rastrear heridos) se activa en <50% HP — juega conservador en esa zona.",
                   "Su R es suppressión de canal — QSS lo rompe o flash pre-R."],
}


def obtener_tip_matchup(enemigo: str) -> str:
    """Devuelve el primer tip relevante para el matchup dado, o cadena vacía si no hay."""
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
            if widget is not None: widget.deleteLater()
            else: clear_layout(item.layout())

# ─── CONFIGURACION DE USUARIO ──────────────────────────────────────
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

CONFIG_DIR = _get_writable_dir()

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
    except: return False

class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings.copy()
        self.setWindowTitle("NEXUS — Configuración")
        self.resize(470, 540)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {BG_DARK}; }}
            QLabel {{ color: {TEXT_WHITE}; font-size: 12px; background: transparent; }}
            QRadioButton {{ color: {TEXT_WHITE}; font-size: 12px; spacing: 6px; padding: 6px 4px; }}
            QRadioButton::indicator {{ width: 18px; height: 18px; }}
            QRadioButton::indicator:checked {{ background-color: {BORDER_ACCENT}; border-radius: 9px; }}
            QRadioButton:hover {{ background-color: #1a2744; border-radius: 4px; }}
            QCheckBox {{ color: {TEXT_WHITE}; font-size: 12px; spacing: 8px; padding: 2px 0; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; }}
            QCheckBox:hover {{ color: {BORDER_ACCENT}; }}
            QComboBox {{ background-color: #1a2b4c; color: {TEXT_WHITE}; border: 1px solid #2a3050; border-radius: 4px; padding: 4px 8px; min-width: 50px; }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox:hover {{ border: 1px solid {BORDER_ACCENT}; }}
            QGroupBox {{ color: {BORDER_ACCENT}; font-weight: bold; font-size: 12px; border: 1px solid #1e3050; border-radius: 6px; margin-top: 8px; padding-top: 14px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 6px; }}
            QPushButton {{ color: white; }}
        """)
        layout = QVBoxLayout(self); layout.setSpacing(4)

        title = QLabel("⚙️ CONFIGURACIÓN")
        title.setStyleSheet(f"color: {BORDER_ACCENT}; font-weight: bold; font-size: 18px; padding: 6px 0 2px 0;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_w = QWidget()
        scroll_w.setStyleSheet("background: transparent;")
        form = QVBoxLayout(scroll_w)
        form.setSpacing(2)
        form.setContentsMargins(0, 0, 0, 0)

        def _seccion(texto):
            gb = QGroupBox(texto)
            gl = QVBoxLayout(gb)
            gl.setSpacing(3)
            form.addWidget(gb)
            return gl

        def _desc(texto):
            lbl = QLabel(texto)
            lbl.setStyleSheet("color: #64748b; font-size: 11px; padding-left: 2px;")
            lbl.setWordWrap(True)
            return lbl

        # ── 1. ¿CUÁNTA AYUDA QUIERES? ──
        g_modo = _seccion("🎯 MODO DE AYUDA")
        self.rb_basico = QRadioButton("🟢 Básico — Todo explicado, guiado paso a paso")
        self.rb_normal = QRadioButton("🟡 Normal — Datos útiles sin vueltas, ideal para la mayoría")
        self.rb_avanzado = QRadioButton("🔴 Avanzado — Análisis táctico completo, tú decides")

        self.grupo_modo = QButtonGroup(self)
        self.grupo_modo.addButton(self.rb_basico, 1)
        self.grupo_modo.addButton(self.rb_normal, 2)
        self.grupo_modo.addButton(self.rb_avanzado, 3)

        modo_actual = "normal"
        if self.settings.get("modo_principiante", False): modo_actual = "basico"
        elif self.settings.get("modo_profesional", False): modo_actual = "avanzado"

        if modo_actual == "basico":
            self.rb_basico.setChecked(True)
        elif modo_actual == "avanzado":
            self.rb_avanzado.setChecked(True)
        else:
            self.rb_normal.setChecked(True)

        self.grupo_modo.buttonClicked.connect(lambda btn: setattr(self, '_modo',
            'basico' if btn == self.rb_basico else 'avanzado' if btn == self.rb_avanzado else 'normal'))
        self._modo = modo_actual

        g_modo.addWidget(self.rb_basico)
        g_modo.addWidget(self.rb_normal)
        g_modo.addWidget(self.rb_avanzado)
        self._lbl_modo_desc = _desc(
            "Básico: explicaciones amplias y tooltips grandes. "
            "Normal: información compacta pero completa. "
            "Avanzado: solo datos crudos, máximo rendimiento visual."
        )
        g_modo.addWidget(self._lbl_modo_desc)

        # ── 2. TECLA DE FLASH ──
        g_flash = _seccion("⌨️ TECLA DE FLASH")
        fl = QHBoxLayout()
        fl.addWidget(QLabel("¿En qué tecla tienes Flash?"))
        self.cb_flash_tecla = QComboBox()
        self.cb_flash_tecla.addItems(["D", "F"])
        self.cb_flash_tecla.setCurrentText("D" if self.settings.get("flash_en_d", True) else "F")
        fl.addWidget(self.cb_flash_tecla)
        fl.addStretch()
        g_flash.addLayout(fl)

        # ── 3. IMPORTACIÓN AUTOMÁTICA ──
        g_auto = _seccion("🤖 IMPORTACIÓN AUTOMÁTICA")
        g_auto.addWidget(_desc(
            "Al elegir un campeón en Champ Select, NEXUS puede importar "
            "automáticamente estas configuraciones al cliente de LoL."
        ))
        self.cb_auto_runas = QCheckBox("📜 Importar runas automáticamente")
        self.cb_auto_runas.setChecked(self.settings.get("auto_runas", False))
        self.cb_auto_runas.setToolTip("Crea una página de runas con la configuración recomendada para tu campeón.")
        g_auto.addWidget(self.cb_auto_runas)

        self.cb_auto_hechizos = QCheckBox("✨ Importar hechizos automáticamente")
        self.cb_auto_hechizos.setChecked(self.settings.get("auto_hechizos", False))
        self.cb_auto_hechizos.setToolTip("Selecciona los hechizos recomendados (respeta tu tecla de Flash).")
        g_auto.addWidget(self.cb_auto_hechizos)

        self.cb_auto_habilidades = QCheckBox("⚡ Importar orden de habilidades automáticamente")
        self.cb_auto_habilidades.setChecked(self.settings.get("auto_habilidades", False))
        self.cb_auto_habilidades.setToolTip("Configura el orden de skills Q>E>W según la recomendación.")
        g_auto.addWidget(self.cb_auto_habilidades)

        self.cb_auto_items = QCheckBox("🛡️ Crear set de objetos automáticamente")
        self.cb_auto_items.setChecked(self.settings.get("auto_items", False))
        self.cb_auto_items.setToolTip("Crea un set de objetos con el core build y early game recomendados.")
        g_auto.addWidget(self.cb_auto_items)

        # ── 4. OVERLAY ──
        g_overlay = _seccion("🖥️ OVERLAY IN-GAME")
        self.cb_overlay = QCheckBox("📡 Mostrar overlay flotante durante la partida (KDA, CS, jugadores)")
        self.cb_overlay.setChecked(self.settings.get("overlay_ingame", False))
        self.cb_overlay.setToolTip("Ventana flotante sobre el juego con tu KDA, CS y estado de todos los jugadores.\nAtajo: Ctrl+Shift+I para mostrar/ocultar.")
        g_overlay.addWidget(self.cb_overlay)

        # ── 5. COMPORTAMIENTO ──
        g_comp = _seccion("🎮 COMPORTAMIENTO")
        self.cb_auto_switch = QCheckBox("🔄 Cambiar automáticamente a la pestaña Radar en Champ Select")
        self.cb_auto_switch.setChecked(self.settings.get("auto_switch_radar", True))
        self.cb_auto_switch.setToolTip("NEXUS cambiará a Radar en Vivo cuando detecte una sesión de draft.")
        g_comp.addWidget(self.cb_auto_switch)

        self.cb_auto_aceptar = QCheckBox("✅ Auto-aceptar partida (ReadyCheck)")
        self.cb_auto_aceptar.setChecked(self.settings.get("auto_aceptar", False))
        self.cb_auto_aceptar.setToolTip("Acepta automáticamente cuando salta la cola. ¡No te pierdas partidas!")
        g_comp.addWidget(self.cb_auto_aceptar)

        # Frecuencia del radar
        freq_layout = QHBoxLayout()
        freq_layout.addWidget(QLabel("Frecuencia del radar:"))
        self.slider_freq = QSlider(Qt.Horizontal)
        self.slider_freq.setRange(500, 3000)
        self.slider_freq.setSingleStep(250)
        self.slider_freq.setValue(self.settings.get("frecuencia_radar", 1500))
        self.slider_freq.setToolTip("Cada cuántos ms se actualiza el Radar en Vivo.")
        freq_layout.addWidget(self.slider_freq)
        self.lbl_freq_val = QLabel(f"{self.slider_freq.value()}ms")
        self.lbl_freq_val.setStyleSheet("color: #94a3b8; font-size: 11px; min-width: 50px;")
        self.slider_freq.valueChanged.connect(lambda v: self.lbl_freq_val.setText(f"{v}ms"))
        freq_layout.addWidget(self.lbl_freq_val)
        g_comp.addLayout(freq_layout)

        # ── 6. NOTIFICACIONES ──
        g_notif = _seccion("🔔 NOTIFICACIONES")
        self.cb_sonido = QCheckBox("🔔 Sonidos al conectar, encontrar partida o terminar")
        self.cb_sonido.setChecked(self.settings.get("sonidos", False))
        self.cb_sonido.setToolTip("Avisos sonoros para que sepas qué pasa sin mirar la app.")
        g_notif.addWidget(self.cb_sonido)

        self.cb_notificaciones = QCheckBox("💬 Notificaciones de escritorio (cola, draft, fin de partida)")
        self.cb_notificaciones.setChecked(self.settings.get("notificaciones_escritorio", True))
        self.cb_notificaciones.setToolTip("Muestra avisos emergentes de Windows en eventos clave.")
        g_notif.addWidget(self.cb_notificaciones)

        # ── 7. EXTRAS ──
        g_extra = _seccion("🎨 EXTRAS")
        self.cb_dificultad = QCheckBox("⭐ Estrellas de dificultad en campeones (Garen ⭐, Zed ⭐⭐⭐)")
        self.cb_dificultad.setChecked(self.settings.get("mostrar_dificultad", True))
        self.cb_dificultad.setToolTip("Identifica de un vistazo qué tan difícil es un campeón.")
        g_extra.addWidget(self.cb_dificultad)
        self.cb_recordatorios = QCheckBox("💬 Recordatorios en partida (wardear, objetivos, etc.)")
        self.cb_recordatorios.setChecked(self.settings.get("recordatorios_partida", True))
        self.cb_recordatorios.setToolTip("Consejos que aparecen durante la partida para no perder el foco.")
        g_extra.addWidget(self.cb_recordatorios)

        form.addStretch()
        scroll.setWidget(scroll_w)
        layout.addWidget(scroll, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_settings(self):
        return {"auto_deteccion": True,
                "mostrar_power_spikes": self._modo != "avanzado",
                "mostrar_explicaciones": self._modo == "basico",
                "sonidos": self.cb_sonido.isChecked(),
                "frecuencia_radar": self.slider_freq.value(),
                "modo_principiante": self._modo == "basico",
                "modo_profesional": self._modo == "avanzado",
                "recordatorios_partida": self.cb_recordatorios.isChecked(),
                "mostrar_dificultad": self.cb_dificultad.isChecked(),
                "tooltips_grandes": self._modo == "basico",
                "flash_en_d": self.cb_flash_tecla.currentText() == "D",
                "auto_runas": self.cb_auto_runas.isChecked(),
                "auto_hechizos": self.cb_auto_hechizos.isChecked(),
                "auto_habilidades": self.cb_auto_habilidades.isChecked(),
                "auto_items": self.cb_auto_items.isChecked(),
                "auto_switch_radar": self.cb_auto_switch.isChecked(),
                "auto_aceptar": self.cb_auto_aceptar.isChecked(),
                "overlay_ingame": self.cb_overlay.isChecked(),
                "notificaciones_escritorio": self.cb_notificaciones.isChecked(),
                }

# ═══════════════════════════════════════════════════════════════
# FILOSOFÍA DE JUEGO — Basado en el Curso de Bienestar y Aprendizaje
# ═══════════════════════════════════════════════════════════════

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
        <p style="font-size:11px; color:#cbd5e1; margin:0; line-height:1.5;">{principios[idx]}</p>
        </div>"""
    
    return f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;line-height:1.6;">
    <p style="font-size:12px;color:#c084fc;margin:0 0 10px 0;">
    💡 <b>Antes de ver tus números, quiero compartirte algo importante.</b> 
    Estas ideas me ayudaron a mí y a cientos de jugadores a pensar mejor el juego. No son reglas rígidas, son principios que puedes comprobar tú mismo.
    </p>
    {partes_html}
    <p style="font-size:10px;color:#64748b;margin:10px 0 0 0;font-style:italic;">
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
    <p style="font-size:14px;color:#a78bfa;margin:0 0 8px 0;"><b>🦾 Tu ejercicio de práctica deliberada</b></p>
    <p style="font-size:12px;color:#cbd5e1;margin:0 0 8px 0;">
    {nombre}, la <b>práctica deliberada</b> es aislar UNA habilidad y trabajarla con intención. 
    No se trata de jugar más partidas: se trata de que cada una tenga un propósito claro.
    Jugar en automático no enseña. Jugar con foco en algo específico, sí.
    </p>
    <p style="font-size:12px;color:#f1f5f9;margin:0 0 4px 0;"><b>🎯 Esta semana practica: {habilidad}</b></p>
    <div style="background:#1a1525;border-radius:6px;padding:10px 14px;margin:8px 0;">
    <p style="font-size:11px;color:#a78bfa;margin:0 0 4px 0;"><b>📚 1. Aprende la teoría</b></p>
    <p style="font-size:11px;color:#cbd5e1;margin:0 0 8px 0;">{teoria}</p>
    <p style="font-size:11px;color:#a78bfa;margin:0 0 4px 0;"><b>🎮 2. Aplica activamente</b></p>
    <p style="font-size:11px;color:#cbd5e1;margin:0 0 8px 0;">{practica}</p>
    <p style="font-size:11px;color:#a78bfa;margin:0 0 4px 0;"><b>🔍 3. Revisa y ajusta</b></p>
    <p style="font-size:11px;color:#cbd5e1;margin:0 0 0 0;">{revision}</p>
    </div>
    <p style="font-size:11px;color:#64748b;margin:8px 0 0 0;">
    💡 Dato: jugar 3 partidas con foco en UNA habilidad enseña más que 15 partidas en automático. 
    El cerebro aprende cuando prestas atención, no cuando repites sin pensar.
    </p>
    </div>"""


def _generar_tips_salud():
    """Genera tips de salud mental y fisiología basados en el curso del coach.
    6 tareas simples: contenido salud mental, movimiento, entorno, descanso vista, manos, hidratación."""
    return f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;line-height:1.7;">
    <p style="font-size:14px;color:#34d399;margin:0 0 8px 0;"><b>💚 6 hábitos simples que mejoran tu juego</b></p>
    <p style="font-size:12px;color:#cbd5e1;margin:0 0 8px 0;">
    Tu rendimiento no depende solo de cómo juegas, sino de <b>cómo estás</b>. 
    Estos micro-hábitos son fáciles de empezar hoy y tienen impacto real en tu concentración.
    </p>
    <div style="background:#0d1f17;border-radius:6px;padding:10px 14px;margin:8px 0;">
    <p style="font-size:11px;color:#cbd5e1;margin:2px 0;"><b>🌱 Día a día</b></p>
    <p style="font-size:11px;color:#94a3b8;margin:0 0 2px 12px;">• 5 min de contenido sobre salud mental (puede ser un video, un artículo).</p>
    <p style="font-size:11px;color:#94a3b8;margin:0 0 2px 12px;">• 6 min de movimiento físico diario (mejor poco y constante que nada).</p>
    <p style="font-size:11px;color:#cbd5e1;margin:8px 0 2px;"><b>🎓 Antes de jugar</b></p>
    <p style="font-size:11px;color:#94a3b8;margin:0 0 2px 12px;">• Elimina distracciones: silencia notificaciones, aleja el celular, cierra redes sociales.</p>
    <p style="font-size:11px;color:#94a3b8;margin:0 0 2px 12px;">• Prepara tu espacio: escritorio limpio, agua cerca, periféricos cómodos.</p>
    <p style="font-size:11px;color:#cbd5e1;margin:8px 0 2px;"><b>🧾 Durante el juego</b></p>
    <p style="font-size:11px;color:#94a3b8;margin:0 0 2px 12px;">• Cada 10-15 min: suelta mouse/teclado, estira los dedos y las muñecas.</p>
    <p style="font-size:11px;color:#94a3b8;margin:0 0 2px 12px;">• En momentos tranquilos: mira a lo lejos unos segundos para descansar la vista.</p>
    </div>
    <p style="font-size:11px;color:#64748b;margin:8px 0 0 0;">
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
    <p style="font-size: 16px; color: #f1f5f9; margin: 0 0 8px 0;"><b>👋 ¡Hola, {nombre}!</b></p>
    <p style="font-size: 13px; color: #cbd5e1; margin: 0 0 12px 0;">{tono}</p>
    <p style="font-size: 12px; color: #94a3b8; margin: 0 0 4px 0;">
    📊 <b>{total}</b> partidas analizadas · WR <b style="color:{'#22c55e' if wr >= 50 else '#ef4444'};">{wr:.0f}%</b> · 
    KDA <b>{avg_k:.0f}/{avg_d:.0f}/{avg_a:.0f}</b> · CS/min <b>{avg_cs:.1f}</b>
    </p>
    <p style="font-size: 12px; color: #94a3b8; margin: 0 0 0 0;">{estado_mental}</p>
    </div>
    """
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 0.5: FILOSOFÍA DE JUEGO (basado en el curso del coach)
    # ═══════════════════════════════════════════════════
    filo_html = _generar_filosofia_juego(nombre, nivel, wr, avg_d, total)
    secciones.append({
        "titulo": "FILOSOFÍA DE JUEGO — Tu Mentalidad",
        "icono": "🧘",
        "color": "#c084fc",
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
        <p style="font-size: 14px; color: #f59e0b; margin: 0 0 8px 0;"><b>⚠️ Estás jugando demasiados campeones ({unique_champs} en {total} partidas)</b></p>
        <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
        Esto es lo que pasa: tu cerebro gasta energía adaptándose a cada campeón en vez de enfocarse en el mapa. 
        <b style="color: #22c55e;">Tu WR con tu top 3 es {top3_wr:.0f}%</b>, pero con el resto cae a 
        <b style="color: #ef4444;">{rest_wr:.0f}%</b>. Esa diferencia son partidas que regalas.
        </p>
        <p style="font-size: 12px; color: #f1f5f9; margin: 0 0 4px 0;"><b>🎯 Plan de acción:</b></p>
        <ul style="margin: 4px 0; padding-left: 18px; color: #cbd5e1; font-size: 12px;">
        <li>Elige <b>2 campeones principales</b> y 1 de reserva. Juega solo esos durante 2 semanas.</li>
        <li>Tus picks deben <b>compartir estilo de juego</b> (coherencia mecánica): así las habilidades se transfieren y el aprendizaje se acumula.</li>
        <li>Idealmente, que <b>se cubran entre sí</b>: si te pickean tu main, que el otro sea una buena respuesta.</li>
        <li>Si quieres probar algo nuevo, hazlo en normals, no en ranked.</li>
        <li>La consistencia gana más partidas que el counterpick perfecto.</li>
        </ul>
        """
    else:
        cp_html += f"""
        <p style="font-size: 14px; color: #22c55e; margin: 0 0 8px 0;"><b>✅ Pool de campeones enfocada ({unique_champs} distintos)</b></p>
        <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
        Buena disciplina. Mantener un pool reducido y coherente te permite dominar matchups y concentrarte en el macro.
        Tus picks deben <b>compartir patrones de gameplay</b>: así las mecánicas se transfieren, el aprendizaje se acumula
        y cambiar de campeón se siente natural. Tu WR con tu top 3 es <b style="color: #22c55e;">{top3_wr:.0f}%</b>. Así se construye el elo.
        </p>
        """
    
    # Mostrar top 3 con stats
    cp_html += '<p style="font-size: 12px; color: #94a3b8; margin: 8px 0 4px 0;"><b>Tu top 3:</b></p>'
    for i, (champ_name, cs_data) in enumerate(top3):
        c_wr = (cs_data["wins"] / cs_data["games"] * 100) if cs_data["games"] > 0 else 0
        c_kda = (cs_data["kills"] + cs_data["assists"]) / max(1, cs_data["deaths"])
        c_cs = cs_data["cs"] / max(1, cs_data["games"])
        color_wr = "#22c55e" if c_wr >= 50 else "#ef4444"
        cp_html += f'<p style="font-size: 11px; color: {color_wr}; margin: 2px 0 2px 12px;">{i+1}. {champ_name} — {c_wr:.0f}% WR · KDA {c_kda:.1f} · {cs_data["games"]} partidas</p>'
    
    cp_html += '</div>'
    
    secciones.append({
        "titulo": "AUDITORÍA DE CHAMPION POOL",
        "icono": "📋",
        "color": "#f59e0b" if is_too_wide else "#22c55e",
        "html": cp_html,
        "prioridad": 1 if is_too_wide else 3,
    })
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 2: FASE DE LÍNEAS (CS + EARLY)
    # ═══════════════════════════════════════════════════
    cs_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
    
    if avg_cs < 4.5:
        cs_html += f"""
        <p style="font-size: 14px; color: #ef4444; margin: 0 0 8px 0;"><b>🔴 Tu farmeo necesita atención urgente: {avg_cs:.1f} CS/min</b></p>
        <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
        Mira, {nombre}, esto es lo más importante que puedes mejorar ahora mismo. Cada 15-20 CS equivalen a 
        <b>una kill en oro</b>. Si farmeas mejor, llegarás a tus objetos más rápido sin necesidad de arriesgarte en peleas.
        </p>
        <p style="font-size: 12px; color: #f1f5f9; margin: 0 0 4px 0;"><b>🎯 Ejercicio concreto:</b></p>
        <ul style="margin: 4px 0; padding-left: 18px; color: #cbd5e1; font-size: 12px;">
        <li>Entra al <b>Practice Tool</b> 10 minutos al día.</li>
        <li>Elige tu campeón principal, <b>sin objetos ni runas de daño</b>.</li>
        <li>Solo last-hit. Nada de habilidades. Apunta a 36 CS a los 5 min (6/min).</li>
        <li>Cuando llegues a 70 CS en 10 min consistentemente, empieza a añadir trades contra un bot.</li>
        </ul>
        <p style="font-size: 11px; color: #64748b; margin: 8px 0 0 0;">💡 Dato: Un campeón con 150 CS a los 20 min tiene el mismo oro que uno con 50 CS y 5 kills. El CS es seguro, las kills no.</p>
        """
    elif avg_cs < 6.5:
        cs_html += f"""
        <p style="font-size: 14px; color: #f59e0b; margin: 0 0 8px 0;"><b>🟡 Farmeo decente pero con margen de mejora: {avg_cs:.1f} CS/min</b></p>
        <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
        No está mal, {nombre}, pero cada CS que pierdes es oro que dejas en la mesa. En partidas igualadas, 
        la diferencia entre 6 y 7.5 CS/min puede ser completar un objeto clave 3 minutos antes.
        </p>
        <p style="font-size: 12px; color: #f1f5f9; margin: 0 0 4px 0;"><b>🎯 Plan:</b></p>
        <ul style="margin: 4px 0; padding-left: 18px; color: #cbd5e1; font-size: 12px;">
        <li>En los primeros 10 min, prioriza <b>NO perder CS</b> sobre tradear.</li>
        <li>Aprende a farmear bajo torre: melé = 2 torre + 1 auto, caster = 1 auto + torre + 1 auto.</li>
        <li>En mid-late, no dejes que las oleadas mueran solas: rotan entre líneas para absorber oro.</li>
        </ul>
        """
    else:
        cs_html += f"""
        <p style="font-size: 14px; color: #22c55e; margin: 0 0 8px 0;"><b>🟢 Excelente farmeo: {avg_cs:.1f} CS/min</b></p>
        <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
        Esto es nivel alto, {nombre}. Tu economía early es sólida y llegas a tus poderes antes que el rival.
        Asegúrate de traducir esa ventaja de oro en presión en el mapa: rotaciones, visión agresiva y objetivos.
        </p>
        """
    
    # First blood
    if primer_sangre >= total * 0.3:
        cs_html += f'<p style="font-size: 11px; color: #22c55e; margin: 8px 0 0 0;">⚔️ Además, consigues First Blood en el {primer_sangre/total*100:.0f}% de tus partidas. ¡Agresividad bien ejecutada!</p>'
    
    cs_html += '</div>'
    
    secciones.append({
        "titulo": "RENDIMIENTO EN FASE DE LÍNEAS",
        "icono": "⚔️",
        "color": "#ef4444" if avg_cs < 5 else "#f59e0b" if avg_cs < 6.5 else "#22c55e",
        "html": cs_html,
        "prioridad": 0 if avg_cs < 5 else 2,
    })
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 3: SUPERVIVENCIA Y DECISIONES
    # ═══════════════════════════════════════════════════
    sv_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
    
    if avg_d > 7:
        sv_html += f"""
        <p style="font-size: 14px; color: #ef4444; margin: 0 0 8px 0;"><b>🔴 Mueres demasiado: {avg_d:.1f} muertes por partida</b></p>
        <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
        {nombre}, esta es la estadística que más te está frenando. Cada muerte le da <b>300g + asistencia</b> al enemigo. 
        En 20 partidas con {avg_d:.0f} muertes de media, has regalado aproximadamente <b>{int(avg_d * 300 * total)} de oro</b>.
        Eso son varios objetos completos.
        </p>
        <p style="font-size: 12px; color: #f1f5f9; margin: 0 0 4px 0;"><b>🎯 Reglas de oro:</b></p>
        <ul style="margin: 4px 0; padding-left: 18px; color: #cbd5e1; font-size: 12px;">
        <li><b>Regla de las 2 muertes:</b> si mueres 2 veces en lane, deja de tradear. Farma bajo torre y espera a tu jungla.</li>
        <li>Antes de pushear una línea lateral, pregúntate: ¿sé dónde están los 5 enemigos? Si la respuesta es no, no pases del río.</li>
        <li>Compra un <b>Control Ward</b> cada vez que vuelvas a base. 75g que te salvan de regalar 300g.</li>
        </ul>
        """
    elif avg_d > 5:
        sv_html += f"""
        <p style="font-size: 14px; color: #f59e0b; margin: 0 0 8px 0;"><b>🟡 Tus muertes son mejorables: {avg_d:.1f} por partida (KDA {kda:.1f})</b></p>
        <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
        No es dramático, {nombre}, pero reducir tus muertes a 4 o menos por partida puede subir tu WR 5-10% 
        sin cambiar nada más de tu juego.
        </p>
        <p style="font-size: 12px; color: #f1f5f9; margin: 0 0 4px 0;"><b>🎯 Claves:</b></p>
        <ul style="margin: 4px 0; padding-left: 18px; color: #cbd5e1; font-size: 12px;">
        <li>Wardea antes de pushear, no mientras.</li>
        <li>Si no ves al jungla enemigo en el mapa, asume que está en tu línea.</li>
        <li>En teamfights, identifica qué habilidad enemiga NO debes recibir y juega alrededor de eso.</li>
        </ul>
        """
    else:
        sv_html += f"""
        <p style="font-size: 14px; color: #22c55e; margin: 0 0 8px 0;"><b>🟢 Buen control de muertes: {avg_d:.1f} por partida (KDA {kda:.1f})</b></p>
        <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
        Muy bien, {nombre}. Mantener baja tu tasa de muertes es señal de buen juicio. 
        Cada muerte que evitas son 300g que no regalas. Sigue así.
        </p>
        """
    
    sv_html += '</div>'
    
    secciones.append({
        "titulo": "TOMA DE DECISIONES Y SUPERVIVENCIA",
        "icono": "🛡️",
        "color": "#ef4444" if avg_d > 7 else "#f59e0b" if avg_d > 5 else "#22c55e",
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
            <p style="font-size: 14px; color: #ef4444; margin: 0 0 8px 0;"><b>🔴 Visión muy baja: {avg_vision:.1f}/min</b></p>
            <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
            La visión es información, y la información gana partidas. Con {avg_vision:.1f} de visión por minuto, 
            estás jugando a ciegas gran parte del tiempo. Cada ward es un "no me matan" potencial.
            </p>
            <p style="font-size: 12px; color: #f1f5f9; margin: 0 0 4px 0;"><b>🎯 Hábito a crear:</b></p>
            <ul style="margin: 4px 0; padding-left: 18px; color: #cbd5e1; font-size: 12px;">
            <li>Cada vez que vuelvas a base, compra al menos 1 Control Ward.</li>
            <li>Usa el trinket en cuanto esté disponible. No lo guardes.</li>
            <li>Mira el minimapa cada 5 segundos. Suena intenso, pero se convierte en hábito.</li>
            </ul>
            """
        elif avg_vision < 1.0:
            vis_html += f"""
            <p style="font-size: 14px; color: #f59e0b; margin: 0 0 8px 0;"><b>🟡 Visión aceptable: {avg_vision:.1f}/min</b></p>
            <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
            No está mal, pero los mejores jugadores suelen estar por encima de 1.5/min en soloQ. 
            Un buen objetivo es comprar 2-3 Control Wards por partida.
            </p>
            """
        else:
            vis_html += f"""
            <p style="font-size: 14px; color: #22c55e; margin: 0 0 8px 0;"><b>🟢 Buena visión: {avg_vision:.1f}/min</b></p>
            <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
            Excelente control de visión. Eso ayuda a tu equipo más de lo que crees. ¡Sigue así!
            </p>
            """
        vis_html += '</div>'
        
        secciones.append({
            "titulo": "CONTROL DE VISIÓN",
            "icono": "👁️",
            "color": "#ef4444" if avg_vision < 0.5 else "#f59e0b" if avg_vision < 1.0 else "#22c55e",
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
                    <p style="font-size: 14px; color: #ef4444; margin: 0 0 8px 0;"><b>🔴 Llevas {total_sesion} partidas en esta sesión con {wr_sesion:.0f}% WR</b></p>
                    <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
                    {nombre}, los datos son claros: tu rendimiento baja drásticamente en sesiones largas. 
                    Llevas {total_sesion} partidas seguidas. Tu cerebro está fatigado aunque no lo notes.
                    </p>
                    <p style="font-size: 12px; color: #f1f5f9; margin: 0 0 4px 0;"><b>🧠 Lo que dice la ciencia:</b></p>
                    <p style="font-size: 11px; color: #94a3b8; margin: 0 0 8px 0;">
                    Después de 90-120 minutos de juego intenso, tu tiempo de reacción y toma de decisiones 
                    se degradan significativamente. Los jugadores profesionales rotan entre partidas y descansos por esto.
                    </p>
                    <p style="font-size: 12px; color: #f1f5f9; margin: 0 0 4px 0;"><b>🎯 Mi recomendación:</b></p>
                    <ul style="margin: 4px 0; padding-left: 18px; color: #cbd5e1; font-size: 12px;">
                    <li>Termina esta sesión ya. Levántate, hidrátate, descansa al menos 30 minutos.</li>
                    <li>Establece un límite: 3 partidas, luego pausa obligatoria de 15-30 min.</li>
                    <li>Si pierdes 2 seguidas, para. No hay recuperación milagrosa en la tercera.</li>
                    </ul>
                    """
                elif wr_sesion >= 60:
                    fat_html += f"""
                    <p style="font-size: 14px; color: #22c55e; margin: 0 0 8px 0;"><b>🔥 Buen momento: {wr_sesion:.0f}% WR en {total_sesion} partidas</b></p>
                    <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
                    Estás en racha, {nombre}. Pero recuerda: incluso en una buena sesión, 
                    tu concentración tiene un límite. Programa un descanso pronto para mantener el nivel.
                    </p>
                    """
                else:
                    fat_html += f"""
                    <p style="font-size: 14px; color: #f1f5f9; margin: 0 0 8px 0;"><b>⚖️ Sesión estable: {wr_sesion:.0f}% WR en {total_sesion} partidas</b></p>
                    <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
                    Rendimiento consistente. Vigila cómo te sientes y no dudes en parar si notas fatiga mental.
                    </p>
                    """
                
                if partidas_hoy:
                    wins_hoy = sum(1 for p in partidas_hoy if p.get("win", False))
                    wr_hoy = (wins_hoy / len(partidas_hoy) * 100) if partidas_hoy else 0
                    fat_html += f'<p style="font-size: 11px; color: #64748b; margin: 8px 0 0 0;">📅 Hoy: {len(partidas_hoy)} partidas · {wr_hoy:.0f}% WR</p>'
                
                fat_html += '</div>'
                
                secciones.append({
                    "titulo": "GESTIÓN DE SESIONES Y FATIGA",
                    "icono": "🧠",
                    "color": "#ef4444" if wr_sesion < 40 else "#22c55e" if wr_sesion >= 60 else "#f59e0b",
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
            <p style="font-size: 14px; color: #ef4444; margin: 0 0 8px 0;"><b>🔴 Llevas {racha_actual} derrotas seguidas</b></p>
            <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
            {nombre}, esto es importante: <b>la mala suerte existe</b>. AFKs, trolls, malos matchups... 
            todo eso pasa y es real. Pero hay dos caminos: puedes enfocarte en lo que no controlas (y frustrarte) 
            o puedes enfocarte en <b>lo que sí depende de ti</b>.
            </p>
            <p style="font-size: 12px; color: #f1f5f9; margin: 0 0 4px 0;"><b>🎯 Qué hacer ahora:</b></p>
            <ul style="margin: 4px 0; padding-left: 18px; color: #cbd5e1; font-size: 12px;">
            <li><b>No juegues en automático.</b> Tómate 5 minutos para respirar antes de la siguiente.</li>
            <li>Pregúntate: ¿Hubo algo que YO podría haber hecho mejor? Incluso en partidas con AFK, siempre hay algo para revisar.</li>
            <li>Si perdiste 2 seguidas, para. No hay recuperación milagrosa en la tercera. Es la trampa más común del LoL.</li>
            </ul>
            <p style="font-size: 11px; color: #64748b; margin: 8px 0 0 0;">📝 Recuerda: <b>todas las partidas son útiles</b>. Rendirse o jugar mal a propósito solo cultiva una mentalidad tóxica que te daña. Incluso en las peores derrotas, siempre hay algo para aprender.</p>
            """
        else:
            racha_html += f"""
            <p style="font-size: 14px; color: #22c55e; margin: 0 0 8px 0;"><b>🔥 ¡{racha_actual} victorias seguidas!</b></p>
            <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
            Excelente momento, {nombre}. Pero no te confíes: <b>el verdadero crecimiento viene de mantener la consistencia</b> 
            incluso cuando las cosas van bien. Disfruta la racha, pero no olvides que cada partida es una nueva oportunidad de aprender.
            </p>
            <p style="font-size: 11px; color: #64748b; margin: 8px 0 0 0;">💡 Dato: los jugadores que más mejoran no son los que ganan más, sino los que <b>analizan tanto sus victorias como sus derrotas</b>.</p>
            """
        racha_html += '</div>'
        
        secciones.append({
            "titulo": "RACHA Y RESILIENCIA",
            "icono": "📈",
            "color": "#ef4444" if racha_tipo == 'L' else "#22c55e",
            "html": racha_html,
            "prioridad": 1 if racha_tipo == 'L' else 4,
        })
    
    # ═══════════════════════════════════════════════════
    # SECCIÓN 5.6: JUGAR POR BLOQUES (método de 3 partidas)
    # ═══════════════════════════════════════════════════
    bloques_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
    bloques_html += f"""
    <p style="font-size: 14px; color: #818cf8; margin: 0 0 8px 0;"><b>🧊 Juega por bloques de 3 partidas</b></p>
    <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">
    Tu concentración <b>tiene un límite</b>. Después de 3-4 partidas seguidas, tu cerebro entra en piloto automático 
    y tomas peores decisiones. No es falta de habilidad: es fatiga mental real.
    </p>
    <p style="font-size: 12px; color: #f1f5f9; margin: 0 0 4px 0;"><b>📊 El método simple:</b></p>
    <ul style="margin: 4px 0; padding-left: 18px; color: #cbd5e1; font-size: 12px;">
    <li>Juega <b>hasta 3 partidas</b> por bloque.</li>
    <li><b>Si pierdes 2 seguidas → corta el bloque.</b> No hay recuperación milagrosa en la tercera.</li>
    <li>Entre bloques: descansa sin LoL (30+ min). Levántate, camina, toma agua.</li>
    <li>Entre partidas: 2-5 min de pausa. Suelta el mouse, estira las manos, mira a lo lejos.</li>
    </ul>
    <p style="font-size: 11px; color: #64748b; margin: 8px 0 0 0;">
    💡 Este sistema hace que tengas más días positivos que negativos. No es frenarte: es <b>administrar tu energía</b>. 
    Las ganas de jugar se acumulan y las aprovechas mejor cuando vuelves fresco.
    </p>
    """
    bloques_html += '</div>'
    
    secciones.append({
        "titulo": "JUGAR POR BLOQUES (3 partidas)",
        "icono": "🧊",
        "color": "#818cf8",
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
        "color": "#a78bfa",
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
        "color": "#34d399",
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


class LPGraphWidget(QWidget):
    """Gráfica de línea LP/MMR usando QPainter nativo — sin dependencias externas."""

    TIER_LABELS = [
        (0,    "Iron"),   (400,  "Bronze"), (800,  "Silver"), (1200, "Gold"),
        (1600, "Plat"),   (2000, "Emerald"),(2400, "Diamond"),(2800, "Master+"),
    ]
    TIER_COLORS = {
        "Iron": "#6b7280", "Bronze": "#b45309", "Silver": "#94a3b8",
        "Gold": "#f59e0b", "Plat": "#14b8a6", "Emerald": "#22c55e",
        "Diamond": "#818cf8", "Master+": "#e879f9",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self.setMinimumHeight(120)

    def set_data(self, history: list):
        self._data = history
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 48, 12, 10, 24

        # Fondo
        p.fillRect(0, 0, w, h, QColor(BG_CARD))

        if not self._data or len(self._data) < 2:
            p.setPen(QColor(TEXT_MUTED))
            p.drawText(0, 0, w, h, Qt.AlignCenter, "Sin datos suficientes (mín. 2 días)")
            p.end()
            return

        values = [d["lp_total"] for d in self._data]
        mn, mx = min(values), max(values)
        rng = max(mx - mn, 200)

        n = len(self._data)
        def to_px(i):
            return pad_l + int(i / max(1, n - 1) * (w - pad_l - pad_r))

        def to_py(val):
            return h - pad_b - int((val - mn) / rng * (h - pad_t - pad_b))

        # Líneas de tier en gris sutil
        p.setFont(QFont("Segoe UI", 7))
        for base, name in self.TIER_LABELS:
            if mn - 100 <= base <= mx + 100:
                py = to_py(base)
                if pad_t <= py <= h - pad_b:
                    p.setPen(QPen(QColor("#1e293b"), 1, Qt.DashLine))
                    p.drawLine(pad_l, py, w - pad_r, py)
                    p.setPen(QColor(self.TIER_COLORS.get(name, "#64748b")))
                    p.drawText(2, py - 6, pad_l - 4, 14, Qt.AlignRight | Qt.AlignVCenter, name)

        # Línea de LP
        points = [(to_px(i), to_py(self._data[i]["lp_total"]))
                  for i in range(len(self._data))]

        pen = QPen(QColor(ACCENT_TEAL), 2)
        p.setPen(pen)
        for i in range(1, len(points)):
            p.drawLine(points[i-1][0], points[i-1][1], points[i][0], points[i][1])

        # Puntos
        p.setPen(Qt.NoPen)
        for i, (px, py) in enumerate(points):
            p.setBrush(QBrush(QColor(ACCENT_TEAL)))
            p.drawEllipse(px - 3, py - 3, 6, 6)

        # Fechas en el eje X (cada ~5 puntos o primero/último)
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(QColor(TEXT_MUTED))
        indices = [0, n - 1] if n <= 4 else list(range(0, n, max(1, n // 4))) + [n - 1]
        for i in set(indices):
            px, _ = points[i]
            fecha_str = self._data[i]["fecha"][5:]  # MM-DD
            p.drawText(px - 18, h - pad_b + 4, 36, 14, Qt.AlignCenter, fecha_str)

        # LP actual en esquina superior derecha
        last = self._data[-1]
        label = f"{last['tier'].title()} {last['division']} {last['lp']} LP"
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.setPen(QColor(ACCENT_TEAL))
        p.drawText(w - 140, pad_t, 136, 16, Qt.AlignRight | Qt.AlignVCenter, label)

        p.end()


class PostGameDialog(QDialog):
    """Resumen rápido al terminar partida: KDA, CS/min, comparativa y consejo del coach."""

    coaching_requested = Signal()

    def __init__(self, stats: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resumen de Partida")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(420)
        self._build_ui(stats)
        if parent:
            pr = parent.frameGeometry()
            self.move(pr.center().x() - self.width() // 2, pr.top() + 80)

    def _build_ui(self, s):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName("pgCard")
        card.setStyleSheet(f"""
            QWidget#pgCard {{
                background: {BG_PANEL};
                border: 2px solid {BORDER_ACCENT};
                border-radius: 10px;
            }}
            QLabel {{ color: {TEXT_WHITE}; background: transparent; }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)

        # Título + resultado
        hdr = QHBoxLayout()
        lbl_title = QLabel("🏁  RESUMEN DE PARTIDA")
        lbl_title.setStyleSheet(f"color: {ACCENT_RED}; font-size: 13px; font-weight: bold; letter-spacing: 1px;")
        hdr.addWidget(lbl_title)
        hdr.addStretch()
        resultado = s.get("resultado", "")
        if resultado == "Victoria":
            lbl_res = QLabel("  VICTORIA  ")
            lbl_res.setStyleSheet(f"background: {GREEN_WR}; color: #fff; font-weight: bold; font-size: 11px; border-radius: 4px; padding: 2px 6px;")
        elif resultado == "Derrota":
            lbl_res = QLabel("  DERROTA  ")
            lbl_res.setStyleSheet(f"background: {RED_WR}; color: #fff; font-weight: bold; font-size: 11px; border-radius: 4px; padding: 2px 6px;")
        else:
            lbl_res = QLabel("")
        hdr.addWidget(lbl_res)
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(20, 20)
        btn_close.setStyleSheet(f"background: transparent; border: none; color: {TEXT_MUTED}; font-size: 12px;")
        btn_close.clicked.connect(self.close)
        hdr.addWidget(btn_close)
        lay.addLayout(hdr)

        sep = QLabel(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER_SUBTLE};")
        lay.addWidget(sep)

        # Campeón
        champ = s.get("champion", "?")
        lbl_champ = QLabel(f"🎮  {champ}")
        lbl_champ.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {ACCENT_TEAL};")
        lay.addWidget(lbl_champ)

        # KDA
        k, d, a = s.get("kills", 0), s.get("deaths", 0), s.get("assists", 0)
        avg_k = s.get("avg_k", 0)
        avg_d = s.get("avg_d", 1)
        avg_a = s.get("avg_a", 0)

        kda_row = QHBoxLayout()
        kda_row.setSpacing(4)
        for val, ref, label, good_high in [(k, avg_k, "K", True), (d, avg_d, "D", False), (a, avg_a, "A", True)]:
            col = GREEN_WR if (val >= ref if good_high else val <= ref) else RED_WR
            lbl = QLabel(f"<b style='color:{col};font-size:22px;'>{val}</b><span style='color:{TEXT_MUTED};font-size:10px;'> {label}</span>")
            lbl.setAlignment(Qt.AlignCenter)
            kda_row.addWidget(lbl)
            if label != "A":
                kda_row.addWidget(QLabel("/"))
        kda_row.addStretch()

        avg_kda_str = f"Tu media: {avg_k:.1f}/{avg_d:.1f}/{avg_a:.1f}"
        lbl_avg = QLabel(avg_kda_str)
        lbl_avg.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        lbl_avg.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        kda_row.addWidget(lbl_avg)
        lay.addLayout(kda_row)

        # CS/min
        cs = s.get("cs", 0)
        game_time = s.get("game_time", 1)
        cs_min = cs / max(1, game_time / 60)
        cs_ref = 6.5
        cs_color = GREEN_WR if cs_min >= cs_ref else (YELLOW_WR if cs_min >= 5.0 else RED_WR)
        lbl_cs = QLabel(f"🌾  CS: {cs}  ({cs_min:.1f}/min)  — ref. {cs_ref}/min")
        lbl_cs.setStyleSheet(f"color: {cs_color}; font-size: 11px;")
        lay.addWidget(lbl_cs)

        # Vision y objetivos
        vision = s.get("vision_score", 0)
        wards = s.get("wards_placed", 0)
        cwards = s.get("control_wards", 0)
        objectives = s.get("objectives", 0)
        dmg = s.get("damage_dealt", 0)
        if game_time > 0:
            dmg_min = dmg / (game_time / 60)
            dmg_str = f"{dmg_min/1000:.1f}k/min" if dmg > 0 else ""
        else:
            dmg_str = ""
        extras = []
        if vision > 0:
            extras.append(f"👁 Vision {vision}")
        if wards > 0:
            extras.append(f"🏮 Wards {wards}")
        if cwards > 0:
            extras.append(f"🔮 Control {cwards}")
        if objectives > 0:
            extras.append(f"🎯 Objs {objectives}")
        if dmg_str:
            extras.append(f"⚔️ Dano {dmg_str}")
        if extras:
            lbl_extras = QLabel("  |  ".join(extras))
            lbl_extras.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; padding: 2px 0;")
            lay.addWidget(lbl_extras)

        # Coaching tip
        tip = s.get("tip", "")
        positives = s.get("positives", [])
        negatives = s.get("negatives", [])

        if positives or negatives:
            sep2 = QLabel(); sep2.setFixedHeight(1)
            sep2.setStyleSheet(f"background: {BORDER_SUBTLE};")
            lay.addWidget(sep2)

            if positives:
                for pt in positives:
                    lbl_p = QLabel(pt)
                    lbl_p.setWordWrap(True)
                    lbl_p.setStyleSheet(f"color: {GREEN_WR}; font-size: 10px; padding: 1px 0;")
                    lay.addWidget(lbl_p)

            if negatives:
                for ng in negatives:
                    lbl_n = QLabel(ng)
                    lbl_n.setWordWrap(True)
                    lbl_n.setStyleSheet(f"color: {RED_WR}; font-size: 10px; padding: 1px 0;")
                    lay.addWidget(lbl_n)

        if tip:
            sep3 = QLabel(); sep3.setFixedHeight(1)
            sep3.setStyleSheet(f"background: {BORDER_SUBTLE};")
            lay.addWidget(sep3)
            lbl_tip = QLabel(tip)
            lbl_tip.setWordWrap(True)
            lbl_tip.setStyleSheet(f"color: {YELLOW_WR}; font-size: 10px; padding: 4px 0;")
            lay.addWidget(lbl_tip)

        # Botones
        btn_row = QHBoxLayout()
        btn_coach = QPushButton("📖 Ver Coaching")
        btn_coach.setStyleSheet(f"""
            QPushButton {{
                background: {BG_CARD}; color: {ACCENT_TEAL};
                border: 1px solid {ACCENT_TEAL}; border-radius: 5px;
                padding: 5px 12px; font-size: 11px;
            }}
            QPushButton:hover {{ background: {ACCENT_TEAL}; color: #000; }}
        """)
        btn_coach.clicked.connect(self._on_coaching)
        btn_row.addWidget(btn_coach)
        btn_row.addStretch()
        btn_ok = QPushButton("Cerrar")
        btn_ok.setStyleSheet(f"""
            QPushButton {{
                background: {BG_CARD}; color: {TEXT_MUTED};
                border: 1px solid {BORDER_SUBTLE}; border-radius: 5px;
                padding: 5px 12px; font-size: 11px;
            }}
            QPushButton:hover {{ color: {TEXT_WHITE}; border-color: {TEXT_WHITE}; }}
        """)
        btn_ok.clicked.connect(self.close)
        btn_row.addWidget(btn_ok)
        lay.addLayout(btn_row)

        outer.addWidget(card)

    def _on_coaching(self):
        self.coaching_requested.emit()
        self.close()


class LoLRecommenderApp(QMainWindow):
    lcu_task_finished = Signal(object, object, str, str)
    perfil_listo = Signal(dict)
    radar_listo = Signal(object)
    meta_builds_listo = Signal(list, dict, str, str)  # (resultados, builds_data, rol_api, enemigo)
    postgame_ready = Signal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("NEXUS // LoL Performance Engine")
        icon_path = os.path.join(BASE_DIR, "icono_app.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1500, 950)
        self.aplicar_estilos()

        self.user_settings = cargar_settings()
        self.champs_dict = cargar_campeones()
        self.nombres_campeones_global = sorted(list(set([data["nombre"] for data in self.champs_dict.values()])))
        # Construir mapeos bidireccionales Spanish <-> English para DB queries e iconos
        # nombre_a_id_img: display (ES) -> ID interno (EN) para URLs de Data Dragon
        # nombre_display:   ID interno (EN) -> display (ES) para mostrar en UI
        self.nombre_a_id_img = {}
        self.nombre_display = {}
        self.nombre_interno = {}  # display (ES) -> interno (EN) para queries SQL
        for k, v in self.champs_dict.items():
            nombre = v.get("nombre")
            if nombre and nombre not in self.nombre_a_id_img:
                self.nombre_a_id_img[nombre] = k  # "Bardo" -> "Bard"
                if nombre != k:
                    self.nombre_display[k] = nombre   # "Bard" -> "Bardo"
                    self.nombre_interno[nombre] = k   # "Bardo" -> "Bard"
        # Overrides manuales
        self.nombre_a_id_img["Wukong"] = "MonkeyKing"
        self.nombre_a_id_img["MaestroYi"] = "MasterYi"
        self.nombre_a_id_img["KhaZix"] = "Khazix"
        self.nombre_display["MonkeyKing"] = "Wukong"
        self.nombre_interno["Wukong"] = "MonkeyKing"
        self.nombre_display["MasterYi"] = "MaestroYi"
        self.nombre_interno["MaestroYi"] = "MasterYi"
        self.nombre_display["Khazix"] = "KhaZix"
        self.nombre_interno["KhaZix"] = "Khazix"

        self.version_juego = obtener_version_actual()
        self.builds_actuales = {}
        self.lcu = LCUConnector()
        self.radar_activo = False
        self.lcu_task_finished.connect(self._on_lcu_task_finished)
        self.perfil_listo.connect(self._on_perfil_listo)
        self.radar_listo.connect(self._on_radar_listo)
        self.meta_builds_listo.connect(self._on_meta_builds_listo)
        self.postgame_ready.connect(self._on_postgame_ready)
        
        self.last_aliados = []
        self.last_enemigos = []
        self.last_my_champ = None
        self.last_my_role = None
        self.last_enemigo_lane = None
        self.current_skill_order = None
        self.perfil_cargado = False
        
        # Cache de imágenes descargadas para evitar HTTP repetidos
        self._cache_imagenes = {}

        # Post-game: caché de stats en vivo y control de fase
        self._last_game_stats = {}
        self._postgame_shown = False
        self._last_fase = None
        
        # Flags anti-freeze
        self._cargando_perfil = False
        self._actualizando_radar = False
        self._cargando_meta = False

        inicializar_db()

        self.crear_interfaz()
        
        self.timer_lcu = QTimer(self)
        self.timer_lcu.timeout.connect(self.auto_detectar_lcu)
        self.timer_lcu.start(1500)
        
        # Timer para partida en vivo (cada 4s)
        self.timer_partida = QTimer(self)
        self.timer_partida.timeout.connect(self.actualizar_partida_vivo)
        self.timer_partida.start(4000)
        
        # In-game timer and hotkeys removed — feature was too buggy
        
        # ─── SYSTEM TRAY + GLOBAL HOTKEYS ───
        self._setup_tray()
        
        # Cache para post-game (eliminado — feature de in-game removida)

        # Overlay in-game
        self.overlay = OverlayWindow()
        self.overlay.closed.connect(lambda: None)

        # Discord Rich Presence
        QTimer.singleShot(3000, self._iniciar_discord_rpc)

        QTimer.singleShot(2000, self._check_actualizaciones)
        QTimer.singleShot(10000, self._check_app_update)

    def _check_app_update(self):
        try:
            update = check_for_update()
            if update and hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.showMessage(
                    "NEXUS - Nueva version disponible",
                    f"v{update['latest']} (actual: v{update['current']})\nVe a GitHub para descargarla.",
                    QIcon(), 8000
                )
                log.info("Nueva version disponible: v%s", update['latest'])
        except Exception as e:
            log.warning("Error verificando actualizacion de app: %s", e)

    def _iniciar_discord_rpc(self):
        try:
            iniciar_discord_rpc()
            actualizar_discord_rpc(
                details="En el cliente de LoL",
                state="Menu principal",
                large_text="League of Legends"
            )
        except Exception as e:
            print(f"[DiscordRPC] Error iniciando: {e}")

    def _check_actualizaciones(self):
        try:
            version_actual = obtener_version_actual()
            version_path = os.path.join(DATA_DIR, "version_local.txt")
            version_local = ""
            if os.path.exists(version_path):
                with open(version_path, "r", encoding="utf-8") as f:
                    version_local = f.read().strip()

            if version_actual != version_local:
                log.info("Nuevo parche detectado: %s -> %s", version_local, version_actual)
                from src.riot_api import actualizar_datos_riot
                actualizar_datos_riot()
                with open(version_path, "w", encoding="utf-8") as f:
                    f.write(version_actual)
                if hasattr(self, 'tray_icon') and self.tray_icon:
                    self.tray_icon.showMessage(
                        "NEXUS - Datos actualizados",
                        f"Parche {version_actual} descargado.",
                        QIcon(), 3000
                    )
        except Exception as e:
            log.warning("Error verificando actualizaciones: %s", e)

    # ═══════════════════════════════════════════════════════════
    # SYSTEM TRAY
    # ═══════════════════════════════════════════════════════════
    
    def _setup_tray(self):
        """Configura el icono en la bandeja del sistema."""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("NEXUS // LoL Performance Engine")
        pm = QPixmap(32, 32); pm.fill(QColor(BORDER_ACCENT))
        from PySide6.QtGui import QPainter, QFont
        p = QPainter(pm); p.setFont(QFont("Segoe UI", 16, QFont.Bold))
        p.setPen(QColor("#ffffff")); p.drawText(pm.rect(), Qt.AlignCenter, "N"); p.end()
        self.tray_icon.setIcon(QIcon(pm))
        # Crear menú contextual
        tray_menu = QMenu()
        a_show = QAction("📊 Mostrar / Ocultar", self)
        a_show.triggered.connect(self._tray_toggle)
        tray_menu.addAction(a_show)
        a_radar = QAction("📡 Ir a Radar", self)
        a_radar.triggered.connect(lambda: self.tabview.setCurrentIndex(2))
        tray_menu.addAction(a_radar)
        tray_menu.addSeparator()
        a_exit = QAction("❌ Salir", self)
        a_exit.triggered.connect(self._salir_app)
        tray_menu.addAction(a_exit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()
    
    def _tray_toggle(self):
        """Alterna visibilidad de la ventana desde el tray."""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()
    
    def _on_tray_activated(self, reason):
        """Doble click en el icono del tray muestra/oculta."""
        if reason == QSystemTrayIcon.DoubleClick:
            self._tray_toggle()
    
    def _salir_app(self):
        """Cierra la app."""
        self.tray_icon.hide()
        if hasattr(self, "overlay"):
            self.overlay.cleanup()
        try:
            detener_discord_rpc()
        except Exception:
            pass
        QApplication.quit()

    def closeEvent(self, event):
        """Minimizar al tray en vez de cerrar."""
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            self._salir_app()
            event.accept()

    def aplicar_estilos(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {BG_DARK}; }}
            QWidget {{ 
                color: {TEXT_WHITE}; 
                font-family: {FONT_FAMILY}; 
                font-size: 12px; 
            }}
            
            /* ═══ PANELES / TARJETAS ═══ */
            QFrame#Panel {{ 
                background-color: {BG_PANEL}; 
                border: 1px solid {BORDER_SUBTLE}; 
                border-radius: 10px; 
                padding: 14px; 
            }}
            QFrame#Panel:hover {{ border: 1px solid {BORDER_ACCENT}; }}
            QFrame#CardAlly {{ 
                background-color: {ALLY_BG}; 
                border: 1px solid {BORDER_SUBTLE}; 
                border-radius: 8px; 
            }}
            QFrame#CardAlly:hover {{ border: 1px solid {ACCENT_TEAL}; }}
            QFrame#CardEnemy {{ 
                background-color: {ENEMY_BG}; 
                border: 1px solid #3b1018; 
                border-radius: 8px; 
            }}
            QFrame#CardEnemy:hover {{ border: 1px solid {RED_WR}; }}
            QFrame#BuildCard {{ 
                background-color: {BG_CARD}; 
                border: 1px solid {BORDER_SUBTLE}; 
                border-radius: 8px; 
            }}
            QFrame#BuildCard:hover {{ 
                border: 1px solid {BORDER_ACCENT}; 
                background-color: #1a1520; 
            }}
            QFrame#StatCard {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 10px;
                padding: 12px;
            }}
            QFrame#StatCard:hover {{
                border: 1px solid {BORDER_ACCENT};
            }}
            
            QLabel {{ border: none; background: transparent; }}
            
            /* ═══ BOTONES ═══ */
            QPushButton {{ 
                background-color: {BG_CARD}; 
                color: {TEXT_WHITE}; 
                border: 1px solid {BORDER_SUBTLE}; 
                border-radius: 6px; 
                padding: 8px 18px; 
                font-weight: 600; 
                font-size: 12px; 
                letter-spacing: 0.3px;
            }}
            QPushButton:hover {{ 
                background-color: {ACCENT_RED}; 
                color: #ffffff; 
                border: 1px solid {ACCENT_RED}; 
            }}
            QPushButton:pressed {{ 
                background-color: #be123c; 
            }}
            QPushButton:disabled {{ 
                background-color: #1e293b; 
                color: #475569; 
                border: 1px solid #334155; 
            }}
            
            /* ═══ PESTAÑAS ═══ */
            QTabWidget::pane {{ 
                border: none; 
                background-color: {BG_PANEL}; 
                border-radius: 10px; 
                border-top-left-radius: 0px; 
                padding: 4px;
            }}
            QTabBar::tab {{ 
                background: transparent; 
                color: {TEXT_MUTED}; 
                padding: 10px 24px; 
                border: none; 
                border-bottom: 2px solid transparent; 
                margin-right: 2px; 
                font-weight: 500; 
                font-size: 12px; 
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }}
            QTabBar::tab:selected {{ 
                color: {ACCENT_RED}; 
                border-bottom: 2px solid {ACCENT_RED};
                font-weight: 700;
            }}
            QTabBar::tab:hover:!selected {{ 
                color: {TEXT_WHITE}; 
                border-bottom: 2px solid {TEXT_MUTED};
            }}
            
            /* ═══ COMBOBOX ═══ */
            QComboBox {{ 
                background-color: {BG_CARD}; 
                color: {TEXT_WHITE}; 
                border: 1px solid {BORDER_SUBTLE}; 
                padding: 7px 12px; 
                border-radius: 6px; 
                font-size: 12px; 
                min-height: 20px;
            }}
            QComboBox:hover {{ border: 1px solid {BORDER_ACCENT}; }}
            QComboBox:focus {{ border: 1px solid {ACCENT_RED}; }}
            QComboBox::drop-down {{ 
                border: none; 
                width: 24px; 
            }}
            QComboBox QAbstractItemView {{ 
                background-color: {BG_PANEL}; 
                color: {TEXT_WHITE}; 
                selection-background-color: {ACCENT_RED}; 
                selection-color: #ffffff; 
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 4px;
                outline: 0;
                padding: 4px;
            }}
            
            /* ═══ TABLAS ═══ */
            QTableWidget {{ 
                background-color: {BG_PANEL}; 
                alternate-background-color: {BG_CARD}; 
                color: {TEXT_WHITE}; 
                gridline-color: transparent; 
                border: 1px solid {BORDER_SUBTLE}; 
                border-radius: 10px; 
                font-size: 12px; 
                outline: 0; 
            }}
            QTableWidget::item {{ 
                padding: 8px 12px; 
                border-bottom: 1px solid #1a2236; 
            }}
            QTableWidget::item:selected {{ 
                background-color: {ACCENT_RED}; 
                color: #ffffff; 
            }}
            QTableWidget::item:hover {{ 
                background-color: #1a2844; 
            }}
            QHeaderView::section {{ 
                background-color: {BG_CARD}; 
                color: {TEXT_MUTED}; 
                font-weight: 700; 
                padding: 12px 12px; 
                border: none; 
                border-bottom: 2px solid {BORDER_ACCENT}; 
                font-size: 11px; 
                letter-spacing: 0.8px;
                text-transform: uppercase;
            }}
            
            /* ═══ BARRA DE PROGRESO ═══ */
            QProgressBar {{ 
                border: 1px solid {BORDER_SUBTLE}; 
                border-radius: 6px; 
                text-align: center; 
                background-color: {BG_CARD}; 
                color: {TEXT_WHITE}; 
                font-weight: 700; 
                font-size: 11px; 
                height: 18px;
            }}
            QProgressBar::chunk {{ 
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {ACCENT_RED}, stop:1 {HOVER_GLOW});
                border-radius: 5px; 
            }}
            
            /* ═══ SCROLLBAR ═══ */
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_SUBTLE};
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {BORDER_ACCENT};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 6px;
                margin: 0;
            }}
            QScrollBar::handle:horizontal {{
                background: {BORDER_SUBTLE};
                border-radius: 3px;
                min-width: 30px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {BORDER_ACCENT};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            
            /* ═══ TOOLTIP ═══ */
            QToolTip {{
                background-color: {BG_PANEL};
                color: {TEXT_WHITE};
                border: 1px solid {BORDER_ACCENT};
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 11px;
            }}
            
            /* ═══ CHECKBOX ═══ */
            QCheckBox {{
                color: {TEXT_WHITE};
                font-size: 12px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid {BORDER_SUBTLE};
                background-color: {BG_CARD};
            }}
            QCheckBox::indicator:checked {{
                background-color: {ACCENT_RED};
                border: 1px solid {ACCENT_RED};
            }}
            QCheckBox::indicator:hover {{
                border: 1px solid {BORDER_ACCENT};
            }}
            
            /* ═══ SPINBOX / SLIDER ═══ */
            QSpinBox {{
                background-color: {BG_CARD};
                color: {TEXT_WHITE};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QSpinBox:hover {{ border: 1px solid {BORDER_ACCENT}; }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: {BG_CARD};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT_RED};
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {HOVER_GLOW};
            }}
            QSlider::sub-page:horizontal {{
                background: {ACCENT_RED};
                border-radius: 3px;
            }}
        """)

    def crear_panel(self, text=""):
        fr = QFrame()
        fr.setObjectName("Panel")
        layout = QVBoxLayout(fr)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        if text:
            lbl = QLabel(text.upper())
            lbl.setStyleSheet(f"color: {ACCENT_RED}; font-weight: 700; font-size: 11px; letter-spacing: 1.5px; margin-bottom: 4px;")
            layout.addWidget(lbl)
            fr.label_title = lbl
        return fr, layout

    def crear_interfaz(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Header con titulo y boton de configuracion
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_lbl = QLabel("NEXUS")
        header_lbl.setStyleSheet(f"color: {BORDER_ACCENT}; font-family: Impact; font-size: 28px;")
        header_lbl.setAlignment(Qt.AlignCenter)
        header_row.addStretch()
        header_row.addWidget(header_lbl)
        header_row.addStretch()
        
        btn_settings = QPushButton()
        btn_settings.setFixedSize(34, 34)
        btn_settings.setCursor(Qt.PointingHandCursor)
        btn_settings.setToolTip("Configuración de la app")
        btn_settings.setIcon(self._crear_icono_engranaje(20, "#4a5070"))
        btn_settings.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: 1px solid #2a3050; border-radius: 17px; }}
            QPushButton:hover {{ border: 1px solid {BORDER_ACCENT}; }}
        """)
        btn_settings.clicked.connect(self.abrir_settings)
        header_row.addWidget(btn_settings)
        main_layout.addLayout(header_row)

        self.tabview = QTabWidget()
        main_layout.addWidget(self.tabview)

        self.tab_perfil = QWidget()
        self.tab_coaching = QWidget()
        self.tab_vivo = QWidget()
        self.tab_partida = QWidget()
        self.tab_counters = QWidget()
        self.tab_ia = QWidget()
        self.tab_bans = QWidget()

        self.tabview.addTab(self.tab_perfil, "👤 MI PERFIL")
        self.tabview.addTab(self.tab_coaching, "🎓 COACHING PRO")
        self.tabview.addTab(self.tab_vivo, "📡 RADAR EN VIVO")
        self.tabview.addTab(self.tab_partida, "🎮 PARTIDA EN VIVO")
        self.tabview.addTab(self.tab_counters, "📊 META & BUILDS")
        self.tabview.addTab(self.tab_ia, "🤖 SIMULADOR 1v1")
        self.tabview.addTab(self.tab_bans, "🚫 TIER LIST DE BANS")

        self.armar_tab_perfil()
        self.armar_tab_coaching()
        self.armar_tab_vivo()
        self.armar_tab_partida()
        self.armar_tab_counters()
        self.armar_tab_ia()
        self.armar_tab_bans()
        
        self.tabview.setCurrentIndex(0)  # Abrir en MI PERFIL

    def descargar_imagen(self, id_elemento, tipo):
        # Cache en RAM: evita HTTP repetidos
        cache_key = f"{tipo}_{id_elemento}"
        if cache_key in self._cache_imagenes:
            return self._cache_imagenes[cache_key]
        
        carpetas = {"runa": RUNAS_DIR, "champ": CHAMPS_DIR, "item": ITEMS_DIR, "spell": SPELLS_DIR, "profile": PROFILE_ICONS_DIR}
        ruta_local = os.path.join(carpetas.get(tipo, CHAMPS_DIR), f"{id_elemento}.png")
        if os.path.exists(ruta_local):
            self._cache_imagenes[cache_key] = ruta_local
            return ruta_local
        try:
            if tipo == "runa": url = f"https://ddragon.leagueoflegends.com/cdn/img/{RUNAS_DICT.get(str(id_elemento), {}).get('icono', '')}"
            elif tipo == "spell": url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/spell/{SPELLS_DICT.get(str(id_elemento), {}).get('icono', '')}"
            elif tipo == "champ": url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/champion/{self.nombre_a_id_img.get(id_elemento, id_elemento)}.png"
            elif tipo == "profile": url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/profileicon/{id_elemento}.png"
            else: url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/item/{id_elemento}.png"
                
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            with open(ruta_local, "wb") as f: f.write(resp.content)
            self._cache_imagenes[cache_key] = ruta_local
            return ruta_local
        except:
            return None

    def renderizar_icono(self, id_elemento, tipo, grid_layout, fila=0, columna=0, info_extra="", size=40):
        ruta = self.descargar_imagen(id_elemento, tipo)
        if not ruta: return
            
        pixmap = QPixmap(ruta).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        info_texto = info_extra
        if tipo == "runa": info_texto = f"{RUNAS_DICT.get(str(id_elemento), {}).get('nombre', 'Runa')}\n{RUNAS_DICT.get(str(id_elemento), {}).get('descripcion', '')}"
        elif tipo == "item": info_texto = f"{ITEMS_DICT.get(str(id_elemento), {}).get('nombre', 'Objeto')}\n{ITEMS_DICT.get(str(id_elemento), {}).get('descripcion', '')}"
        elif tipo == "spell": info_texto = f"{SPELLS_DICT.get(str(id_elemento), {}).get('nombre', 'Hechizo')}\n{SPELLS_DICT.get(str(id_elemento), {}).get('descripcion', '')}"

        lbl_img = QLabel()
        lbl_img.setPixmap(pixmap)
        lbl_img.setAlignment(Qt.AlignCenter)
        if info_texto: lbl_img.setToolTip(info_texto)

        if isinstance(grid_layout, QGridLayout): grid_layout.addWidget(lbl_img, fila, columna)
        else: grid_layout.addWidget(lbl_img)

    def inicializar_panel_setup(self, layout):
        clear_layout(layout)
        lbl = QLabel("Selecciona un campeón para generar su Setup.")
        lbl.setStyleSheet("color: gray; font-style: italic; font-size: 14px;")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

    def _animar_boton(self, btn, text_original):
        btn.setText("¡ÉXITO! ✔")
        btn.setStyleSheet(f"background-color: {GREEN_WR}; color: {BG_DARK}; font-weight: bold;")
        QTimer.singleShot(2000, lambda: self._restaurar_boton(btn, text_original))

    def _restaurar_boton(self, btn, text_original):
        btn.setText(text_original)
        if btn == self.btn_export_skills:
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {BG_CARD}; border: 1px solid {ACCENT_TEAL}; border-radius: 4px; color: {ACCENT_TEAL}; font-size: 11px; padding: 6px 16px; font-weight: bold; }}
                QPushButton:hover {{ background-color: #1a3a3a; }}
                QPushButton:disabled {{ color: #475569; border-color: #1e293b; }}
            """)
        else:
            btn.setStyleSheet("") 

    # ================= FUNCIONES DE BOTONES =================
    def _run_lcu_task(self, task, btn, success_text, error_message):
        res = task()
        self.lcu_task_finished.emit(btn, res, success_text, error_message)

    def _format_lcu_error(self, res):
        texto = str(res)
        if "read timed out" in texto.lower():
            return "Tiempo de espera agotado al guardar el item set. Es posible que el item set ya se haya creado en el cliente."
        if "404" in texto:
            return "Endpoint de item sets no disponible en esta versión del cliente. Actualiza LoL o prueba otro método."
        if len(texto) > 240:
            return texto.splitlines()[0][:240] + "..."
        return texto

    def _on_lcu_task_finished(self, btn, res, success_text, error_message):
        btn.setEnabled(True)
        if res is True:
            self._animar_boton(btn, success_text)
        else:
            detalle = self._format_lcu_error(res)
            QMessageBox.critical(self, "Error API LCU", f"{error_message}\n\nDetalle: {detalle}")

    # ── Auto-import wrappers (sin botón, para modo automático) ──
    def _auto_importar_runas(self, ids_runas, campeon):
        if not ids_runas: return
        threading.Thread(target=lambda: self.lcu.importar_runas(ids_runas, nombre=f"LEA {campeon}"), daemon=True).start()

    def _auto_importar_hechizos(self, ids_spells):
        if not ids_spells or len(ids_spells) < 2: return
        s1, s2 = str(ids_spells[0]), str(ids_spells[1])
        flash_en_d = self.user_settings.get("flash_en_d", True)
        if not flash_en_d:
            if s1 == "4" and s2 != "4": s1, s2 = s2, s1
        else:
            if s2 == "4" and s1 != "4": s1, s2 = s2, s1
        threading.Thread(target=lambda: self.lcu.importar_hechizos(s1, s2), daemon=True).start()

    def _auto_importar_items(self, campeon, ids_start, ids_core):
        if not ids_core: return
        threading.Thread(
            target=lambda: self.lcu.importar_item_set(
                campeon,
                next((int(k) for k, v in MAPEO_IDS_CAMPEONES.items() if v == campeon), 0),
                ids_start or [],
                ids_core
            ), daemon=True
        ).start()

    def _auto_importar_skill_order(self):
        if not hasattr(self, 'current_skill_order') or not self.current_skill_order: return
        threading.Thread(target=lambda: self.lcu.importar_skill_order(self.current_skill_order), daemon=True).start()

    def accion_importar_runas(self, ids_runas, campeon, btn):
        btn.setEnabled(False)
        threading.Thread(
            target=self._run_lcu_task,
            args=(lambda: self.lcu.importar_runas(ids_runas, nombre=f"LEA {campeon}"), btn, "Exportar a LoL", "Asegúrate de tener el cliente abierto."),
            daemon=True
        ).start()

    def accion_importar_spells(self, ids_spells, btn):
        if len(ids_spells) < 2:
            QMessageBox.critical(self, "Error", "Selecciona los dos hechizos primero.")
            return
        s1, s2 = str(ids_spells[0]), str(ids_spells[1])
        flash_en_d = self.user_settings.get("flash_en_d", True)
        if not flash_en_d:
            if s1 == "4" and s2 != "4": s1, s2 = s2, s1
        else:
            if s2 == "4" and s1 != "4": s1, s2 = s2, s1
        btn.setEnabled(False)
        threading.Thread(
            target=self._run_lcu_task,
            args=(lambda: self.lcu.importar_hechizos(s1, s2), btn, "Exportar a LoL", "Asegúrate de estar en una sala de Draft."),
            daemon=True
        ).start()

    def accion_importar_items(self, campeon, ids_start, ids_core, btn):
        btn.setEnabled(False)
        threading.Thread(
            target=self._run_lcu_task,
            args=(
                lambda: self.lcu.importar_item_set(
                    campeon,
                    next((int(k) for k, v in MAPEO_IDS_CAMPEONES.items() if v == campeon), 0),
                    ids_start or [],
                    ids_core
                ),
                btn,
                "Crear Item Set en LoL",
                "No se pudo inyectar el Item Set."
            ),
            daemon=True
        ).start()

    def accion_importar_skill_order(self, btn):
        if not hasattr(self, 'current_skill_order') or not self.current_skill_order:
            QMessageBox.critical(self, "Error", "No hay ruta de habilidades para exportar.\nSelecciona un campeón primero.")
            return
        if not self.lcu or not self.lcu.port:
            QMessageBox.critical(self, "Error", "Cliente de LoL no detectado.\nAsegúrate de tener el cliente abierto.")
            return
        btn.setEnabled(False)
        self._btn_skills_original = btn.text()
        skill = self.current_skill_order
        threading.Thread(
            target=self._run_lcu_task,
            args=(lambda: self.lcu.importar_skill_order(skill), btn,
                  "✅ Subido al Cliente",
                  "No se pudo subir la ruta de habilidades.\nAsegúrate de estar en selección de campeón."),
            daemon=True
        ).start()

    # ================= REDISEÑO DE SETUP & BUILD ANTI-ESTIRAMIENTO =================
    def renderizar_setup_completo(self, campeon, ids_runas, ids_spells, ids_start, ids_core, parent_layout, mostrar_botones=True, ids_sit=None):
        clear_layout(parent_layout)

        main_wrap = QWidget()
        wrap_layout = QHBoxLayout(main_wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(10)

        # CARD RUNAS
        card_runas = QFrame()
        card_runas.setObjectName("BuildCard")
        l_runas = QVBoxLayout(card_runas)
        lbl_r = QLabel("RUNAS RECOMENDADAS")
        lbl_r.setStyleSheet(f"color: {BORDER_ACCENT}; font-weight: bold; font-size: 11px;")
        l_runas.addWidget(lbl_r, alignment=Qt.AlignCenter)

        r_grid = QGridLayout()
        r_grid.setAlignment(Qt.AlignCenter)
        if len(ids_runas) > 4:
            self.renderizar_icono(ids_runas[0], "runa", r_grid, 0, 0, size=35)
            self.renderizar_icono(ids_runas[1], "runa", r_grid, 1, 0, size=50)
            self.renderizar_icono(ids_runas[2], "runa", r_grid, 2, 0, size=35)
            self.renderizar_icono(ids_runas[3], "runa", r_grid, 3, 0, size=35)
            self.renderizar_icono(ids_runas[4], "runa", r_grid, 4, 0, size=35)
        if len(ids_runas) > 7:
            self.renderizar_icono(ids_runas[5], "runa", r_grid, 0, 1, size=30)
            self.renderizar_icono(ids_runas[6], "runa", r_grid, 1, 1, size=35)
            self.renderizar_icono(ids_runas[7], "runa", r_grid, 2, 1, size=35)
        l_runas.addLayout(r_grid)

        fr_shards = QWidget()
        layout_shards = QHBoxLayout(fr_shards)
        layout_shards.setContentsMargins(0, 5, 0, 5)
        layout_shards.setAlignment(Qt.AlignCenter)
        
        shards_list = [str(i) for i in ids_runas[8:11]] if len(ids_runas) >= 11 else ["5008", "5008", "5011"]
        for stat_id in shards_list:
            texto, color = STAT_SHARDS.get(stat_id, (f"Shard", "#ffffff"))
            lbl_shard = QLabel(texto)
            lbl_shard.setFixedSize(80, 25) 
            lbl_shard.setStyleSheet(f"color: {TEXT_WHITE}; border: 1px solid {color}; border-radius: 4px; font-size: 9px; font-weight: bold;")
            lbl_shard.setAlignment(Qt.AlignCenter)
            layout_shards.addWidget(lbl_shard)
            
        l_runas.addWidget(fr_shards)

        # Botones solo en Radar en Vivo
        if mostrar_botones:
            l_runas.addStretch()
            btn_runas = QPushButton("Exportar Runas")
            btn_runas.clicked.connect(lambda: self.accion_importar_runas(ids_runas, campeon, btn_runas))
            l_runas.addWidget(btn_runas, alignment=Qt.AlignBottom)
        wrap_layout.addWidget(card_runas)

        # CARD HECHIZOS
        card_spells = QFrame()
        card_spells.setObjectName("BuildCard")
        l_spells = QVBoxLayout(card_spells)
        lbl_s = QLabel("HECHIZOS")
        lbl_s.setStyleSheet(f"color: {BORDER_ACCENT}; font-weight: bold; font-size: 11px;")
        l_spells.addWidget(lbl_s, alignment=Qt.AlignCenter)

        for sp in ids_spells: self.renderizar_icono(str(sp), "spell", l_spells, size=45)
        
        if mostrar_botones:
            l_spells.addStretch()
            btn_spells = QPushButton("Exportar")
            btn_spells.clicked.connect(lambda: self.accion_importar_spells(ids_spells, btn_spells))
            l_spells.addWidget(btn_spells, alignment=Qt.AlignBottom)
        wrap_layout.addWidget(card_spells)

        # CARD OBJETOS (START + CORE)
        card_items = QFrame()
        card_items.setObjectName("BuildCard")
        l_items = QVBoxLayout(card_items)
        
        lbl_i1 = QLabel("INICIO")
        lbl_i1.setStyleSheet(f"color: {BORDER_ACCENT}; font-weight: bold; font-size: 10px;")
        l_items.addWidget(lbl_i1, alignment=Qt.AlignCenter)
        
        w_start = QWidget()
        grid_start = QHBoxLayout(w_start)
        grid_start.setContentsMargins(0,0,0,0)
        grid_start.setAlignment(Qt.AlignCenter)
        if ids_start:
            for i_id in ids_start: self.renderizar_icono(i_id, "item", grid_start, 0, 0, size=40)
        l_items.addWidget(w_start)
        
        lbl_i2 = QLabel("CORE BUILD")
        lbl_i2.setStyleSheet(f"color: {BORDER_ACCENT}; font-weight: bold; font-size: 10px; padding-top: 10px;")
        l_items.addWidget(lbl_i2, alignment=Qt.AlignCenter)
        
        w_core = QWidget()
        grid_core = QGridLayout(w_core)
        grid_core.setContentsMargins(0,0,0,0)
        grid_core.setAlignment(Qt.AlignCenter)
        if ids_core:
            for idx, i_id in enumerate(ids_core): self.renderizar_icono(i_id, "item", grid_core, idx // 3, idx % 3, size=45)
        l_items.addWidget(w_core)

        if mostrar_botones:
            l_items.addStretch()
            btn_items = QPushButton("Crear Item Set")
            btn_items.clicked.connect(lambda: self.accion_importar_items(campeon, ids_start, ids_core, btn_items))
            l_items.addWidget(btn_items, alignment=Qt.AlignBottom)
        wrap_layout.addWidget(card_items)

        # ── CARD SITUACIONALES ──────────────────────────────────
        if ids_sit:
            _PRIO_COLOR   = {1: "#ef4444", 2: "#f59e0b", 3: "#64748b"}
            _PRIO_LABEL   = {1: "CRÍTICO", 2: "RECOMENDADO", 3: "OPCIONAL"}
            _CAT_LABEL    = {
                "anti_heal": "Anti-curación",  "anti_cc": "Anti-CC",
                "anti_ap": "Anti-AP",          "anti_ad": "Anti-AD",
                "anti_tank": "Anti-tanques",   "penetracion": "Penetración",
                "supervivencia": "Supervivencia",
            }

            card_sit = QFrame()
            card_sit.setObjectName("BuildCard")
            l_sit = QVBoxLayout(card_sit)
            l_sit.setSpacing(6)

            lbl_sit_t = QLabel("SITUACIONALES")
            lbl_sit_t.setStyleSheet(f"color: #f59e0b; font-weight: bold; font-size: 11px;")
            l_sit.addWidget(lbl_sit_t, alignment=Qt.AlignCenter)

            for sit in ids_sit[:5]:  # max 5 items para no saturar
                row_w = QWidget()
                row_l = QHBoxLayout(row_w)
                row_l.setContentsMargins(2, 2, 2, 2)
                row_l.setSpacing(6)

                # Icono del ítem
                self.renderizar_icono(sit["id"], "item", row_l, size=32)

                # Texto: categoría + nombre + razón
                txt_w = QWidget()
                txt_l = QVBoxLayout(txt_w)
                txt_l.setContentsMargins(0, 0, 0, 0)
                txt_l.setSpacing(1)

                prio_col = _PRIO_COLOR.get(sit["prioridad"], "#64748b")
                cat_txt  = _CAT_LABEL.get(sit["categoria"], sit["categoria"])
                lbl_cat = QLabel(f"<span style='color:{prio_col};font-weight:bold;font-size:9px;'>"
                                 f"{_PRIO_LABEL.get(sit['prioridad'],'')}</span>"
                                 f"<span style='color:#94a3b8;font-size:9px;'> · {cat_txt}</span>")
                lbl_cat.setTextFormat(Qt.RichText)
                txt_l.addWidget(lbl_cat)

                lbl_name = QLabel(f"{sit['nombre']}  <span style='color:#64748b;font-size:9px;'>{sit['coste']}g</span>")
                lbl_name.setStyleSheet("color: #f1f5f9; font-size: 10px; font-weight: bold;")
                lbl_name.setTextFormat(Qt.RichText)
                txt_l.addWidget(lbl_name)

                razon = sit["razon"]
                if len(razon) > 75:
                    razon = razon[:72] + "…"
                lbl_razon = QLabel(razon)
                lbl_razon.setStyleSheet("color: #94a3b8; font-size: 9px;")
                lbl_razon.setWordWrap(True)
                txt_l.addWidget(lbl_razon)

                row_l.addWidget(txt_w)
                row_l.addStretch()
                l_sit.addWidget(row_w)

            l_sit.addStretch()
            wrap_layout.addWidget(card_sit)

        parent_layout.addWidget(main_wrap)

    # ================= PESTAÑA MI PERFIL DASHBOARD =================
    @staticmethod
    def _parse_game_date(g: dict):
        """Parsea la fecha de una partida LCU de forma robusta (soporta locale ES/EN).
        Retorna un objeto datetime o None si no se puede parsear."""
        ts = g.get("gameCreation", 0)
        if ts:
            if ts > 1000000000000:
                ts = ts / 1000
            try:
                return datetime.fromtimestamp(ts)
            except:
                pass
        fecha_str = g.get("gameCreationDate", "")
        if not fecha_str:
            return None
        for fmt in [
            "%b %d, %Y %I:%M:%S %p",
            "%b. %d, %Y %I:%M:%S %p",
            "%b %d, %Y %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ]:
            try:
                return datetime.strptime(fecha_str, fmt)
            except:
                continue
        try:
            return datetime.strptime(fecha_str[:10], "%b %d, %Y")
        except:
            pass
        return None

    @staticmethod
    def _format_game_date(g: dict):
        """Devuelve la fecha formateada dd/mm de una partida."""
        dt = LoLRecommenderApp._parse_game_date(g)
        if dt:
            return dt.strftime("%d/%m")
        fecha_str = g.get("gameCreationDate", "")
        return fecha_str[:10] if len(fecha_str) >= 10 else "?"

    @staticmethod
    def _extraer_year(g: dict):
        """Extrae el año de una partida (gameCreationDate string o gameCreation timestamp)."""
        dt = LoLRecommenderApp._parse_game_date(g)
        if dt:
            return dt.year
        return None

    def _crear_icono_engranaje(self, size=20, color="#4a5070"):
        """Crea un icono de engranaje gear con QPainter."""
        import math
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(color), size * 0.1)
        painter.setPen(pen)
        painter.setBrush(QColor(color))
        cx = cy = size / 2
        r_outer = size * 0.42
        r_inner = size * 0.18
        painter.drawEllipse(QPointF(cx, cy), r_outer, r_outer)
        painter.setBrush(Qt.transparent)
        painter.drawEllipse(QPointF(cx, cy), r_inner, r_inner)
        for i in range(8):
            angle = i * 45
            rad = math.radians(angle)
            x1 = cx + (r_outer + size * 0.08) * math.cos(rad)
            y1 = cy + (r_outer + size * 0.08) * math.sin(rad)
            x2 = cx + (r_outer - size * 0.08) * math.cos(rad)
            y2 = cy + (r_outer - size * 0.08) * math.sin(rad)
            painter.setBrush(QColor(color))
            painter.setPen(Qt.NoPen)
            painter.drawRect(x1 - size * 0.04, y1 - size * 0.04, size * 0.08, size * 0.08)
        painter.end()
        return QIcon(pixmap)

    def _crear_stat_card(self, titulo, valor, color):
        card = QFrame()
        card.setObjectName("BuildCard")
        card.setFixedHeight(82)
        l = QVBoxLayout(card)
        l.setContentsMargins(8, 6, 8, 6)
        l.setSpacing(2)
        l.setAlignment(Qt.AlignCenter)
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"color: #8fa3b8; font-size: 10px; font-weight: bold;")
        lbl_titulo.setAlignment(Qt.AlignCenter)
        l.addWidget(lbl_titulo)
        lbl_valor = QLabel(valor)
        lbl_valor.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold;")
        lbl_valor.setAlignment(Qt.AlignCenter)
        l.addWidget(lbl_valor)
        return card, lbl_valor

    def _rank_to_color(self, tier):
        colors = {
            "IRON": "#5c5550", "BRONZE": "#8b5e3c", "SILVER": "#9dafbf",
            "GOLD": "#f0c75e", "PLATINUM": "#4e9999", "EMERALD": "#50c878",
            "DIAMOND": "#b9a0ff", "MASTER": "#b44cc6", "GRANDMASTER": "#c62828",
            "CHALLENGER": "#f4c542"
        }
        return colors.get(tier.upper(), TEXT_WHITE)

    def _rank_icon(self, tier):
        icons = {"IRON": "🔩", "BRONZE": "🥉", "SILVER": "🥈", "GOLD": "🥇",
                 "PLATINUM": "💠", "EMERALD": "💚", "DIAMOND": "💎",
                 "MASTER": "👑", "GRANDMASTER": "🔥", "CHALLENGER": "🏆"}
        return icons.get(tier.upper(), "❓")

    def armar_tab_perfil(self):
        layout = QVBoxLayout(self.tab_perfil)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        
        self.pnl_perfil = QWidget()
        l_pnl = QHBoxLayout(self.pnl_perfil)
        l_pnl.setContentsMargins(0, 0, 0, 0)
        l_pnl.setSpacing(8)
        l_pnl.setAlignment(Qt.AlignTop)
        
        # ===== COLUMNA IZQUIERDA =====
        self.col_id = QVBoxLayout()
        self.col_id.setAlignment(Qt.AlignTop)
        self.col_id.setSpacing(6)
        
        # ===== TARJETA COMPACTA: IDENTIDAD + LIGAS (FUSIONADA) =====
        self.pnl_identity_card = QFrame()
        self.pnl_identity_card.setObjectName("Panel")
        id_card_layout = QHBoxLayout(self.pnl_identity_card)
        id_card_layout.setContentsMargins(10, 10, 10, 10)
        id_card_layout.setSpacing(10)
        
        # Icono perfil (izquierda, 60x60)
        self.lbl_prof_icon = QLabel()
        self.lbl_prof_icon.setFixedSize(60, 60)
        self.lbl_prof_icon.setAlignment(Qt.AlignCenter)
        id_card_layout.addWidget(self.lbl_prof_icon)
        
        # Centro: Nombre + Nivel
        center_info = QVBoxLayout()
        center_info.setSpacing(2)
        self.lbl_sum_name = QLabel("Esperando al Cliente...")
        self.lbl_sum_name.setStyleSheet(f"color: {BORDER_ACCENT}; font-size: 16px; font-weight: bold;")
        center_info.addWidget(self.lbl_sum_name)
        self.lbl_sum_lvl = QLabel("Nivel: --")
        self.lbl_sum_lvl.setStyleSheet("color: #8fa3b8; font-size: 11px;")
        center_info.addWidget(self.lbl_sum_lvl)
        id_card_layout.addLayout(center_info, 1)
        
        # Derecha: SoloQ + Flex (compacto, una linea cada uno)
        ranks_info = QVBoxLayout()
        ranks_info.setSpacing(2)
        self.lbl_soloq_tier = QLabel("⚔️ --")
        self.lbl_soloq_tier.setStyleSheet(f"color: {ACCENT_RED}; font-weight: bold; font-size: 11px;")
        ranks_info.addWidget(self.lbl_soloq_tier)
        self.lbl_soloq_stats = QLabel("")
        self.lbl_soloq_stats.setStyleSheet("color: #8fa3b8; font-size: 9px;")
        ranks_info.addWidget(self.lbl_soloq_stats)
        self.lbl_flex_tier = QLabel("🛡️ --")
        self.lbl_flex_tier.setStyleSheet(f"color: {TEXT_GOLD}; font-weight: bold; font-size: 11px;")
        ranks_info.addWidget(self.lbl_flex_tier)
        self.lbl_flex_stats = QLabel("")
        self.lbl_flex_stats.setStyleSheet("color: #8fa3b8; font-size: 9px;")
        ranks_info.addWidget(self.lbl_flex_stats)
        id_card_layout.addLayout(ranks_info)
        
        self.col_id.addWidget(self.pnl_identity_card)
        
        # ===== ESTADÍSTICAS DE LA TEMPORADA (columna izquierda) =====
        self.pnl_season, self.l_season = self.crear_panel("📊 ESTADÍSTICAS DE LA TEMPORADA")
        self.lbl_season_stats = QLabel("")
        self.lbl_season_stats.setVisible(False)
        self.l_season.addWidget(self.lbl_season_stats)
        self.tb_season_champs = QTableWidget()
        self.tb_season_champs.setColumnCount(4)
        self.tb_season_champs.setHorizontalHeaderLabels(["Campeón", "Partidas", "WR", "KDA"])
        self.tb_season_champs.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 4):
            self.tb_season_champs.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.tb_season_champs.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb_season_champs.setSelectionMode(QAbstractItemView.NoSelection)
        self.tb_season_champs.setShowGrid(False)
        self.tb_season_champs.setAlternatingRowColors(True)
        self.tb_season_champs.verticalHeader().setVisible(False)
        self.tb_season_champs.horizontalHeader().setVisible(True)
        self.tb_season_champs.verticalHeader().setDefaultSectionSize(28)
        self.tb_season_champs.setIconSize(QSize(20, 20))
        self.tb_season_champs.setStyleSheet("""
            QTableWidget { border: none; background-color: transparent; }
            QHeaderView::section { background-color: #152040; border: none; border-bottom: 1px solid #c89b3c; color: #c89b3c; font-weight: bold; padding: 4px; }
            QTableWidget::item { border-bottom: 1px solid #1e2535; padding: 2px 6px; }
        """)
        self.l_season.addWidget(self.tb_season_champs)
        self.col_id.addWidget(self.pnl_season)
        
        # ===== PANEL DE FATIGA (columna izquierda, abajo) =====
        self.pnl_fatiga, self.l_fatiga = self.crear_panel("🧠 ESTADO MENTAL")
        self.l_fatiga.setAlignment(Qt.AlignTop)
        self.l_fatiga.setSpacing(6)
        self.l_fatiga.setContentsMargins(12, 12, 12, 12)
        
        fr_estado = QFrame()
        fr_estado.setObjectName("InnerPanel")
        l_estado = QHBoxLayout(fr_estado)
        l_estado.setContentsMargins(8, 6, 8, 6)
        l_estado.setSpacing(10)
        l_estado.setAlignment(Qt.AlignLeft)
        
        self.lbl_fatiga_icono = QLabel("⏳")
        self.lbl_fatiga_icono.setFixedSize(46, 46)
        self.lbl_fatiga_icono.setAlignment(Qt.AlignCenter)
        self.lbl_fatiga_icono.setStyleSheet("font-size: 28px; padding: 0px;")
        l_estado.addWidget(self.lbl_fatiga_icono)
        
        fr_texto_estado = QFrame()
        l_texto_estado = QVBoxLayout(fr_texto_estado)
        l_texto_estado.setContentsMargins(0, 0, 0, 0)
        l_texto_estado.setSpacing(2)
        
        self.lbl_fatiga_estado = QLabel("ANALIZANDO...")
        self.lbl_fatiga_estado.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.lbl_fatiga_estado.setStyleSheet("color: #8fa3b8; font-size: 16px; font-weight: bold;")
        l_texto_estado.addWidget(self.lbl_fatiga_estado)
        
        self.lbl_fatiga_barra = QFrame()
        self.lbl_fatiga_barra.setFixedHeight(4)
        self.lbl_fatiga_barra.setStyleSheet("background-color: #2a3050; border-radius: 2px;")
        l_texto_estado.addWidget(self.lbl_fatiga_barra)
        
        l_estado.addWidget(fr_texto_estado, 1)
        self.l_fatiga.addWidget(fr_estado)
        
        self.lbl_fatiga_consejo = QLabel("Esperando datos del cliente.")
        self.lbl_fatiga_consejo.setAlignment(Qt.AlignLeft)
        self.lbl_fatiga_consejo.setStyleSheet("color: #8fa3b8; font-size: 10px; padding: 2px 6px 4px 6px;")
        self.lbl_fatiga_consejo.setWordWrap(True)
        self.l_fatiga.addWidget(self.lbl_fatiga_consejo)
        
        self.col_id.addWidget(self.pnl_fatiga)

        # ── PANEL LP HISTORY ──
        self.pnl_lp, self.l_lp = self.crear_panel("📈 EVOLUCIÓN DE LP (30 DÍAS)")
        lp_header = QHBoxLayout()
        self.cb_lp_queue = QComboBox()
        self.cb_lp_queue.addItems(["Solo/Dúo", "Flex"])
        self.cb_lp_queue.setFixedWidth(90)
        self.cb_lp_queue.currentIndexChanged.connect(self._actualizar_grafica_lp)
        lp_header.addWidget(QLabel("Cola:"))
        lp_header.addWidget(self.cb_lp_queue)
        lp_header.addStretch()
        self.l_lp.addLayout(lp_header)
        self.lp_graph = LPGraphWidget()
        self.lp_graph.setMinimumHeight(130)
        self.l_lp.addWidget(self.lp_graph)
        self.col_id.addWidget(self.pnl_lp)

        l_pnl.addLayout(self.col_id, 35)
        
        # ===== COLUMNA DERECHA: ESTADÍSTICAS + PERFIL + HISTORIAL =====
        self.col_hist = QVBoxLayout()
        self.col_hist.setAlignment(Qt.AlignTop)
        self.col_hist.setSpacing(6)
        
        # 1. Tarjetas de estadísticas (KDA / WR / Más jugado / Mejor WR)
        self.fr_stats_cards = QHBoxLayout()
        self.fr_stats_cards.setSpacing(6)
        
        self.card_wr, self.lbl_card_wr_val = self._crear_stat_card("📊 WINRATE", "--%", GREEN_WR)
        self.fr_stats_cards.addWidget(self.card_wr, 1)
        
        self.card_kda, self.lbl_card_kda_val = self._crear_stat_card("⚔️ KDA", "--", ACCENT_TEAL)
        self.fr_stats_cards.addWidget(self.card_kda, 1)
        
        self.card_most, self.lbl_card_most_val = self._crear_stat_card("🔥 +JUGADO", "--", BORDER_ACCENT)
        self.fr_stats_cards.addWidget(self.card_most, 1)
        
        self.card_best, self.lbl_card_best_val = self._crear_stat_card("🏆 MEJOR WR", "--", GREEN_WR)
        self.fr_stats_cards.addWidget(self.card_best, 1)
        
        self.col_hist.addLayout(self.fr_stats_cards)
        
        # WR POR LÍNEA
        self.pnl_wr_rol, self.l_wr_rol = self.crear_panel("WINRATE POR LÍNEA")
        self.fr_wr_rol = QHBoxLayout()
        self.fr_wr_rol.setSpacing(4)
        self.labels_wr_rol = {}
        for rol in UI_ROLES:
            lbl = QLabel(f"{rol}\n--")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size: 10px; color: #8fa3b8; padding: 4px;")
            self.fr_wr_rol.addWidget(lbl)
            self.labels_wr_rol[rol] = lbl
        self.l_wr_rol.addLayout(self.fr_wr_rol)
        self.col_hist.addWidget(self.pnl_wr_rol)
        
        # Filtro por campeón, modo y temporada
        self.fr_filtro = QHBoxLayout()
        lbl_filtro = QLabel("Filtrar:")
        lbl_filtro.setStyleSheet("color: #8fa3b8; font-size: 11px;")
        self.fr_filtro.addWidget(lbl_filtro)
        self.cb_filtro_champ = QComboBox()
        self.cb_filtro_champ.setMinimumWidth(140)
        self.cb_filtro_champ.addItem("Todos los campeones")
        self.cb_filtro_champ.currentTextChanged.connect(self.filtrar_historial)
        self.fr_filtro.addWidget(self.cb_filtro_champ)
        self.cb_filtro_modo = QComboBox()
        self.cb_filtro_modo.setMinimumWidth(100)
        self.cb_filtro_modo.addItem("Todos los modos")
        self.cb_filtro_modo.currentTextChanged.connect(self.filtrar_historial)
        self.fr_filtro.addWidget(self.cb_filtro_modo)
        self.cb_filtro_season = QComboBox()
        self.cb_filtro_season.setMinimumWidth(110)
        self.cb_filtro_season.addItem("Todas las temporadas")
        self.cb_filtro_season.currentTextChanged.connect(self.filtrar_historial)
        self.fr_filtro.addWidget(self.cb_filtro_season)
        self.fr_filtro.addStretch()
        self.col_hist.addLayout(self.fr_filtro)
        
        # 3. HISTORIAL DE PARTIDAS (stretch masivo)
        lbl_h = QLabel("HISTORIAL DE PARTIDAS")
        lbl_h.setStyleSheet(f"color: {ACCENT_RED}; font-weight: bold; font-size: 13px; margin-top: 4px;")
        self.col_hist.addWidget(lbl_h)
        
        # Stack: historial table + overlay vacío
        self.historial_stack = QFrame()
        hs_layout = QStackedLayout(self.historial_stack)
        hs_layout.setStackingMode(QStackedLayout.StackAll)
        
        self.tb_historial = QTableWidget()
        self.tb_historial.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.tb_historial.setColumnCount(7)
        self.tb_historial.setHorizontalHeaderLabels(["Campeón", "Resultado", "K/D/A", "CS", "Dur.", "Modo", "Fecha"])
        self.tb_historial.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tb_historial.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tb_historial.horizontalHeader().setMinimumSectionSize(80)
        self.tb_historial.setColumnWidth(1, 90)
        self.tb_historial.setColumnWidth(2, 70)
        self.tb_historial.setColumnWidth(3, 50)
        self.tb_historial.setColumnWidth(4, 60)
        self.tb_historial.setColumnWidth(5, 70)
        self.tb_historial.setColumnWidth(6, 90)
        self.tb_historial.horizontalHeader().setStretchLastSection(False)
        self.tb_historial.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb_historial.setSelectionMode(QAbstractItemView.NoSelection)
        self.tb_historial.verticalHeader().setDefaultSectionSize(28)
        self.tb_historial.setIconSize(QSize(20, 20))
        self.tb_historial.verticalHeader().setVisible(False)
        self.tb_historial.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.tb_historial.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        hs_layout.addWidget(self.tb_historial)
        
        self.lbl_historial_vacio = QLabel(
            '<div style="text-align: center; padding: 40px;">'
            '<p style="font-size: 36px; margin: 0;">📜</p>'
            '<p style="font-size: 14px; color: #64748b; margin: 8px 0 0 0;">Esperando datos del cliente...</p>'
            '<p style="font-size: 11px; color: #475569; margin: 4px 0 0 0;">Conecta al cliente de LoL para ver tu historial de partidas.</p>'
            '</div>'
        )
        self.lbl_historial_vacio.setTextFormat(Qt.RichText)
        self.lbl_historial_vacio.setAlignment(Qt.AlignCenter)
        self.lbl_historial_vacio.setStyleSheet("background: transparent;")
        self.lbl_historial_vacio.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        hs_layout.addWidget(self.lbl_historial_vacio)
        
        self.col_hist.addWidget(self.historial_stack, 1)

        # Logros row
        self.lbl_logros_title = QLabel("LOGROS")
        self.lbl_logros_title.setStyleSheet(f"color: {ACCENT_RED}; font-weight: bold; font-size: 13px; margin-top: 8px;")
        self.col_hist.addWidget(self.lbl_logros_title)
        self.fr_logros = QHBoxLayout()
        self.fr_logros.setSpacing(4)
        self.lbl_logros_text = QLabel("Conecta al cliente para ver tus logros...")
        self.lbl_logros_text.setStyleSheet("color: #64748b; font-size: 11px;")
        self.lbl_logros_text.setWordWrap(True)
        self.fr_logros.addWidget(self.lbl_logros_text)
        self.fr_logros.addStretch()
        self.col_hist.addLayout(self.fr_logros)

        self.tb_historial.verticalScrollBar().valueChanged.connect(self._on_scroll_historial)
        
        l_pnl.addLayout(self.col_hist, 65)
        layout.addWidget(self.pnl_perfil)

    def armar_tab_coaching(self):
        """Pestaña COACHING PRO con scroll, perfil de jugador y reporte de coaching completo."""
        layout = QVBoxLayout(self.tab_coaching)
        layout.setContentsMargins(10, 10, 10, 10)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("scrollCoaching")
        scroll.setStyleSheet(f"QScrollArea#scrollCoaching {{ border: none; background-color: {BG_DARK}; }} QWidget#scrollAreaWidgetContents {{ background-color: {BG_DARK}; }}")
        
        content = QWidget()
        content.setObjectName("scrollAreaWidgetContents")
        content.setStyleSheet(f"background-color: {BG_DARK};")
        self.coaching_scroll_content = QVBoxLayout(content)
        self.coaching_scroll_content.setSpacing(10)
        self.coaching_scroll_content.setAlignment(Qt.AlignTop)
        
        # ── Saludo inicial ──
        lbl_espera = QLabel(
            '<div style="font-family: \'Segoe UI\', Arial, sans-serif; text-align: center; padding: 30px;">'
            '<p style="font-size: 48px; margin: 0;">🎓</p>'
            '<p style="font-size: 16px; color: #e63946; font-weight: 700; margin: 12px 0 4px 0;">COACHING PRO</p>'
            '<p style="font-size: 12px; color: #94a3b8; margin: 0; line-height: 1.6;">'
            'Conecta al cliente de LoL para recibir tu análisis personalizado.<br><br>'
            'Aquí encontrarás:<br>'
            '🧘 Filosofía de juego y mentalidad<br>'
            '📋 Auditoría de champion pool<br>'
            '🦾 Práctica deliberada personalizada<br>'
            '⚔️ Análisis de farmeo y fase de líneas<br>'
            '🛡️ Gestión de muertes y toma de decisiones<br>'
            '👁️ Control de visión<br>'
            '🧊 Sistema de juego por bloques (3 partidas)<br>'
            '🧠 Gestión de fatiga y sesiones<br>'
            '💚 Tips de salud mental y fisiología<br>'
            '💬 Consejos personalizados de tu coach</p>'
            '<p style="font-size: 10px; color: #64748b; margin: 14px 0 0 0; font-style: italic;">'
            '✨ "Cuando cambia tu forma de pensar el LoL, cambia todo lo demás."</p>'
            '</div>'
        )
        lbl_espera.setTextFormat(Qt.RichText)
        lbl_espera.setAlignment(Qt.AlignCenter)
        lbl_espera.setWordWrap(True)
        self.coaching_scroll_content.addWidget(lbl_espera)
        self.coaching_scroll_content.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _actualizar_coaching(self):
        """Puebla la pestaña de coaching con el reporte completo y empático."""
        if not hasattr(self, 'historial_games') or not self.historial_games:
            self._mostrar_coaching_vacio()
            return
        try:
            # Obtener nombre del invocador
            nombre = "Invocador"
            if hasattr(self, 'lbl_sum_name'):
                nombre = self.lbl_sum_name.text().replace("✓ ", "").strip()
                if nombre == "Esperando al Cliente...":
                    nombre = "Invocador"
            
            # Datos de fatiga para el reporte
            datos_fatiga = None
            if hasattr(self, 'historial_games') and self.historial_games:
                try:
                    datos_fatiga = analizar_fatiga(self.historial_games)
                except: pass
            
            # Datos de personalidad, hábitos y objetivos
            datos_extra = self._generar_datos_perfil_jugador()
            
            reporte = generar_reporte_coach(self.historial_games, nombre, datos_extra, datos_fatiga)
            self._renderizar_coaching(reporte, datos_extra)
        except Exception as e:
            print(f"[_actualizar_coaching] Error: {e}")
            import traceback
            traceback.print_exc()
    
    def _generar_datos_perfil_jugador(self):
        """Genera datos de personalidad, hábitos y objetivos sin tocar UI."""
        if not hasattr(self, 'historial_games') or not self.historial_games:
            return None
        try:
            games = self.historial_games
            datos = {}
            
            personalidad = analizar_personalidad(games)
            datos["personalidad"] = personalidad
            
            insights = detectar_habitos(games)
            datos["insights"] = insights
            
            objetivos = generar_objetivos_semanales(games)
            datos["objetivos"] = objetivos
            
            emocional = analizar_emocional_vs_wr(games)
            datos["emocional"] = emocional
            
            return datos
        except Exception as e:
            print(f"[_generar_datos_perfil_jugador] Error: {e}")
            return None
    
    def _mostrar_coaching_vacio(self):
        """Muestra el estado inicial sin datos."""
        if hasattr(self, 'coaching_scroll_content'):
            clear_layout(self.coaching_scroll_content)
            lbl = QLabel(
                '<div style="font-family: \'Segoe UI\', Arial, sans-serif; text-align: center; padding: 30px;">'
                '<p style="font-size: 48px; margin: 0;">🎓</p>'
                '<p style="font-size: 16px; color: #e63946; font-weight: 700; margin: 12px 0 4px 0;">COACHING PRO</p>'
                '<p style="font-size: 12px; color: #94a3b8; margin: 0; line-height: 1.6;">'
                'Conecta al cliente de LoL para recibir tu análisis personalizado.<br><br>'
                'Aquí encontrarás:<br>'
                '🧘 Filosofía de juego y mentalidad<br>'
                '📋 Auditoría de champion pool<br>'
                '⚔️ Análisis de farmeo y fase de líneas<br>'
                '🛡️ Gestión de muertes y toma de decisiones<br>'
                '👁️ Control de visión<br>'
                '🧠 Gestión de fatiga y sesiones<br>'
                '💬 Consejos personalizados de tu coach</p>'
                '<p style="font-size: 10px; color: #64748b; margin: 14px 0 0 0; font-style: italic;">'
                '✨ "Cuando cambia tu forma de pensar el LoL, cambia todo lo demás."</p>'
                '</div>'
            )
            lbl.setTextFormat(Qt.RichText)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setWordWrap(True)
            self.coaching_scroll_content.addWidget(lbl)
            self.coaching_scroll_content.addStretch()
    
    def _renderizar_coaching(self, reporte, datos_extra=None):
        """Renderiza el reporte de coaching en la UI."""
        if not hasattr(self, 'coaching_scroll_content') or not reporte:
            return
        
        clear_layout(self.coaching_scroll_content)
        
        def _crear_card(mensaje, color_accent="#e63946", padding="16px"):
            """Crea un QFrame con borde izquierdo de acento."""
            card = QFrame()
            card.setObjectName("CoachingCard")
            card.setStyleSheet(f"""
                QFrame#CoachingCard {{ 
                    border: 1px solid #1e293b; 
                    border-left: 3px solid {color_accent}; 
                    border-radius: 6px; 
                    background-color: {BG_CARD}; 
                    padding: {padding}; 
                    margin-bottom: 6px; 
                }}
            """)
            l = QVBoxLayout(card)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(0)
            lbl = QLabel(mensaje)
            lbl.setTextFormat(Qt.RichText)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("background: transparent; border: none; color: #cbd5e1; font-size: 12px;")
            l.addWidget(lbl)
            return card
        
        # ── 1. Resumen inicial ──
        resumen = reporte.get("resumen", "")
        if resumen:
            self.coaching_scroll_content.addWidget(_crear_card(resumen, ACCENT_RED))
        
        # ── 2. Estilo de juego (personalidad) ──
        if datos_extra and datos_extra.get("personalidad"):
            pers = datos_extra["personalidad"]
            estilo = pers.get("estilo", "NEUTRAL")
            perfil_texto = pers.get("perfil", "")
            detalles = pers.get("detalles", {})
            
            colores_estilo = {"AGRESIVO": ACCENT_RED, "CONSISTENTE": GREEN_WR, "CONTROL": ACCENT_TEAL, "BALANCEADO": TEXT_GOLD}
            color_estilo = colores_estilo.get(estilo, TEXT_WHITE)
            
            pers_html = f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7;">
            <p style="font-size: 14px; color: {color_estilo}; margin: 0 0 8px 0;"><b>🎯 Tu estilo: {estilo}</b></p>
            <p style="font-size: 12px; color: #cbd5e1; margin: 0 0 8px 0;">{perfil_texto}</p>
            <p style="font-size: 11px; color: #64748b; margin: 0;">KDA: {detalles.get('avg_kda','?')} · Clase preferida: {detalles.get('clase_predominante','?')} · Partidas: {detalles.get('total_games','?')}</p>
            </div>"""
            self.coaching_scroll_content.addWidget(_crear_card(pers_html, color_estilo))
        
        # ── 3. Insights / hábitos ──
        if datos_extra and datos_extra.get("insights"):
            insights = datos_extra["insights"]
            if insights and insights[0] != "⚠️ Necesitas al menos 5 partidas para detectar patrones.":
                ins_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
                ins_html += '<p style="font-size: 13px; color: #2dd4bf; margin: 0 0 6px 0;"><b>🔍 Lo que detecté en tu juego:</b></p>'
                for ins in insights[:5]:
                    ins_html += f'<p style="font-size: 11px; color: #cbd5e1; margin: 3px 0;">• {ins}</p>'
                ins_html += '</div>'
                self.coaching_scroll_content.addWidget(_crear_card(ins_html, "#2dd4bf"))
        
        # ── 4. Secciones de análisis ──
        secciones = reporte.get("secciones", [])
        for sec in secciones:
            color_borde = sec.get("color", BORDER_SUBTLE)
            html = f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7;">
            <p style="font-size: 13px; color: {color_borde}; font-weight: 700; margin: 0 0 6px 0;">
            {sec.get('icono', '📊')} {sec.get('titulo', '')}
            </p>
            {sec.get('html', '')}
            </div>"""
            self.coaching_scroll_content.addWidget(_crear_card(html, color_borde, "14px"))
        
        # ── 5. Objetivos semanales ──
        if datos_extra and datos_extra.get("objetivos"):
            objs = datos_extra["objetivos"]
            if objs and "Juega al menos 5 partidas" not in objs[0]:
                obj_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
                obj_html += '<p style="font-size: 13px; color: #e63946; margin: 0 0 6px 0;"><b>🎯 Tus objetivos para esta semana:</b></p>'
                for obj in objs:
                    obj_html += f'<p style="font-size: 11px; color: #cbd5e1; margin: 3px 0;">🎯 {obj}</p>'
                obj_html += '</div>'
                self.coaching_scroll_content.addWidget(_crear_card(obj_html, "#e63946"))
        
        # ── 6. Rendimiento emocional ──
        if datos_extra and datos_extra.get("emocional"):
            emocional = datos_extra["emocional"]
            if emocional:
                emo_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
                emo_html += '<p style="font-size: 13px; color: #f59e0b; margin: 0 0 6px 0;"><b>📊 Rendimiento por estado de ánimo:</b></p>'
                emoji_map = {"Concentrado": "🔥", "Normal": "😐", "Tilted": "😤", "Cansado": "😴"}
                for estado, data in sorted(emocional.items(), key=lambda x: x[1].get("wr", 0), reverse=True):
                    wr_e = data.get("wr", 0)
                    n = data.get("partidas", 0)
                    emoji = emoji_map.get(estado, "❓")
                    color_wr = "#22c55e" if wr_e >= 50 else "#ef4444"
                    emo_html += f'<p style="font-size: 11px; color: #cbd5e1; margin: 2px 0;">{emoji} {estado}: <b style="color:{color_wr};">{wr_e}% WR</b> ({n} partidas)</p>'
                emo_html += '<p style="font-size: 10px; color: #64748b; margin: 6px 0 0 0;">💡 Etiqueta tus partidas en MI PERFIL para ver estadísticas emocionales.</p>'
                emo_html += '</div>'
                self.coaching_scroll_content.addWidget(_crear_card(emo_html, "#f59e0b"))
        
        # ── 7. Consejo final ──
        consejo = reporte.get("consejo_final", "")
        if consejo:
            consejo_html = f'<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;"><p style="font-size: 13px; color: #f1f5f9; margin: 0 0 6px 0;"><b>💬 Mensaje de tu coach:</b></p><p style="font-size: 12px; color: #cbd5e1; margin: 0; font-style: italic;">{consejo}</p></div>'
            self.coaching_scroll_content.addWidget(_crear_card(consejo_html, ACCENT_RED))
        
        # Añadir stretch al final
        self.coaching_scroll_content.addStretch()

    # ================= CARGA DE PERFIL (HILO SEGUNDARIO) =================
    def _fetch_perfil(self):
        """Se ejecuta en hilo secundario. Recoge TODOS los datos de LCU sin tocar UI.
        Incluye reintentos con backoff porque la API de LCU tarda unos segundos en
        estar disponible tras abrir el cliente."""
        data = {"ok": False}
        try:
            # ── Fase 1: Perfil base (con reintentos, la API puede no estar lista) ──
            perfil = None
            for intento in range(5):
                perfil = self.lcu.obtener_perfil()
                if perfil and (perfil.get("displayName") or perfil.get("gameName") or perfil.get("summonerName")):
                    break
                print(f"[_fetch_perfil] Intento {intento+1}/5: perfil no disponible, esperando...")
                perfil = None
                time.sleep(2)
            
            if not perfil:
                print("[_fetch_perfil] No se pudo obtener el perfil tras 5 intentos.")
                self._cargando_perfil = False
                self.perfil_listo.emit(data)
                return
            
            data["perfil"] = perfil
            perfil_ok = True
            
            # ── Fase 2: Ligas (con reintentos — la API de ranked tarda en arrancar) ──
            ligas = None
            for intento_l in range(4):
                try:
                    ligas = self.lcu.obtener_ligas()
                    if ligas and ligas.get("queues"):
                        break
                except Exception as e:
                    print(f"[_fetch_perfil] Error ligas intento {intento_l+1}: {e}")
                if intento_l < 3:
                    time.sleep(1.5)
            if not ligas or not ligas.get("queues"):
                print("[_fetch_perfil] No se pudieron obtener ligas (no fatal).")
            data["ligas"] = ligas
            
            # ── Fase 3: Maestrías (no fatal si falla) ──
            maestrias = []
            try:
                maestrias = self.lcu.obtener_maestrias()
            except Exception as e:
                print(f"[_fetch_perfil] Error obteniendo maestrías (no fatal): {e}")
            data["maestrias"] = maestrias[:3] if maestrias else []
            
            # ── Fase 4: Historial (con reintentos, no fatal si falla) ──
            puuid = perfil.get("puuid")
            historial = None
            if puuid:
                for intento in range(3):
                    try:
                        historial = self.lcu.obtener_historial_extendido(puuid=puuid, inicio=0, cantidad=100)
                        if historial:
                            break
                    except Exception as e:
                        print(f"[_fetch_perfil] Error historial intento {intento+1}: {e}")
                    if intento < 2:
                        time.sleep(2)
                if not historial:
                    print("[_fetch_perfil] No se pudo obtener historial (no fatal).")
            data["historial"] = historial
            
            # ── Fase 5: Season stats (paginación completa para toda la temporada) ──
            all_games = list(historial) if historial else []
            if all_games and self.lcu and self.lcu.port:
                try:
                    def _gid(g):
                        gid = str(g.get("gameId", "") or "")
                        if not gid:
                            gid = f"{g.get('gameCreationDate','')}_{g.get('gameDuration',0)}"
                        return gid
                    existing_ids = {_gid(g) for g in all_games}
                    for offset in range(100, 2000, 100):
                        batch = self.lcu.obtener_historial_extendido(puuid=puuid, inicio=offset, cantidad=100)
                        if not batch:
                            break
                        new_batch = [g for g in batch if _gid(g) and _gid(g) not in existing_ids]
                        if not new_batch:
                            break
                        for g in new_batch:
                            existing_ids.add(_gid(g))
                        all_games.extend(new_batch)
                        if len(batch) < 100:
                            break
                    print(f"[_fetch_perfil] Season stats: {len(all_games)} partidas totales (temporada completa)")
                except Exception as e:
                    print(f"[_fetch_perfil] Error paginando season stats (no fatal): {e}")
            data["all_games_season"] = all_games
            
            data["ok"] = perfil_ok
        except Exception as e:
            print(f"[_fetch_perfil] Error crítico: {e}")
            data["ok"] = False
        finally:
            # Emitir señal para que el hilo principal actualice la UI
            self.perfil_listo.emit(data)

    def _on_perfil_listo(self, data):
        """Se ejecuta en el hilo principal. Actualiza la UI con los datos ya recogidos."""
        self._cargando_perfil = False
        
        if not data.get("ok") or not data.get("perfil"):
            print(f"[_on_perfil_listo] Datos insuficientes (ok={data.get('ok')}), se reintentará.")
            return
        
        try:
            perfil = data["perfil"]
            self.perfil_cargado = True
            
            # --- Nombre y nivel ---
            display_name = perfil.get("displayName") or perfil.get("gameName") or perfil.get("summonerName") or perfil.get("name") or "Invocador"
            tagline = perfil.get("tagLine")
            if tagline and tagline not in display_name:
                display_name = f"{display_name}#{tagline}"
            self.lbl_sum_name.setText(display_name)
            self.lbl_sum_lvl.setText(f"Nivel: {perfil.get('summonerLevel', '--')}")
            
            # --- Icono de perfil (tamano compacto para tarjeta fusionada) ---
            icon_id = perfil.get("profileIconId")
            ruta_icon = self.descargar_imagen(icon_id, "profile")
            if ruta_icon:
                self.lbl_prof_icon.setPixmap(QPixmap(ruta_icon).scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))

            # --- Ligas ---
            ligas = data.get("ligas")
            queues = []
            if isinstance(ligas, dict) and "queues" in ligas:
                queues = ligas["queues"]
            elif isinstance(ligas, list):
                queues = ligas

            ranked_solo = None
            ranked_flex = None
            for queue in queues:
                qtype = str(queue.get("queueType") or queue.get("queue") or "").upper()
                tier = str(queue.get("tier") or "").strip()
                division = str(queue.get("division") or queue.get("rankDivision") or queue.get("rank") or "").strip()
                lp = queue.get("leaguePoints") or queue.get("lp") or 0
                wins = queue.get("wins") or queue.get("winCount") or 0
                losses = queue.get("losses") or queue.get("lossCount") or 0
                if not tier:
                    continue
                if "SOLO" in qtype and "FLEX" not in qtype:
                    ranked_solo = {"tier": tier, "division": division, "lp": lp, "wins": wins, "losses": losses}
                elif "FLEX" in qtype:
                    ranked_flex = {"tier": tier, "division": division, "lp": lp, "wins": wins, "losses": losses}
                elif not ranked_solo and ("RANKED" in qtype or "SOLO" in qtype):
                    ranked_solo = {"tier": tier, "division": division, "lp": lp, "wins": wins, "losses": losses}

            print(f"[Perfil] SoloQ: {ranked_solo}, Flex: {ranked_flex}")

            def _format_rank(rank_data, lbl_tier, lbl_stats, prefijo=""):
                """Formato compacto para tarjeta fusionada (1 linea)."""
                if not rank_data or not rank_data.get("tier"):
                    lbl_tier.setText(f"{prefijo}--")
                    lbl_stats.setText("")
                    return
                t = rank_data["tier"]
                d = rank_data.get("division", "").strip()
                lp = rank_data.get("lp", 0)
                w = rank_data.get("wins", 0)
                l = rank_data.get("losses", 0)
                color = self._rank_to_color(t)
                icon = self._rank_icon(t)
                if d not in ("I", "II", "III", "IV"):
                    d = ""
                display_tier = f"{icon} {t.capitalize()} {d}" if d else f"{icon} {t.capitalize()}"
                lbl_tier.setText(display_tier)
                lbl_tier.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px;")
                total = w + l
                if total > 0:
                    wr = round(w / total * 100)
                    lbl_stats.setText(f"{lp} PL | {total}p | {wr}%")
                else:
                    lbl_stats.setText(f"{lp} PL")

            _format_rank(ranked_solo, self.lbl_soloq_tier, self.lbl_soloq_stats)
            _format_rank(ranked_flex, self.lbl_flex_tier, self.lbl_flex_stats)

            # Registrar LP del día y actualizar gráfica
            try:
                if ranked_solo and ranked_solo.get("tier"):
                    registrar_lp(ranked_solo["tier"], ranked_solo.get("division", ""),
                                 ranked_solo.get("lp", 0), ranked_solo.get("wins", 0),
                                 ranked_solo.get("losses", 0), "RANKED_SOLO_5x5")
                if ranked_flex and ranked_flex.get("tier"):
                    registrar_lp(ranked_flex["tier"], ranked_flex.get("division", ""),
                                 ranked_flex.get("lp", 0), ranked_flex.get("wins", 0),
                                 ranked_flex.get("losses", 0), "RANKED_FLEX_SR")
                self._actualizar_grafica_lp()
            except Exception as _e_lp:
                print(f"[LP] Error registrando: {_e_lp}")

            # --- Historial ---
            historial = data.get("historial")
            if not historial:
                self.lbl_card_wr_val.setText("--%")
                self.lbl_card_kda_val.setText("--")
                self.lbl_card_most_val.setText("--")
                self.lbl_card_best_val.setText("--")
                self.cb_filtro_champ.clear()
                self.cb_filtro_champ.addItem("Todos los campeones")
                self._analizar_fatiga()
                return
            
            # obtener_historial_extendido devuelve lista directa, el viejo devuelve dict
            games = historial if isinstance(historial, list) else historial.get("games", {}).get("games", [])
            # DEDUP: el batching de LCU puede devolver partidas duplicadas entre lotes
            seen = set()
            games_dedup = []
            for g in games:
                gid = str(g.get("gameId", ""))
                if not gid:
                    gid = f"{g.get('gameCreationDate','')}_{g.get('gameDuration',0)}"
                if gid and gid not in seen:
                    seen.add(gid)
                    games_dedup.append(g)
            if len(games_dedup) < len(games):
                print(f"[Perfil] DEDUP historial: {len(games)} -> {len(games_dedup)} partidas unicas")
            games = games_dedup
            self.historial_games = games
            # Guardar all_games_season si viene del fetch (paginación ya hecha en hilo secundario)
            self.all_games_season = data.get("all_games_season", list(games))
            self._renderizar_historial(games)
        except Exception as e:
            print(f"[_on_perfil_listo] Error renderizando UI: {e}")
            import traceback
            traceback.print_exc()
            # Si falla el renderizado, permitimos reintentar en el siguiente tick
            self.perfil_cargado = False

    def _renderizar_historial(self, games):
        """Renderiza la tabla de historial (reusable para lazy loading)."""
        self.tb_historial.setRowCount(0)

        # DEDUP: evitar partidas duplicadas del batching de LCU
        seen_gids = set()
        unique = []
        for g in games:
            gid = str(g.get("gameId", ""))
            if not gid:
                gid = f"{g.get('gameCreationDate','')}_{g.get('gameDuration',0)}"
            if gid and gid not in seen_gids:
                seen_gids.add(gid)
                unique.append(g)
        games = unique

        # Ordenar partidas por fecha (mas reciente primero) usando timestamp
        try:
            games = sorted(games, key=lambda g: (
                self._parse_game_date(g) or datetime(2000,1,1)
            ), reverse=True)
        except:
            pass

        total_k = 0; total_d = 0; total_a = 0; victorias = 0; total_games = 0
        champ_stats = {}
        
        for g in games:
            part_info = g.get("participants", [{}])[0]
            stats = part_info.get("stats", {})
            champ_id = str(part_info.get("championId", "0"))
            champ_name = self.procesar_nombre_champ(champ_id, "0") or "Desconocido"
            
            win = stats.get("win", False)
            k = stats.get("kills", 0)
            d = stats.get("deaths", 0)
            a = stats.get("assists", 0)
            cs = stats.get("totalMinionsKilled", 0) + stats.get("neutralMinionsKilled", 0)
            duration_sec = g.get("gameDuration", 0)
            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
            
            # LP
            lp_delta = g.get("eloChange") or g.get("playerScoreChange") or stats.get("eloChange")
            if lp_delta is not None:
                lp_str = f"{'+' if lp_delta > 0 else ''}{lp_delta}"
            else:
                lp_str = "--"
            
            # Fecha (usa timestamp gameCreation, fallback a gameCreationDate)
            fecha = self._format_game_date(g)
            
            total_k += k; total_d += d; total_a += a; total_games += 1
            if win: victorias += 1
            
            if champ_name not in champ_stats:
                champ_stats[champ_name] = {"wins": 0, "games": 0, "kills": 0, "deaths": 0, "assists": 0}
            cs_entry = champ_stats[champ_name]
            cs_entry["games"] += 1
            if win: cs_entry["wins"] += 1
            cs_entry["kills"] += k
            cs_entry["deaths"] += d
            cs_entry["assists"] += a
            
            row = self.tb_historial.rowCount()
            self.tb_historial.insertRow(row)
            item_c = QTableWidgetItem(f"  {self._nombre_con_dificultad(champ_name)}")
            icon_p = self.descargar_imagen(champ_name, "champ")
            if icon_p: item_c.setIcon(QIcon(icon_p))
            item_w = QTableWidgetItem("VICTORIA" if win else "DERROTA")
            item_w.setForeground(QColor(GREEN_WR if win else RED_WR))
            modo_juego = self._clasificar_modo_juego(g)
            
            self.tb_historial.setItem(row, 0, item_c)
            self.tb_historial.setItem(row, 1, item_w)
            self.tb_historial.setItem(row, 2, QTableWidgetItem(f"{k}/{d}/{a}"))
            self.tb_historial.setItem(row, 3, QTableWidgetItem(str(cs)))
            self.tb_historial.setItem(row, 4, QTableWidgetItem(duration_min))
            self.tb_historial.setItem(row, 5, QTableWidgetItem(modo_juego))
            self.tb_historial.setItem(row, 6, QTableWidgetItem(fecha))

        # --- Tarjetas de estadisticas ---
        if total_games > 0:
            wr = round((victorias / total_games) * 100)
            kda = round((total_k + total_a) / max(1, total_d), 2)
            avg_k = round(total_k / total_games, 1)
            avg_d = round(total_d / total_games, 1)
            avg_a = round(total_a / total_games, 1)
            self.lbl_card_wr_val.setText(f"{wr}%")
            self.lbl_card_wr_val.setToolTip(f"{victorias}V / {total_games - victorias}D en {total_games} partidas")
            self.lbl_card_kda_val.setText(f"{kda}")
            self.lbl_card_kda_val.setToolTip(f"Promedio: {avg_k}/{avg_d}/{avg_a} por partida")
            most_played = max(champ_stats, key=lambda c: champ_stats[c]["games"])
            most_g = champ_stats[most_played]["games"]
            self.lbl_card_most_val.setText(most_played[:10])
            self.lbl_card_most_val.setStyleSheet(f"color: {BORDER_ACCENT}; font-size: 16px; font-weight: bold;")
            self.lbl_card_most_val.setToolTip(f"{most_g} partidas con {most_played}")
            best_wr_champs = {c: s for c, s in champ_stats.items() if s["games"] >= 2}
            if best_wr_champs:
                best_champ = max(best_wr_champs, key=lambda c: best_wr_champs[c]["wins"] / best_wr_champs[c]["games"])
                best_wr = round(champ_stats[best_champ]["wins"] / champ_stats[best_champ]["games"] * 100)
                self.lbl_card_best_val.setText(f"{best_champ[:8]} {best_wr}%")
                self.lbl_card_best_val.setStyleSheet(f"color: {GREEN_WR}; font-size: 14px; font-weight: bold;")
                self.lbl_card_best_val.setToolTip(f"{best_wr}% WR con {best_champ} en {champ_stats[best_champ]['games']} partidas")
            else:
                self.lbl_card_best_val.setText("--")
            wr_color = GREEN_WR if wr >= 50 else RED_WR
            self.lbl_card_wr_val.setStyleSheet(f"color: {wr_color}; font-size: 26px; font-weight: bold;")
        else:
            self.lbl_card_wr_val.setText("--%")
            self.lbl_card_kda_val.setText("--")
            self.lbl_card_most_val.setText("--")
            self.lbl_card_best_val.setText("--")

        # --- WR POR LÍNEA (1 sola query para todos los campeones) ---
        conn = obtener_conexion()
        cur = conn.cursor()
        
        # Recoger campeones únicos del historial
        champs_hist = list(set(
            self.procesar_nombre_champ(str(g.get("participants", [{}])[0].get("championId", "0")), "0") or "?"
            for g in self.historial_games
        ))
        
        # 1 sola query: rol más frecuente de cada campeón
        rol_por_champ = {}
        if champs_hist:
            placeholders = ",".join(["?"] * len(champs_hist))
            cur.execute(f"""
                SELECT champion, team_position FROM (
                    SELECT champion, team_position,
                           ROW_NUMBER() OVER (PARTITION BY champion ORDER BY COUNT(*) DESC) as rn
                    FROM participantes
                    WHERE champion IN ({placeholders})
                    GROUP BY champion, team_position
                ) WHERE rn = 1
            """, champs_hist)
            for row in cur.fetchall():
                rol_por_champ[row["champion"]] = row["team_position"]
        
        rol_stats = {}
        for g in self.historial_games:
            part_info = g.get("participants", [{}])[0]
            champ_id = str(part_info.get("championId", "0"))
            champ_name = self.procesar_nombre_champ(champ_id, "0") or "Desconocido"
            rol_api = rol_por_champ.get(champ_name)
            if not rol_api:
                continue
            rol_ui = API_TO_ROL.get(rol_api.upper(), rol_api.upper())
            if rol_ui not in rol_stats:
                rol_stats[rol_ui] = {"wins": 0, "games": 0}
            win = part_info.get("stats", {}).get("win", False)
            rol_stats[rol_ui]["games"] += 1
            if win:
                rol_stats[rol_ui]["wins"] += 1
        conn.close()
        
        for rol, lbl in self.labels_wr_rol.items():
            if rol in rol_stats and rol_stats[rol]["games"] > 0:
                s = rol_stats[rol]
                wr_rol = round(s["wins"] / s["games"] * 100)
                color = GREEN_WR if wr_rol >= 50 else RED_WR
                lbl.setText(f"{rol}\n{wr_rol}%")
                lbl.setStyleSheet(f"font-size: 11px; color: {color}; font-weight: bold; padding: 4px;")
                lbl.setToolTip(f"{s['wins']}V / {s['games']-s['wins']}D en {s['games']} partidas")
            else:
                lbl.setText(f"{rol}\n--")
                lbl.setStyleSheet("font-size: 10px; color: #8fa3b8; padding: 4px;")
                lbl.setToolTip("Sin datos en el historial reciente")

        # --- ESTADÍSTICAS DE LA SEASON + FATIGA ---
        self._cargar_stats_season()
        self._analizar_fatiga()

        # --- Filtro de campeones + modos de juego ---
        champs_usados = sorted(set(
            self.procesar_nombre_champ(str(g.get("participants", [{}])[0].get("championId", "0")), "0") or "?"
            for g in self.historial_games
        ))
        self.cb_filtro_champ.blockSignals(True)
        self.cb_filtro_champ.clear()
        self.cb_filtro_champ.addItem("Todos los campeones")
        self.cb_filtro_champ.addItems(champs_usados)
        self.cb_filtro_champ.blockSignals(False)
        
        modos_usados = sorted(set(
            self._clasificar_modo_juego(g)
            for g in self.historial_games
        ))
        self.cb_filtro_modo.blockSignals(True)
        self.cb_filtro_modo.clear()
        self.cb_filtro_modo.addItem("Todos los modos")
        self.cb_filtro_modo.addItems(modos_usados)
        self.cb_filtro_modo.blockSignals(False)
        
        # --- Filtro por temporada ---
        years_usados = sorted(set(
            str(y) for y in (self._extraer_year(g) for g in self.historial_games)
            if y is not None
        ), reverse=True)
        self.cb_filtro_season.blockSignals(True)
        self.cb_filtro_season.clear()
        self.cb_filtro_season.addItem("Todas las temporadas")
        self.cb_filtro_season.addItems(years_usados)
        self.cb_filtro_season.blockSignals(False)

        # ─── FASE 4: COACHING PRO ───
        self._actualizar_coaching()

        # ─── FASE 5: LOGROS ───
        self._cargar_logros()

    def _actualizar_perfil_jugador(self):
        """Puebla el panel de PERFIL DE JUGADOR & OBJETIVOS con datos del historial."""
        if not hasattr(self, 'historial_games') or not self.historial_games:
            return
        try:
            games = self.historial_games
            
            # 1. Personalidad
            personalidad = analizar_personalidad(games)
            estilo = personalidad.get("estilo", "NEUTRAL")
            perfil_texto = personalidad.get("perfil", "")
            detalles = personalidad.get("detalles", {})
            
            colores_estilo = {
                "AGRESIVO": ACCENT_RED, "CONSISTENTE": GREEN_WR,
                "CONTROL": ACCENT_TEAL, "BALANCEADO": TEXT_GOLD
            }
            color_estilo = colores_estilo.get(estilo, TEXT_WHITE)
            
            self.lbl_personality_style.setText(f"{estilo}")
            self.lbl_personality_style.setStyleSheet(
                f"color: {color_estilo}; font-size: 16px; font-weight: 700; padding: 4px 0;")
            self.lbl_personality_desc.setText(perfil_texto)
            
            # 2. Insights / Habitos
            insights = detectar_habitos(games)
            if insights:
                self.lbl_insights_title.setText("🔍 INSIGHTS DETECTADOS")
                self.lbl_insights.setText("\n".join(f"• {i}" for i in insights[:5]))
            
            # 3. Objetivos semanales
            objetivos = generar_objetivos_semanales(games)
            if objetivos:
                self.lbl_objetivos_title.setText("🎯 OBJETIVOS SEMANALES")
                self.lbl_objetivos.setText("\n".join(objetivos))
            
            # 4. Cruce emocional vs WR
            emocional = analizar_emocional_vs_wr(games)
            if emocional:
                self.lbl_emocional_title.setText("📊 RENDIMIENTO POR ESTADO")
                lineas = []
                emoji_map = {"Concentrado": "🔥", "Normal": "😐", "Tilted": "😤", "Cansado": "😴"}
                for estado, data in sorted(emocional.items(), key=lambda x: x[1].get("wr", 0), reverse=True):
                    wr_e = data.get("wr", 0)
                    n = data.get("partidas", 0)
                    emoji = emoji_map.get(estado, "❓")
                    lineas.append(f"{emoji} {estado}: {wr_e}% WR ({n} partidas)")
                self.lbl_emocional_stats.setText("\n".join(lineas) if lineas else "Etiqueta tus partidas para ver estadísticas")
        except Exception as e:
            print(f"[_actualizar_perfil_jugador] Error: {e}")

    def _actualizar_grafica_lp(self):
        """Refresca la gráfica de LP con los datos de la cola seleccionada."""
        if not hasattr(self, "lp_graph"):
            return
        queue_map = {"Solo/Dúo": "RANKED_SOLO_5x5", "Flex": "RANKED_FLEX_SR"}
        queue = queue_map.get(self.cb_lp_queue.currentText(), "RANKED_SOLO_5x5")
        try:
            history = obtener_historial_lp(queue, dias=30)
            self.lp_graph.set_data(history)
        except Exception as e:
            print(f"[LP Graph] Error: {e}")

    def _analizar_fatiga(self):
        """Analiza fatiga/tilt desde el historial de la LCU y actualiza el dashboard premium."""
        if not hasattr(self, 'historial_games') or not self.historial_games:
            self.lbl_fatiga_icono.setText("📊")
            self.lbl_fatiga_icono.setStyleSheet("font-size: 28px; padding: 0px;")
            self.lbl_fatiga_estado.setText("SIN DATOS")
            self.lbl_fatiga_estado.setStyleSheet("color: #8fa3b8; font-size: 16px; font-weight: bold;")
            self.lbl_fatiga_consejo.setText("Esperando datos del cliente.")
            self.lbl_fatiga_consejo.setStyleSheet("color: #8fa3b8; font-size: 10px; padding: 2px 6px 4px 6px;")
            return
        try:
            # Solo considerar partidas de hoy para no detectar fatiga de sesiones viejas
            hoy = str(date.today())
            games_hoy = []
            for g in self.historial_games:
                dt = self._parse_game_date(g)
                if dt and str(dt.date()) == hoy:
                    games_hoy.append(g)
            if not games_hoy:
                estado = "fresh"
                mensaje = "🌅 ¡No has jugado hoy! Estás en tu mejor momento."
                recomendacion = "La mente está fresca y los reflejos listos. Calienta con un normal o salta directo a ranked. Hoy es tu día."
            else:
                fatiga = analizar_fatiga(games_hoy)
                estado = fatiga.get("estado", "neutral")
                mensaje = fatiga.get("mensaje", "Sin datos")
                recomendacion = fatiga.get("recomendacion", "")
            
            emojis = {"fresh": "🔥", "neutral": "⚖️", "tired": "🥱", "tilted": "💢"}
            colores = {"fresh": GREEN_WR, "neutral": ACCENT_TEAL, "tired": YELLOW_WR, "tilted": RED_WR}
            textos_color = {"fresh": "#064e3b", "neutral": "#134e4a", "tired": "#713f12", "tilted": "#7f1d1d"}
            textos = {"fresh": "ÓPTIMO", "neutral": "NEUTRAL", "tired": "CANSADO", "tilted": "TILTEADO"}
            
            emoji = emojis.get(estado, "🔥")
            color = colores.get(estado, GREEN_WR)
            bar_color = colores.get(estado, GREEN_WR)
            bar_bg = textos_color.get(estado, "#064e3b")
            estado_txt = textos.get(estado, "ÓPTIMO")
            
            self.lbl_fatiga_icono.setText(emoji)
            self.lbl_fatiga_icono.setStyleSheet("font-size: 28px; padding: 0px;")
            self.lbl_fatiga_estado.setText(estado_txt)
            self.lbl_fatiga_estado.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
            self.lbl_fatiga_barra.setStyleSheet(f"background-color: {bar_color}; border-radius: 2px;")
            
            if recomendacion:
                self.lbl_fatiga_consejo.setText(f"💡 {recomendacion}")
            else:
                self.lbl_fatiga_consejo.setText(mensaje)
            self.lbl_fatiga_consejo.setStyleSheet("color: #8fa3b8; font-size: 10px; padding: 2px 6px 4px 6px;")
        except Exception as e:
            print(f"[_analizar_fatiga] Error: {e}")
            self.lbl_fatiga_icono.setText("❌")
            self.lbl_fatiga_icono.setStyleSheet("font-size: 28px; padding: 0px;")
            self.lbl_fatiga_estado.setText("ERROR")
            self.lbl_fatiga_estado.setStyleSheet(f"color: {RED_WR}; font-size: 16px; font-weight: bold;")
            self.lbl_fatiga_consejo.setText("No se pudo analizar el estado mental.")
            self.lbl_fatiga_consejo.setStyleSheet("color: #8fa3b8; font-size: 10px; padding: 2px 6px 4px 6px;")

    def _on_scroll_historial(self, value):
        """Scroll infinito: carga mas partidas cuando el usuario llega al final."""
        scrollbar = self.tb_historial.verticalScrollBar()
        if scrollbar.maximum() > 0 and value >= scrollbar.maximum() - 50:
            if not hasattr(self, '_cargando_historial'):
                self._cargando_historial = False
            if self._cargando_historial:
                return
            self._cargando_historial = True
            self._cargar_mas_partidas_scroll()

    def _cargar_mas_partidas_scroll(self):
        """Carga 50 partidas ADICIONALES via LCU. Concatena sin borrar la tabla."""
        try:
            if not self.lcu or not self.lcu.port: return
            current = len(self.historial_games) if hasattr(self, 'historial_games') else 0
            if current >= 500: return
            perfil = self.lcu.obtener_perfil()
            if not perfil: return
            puuid = perfil.get("puuid")
            if not puuid: return
            
            # Cargar siguiente bloque: desde current hasta current+50
            nuevas = self.lcu.obtener_historial_extendido(inicio=current, cantidad=50)
            if not nuevas: return
            
            # Filtrar duplicados por gameId
            existing_ids = {str(g.get("gameId", "")) for g in self.historial_games}
            really_new = [g for g in nuevas if str(g.get("gameId", "")) not in existing_ids]
            
            if really_new:
                self.historial_games.extend(really_new)
                # Añadir filas de forma ADITIVA (no limpiar tabla)
                self._append_games_to_table(really_new)
        finally:
            self._cargando_historial = False

    def _append_games_to_table(self, games):
        """Añade partidas a la tabla sin borrar las existentes."""
        for g in games:
            part_info = g.get("participants", [{}])[0]
            stats = part_info.get("stats", {})
            champ_id = str(part_info.get("championId", "0"))
            champ_name = self.procesar_nombre_champ(champ_id, "0") or "Desconocido"
            
            win = stats.get("win", False)
            k = stats.get("kills", 0)
            d = stats.get("deaths", 0)
            a = stats.get("assists", 0)
            cs = stats.get("totalMinionsKilled", 0) + stats.get("neutralMinionsKilled", 0)
            duration_sec = g.get("gameDuration", 0)
            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
            
            fecha = self._format_game_date(g)
            
            modo_juego = self._clasificar_modo_juego(g)
            
            row = self.tb_historial.rowCount()
            self.tb_historial.insertRow(row)
            item_c = QTableWidgetItem(f"  {self._nombre_con_dificultad(champ_name)}")
            icon_p = self.descargar_imagen(champ_name, "champ")
            if icon_p: item_c.setIcon(QIcon(icon_p))
            item_w = QTableWidgetItem("VICTORIA" if win else "DERROTA")
            item_w.setForeground(QColor(GREEN_WR if win else RED_WR))
            
            self.tb_historial.setItem(row, 0, item_c)
            self.tb_historial.setItem(row, 1, item_w)
            self.tb_historial.setItem(row, 2, QTableWidgetItem(f"{k}/{d}/{a}"))
            self.tb_historial.setItem(row, 3, QTableWidgetItem(str(cs)))
            self.tb_historial.setItem(row, 4, QTableWidgetItem(duration_min))
            self.tb_historial.setItem(row, 5, QTableWidgetItem(modo_juego))
            self.tb_historial.setItem(row, 6, QTableWidgetItem(fecha))

    # ═══════════════════════════════════════════════════════════
    # MOTOR EMOCIONAL — ETIQUETADO DE PARTIDAS (NEXUS)
    # ═══════════════════════════════════════════════════════════

    def _crear_widget_emocional(self, game_id: str, champ_name: str, estado_actual: str = None):
        """Crea un widget con 4 botones de estado emocional para una fila del historial."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        estados = [
            ("🔥", "Concentrado", "#ef4444", "Concentrado: enfoque total"),
            ("😐", "Normal", "#64748b", "Normal: estado neutro"),
            ("😤", "Tilted", "#f59e0b", "Tilted: frustrado"),
            ("😴", "Cansado", "#3b82f6", "Cansado: fatiga"),
        ]

        for emoji, estado, color, tooltip in estados:
            btn = QPushButton(emoji)
            btn.setFixedSize(28, 24)
            btn.setToolTip(tooltip)
            if estado_actual == estado:
                btn.setStyleSheet(f"""
                    QPushButton {{ background-color: {color}; color: #fff; border: 1px solid {color}; 
                                   border-radius: 3px; font-size: 13px; padding: 0px; }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{ background-color: transparent; color: #475569; border: 1px solid #1e293b; 
                                   border-radius: 3px; font-size: 13px; padding: 0px; }}
                    QPushButton:hover {{ background-color: {color}; color: #fff; border: 1px solid {color}; }}
                """)
            btn.clicked.connect(lambda checked, gid=game_id, est=estado, ch=champ_name: 
                                self._on_tag_emocional(gid, est, ch))
            layout.addWidget(btn)

        return widget

    def _on_tag_emocional(self, game_id: str, estado: str, champion: str):
        """Guarda el estado emocional y refresca la fila."""
        try:
            # Obtener puuid del perfil actual
            puuid = ""
            if hasattr(self, 'perfil_data') and self.perfil_data:
                puuid = self.perfil_data.get("puuid", "")
            etiquetar_estado_emocional(game_id, estado, puuid, champion)
            # Refrescar solo el historial para mostrar el nuevo estado
            if hasattr(self, 'historial_games'):
                self._renderizar_historial(self.historial_games)
        except Exception as e:
            print(f"[_on_tag_emocional] Error: {e}")

    def filtrar_historial(self, _=None):
        """Filtra la tabla de historial por campeón, modo y temporada."""
        if not hasattr(self, 'historial_games') or not self.historial_games:
            return
        filtro_champ = self.cb_filtro_champ.currentText()
        filtro_modo = self.cb_filtro_modo.currentText()
        filtro_season = self.cb_filtro_season.currentText()
        
        self.tb_historial.setRowCount(0)
        for g in self.historial_games:
            part_info = g.get("participants", [{}])[0]
            stats = part_info.get("stats", {})
            champ_id = str(part_info.get("championId", "0"))
            champ_name = self.procesar_nombre_champ(champ_id, "0") or "Desconocido"
            
            modo_juego = g.get("gameMode", "Draft")
            if modo_juego == "CLASSIC": modo_juego = "Ranked"

            if filtro_champ != "Todos los campeones" and champ_name != filtro_champ:
                continue
            if filtro_modo != "Todos los modos" and modo_juego != filtro_modo:
                continue

            season_year = self._extraer_year(g)
            if filtro_season != "Todas las temporadas" and str(season_year) != filtro_season:
                continue

            win = stats.get("win", False)
            k = stats.get("kills", 0)
            d = stats.get("deaths", 0)
            a = stats.get("assists", 0)
            cs = stats.get("totalMinionsKilled", 0) + stats.get("neutralMinionsKilled", 0)
            duration_sec = g.get("gameDuration", 0)
            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
            
            # LP delta
            lp_delta = g.get("eloChange") or g.get("playerScoreChange") or stats.get("eloChange")
            if lp_delta is not None:
                lp_str = f"{'+' if lp_delta > 0 else ''}{lp_delta}"
            else:
                lp_str = "--"
            
            # Fecha
            fecha = self._format_game_date(g)

            row = self.tb_historial.rowCount()
            self.tb_historial.insertRow(row)
            item_c = QTableWidgetItem(f"  {self._nombre_con_dificultad(champ_name)}")
            icon_p = self.descargar_imagen(champ_name, "champ")
            if icon_p: item_c.setIcon(QIcon(icon_p))
            item_w = QTableWidgetItem("VICTORIA" if win else "DERROTA")
            item_w.setForeground(QColor(GREEN_WR if win else RED_WR))
            
            self.tb_historial.setItem(row, 0, item_c)
            self.tb_historial.setItem(row, 1, item_w)
            self.tb_historial.setItem(row, 2, QTableWidgetItem(f"{k}/{d}/{a}"))
            self.tb_historial.setItem(row, 3, QTableWidgetItem(str(cs)))
            self.tb_historial.setItem(row, 4, QTableWidgetItem(duration_min))
            self.tb_historial.setItem(row, 5, QTableWidgetItem(modo_juego))
            self.tb_historial.setItem(row, 6, QTableWidgetItem(fecha))

    # ================= RADAR EN VIVO =================
    def armar_tab_vivo(self):
        layout = QVBoxLayout(self.tab_vivo)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        top_bar = QHBoxLayout()
        self.lbl_estado_lcu = QLabel("Buscando Cliente de LoL...")
        self.lbl_estado_lcu.setStyleSheet(f"color: {YELLOW_WR}; font-weight: bold; font-size: 14px;")
        top_bar.addWidget(self.lbl_estado_lcu)
        top_bar.addStretch()
        
        self.lbl_wr_numero = QLabel("--%")
        self.lbl_wr_numero.setStyleSheet("color: gray; font-family: Impact; font-size: 42px;")
        top_bar.addWidget(self.lbl_wr_numero)
        self.lbl_wr_razon = QLabel("Esperando equipos...")
        self.lbl_wr_razon.setStyleSheet("color: gray; font-style: italic;")
        top_bar.addWidget(self.lbl_wr_razon)
        layout.addLayout(top_bar)

        # Coach tip en Champ Select
        self.lbl_radar_tip = QLabel("💡 <b>Consejo:</b> En Champ Select, prioriza counter-pickear a tu rival de línea. Revisa runas y hechizos recomendados abajo.")
        self.lbl_radar_tip.setWordWrap(True)
        self.lbl_radar_tip.setTextFormat(Qt.RichText)
        self.lbl_radar_tip.setStyleSheet(f"color: #cbd5e1; font-size: 10px; padding: 6px 10px; background-color: #0f172a; border: 1px solid #1e293b; border-left: 3px solid {ACCENT_TEAL}; border-radius: 4px; margin-bottom: 2px;")
        layout.addWidget(self.lbl_radar_tip)

        # Tips de matchup (ocultos hasta que haya rival detectado)
        self.lbl_matchup_tips = QLabel("")
        self.lbl_matchup_tips.setWordWrap(True)
        self.lbl_matchup_tips.setTextFormat(Qt.RichText)
        self.lbl_matchup_tips.setStyleSheet(f"color: {YELLOW_WR}; font-size: 10px; padding: 5px 10px; background-color: #1a1200; border: 1px solid #3d2e00; border-left: 3px solid {YELLOW_WR}; border-radius: 4px; margin-bottom: 2px;")
        self.lbl_matchup_tips.setVisible(False)
        layout.addWidget(self.lbl_matchup_tips)

        draft_layout = QHBoxLayout()
        draft_layout.setAlignment(Qt.AlignTop)

        self.col_enemy, l_enemy = self.crear_panel("Enemigos")
        self.lbl_enemy_stats = QLabel("AD: --% | AP: --% | Tanks: 0")
        self.lbl_enemy_stats.setStyleSheet(f"color: {RED_WR}; font-weight: bold;")
        l_enemy.addWidget(self.lbl_enemy_stats)
        
        self.fr_enemigos_picks = QVBoxLayout()
        l_enemy.addLayout(self.fr_enemigos_picks)
        l_enemy.addStretch()
        
        self.panel_bans_vivo, self.l_bans_vivo = self.crear_panel("Bans Sugeridos (Tu Línea)")
        self.fr_bans_icons_vivo = QHBoxLayout()
        self.l_bans_vivo.addLayout(self.fr_bans_icons_vivo)
        l_enemy.addWidget(self.panel_bans_vivo)
        
        self.panel_counters_vivo, self.l_counters_vivo = self.crear_panel("Counters vs Rival")
        self.fr_counters_vivo = QHBoxLayout()
        self.l_counters_vivo.addLayout(self.fr_counters_vivo)
        l_enemy.addWidget(self.panel_counters_vivo)
        draft_layout.addWidget(self.col_enemy, 1)

        col_center = QWidget()
        l_center = QVBoxLayout(col_center)
        l_center.setAlignment(Qt.AlignTop)
        
        self.lbl_rol_vivo = QLabel("ASIGNACIÓN PENDIENTE")
        self.lbl_rol_vivo.setStyleSheet(f"color: {BORDER_ACCENT}; font-weight: bold; font-size: 18px;")
        self.lbl_rol_vivo.setAlignment(Qt.AlignCenter)
        l_center.addWidget(self.lbl_rol_vivo)
        
        self.panel_sugerencias, self.l_sugerencias = self.crear_panel("Recomendaciones de Pick")
        self.fr_picks_icons = QGridLayout()
        self.l_sugerencias.addLayout(self.fr_picks_icons)
        l_center.addWidget(self.panel_sugerencias, 1)
        
        self.panel_runas_vivo, self.l_runas_vivo = self.crear_panel("Setup Recomendado Integral")
        self.fr_runas_icons_vivo = QVBoxLayout()
        self.fr_runas_icons_vivo.setAlignment(Qt.AlignTop)
        self.l_runas_vivo.addLayout(self.fr_runas_icons_vivo)
        l_center.addWidget(self.panel_runas_vivo, 2)
        self.inicializar_panel_setup(self.fr_runas_icons_vivo)
        
        # Skill Order
        self.panel_skills, self.l_skills = self.crear_panel("📖 RUTA DE HABILIDADES")
        self.lbl_skill_order = QLabel("Selecciona un campeón")
        self.lbl_skill_order.setAlignment(Qt.AlignCenter)
        self.lbl_skill_order.setStyleSheet(f"color: {ACCENT_TEAL}; font-size: 16px; font-weight: bold; padding: 8px;")
        self.l_skills.addWidget(self.lbl_skill_order)
        self.btn_export_skills = QPushButton("📤 Subir orden al Cliente")
        self.btn_export_skills.setStyleSheet(f"""
            QPushButton {{ background-color: {BG_CARD}; border: 1px solid {ACCENT_TEAL}; border-radius: 4px; color: {ACCENT_TEAL}; font-size: 11px; padding: 6px 16px; font-weight: bold; }}
            QPushButton:hover {{ background-color: #1a3a3a; }}
            QPushButton:disabled {{ color: #475569; border-color: #1e293b; }}
        """)
        self.btn_export_skills.clicked.connect(lambda: self.accion_importar_skill_order(self.btn_export_skills))
        self.btn_export_skills.setVisible(False)
        self.l_skills.addWidget(self.btn_export_skills, alignment=Qt.AlignCenter)
        l_center.addWidget(self.panel_skills)

        # ── PANEL PATHING JUNGLA (solo visible cuando rol = JUNGLA) ──
        self.pnl_pathing, self.l_pathing = self.crear_panel("🗺️ PATHING DE JUNGLA")
        self.lbl_pathing_estilo = QLabel("")
        self.lbl_pathing_estilo.setStyleSheet(f"font-size: 12px; font-weight: bold; padding: 2px 0;")
        self.l_pathing.addWidget(self.lbl_pathing_estilo)
        self.lbl_pathing_inicio = QLabel("")
        self.lbl_pathing_inicio.setWordWrap(True)
        self.lbl_pathing_inicio.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 10px;")
        self.l_pathing.addWidget(self.lbl_pathing_inicio)
        self.lbl_pathing_ruta = QLabel("")
        self.lbl_pathing_ruta.setWordWrap(True)
        self.lbl_pathing_ruta.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 10px;")
        self.l_pathing.addWidget(self.lbl_pathing_ruta)
        self.lbl_pathing_gank = QLabel("")
        self.lbl_pathing_gank.setWordWrap(True)
        self.lbl_pathing_gank.setStyleSheet(f"color: {ACCENT_TEAL}; font-size: 10px;")
        self.l_pathing.addWidget(self.lbl_pathing_gank)
        self.lbl_pathing_vs = QLabel("")
        self.lbl_pathing_vs.setWordWrap(True)
        self.lbl_pathing_vs.setStyleSheet(f"color: {YELLOW_WR}; font-size: 10px; padding-top: 2px;")
        self.l_pathing.addWidget(self.lbl_pathing_vs)
        self.pnl_pathing.setVisible(False)
        l_center.addWidget(self.pnl_pathing)

        draft_layout.addWidget(col_center, 3)

        self.col_ally, l_ally = self.crear_panel("Aliados")
        self.lbl_ally_stats = QLabel("AD: --% | AP: --% | Tanks: 0")
        self.lbl_ally_stats.setStyleSheet(f"color: {ACCENT_TEAL}; font-weight: bold;")
        l_ally.addWidget(self.lbl_ally_stats)
        self.fr_aliados_picks = QVBoxLayout()
        l_ally.addLayout(self.fr_aliados_picks)
        l_ally.addStretch() 
        draft_layout.addWidget(self.col_ally, 1)
        
        layout.addLayout(draft_layout)

    def abrir_settings(self):
        dlg = SettingsDialog(self.user_settings, self)
        if dlg.exec() == QDialog.Accepted:
            self.user_settings = dlg.get_settings()
            guardar_settings(self.user_settings)
            self._aplicar_settings()

    def _aplicar_settings(self):
        """Aplica los settings actuales a los timers y comportamientos."""
        self.timer_lcu.setInterval(self.user_settings.get("frecuencia_radar", 1500))
        if not self.user_settings.get("auto_deteccion", True):
            self.timer_lcu.stop()
        else:
            if not self.timer_lcu.isActive():
                self.timer_lcu.start()

    def _reproducir_sonido(self, tipo="info"):
        """Reproduce un sonido de alerta si los sonidos estan activados."""
        if not self.user_settings.get("sonidos", False):
            return
        try:
            import winsound
            if tipo == "info": winsound.MessageBeep(winsound.MB_ICONINFORMATION)
            elif tipo == "alerta": winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            elif tipo == "draft": winsound.MessageBeep(winsound.MB_OK)
        except: pass

    def auto_detectar_lcu(self):
        """Solo hace operaciones rápidas (leer lockfile). El trabajo pesado (HTTP)
        se lanza en hilos secundarios para no congelar la UI."""
        conectado = self.lcu.conectar()
        
        if not conectado:
            # Cliente cerrado o lockfile desapareció → resetear todo
            if self.radar_activo:
                self.radar_activo = False
                self.perfil_cargado = False
                self._cargando_perfil = False
                self._actualizando_radar = False
                self.last_aliados = []
                self.last_enemigos = []
                self.last_my_champ = None
                self.lbl_estado_lcu.setText("Buscando Cliente de LoL... (Abre el juego)")
                self.lbl_estado_lcu.setStyleSheet(f"color: {YELLOW_WR}; font-weight: bold; font-size: 14px;")
            return
        
        # Cliente detectado por primera vez
        if not self.radar_activo:
            self.radar_activo = True
            self._reproducir_sonido("info")
            self.lbl_estado_lcu.setText("✓ ENLAZADO AL CLIENTE DE LOL")
            self.lbl_estado_lcu.setStyleSheet(f"color: {GREEN_WR}; font-weight: bold; font-size: 14px;")
            # Pequeña pausa: la API HTTP del cliente tarda ~2s en estar lista tras
            # aparecer el lockfile. Sin esto, el primer fetch falla y el usuario
            # pensaría que la app no funciona.
            time.sleep(1.5)
        
        # Cargar perfil en hilo secundario (si no está ya cargándose)
        if not self.perfil_cargado and not self._cargando_perfil:
            self._cargando_perfil = True
            threading.Thread(target=self._fetch_perfil, daemon=True).start()
        
        # Actualizar radar/draft en hilo secundario (si no está ya actualizándose)
        if not self._actualizando_radar:
            self._actualizando_radar = True
            threading.Thread(target=self._fetch_radar, daemon=True).start()
        
        # Auto-switch de pestañas segun fase del juego + notificaciones
        fase = self.lcu.obtener_fase_juego()
        if fase != self._last_fase:
            # Notificaciones de escritorio en transiciones de fase
            if self.user_settings.get("notificaciones_escritorio", True) and hasattr(self, 'tray_icon') and self.tray_icon:
                if fase == "ReadyCheck":
                    self.tray_icon.showMessage("NEXUS", "Partida encontrada", QIcon(), 4000)
                    self._reproducir_sonido("info")
                elif fase == "ChampSelect":
                    self.tray_icon.showMessage("NEXUS", "Champ Select iniciado", QIcon(), 4000)
                elif fase == "PreEndOfGame":
                    self.tray_icon.showMessage("NEXUS", "Partida terminada — Ver analisis", QIcon(), 4000)
                    # Marcar ultimo draft como completado
                    try:
                        from datetime import date
                        completar_draft_resultado(str(date.today()), None)
                    except Exception as e:
                        print(f"[DraftHistory] Error completando draft: {e}")

            # Auto-aceptar partida
            if fase == "ReadyCheck" and self.user_settings.get("auto_aceptar", False):
                try:
                    self.lcu.request('POST', '/lol-matchmaking/v1/ready-check/accept')
                    if hasattr(self, 'tray_icon') and self.tray_icon:
                        self.tray_icon.showMessage("NEXUS", "Partida aceptada automaticamente", QIcon(), 3000)
                except Exception as e:
                    log.warning("Auto-aceptar fallo: %s", e)

            self._last_fase = fase

            # Actualizar Discord Rich Presence
            try:
                if fase in ("GameStart", "InProgress"):
                    actualizar_discord_rpc(
                        details="En partida",
                        state="League of Legends - SoloQ",
                        large_text="Jugando"
                    )
                elif fase == "ChampSelect":
                    actualizar_discord_rpc(
                        details="Seleccion de campeones",
                        state="Champ Select",
                        large_text="Draftero"
                    )
                elif fase == "ReadyCheck":
                    actualizar_discord_rpc(
                        details="Partida encontrada",
                        state="Aceptando...",
                        large_text="En cola"
                    )
                else:
                    actualizar_discord_rpc(
                        details="En el cliente de LoL",
                        state="Menu principal",
                        large_text="League of Legends"
                    )
            except Exception:
                pass

        if fase == "ChampSelect":
            if self.tabview.currentIndex() != 2 and self.user_settings.get("auto_switch_radar", True):
                self.tabview.setCurrentIndex(2)  # RADAR EN VIVO
        elif fase in ("GameStart", "InProgress"):
            if self.tabview.currentIndex() != 3 and self.user_settings.get("auto_switch_radar", True):
                self.tabview.setCurrentIndex(3)  # PARTIDA EN VIVO

    def _clasificar_modo_juego(self, g):
        game_type = g.get("gameType", "")
        game_mode = g.get("gameMode", "")
        queue_id = g.get("queueId", 0)
        if game_type == "CUSTOM_GAME":
            return "Custom"
        if game_type == "PRACTICE_GAME":
            return "vs IA"
        if queue_id == 420:
            return "SoloQ"
        if queue_id == 440:
            return "Flex"
        if queue_id in (400, 430):
            return "Normal"
        if game_mode == "ARAM":
            return "ARAM"
        if game_mode == "CLASSIC":
            return "Normal"
        return game_mode or "Normal"

    def procesar_nombre_champ(self, cid, intent):
        final_id = str(cid) if str(cid) != "0" else str(intent)
        if final_id != "0": return "Wukong" if MAPEO_IDS_CAMPEONES.get(final_id) == "MonkeyKing" else MAPEO_IDS_CAMPEONES.get(final_id, "Desconocido")
        return None

    def _nombre_db(self, nombre):
        """Normaliza un nombre de campeon (posiblemente en espanol) al nombre interno
        en ingles que usa la base de datos y el sistema de tags."""
        if not nombre: return nombre
        return self.nombre_interno.get(nombre, nombre)

    def _nombres_db(self, nombres):
        """Normaliza una lista de nombres para queries SQL."""
        return [self._nombre_db(n) for n in nombres] if nombres else nombres

    def _nombre_display(self, nombre):
        """Traduce nombre interno (EN) a nombre para mostrar en UI (ES)."""
        if not nombre: return nombre
        return self.nombre_display.get(nombre, nombre)

    # ================= RADAR / DRAFT (HILO SEGUNDARIO) =================
    def _fetch_radar(self):
        """Se ejecuta en hilo secundario. Solo obtiene el draft de LCU."""
        try:
            draft = self.lcu.obtener_sesion_draft()
        except Exception as e:
            draft = None
        self.radar_listo.emit(draft)

    def _on_radar_listo(self, draft):
        """Se ejecuta en el hilo principal. Actualiza la UI del radar.
        Si no hay draft activo, simplemente se salta la actualización SIN desconectar."""
        self._actualizando_radar = False
        
        if not self.radar_activo:
            return
        
        if not draft:
            # No hay sesión de draft activa → no desconectar, solo esperar
            return
        
        try:
            rol_api = self.lcu.obtener_mi_rol(draft)
            rol_ui = API_TO_ROL.get(rol_api, "MID")
            self.lbl_rol_vivo.setText(f"LÍNEA ASIGNADA: {rol_ui}")

            picks_al, picks_en = [], []
            pos_al, pos_en = [], []
            mi_campeon = None
            mi_celda = draft.get("localPlayerCellId")

            for j in draft.get("myTeam", []):
                champ = self.procesar_nombre_champ(j.get("championId", 0), j.get("championPickIntent", 0))
                if champ:
                    picks_al.append(champ)
                    pos_al.append(j.get("assignedPosition", "MIDDLE"))
                if j.get("cellId") == mi_celda: mi_campeon = champ
                
            enemigo_lane = None
            posiciones = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
            # Normalizador de posiciones (LCU puede devolver SUPPORT en vez de UTILITY)
            def _normalizar_pos(pos_str):
                p = (pos_str or "").upper().strip()
                mapa = {"SUPPORT": "UTILITY", "ADC": "BOTTOM", "JUNGLA": "JUNGLE", "MID": "MIDDLE"}
                return mapa.get(p, p) if p in posiciones or p in mapa else ""

            # Cache de campeones por rol para inferir rol tipico
            if not hasattr(self, '_cache_rol_tipico'):
                self._cache_rol_tipico = {}
            # Reconstruir cache si el rol actual no tiene datos
            if rol_api not in self._cache_rol_tipico or not self._cache_rol_tipico.get(rol_api):
                for rol_key in posiciones:
                    champs_rol = set(obtener_campeones_por_rol(rol_key, min_partidas=5))
                    self._cache_rol_tipico[rol_key] = champs_rol

            enemigos_procesados = []
            for idx, j in enumerate(draft.get("theirTeam", [])):
                champ = self.procesar_nombre_champ(j.get("championId", 0), j.get("championPickIntent", 0))
                if champ:
                    picks_en.append(champ)
                    pos = _normalizar_pos(j.get("assignedPosition", ""))
                    pos_from_lcu = bool(pos)  # Solo confiar en posiciones reales de la LCU
                    if not pos:
                        # Inferir rol por indice (ultimo recurso antes de datos)
                        pos = posiciones[idx] if idx < 5 else "MIDDLE"
                    pos_en.append(pos)
                    enemigos_procesados.append((champ, pos, idx))
                    # Solo asignar rival de linea si la posicion viene de la LCU (no del indice)
                    if pos_from_lcu and pos == rol_api:
                        enemigo_lane = champ
            
            # Fallback inteligente si no se encontro rival de linea por posicion
            if not enemigo_lane and enemigos_procesados:
                # 1. Por CLASE del campeon (mas fiable: Marksman→BOTTOM, Support→UTILITY, etc.)
                from src.tags_champions import obtener_tag
                rol_to_class = {
                    "TOP": ("Fighter", "Tank"), "JUNGLE": ("Fighter", "Tank", "Assassin"),
                    "MIDDLE": ("Mage", "Assassin"), "BOTTOM": ("Marksman",),
                    "UTILITY": ("Support",)
                }
                expected = rol_to_class.get(rol_api, ())
                for champ, pos, idx in enemigos_procesados:
                    try:
                        tag = obtener_tag(champ)
                        if tag.get("champion_class", "") in expected:
                            enemigo_lane = champ
                            print(f"[Radar] Rival de linea por clase: {champ} ({tag.get('champion_class')}) en {rol_api}")
                            break
                    except Exception:
                        pass
                
                # 2. Por rol tipico en BD (cache) — con tiebreaker: el mas frecuente en este rol
                if not enemigo_lane:
                    cache_rol = self._cache_rol_tipico.get(rol_api, set())
                    candidatos_cache = []
                    conn_radar = obtener_conexion()
                    try:
                        for champ, pos, idx in enemigos_procesados:
                            if champ in cache_rol:
                                # Obtener frecuencia de este champ en este rol para tiebreaker
                                try:
                                    cur = conn_radar.cursor()
                                    cur.execute(
                                        "SELECT COUNT(*) FROM participantes WHERE champion=? AND team_position=?",
                                        (champ, rol_api))
                                    freq = cur.fetchone()[0]
                                except Exception:
                                    freq = 0
                                candidatos_cache.append((champ, freq))
                    finally:
                        conn_radar.close()
                    if candidatos_cache:
                        # Elegir el campeon mas frecuente en este rol, no el primero de la lista
                        candidatos_cache.sort(key=lambda x: x[1], reverse=True)
                        enemigo_lane = candidatos_cache[0][0]
                        print(f"[Radar] Rival de linea inferido por rol tipico (frec={candidatos_cache[0][1]}): {enemigo_lane} en {rol_api}")
                
                # 3. Por posicion normalizada de la LCU (si no coincidio antes por alguna razon)
                if not enemigo_lane:
                    for champ, pos, idx in enemigos_procesados:
                        if pos and pos.upper() == rol_api.upper():
                            enemigo_lane = champ
                            break
                
                # 4. Por indice verificando rol tipico (ultimo recurso)
                if not enemigo_lane:
                    mi_idx = next((i for i, j in enumerate(draft.get("myTeam", [])) if j.get("cellId") == mi_celda), -1)
                    if 0 <= mi_idx < len(enemigos_procesados):
                        champ_idx = enemigos_procesados[mi_idx][0]
                        if champ_idx in cache_rol:
                            enemigo_lane = champ_idx
                            print(f"[Radar] Rival de linea por indice (verificado): {champ_idx} en {rol_api}")
                
            if picks_al != self.last_aliados or picks_en != self.last_enemigos:
                self.last_aliados, self.last_enemigos = picks_al.copy(), picks_en.copy()
                
                self.mostrar_equipo_vivo(self.fr_aliados_picks, picks_al, is_ally=True)
                self.mostrar_equipo_vivo(self.fr_enemigos_picks, picks_en, is_ally=False)
                
                # Normalizar nombres a ingles para queries SQL y tags
                picks_al_db = self._nombres_db(picks_al)
                picks_en_db = self._nombres_db(picks_en)
                
                ad_al, ap_al, tanks_al = analizar_composicion(picks_al_db)
                self.lbl_ally_stats.setText(f"Daño AD: {ad_al}% | Daño AP: {ap_al}% | Frontlane: {tanks_al}")
                ad_en, ap_en, tanks_en = analizar_composicion(picks_en_db)
                self.lbl_enemy_stats.setText(f"Daño AD: {ad_en}% | Daño AP: {ap_en}% | Frontlane: {tanks_en}")
                
                self.mostrar_picks_vivo(rol_api, picks_al_db, picks_en_db)

                # Actualizar counters si cambia el rival de linea (aunque no haya cambiado mi pick)
                if enemigo_lane != self.last_enemigo_lane:
                    self._actualizar_counters_vivo(rol_api, enemigo_lane)

                if len(picks_al_db) == 5 and len(picks_en_db) == 5:
                    wr = calcular_winrate_5v5(picks_al_db, picks_en_db, pos_al, pos_en)
                    color = GREEN_WR if wr > 52 else RED_WR if wr < 48 else YELLOW_WR
                    tendencia = "↑ Ventaja de Sinergia" if wr > 52 else "↓ Desventaja de Draft" if wr < 48 else "≈ Matchup Equilibrado"
                    self.lbl_wr_numero.setText(f"{wr}%")
                    self.lbl_wr_numero.setStyleSheet(f"color: {color}; font-family: Impact; font-size: 42px;")
                    self.lbl_wr_razon.setText(tendencia)
                    self.lbl_wr_razon.setStyleSheet(f"color: {color}; font-style: italic;")

                    # Guardar draft en historial
                    if mi_campeon:
                        try:
                            bans_actuales = [self.procesar_nombre_champ(
                                b.get("championId", 0), 0) for b in draft.get("bans", {}).get("myBans", [])]
                            bans_actuales = [b for b in bans_actuales if b]
                            guardar_draft(mi_campeon, rol_api, bans_actuales, picks_al, picks_en, wr)
                        except Exception as e:
                            print(f"[DraftHistory] Error guardando draft: {e}")

            if mi_campeon != self.last_my_champ or rol_api != self.last_my_role:
                self.last_my_champ = mi_campeon
                self.last_my_role = rol_api
                
                clear_layout(self.fr_bans_icons_vivo)
                if mi_campeon: 
                    self.panel_bans_vivo.label_title.setText(
                        f"BANS SI PICKEO {self._nombre_display(mi_campeon).upper()}"
                    )
                    bans_sugeridos = obtener_peores_matchups(mi_campeon, rol_api, min_partidas=20)
                    # Fallback: si no hay datos para este campeon en este rol (ej. Quinn JG),
                    # usar bans generales del rol
                    if not bans_sugeridos:
                        bans_sugeridos = obtener_peores_matchups(mi_campeon, rol_api, min_partidas=5)
                    if not bans_sugeridos:
                        # Ultimo fallback: bans mas comunes del rol
                        bans_sugeridos = obtenermejoresbaneos(rol_api, min_partidas=20)
                        self.panel_bans_vivo.label_title.setText(f"BANS SUGERIDOS ({rol_ui})")
                else: 
                    self.panel_bans_vivo.label_title.setText(f"BANS SUGERIDOS ({rol_ui})")
                    bans_sugeridos = obtenermejoresbaneos(rol_api, min_partidas=20)

                bans_filtrados = [(b, wr, p) for b, wr, p in bans_sugeridos if b not in self.last_aliados and b not in self.last_enemigos][:4]
                if bans_filtrados:
                    for i, (ban, wr, partidas) in enumerate(bans_filtrados): 
                        self.renderizar_icono(ban, "champ", self.fr_bans_icons_vivo, 0, i,
                            f"🚫 Baneo sugerido: {self._nombre_display(ban)}\n📊 WR rival: {wr}% en {partidas} partidas", size=35)
                else: 
                    lbl_noban = QLabel("Sin recomendaciones")
                    lbl_noban.setStyleSheet("color: gray;")
                    self.fr_bans_icons_vivo.addWidget(lbl_noban)

                # ── COUNTER PICKS contra el rival de linea ──
                self._actualizar_counters_vivo(rol_api, enemigo_lane)

                if mi_campeon:
                    ids_runas = obtener_top_runas(mi_campeon, rol_api)
                    ids_runas = ajustar_shards_adaptativos(
                        ids_runas,
                        self._nombre_db(mi_campeon) or mi_campeon,
                        self._nombre_db(enemigo_lane) or enemigo_lane if enemigo_lane else None,
                        [self._nombre_db(c) or c for c in picks_en_db],
                    )
                    ids_spells = obtener_top_hechizos(mi_campeon, rol_api)
                    ids_start, ids_core = obtener_top_items(mi_campeon, rol_api, enemigos=self.last_enemigos)
                    ids_sit = obtener_items_situacionales(
                        self._nombre_db(mi_campeon) or mi_campeon,
                        rol_api,
                        [self._nombre_db(e) or e for e in self.last_enemigos],
                        excluir=ids_core,
                    ) if self.last_enemigos else []
                    self.renderizar_setup_completo(mi_campeon, ids_runas, ids_spells, ids_start, ids_core, self.fr_runas_icons_vivo, ids_sit=ids_sit)
                    
                    # Ruta de habilidades
                    skill_key = self._nombre_db(mi_campeon) or mi_campeon
                    skill_key_sanitized = skill_key.replace(" ", "").replace("'", "").replace(".", "")
                    skill_order = SKILL_ORDERS.get(skill_key_sanitized, SKILL_ORDERS.get(skill_key, "Q>W>E"))
                    self.current_skill_order = skill_order
                    self.lbl_skill_order.setText(f"Max: {skill_order}  (R al 6/11/16)")
                    self.btn_export_skills.setVisible(True)

                    # Auto-import segun configuración
                    if self.user_settings.get("auto_runas", False):
                        self._auto_importar_runas(ids_runas, mi_campeon)
                    if self.user_settings.get("auto_hechizos", False):
                        self._auto_importar_hechizos(ids_spells)
                    if self.user_settings.get("auto_habilidades", False):
                        self._auto_importar_skill_order()
                    if self.user_settings.get("auto_items", False):
                        self._auto_importar_items(mi_campeon, ids_start, ids_core)
                else: 
                    self.current_skill_order = None
                    self.inicializar_panel_setup(self.fr_runas_icons_vivo)
                    self.lbl_skill_order.setText("Selecciona un campeón")
                    self.btn_export_skills.setVisible(False)
            # ── PATHING JUNGLA ──
            if rol_api == "JUNGLE" and mi_campeon:
                # Buscar jungla enemigo en picks
                enemy_jg = None
                for champ, pos, _ in enemigos_procesados:
                    if pos and pos.upper() == "JUNGLE":
                        enemy_jg = champ
                        break
                pathing = sugerir_pathing_jungla(
                    self._nombre_db(mi_campeon) or mi_campeon,
                    self._nombre_db(enemy_jg) or enemy_jg if enemy_jg else None,
                    [self._nombre_db(c) or c for c in picks_al if c != mi_campeon],
                    [self._nombre_db(c) or c for c in picks_en],
                )
                self.lbl_pathing_estilo.setText(pathing.get("label", ""))
                self.lbl_pathing_estilo.setStyleSheet(
                    f"font-size: 12px; font-weight: bold; color: {pathing.get('color', ACCENT_TEAL)};"
                )
                self.lbl_pathing_inicio.setText(f"🏁 Inicio: {pathing.get('inicio', '')}")
                self.lbl_pathing_ruta.setText(f"📍 Ruta: {pathing.get('ruta', '')}")
                self.lbl_pathing_gank.setText(f"🗡️ Gank: {pathing.get('prioridad_gank', '')}")
                vs = pathing.get("vs_jungla", "")
                self.lbl_pathing_vs.setText(vs)
                self.lbl_pathing_vs.setVisible(bool(vs))
                self.pnl_pathing.setVisible(True)
            else:
                self.pnl_pathing.setVisible(False)

            # Actualizar tip según estado del draft
            if mi_campeon and enemigo_lane:
                self.lbl_radar_tip.setText(
                    f"⚡ <b>Coach:</b> Juegas <b>{self._nombre_display(mi_campeon)}</b> vs <b>{self._nombre_display(enemigo_lane)}</b>. "
                    f"Revisa los counters, runas y hechizos abajo. ¡Buena suerte!"
                )
            elif mi_campeon and not enemigo_lane:
                self.lbl_radar_tip.setText(
                    f"🎯 <b>Coach:</b> Pickeaste {self._nombre_display(mi_campeon)}. Revisa el setup recomendado abajo. "
                    f"Prioriza runas y objetos según la composición enemiga."
                )
            elif not mi_campeon and len(picks_al) > 0:
                self.lbl_radar_tip.setText(
                    "💡 <b>Coach:</b> Espera a ver el pick rival antes de elegir. "
                    "Mientras, revisa los bans sugeridos y la composición de tu equipo."
                )
            else:
                self.lbl_radar_tip.setText(
                    "💡 <b>Coach:</b> En Champ Select, prioriza counter-pickear a tu rival de línea. "
                    "Revisa runas y hechizos recomendados abajo."
                )

            # Tips de matchup específicos
            if enemigo_lane:
                enemy_db = self._nombre_db(enemigo_lane) or enemigo_lane
                tips = obtener_tips_matchup(enemy_db)
                if tips:
                    tips_html = "  |  ".join(f"• {t}" for t in tips[:2])
                    self.lbl_matchup_tips.setText(
                        f"🗡️ <b>vs {self._nombre_display(enemigo_lane)}:</b>  {tips_html}"
                    )
                    self.lbl_matchup_tips.setVisible(True)
                else:
                    self.lbl_matchup_tips.setVisible(False)
            else:
                self.lbl_matchup_tips.setVisible(False)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════
    # PARTIDA EN VIVO (Porofessor-style)
    # ═══════════════════════════════════════════════════════════

    def armar_tab_partida(self):
        layout = QVBoxLayout(self.tab_partida)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Header
        self.lbl_partida_header = QLabel("🎮 Esperando partida...\n\nLos datos apareceran cuando entres a la Grieta")
        self.lbl_partida_header.setAlignment(Qt.AlignCenter)
        self.lbl_partida_header.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 16px; padding: 20px;")
        layout.addWidget(self.lbl_partida_header)

        # Dashboard compacto
        self.pnl_partida_dash = QFrame()
        self.pnl_partida_dash.setObjectName("Panel")
        self.pnl_partida_dash.setVisible(False)
        dash_layout = QVBoxLayout(self.pnl_partida_dash)
        dash_layout.setSpacing(6)

        # Fila 1: Tu KDA + tiempo
        fila1 = QHBoxLayout()
        self.lbl_partida_kda = QLabel("Tu KDA: --/--/--")
        self.lbl_partida_kda.setStyleSheet(f"color: {TEXT_GOLD}; font-size: 16px; font-weight: bold;")
        fila1.addWidget(self.lbl_partida_kda)
        fila1.addStretch()
        self.lbl_partida_timer = QLabel("00:00")
        self.lbl_partida_timer.setStyleSheet(f"color: {ACCENT_TEAL}; font-size: 22px; font-weight: bold; font-family: Consolas;")
        fila1.addWidget(self.lbl_partida_timer)
        self.lbl_partida_cs = QLabel("CS: --")
        self.lbl_partida_cs.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; margin-left: 12px;")
        fila1.addWidget(self.lbl_partida_cs)
        dash_layout.addLayout(fila1)

        layout.addWidget(self.pnl_partida_dash)

        # Dos tablas lado a lado: aliados y enemigos
        tablas_layout = QHBoxLayout()
        tablas_layout.setSpacing(8)

        # ── Aliados ──
        self.tb_partida_aliados = QTableWidget()
        self.tb_partida_aliados.setColumnCount(4)
        self.tb_partida_aliados.setHorizontalHeaderLabels(["Campeon", "KDA", "CS", "Comentario"])
        self._estilizar_tabla_partida(self.tb_partida_aliados, "#0f172a")
        tablas_layout.addWidget(self.tb_partida_aliados)

        # ── Enemigos ──
        self.tb_partida_enemigos = QTableWidget()
        self.tb_partida_enemigos.setColumnCount(4)
        self.tb_partida_enemigos.setHorizontalHeaderLabels(["Campeon", "KDA", "CS", "Comentario"])
        self._estilizar_tabla_partida(self.tb_partida_enemigos, "#1a0a0f")
        tablas_layout.addWidget(self.tb_partida_enemigos)

        layout.addLayout(tablas_layout, 1)

        # Composición
        self.lbl_partida_comp = QLabel("")
        self.lbl_partida_comp.setAlignment(Qt.AlignCenter)
        self.lbl_partida_comp.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self.lbl_partida_comp)

    def _estilizar_tabla_partida(self, tabla, bg_color):
        tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tabla.setSelectionMode(QAbstractItemView.NoSelection)
        tabla.verticalHeader().setDefaultSectionSize(38)
        tabla.verticalHeader().setVisible(False)
        tabla.setStyleSheet(f"""
            QTableWidget {{ background-color: {bg_color}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; font-size: 11px; }}
            QTableWidget::item {{ padding: 2px 6px; border-bottom: 1px solid #1a2236; }}
            QHeaderView::section {{ background-color: #0f172a; color: {TEXT_MUTED}; font-size: 10px; padding: 3px; border: none; }}
        """)

    def actualizar_partida_vivo(self):
        """Actualiza la pestaña de partida en vivo con datos del LiveClient."""
        if not self.lcu or not self.lcu.port:
            return

        fase = self.lcu.obtener_fase_juego()
        if fase not in ("InProgress", "GameStart"):
            if hasattr(self, "overlay") and self.overlay._visible:
                self.overlay.hide_overlay()
            self.pnl_partida_dash.setVisible(False)
            self.tb_partida_aliados.setVisible(False)
            self.tb_partida_enemigos.setVisible(False)
            self.lbl_partida_header.setVisible(True)
            if fase in ("WaitingForStats", "PreEndOfGame", "EndOfGame"):
                self.lbl_partida_header.setText("🏁 Partida terminada\n\nRevisa tu perfil para ver el analisis")
                # Mostrar post-game una sola vez por partida (al transicionar desde InProgress)
                if not self._postgame_shown and self._last_fase in ("InProgress", "GameStart"):
                    self._postgame_shown = True
                    threading.Thread(target=self._preparar_postgame, daemon=True).start()
            else:
                # Nueva fase de lobby → resetear para la próxima partida
                self._postgame_shown = False
                self.lbl_partida_header.setText("🎮 Esperando partida...\n\nLos datos apareceran cuando entres a la Grieta")
            self._last_fase = fase
            return

        # Entró a una partida nueva → resetear el flag
        if self._last_fase not in ("InProgress", "GameStart"):
            self._postgame_shown = False
            self._last_game_stats = {}
        self._last_fase = fase

        # Partida en vivo
        jugadores, game_info = self.lcu.obtener_liveclient_data()

        if jugadores and len(jugadores) >= 2:
            self._renderizar_partida_live(jugadores, game_info)
            return

        # Fallback: LCU (solo campeones, sin KDA)
        jugadores_lcu = self.lcu.obtener_summoners_partida()
        if jugadores_lcu and len(jugadores_lcu) >= 2:
            self._renderizar_partida_lcu(jugadores_lcu)
            return

        # Loading
        if isinstance(game_info, dict) and game_info.get("status") == "loading":
            self.lbl_partida_header.setVisible(True)
            self.pnl_partida_dash.setVisible(False)
            self.tb_partida_aliados.setVisible(False)
            self.tb_partida_enemigos.setVisible(False)
            self.lbl_partida_header.setText("⏳ Entrando a la Grieta...\n\nLos datos apareceran al iniciar la partida")

    def _renderizar_partida_live(self, jugadores, game_info):
        """Renderiza la partida con datos del LiveClient (KDA, CS, etc.)."""
        self.lbl_partida_header.setVisible(False)
        self.pnl_partida_dash.setVisible(True)
        self.tb_partida_aliados.setVisible(True)
        self.tb_partida_enemigos.setVisible(True)

        aliados = [j for j in jugadores if j.get("team") == "ORDER"]
        enemigos = [j for j in jugadores if j.get("team") == "CHAOS"]

        # Buscar nuestro jugador
        mi_nombre_raw = self.lcu.obtener_nombre_invocador() or ""
        mi_nombre = mi_nombre_raw.split("#")[0].strip().lower()
        yo = None
        for j in jugadores:
            sn = (j.get("summonerName", "") or "").lower()
            if sn == mi_nombre or mi_nombre in sn or sn in mi_nombre:
                yo = j
                break

        # Dashboard personal
        game_time = game_info.get("gameTime", 0) if isinstance(game_info, dict) else 0
        mins, secs = int(game_time // 60), int(game_time % 60)
        self.lbl_partida_timer.setText(f"{mins:02d}:{secs:02d}")

        if yo:
            k, d, a = yo.get("kills", 0) or 0, yo.get("deaths", 0) or 0, yo.get("assists", 0) or 0
            cs = yo.get("creepScore", 0) or 0
            cname = yo.get("championName", "?")
            cs_min = cs / max(1, game_time / 60)
            self.lbl_partida_kda.setText(f"🔥 Tu {cname}: {k}/{d}/{a}")
            self.lbl_partida_cs.setText(f"CS: {cs} ({cs_min:.1f}/min)")
            # Cachear para post-game (actualizamos siempre para tener el estado más reciente)
            self._last_game_stats = {
                "champion": cname, "kills": k, "deaths": d, "assists": a,
                "cs": cs, "game_time": game_time,
            }
        else:
            self.lbl_partida_kda.setText("🔥 Tu: (buscando...)")
            self.lbl_partida_cs.setText("CS: --")

        # Tablas aliados/enemigos
        self._llenar_tabla_partida(self.tb_partida_aliados, aliados, "🔵 ALIADOS", "#0f172a", yo)
        self._llenar_tabla_partida(self.tb_partida_enemigos, enemigos, "🔴 ENEMIGOS", "#1a0a0f", yo)

        # Alimentar overlay si está activado
        if self.user_settings.get("overlay_ingame", False):
            if not self.overlay._visible:
                self.overlay.show_overlay()
            self.overlay.feed_live_data(jugadores, game_info, mi_nombre_raw)

        # Composicion
        a_nombres = [j.get("championName", "") for j in aliados if j.get("championName")]
        e_nombres = [j.get("championName", "") for j in enemigos if j.get("championName")]
        if len(a_nombres) >= 3 and len(e_nombres) >= 3:
            try:
                ad_a, ap_a, tk_a = analizar_composicion(a_nombres)
                ad_e, ap_e, tk_e = analizar_composicion(e_nombres)
                self.lbl_partida_comp.setText(
                    f"⚔️ Aliados: AD {ad_a}% / AP {ap_a}% ({tk_a} front)  |  "
                    f"Enemigos: AD {ad_e}% / AP {ap_e}% ({tk_e} front)"
                )
            except:
                self.lbl_partida_comp.setText("")
        else:
            self.lbl_partida_comp.setText("")

    def _renderizar_partida_lcu(self, jugadores):
        """Renderiza la partida usando solo datos LCU (campeones, sin KDA)."""
        self.lbl_partida_header.setVisible(False)
        self.pnl_partida_dash.setVisible(True)
        self.tb_partida_aliados.setVisible(True)
        self.tb_partida_enemigos.setVisible(True)

        # Buscar nuestro jugador en LCU
        mi_nombre_raw = self.lcu.obtener_nombre_invocador() or ""
        mi_nombre = mi_nombre_raw.split("#")[0].strip().lower()
        yo = None
        for j in jugadores:
            sn = (j.get("summonerName", "") or "").lower()
            if sn == mi_nombre or mi_nombre in sn or sn in mi_nombre:
                yo = j
                break

        if yo:
            cid = str(yo.get("championId", "0"))
            cname = self.procesar_nombre_champ(cid, "0") or "Desconocido"
            self.lbl_partida_kda.setText(f"🎮 En partida con {cname} (datos basicos LCU)")
            self._last_game_stats = {"champion": cname, "kills": 0, "deaths": 0, "assists": 0, "cs": 0, "game_time": 0}
        else:
            self.lbl_partida_kda.setText("🎮 Partida en vivo (datos basicos LCU)")
        self.lbl_partida_cs.setText("CS: --")
        self.lbl_partida_timer.setText("--:--")

        aliados = [j for j in jugadores if j.get("team") == "ORDER"]
        enemigos = [j for j in jugadores if j.get("team") == "CHAOS"]

        self._llenar_tabla_partida_lcu(self.tb_partida_aliados, aliados, "🔵 ALIADOS", "#0f172a")
        self._llenar_tabla_partida_lcu(self.tb_partida_enemigos, enemigos, "🔴 ENEMIGOS", "#1a0a0f")

        a_nombres = [self.procesar_nombre_champ(str(j.get("championId", 0)), "0") for j in aliados if self.procesar_nombre_champ(str(j.get("championId", 0)), "0")]
        e_nombres = [self.procesar_nombre_champ(str(j.get("championId", 0)), "0") for j in enemigos if self.procesar_nombre_champ(str(j.get("championId", 0)), "0")]
        if len(a_nombres) >= 3 and len(e_nombres) >= 3:
            try:
                ad_a, ap_a, tk_a = analizar_composicion(a_nombres)
                ad_e, ap_e, tk_e = analizar_composicion(e_nombres)
                self.lbl_partida_comp.setText(
                    f"⚔️ Aliados: AD {ad_a}% / AP {ap_a}% ({tk_a} front)  |  "
                    f"Enemigos: AD {ad_e}% / AP {ap_e}% ({tk_e} front)"
                )
            except:
                self.lbl_partida_comp.setText("")
        else:
            self.lbl_partida_comp.setText("")

    def _preparar_postgame(self):
        """Ejecutado en thread: reune datos y emite postgame_ready para mostrar el dialogo."""
        try:
            stats = dict(self._last_game_stats) if self._last_game_stats else {}

            # Obtener datos reales de la ultima partida desde LCU history
            try:
                historial = self.lcu.obtener_historial_extendido(cantidad=1)
                if historial:
                    ult = historial[0]
                    part = ult.get("participants", [{}])[0]
                    part_stats = part.get("stats", {})

                    # Datos basicos de la partida
                    stats["kills"] = part_stats.get("kills", stats.get("kills", 0))
                    stats["deaths"] = part_stats.get("deaths", stats.get("deaths", 0))
                    stats["assists"] = part_stats.get("assists", stats.get("assists", 0))
                    stats["cs"] = part_stats.get("totalMinionsKilled", 0) + part_stats.get("neutralMinionsKilled", 0)
                    stats["game_time"] = ult.get("gameDuration", stats.get("game_time", 0))
                    cid = str(part.get("championId", "0"))
                    stats["champion"] = self.procesar_nombre_champ(cid, "0") or stats.get("champion", "?")
                    win = part_stats.get("win", None)
                    if win is True:
                        stats["resultado"] = "Victoria"
                    elif win is False:
                        stats["resultado"] = "Derrota"

                    # Estadisticas adicionales de la partida
                    stats["vision_score"] = part_stats.get("visionScore", 0)
                    stats["wards_placed"] = part_stats.get("wardsPlaced", 0)
                    stats["control_wards"] = part_stats.get("visionWardsBoughtInGame", 0)
                    stats["damage_dealt"] = part_stats.get("totalDamageDealtToChampions", 0)
                    stats["damage_taken"] = part_stats.get("totalDamageTaken", 0)
                    stats["gold"] = part_stats.get("goldEarned", 0)
                    stats["cc_score"] = part_stats.get("timeCCingOthers", 0)
                    stats["turret_kills"] = part_stats.get("turretKills", 0)
                    stats["objectives"] = (part_stats.get("dragonKills", 0) + part_stats.get("baronKills", 0)
                                          + part_stats.get("turretKills", 0))
                    stats["penta"] = part_stats.get("pentaKills", 0)
                    stats["triple"] = part_stats.get("tripleKills", 0)
                    stats["first_blood"] = part_stats.get("firstBloodKill", False)
            except Exception as e:
                print(f"[PostGame] Error obteniendo datos LCU: {e}")

            # Medias historicas desde BD para comparativa
            try:
                conn = obtener_conexion()
                cur = conn.cursor()
                cur.execute("""
                    SELECT AVG(COALESCE(kills,0)), AVG(COALESCE(deaths,1)), AVG(COALESCE(assists,0))
                    FROM participantes
                    WHERE kills IS NOT NULL
                """)
                row = cur.fetchone()
                conn.close()
                if row and row[0] is not None:
                    stats["avg_k"] = round(float(row[0]), 1)
                    stats["avg_d"] = round(float(row[1]), 1)
                    stats["avg_a"] = round(float(row[2]), 1)
                else:
                    stats.setdefault("avg_k", 5.0)
                    stats.setdefault("avg_d", 4.0)
                    stats.setdefault("avg_a", 7.0)
            except Exception:
                stats.setdefault("avg_k", 5.0)
                stats.setdefault("avg_d", 4.0)
                stats.setdefault("avg_a", 7.0)

            # Analisis completo: puntos fuertes, debiles y consejos
            positives = []
            negatives = []
            tips = []

            k = stats.get("kills", 0)
            d = stats.get("deaths", 0)
            a = stats.get("assists", 0)
            cs_val = stats.get("cs", 0)
            game_time = stats.get("game_time", 600)
            avg_k = stats.get("avg_k", 5)
            avg_d = stats.get("avg_d", 4)
            avg_a = stats.get("avg_a", 7)
            result = stats.get("resultado", "")

            if game_time > 60:
                cs_min = cs_val / (game_time / 60)
            else:
                cs_min = 0

            # Puntos fuertes
            if k >= 10:
                positives.append(f"⚔️ {k} kills — excelente presencia ofensiva")
            if d <= 2 and game_time >= 600:
                positives.append(f"🛡️ Solo {d} muertes — muy buena supervivencia")
            if a >= 10:
                positives.append(f"🤝 {a} asistencias — gran impacto en equipo")
            if cs_min >= 7.5 and game_time >= 600:
                positives.append(f"🌾 {cs_min:.1f} CS/min — farmeo solido")
            if k > avg_k * 1.3:
                positives.append(f"📈 +{k - int(avg_k)} kills sobre tu media ({avg_k:.0f})")
            if d < avg_d * 0.7 and d <= avg_d:
                positives.append(f"📉 -{int(avg_d) - d} muertes bajo tu media ({avg_d:.0f})")
            if k + a >= 20:
                positives.append(f"🎯 {k + a} de participacion — muy activo en el mapa")
            if stats.get("vision_score", 0) >= 30:
                positives.append(f"👁️ {stats['vision_score']} de vision — buen control de mapa")
            if stats.get("penta", 0) >= 1:
                positives.append("🔥 PENTAKILL — partida legendaria")
            if stats.get("first_blood", False):
                positives.append("⚡ First Blood — ventaja temprana")

            # Puntos debiles
            if d >= 7:
                negatives.append(f"⚠️ {d} muertes — demasiadas, revisa tu posicionamiento")
            if d > avg_d * 1.5:
                negatives.append(f"📊 +{d - int(avg_d)} muertes sobre tu media — partida atipica o tilt")
            if cs_min < 5.0 and game_time >= 600:
                negatives.append(f"📉 CS/min bajo ({cs_min:.1f}) — practica el farmeo")
            if k + a < d * 1.5 and game_time >= 600:
                negatives.append(f"📉 Baja participacion — K+A ({k + a}) vs D ({d})")
            if stats.get("vision_score", 0) < 5 and game_time >= 900:
                negatives.append(f"🔦 Poca vision ({stats.get('vision_score', 0)}) — compra wards de control")
            if d >= 3 and k == 0 and game_time >= 600:
                negatives.append("😓 Sin kills — enfocate en jugadas seguras")
            if cs_min < 3.5 and game_time >= 900:
                negatives.append("🚫 Farmeo muy bajo — prioriza las oleadas de minions")

            # Consejos de mejora
            if negatives:
                tips.append("Consejo: " + negatives[0].split("—")[-1].strip() if "—" in negatives[0] else negatives[0])
            if d >= 5:
                tips.append("Juega mas conservador si vas detras y espera los powerspikes de tu campeon")
            if k + a < 5 and game_time >= 900:
                tips.append("Intenta rotar mas para ayudar a tu equipo en objetivos (dragon, heraldo)")
            if cs_min < 6.0:
                tips.append("Dedica 10 min en practica de herramientas a farmear bajo torre")
            if result == "Derrota" and k >= 8:
                tips.append("Aunque perdiste, tu desempeno ofensivo fue bueno. Revisa decisiones macro")
            if result == "Victoria" and d >= 7:
                tips.append("Buen resultado pero cuidado con las muertes — en partidas mas dificiles te castigaran")

            stats["positives"] = positives[:4]
            stats["negatives"] = negatives[:4]
            tips_dedup = list(dict.fromkeys(tips))
            stats["tip"] = "  |  ".join(tips_dedup[:3]) if tips_dedup else ""

            self.postgame_ready.emit(stats)
        except Exception as e:
            print(f"[PostGame] Error preparando resumen: {e}")
            import traceback
            traceback.print_exc()

    def _on_postgame_ready(self, stats: dict):
        """Muestra el diálogo de post-game en el hilo principal."""
        try:
            dlg = PostGameDialog(stats, parent=self)
            dlg.coaching_requested.connect(self._ir_a_coaching)
            dlg.show()
        except Exception as e:
            print(f"[PostGame] Error mostrando diálogo: {e}")

    def _ir_a_coaching(self):
        """Navega a la pestaña de Coaching."""
        try:
            for i in range(self.tabview.count()):
                if "coaching" in self.tabview.tabText(i).lower() or "perfil" in self.tabview.tabText(i).lower():
                    self.tabview.setCurrentIndex(i)
                    break
        except Exception:
            pass

    def _llenar_tabla_partida(self, tabla, jugadores, team_label, bg, yo):
        """Llena una tabla con datos de jugadores (LiveClient)."""
        tabla.setRowCount(0)

        # Header row
        row = tabla.rowCount(); tabla.insertRow(row)
        hdr = QTableWidgetItem(team_label)
        hdr.setBackground(QColor(bg)); hdr.setForeground(QColor(BORDER_ACCENT))
        f = hdr.font(); f.setBold(True); hdr.setFont(f)
        tabla.setItem(row, 0, hdr)
        for c in range(1, 4):
            e = QTableWidgetItem(""); e.setBackground(QColor(bg)); tabla.setItem(row, c, e)

        conn_db = obtener_conexion()
        try:
            for j in jugadores:
                cname = j.get("championName", "?") or "?"
                k, d, a_v = j.get("kills", 0) or 0, j.get("deaths", 0) or 0, j.get("assists", 0) or 0
                cs = j.get("creepScore", 0) or 0

                # Comentario: basado en KDA y WR de BD
                kda_val = (k + a_v) / max(1, d)
                comentario, color_com = self._comentar_jugador_partida(cname, k, d, a_v, kda_val, conn=conn_db)

                # WR desde BD
                wr = "--"
                try:
                    cur = conn_db.cursor()
                    cur.execute("SELECT ROUND(SUM(win)*100.0/COUNT(*),1) FROM participantes WHERE champion=?", (cname,))
                    r = cur.fetchone()
                    if r and r[0]:
                        wr = f"{r[0]}%"
                except:
                    pass

                row = tabla.rowCount(); tabla.insertRow(row)
                item_c = QTableWidgetItem(f"  {cname}")
                icon_p = self.descargar_imagen(cname, "champ")
                if icon_p:
                    item_c.setIcon(QIcon(icon_p))
                # Color de nombre segun si es el jugador local
                item_c.setForeground(QColor(TEXT_GOLD if j == yo else TEXT_WHITE))
                tabla.setItem(row, 0, item_c)

                item_kda = QTableWidgetItem(f"{k}/{d}/{a_v}")
                if k + d + a_v > 0:
                    color_kda = GREEN_WR if kda_val >= 3 else YELLOW_WR if kda_val >= 1.5 else RED_WR
                    item_kda.setForeground(QColor(color_kda))
                tabla.setItem(row, 1, item_kda)

                item_cs = QTableWidgetItem(str(cs))
                item_cs.setForeground(QColor(ACCENT_TEAL))
                tabla.setItem(row, 2, item_cs)

                item_com = QTableWidgetItem(f"WR:{wr} {comentario}")
                item_com.setForeground(QColor(color_com))
                tabla.setItem(row, 3, item_com)
        finally:
            conn_db.close()

    def _llenar_tabla_partida_lcu(self, tabla, jugadores, team_label, bg):
        """Llena una tabla con datos de jugadores (LCU, sin KDA)."""
        tabla.setRowCount(0)

        row = tabla.rowCount(); tabla.insertRow(row)
        hdr = QTableWidgetItem(team_label)
        hdr.setBackground(QColor(bg)); hdr.setForeground(QColor(BORDER_ACCENT))
        f = hdr.font(); f.setBold(True); hdr.setFont(f)
        tabla.setItem(row, 0, hdr)
        for c in range(1, 4):
            e = QTableWidgetItem(""); e.setBackground(QColor(bg)); tabla.setItem(row, c, e)

        conn_db = obtener_conexion()
        try:
            for j in jugadores:
                cid = int(j.get("championId", 0))
                cname = self.procesar_nombre_champ(str(cid), "0") or "?"

                # Comentario desde BD
                comentario, color_com = self._comentar_jugador_partida(cname, 0, 0, 0, 0, conn=conn_db)

                wr = "--"
                try:
                    cur = conn_db.cursor()
                    cur.execute("SELECT ROUND(SUM(win)*100.0/COUNT(*),1) FROM participantes WHERE champion=?", (cname,))
                    r = cur.fetchone()
                    if r and r[0]:
                        wr = f"{r[0]}%"
                except:
                    pass

                row = tabla.rowCount(); tabla.insertRow(row)
                item_c = QTableWidgetItem(f"  {cname}")
                icon_p = self.descargar_imagen(cname, "champ")
                if icon_p:
                    item_c.setIcon(QIcon(icon_p))
                tabla.setItem(row, 0, item_c)
                tabla.setItem(row, 1, QTableWidgetItem("--/--/--"))
                tabla.setItem(row, 2, QTableWidgetItem("--"))
                item_com = QTableWidgetItem(f"WR:{wr} {comentario}")
                item_com.setForeground(QColor(color_com))
                tabla.setItem(row, 3, item_com)
        finally:
            conn_db.close()

    def _comentar_jugador_partida(self, champion, k, d, a, kda_val, conn=None):
        """Genera un comentario estilo Porofessor sobre un jugador."""
        close_conn = conn is None
        try:
            if conn is None:
                conn = obtener_conexion()
            cur = conn.cursor()
            # WR y partidas totales
            cur.execute("SELECT COUNT(*), ROUND(AVG(kills),1), ROUND(AVG(deaths),1) FROM participantes WHERE champion=?", (champion,))
            r = cur.fetchone()
            total, avg_k, avg_d = r[0] if r else (0, 0, 0)

            comentarios = []
            color = "#94a3b8"  # default gray

            if total < 5:
                comentarios.append("1a vez?")
                color = "#64748b"
            else:
                if avg_d and avg_d >= 6:
                    comentarios.append("Muchas muertes")
                if avg_k and avg_k >= 7:
                    comentarios.append("Buenas kills")

            # KDA actual
            if k + d + a > 0:
                if kda_val >= 5:
                    comentarios.append("🔥 En fuego")
                    color = GREEN_WR
                elif kda_val >= 3:
                    comentarios.append("✅ Sólido")
                    color = GREEN_WR
                elif kda_val < 1.0:
                    comentarios.append("💀 Feedeando")
                    color = RED_WR
                elif d >= 5:
                    comentarios.append("⚠️ Frágil")
                    color = YELLOW_WR

            # Racha reciente
            if total >= 5:
                try:
                    cur.execute("""SELECT p.win FROM participantes p JOIN matches m ON p.match_id=m.match_id 
                                  WHERE p.champion=? ORDER BY m.fecha_descarga DESC LIMIT 5""", (champion,))
                    wins = [r2[0] for r2 in cur.fetchall()]
                    if wins:
                        w_count = sum(1 for w in wins if w)
                        if w_count >= 4:
                            comentarios.append("🔥 Racha buena")
                            color = GREEN_WR
                        elif w_count <= 1:
                            comentarios.append("❄️ Racha mala")
                            color = RED_WR if total > 10 else color
                except:
                    pass

            if not comentarios:
                comentarios.append("—")

            return " · ".join(comentarios), color
        except:
            return "—", "#94a3b8"
        finally:
            if close_conn and conn is not None:
                conn.close()

    def _actualizar_counters_vivo(self, rol_api, enemigo_lane):
        """Actualiza la seccion de counter picks contra el rival de linea."""
        self.last_enemigo_lane = enemigo_lane
        clear_layout(self.fr_counters_vivo)
        if enemigo_lane:
            self.panel_counters_vivo.label_title.setText(
                f"COUNTERS vs {self._nombre_display(enemigo_lane).upper()}"
            )
            counters = obtener_counters(rol_api, enemigo_lane, min_partidas=10)
            counters_filtrados = [(c, wr, p) for c, wr, p in counters 
                                 if c not in self.last_aliados and c not in self.last_enemigos][:6]
            for i, (c, wr, p) in enumerate(counters_filtrados):
                self.renderizar_icono(c, "champ", self.fr_counters_vivo, 0, i,
                    f"{self._nombre_display(c)}\nWR: {wr}% ({p} partidas)", size=35)
            if not counters_filtrados:
                lbl = QLabel("Sin datos suficientes")
                lbl.setStyleSheet("color: gray;")
                self.fr_counters_vivo.addWidget(lbl)
        else:
            self.panel_counters_vivo.label_title.setText("COUNTERS (esperando rival...)")

    def _actualizar_counters_manual(self, rol_api, rival_nombre):
        """Actualiza counters cuando el usuario selecciona un rival manualmente."""
        rival_db = self._nombre_db(rival_nombre)
        if not rival_db or rival_db == "Seleccionar rival...": return
        clear_layout(self.fr_counters_vivo)
        self.panel_counters_vivo.label_title.setText(f"COUNTERS vs {self._nombre_display(rival_db).upper()}")
        counters = obtener_counters(rol_api, rival_db, min_partidas=5)
        counters_filtrados = [(c, wr, p) for c, wr, p in counters 
                             if c not in self.last_aliados and c not in self.last_enemigos][:6]
        for i, (c, wr, p) in enumerate(counters_filtrados):
            self.renderizar_icono(c, "champ", self.fr_counters_vivo, 0, i,
                f"{self._nombre_display(c)}\nWR: {wr}% ({p} partidas)", size=35)
        if not counters_filtrados:
            lbl = QLabel("Sin datos"); lbl.setStyleSheet("color: gray;"); self.fr_counters_vivo.addWidget(lbl)

    def mostrar_equipo_vivo(self, layout, picks, is_ally=True):
        clear_layout(layout)
        if not picks:
            lbl = QLabel("Esperando equipo...")
            lbl.setStyleSheet("color: gray; font-style: italic;")
            lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl)
            return
            
        for champ in picks:
            card = QFrame()
            card.setObjectName("CardPick")
            border_color = ACCENT_TEAL if is_ally else RED_WR
            card.setStyleSheet(f"""
                QFrame#CardPick {{
                    border: 1px solid #1e293b;
                    border-left: 3px solid {border_color};
                    border-radius: 4px;
                    background-color: {BG_CARD};
                    margin-bottom: 3px;
                }}
            """)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(8, 4, 8, 4)
            card_layout.setSpacing(6)
            
            icon_layout = QGridLayout()
            self.renderizar_icono(champ, "champ", icon_layout, 0, 0, size=30)
            card_layout.addLayout(icon_layout)
            
            lbl_name = QLabel(self._nombre_display(champ))
            lbl_name.setStyleSheet("font-weight: bold; font-size: 12px; color: #f1f5f9;")
            card_layout.addWidget(lbl_name)
            card_layout.addStretch()
            layout.addWidget(card)

    def _cargar_stats_season(self):
        """Carga estadísticas de la season desde los datos ya paginados en hilo secundario.
        NO hace llamadas HTTP — solo procesa datos en memoria. Incluye TODOS los modos de juego."""
        if not hasattr(self, 'all_games_season') or not self.all_games_season:
            if hasattr(self, 'historial_games') and self.historial_games:
                self.all_games_season = list(self.historial_games)
            else:
                return
        try:
            all_games = self.all_games_season
            # DEDUP: evitar partidas duplicadas que inflen estadisticas
            seen_ids = set()
            unique_games = []
            for g in all_games:
                gid = str(g.get("gameId", ""))
                if not gid:
                    gid = f"{g.get('gameCreationDate','')}_{g.get('gameDuration',0)}"
                if gid and gid not in seen_ids:
                    seen_ids.add(gid)
                    unique_games.append(g)
            if len(unique_games) < len(all_games):
                print(f"[_cargar_stats_season] DEDUP: {len(all_games)} -> {len(unique_games)} partidas unicas")
            champ_stats = {}
            for g in unique_games:
                part = g.get("participants", [{}])[0]
                stats = part.get("stats", {})
                cid = str(part.get("championId", "0"))
                cname = self.procesar_nombre_champ(cid, "0") or "?"
                if cname == "?":
                    continue
                if cname not in champ_stats:
                    champ_stats[cname] = {"wins": 0, "games": 0, "kills": 0, "deaths": 0, "assists": 0}
                cs_data = champ_stats[cname]
                cs_data["games"] += 1
                if stats.get("win", False):
                    cs_data["wins"] += 1
                cs_data["kills"] += stats.get("kills", 0)
                cs_data["deaths"] += stats.get("deaths", 0)
                cs_data["assists"] += stats.get("assists", 0)
            
            top = sorted(champ_stats.items(), key=lambda x: x[1]["games"], reverse=True)[:8]
            print(f"[_cargar_stats_season] {len(unique_games)} partidas, {len(champ_stats)} campeones, top={[(c, s['games']) for c, s in top[:5]]}")
            self.tb_season_champs.setRowCount(0)
            for cname, cs in top:
                games = cs["games"]
                wr_c = round(cs["wins"] * 100 / games, 1) if games > 0 else 0
                kda = round((cs["kills"] + cs["assists"]) / max(1, cs["deaths"]), 1)
                r = self.tb_season_champs.rowCount()
                self.tb_season_champs.insertRow(r)
                item_c = QTableWidgetItem(f"  {self._nombre_con_dificultad(cname)}")
                icon = self.descargar_imagen(cname, "champ")
                if icon:
                    item_c.setIcon(QIcon(icon))
                self.tb_season_champs.setItem(r, 0, item_c)
                item_p = QTableWidgetItem(str(games))
                item_p.setTextAlignment(Qt.AlignCenter)
                self.tb_season_champs.setItem(r, 1, item_p)
                item_w = QTableWidgetItem(f"{wr_c}%")
                item_w.setTextAlignment(Qt.AlignCenter)
                item_w.setForeground(QColor(GREEN_WR if wr_c >= 50 else RED_WR))
                self.tb_season_champs.setItem(r, 2, item_w)
                item_k = QTableWidgetItem(str(kda))
                item_k.setTextAlignment(Qt.AlignCenter)
                self.tb_season_champs.setItem(r, 3, item_k)
        except Exception as e:
            print(f"[_cargar_stats_season] Error: {e}")

    def mostrar_picks_vivo(self, rol, aliados, enemigos):
        clear_layout(self.fr_picks_icons)
        sugerencias = recomendar_picks_vivo(rol, aliados, enemigos)
        col_idx = 0
        
        for categoria, champs in sugerencias.items():
            if not champs: continue
            
            cat_layout = QVBoxLayout()
            cat_layout.setAlignment(Qt.AlignTop)
            lbl_cat = QLabel(categoria)
            lbl_cat.setStyleSheet(f"color: {BORDER_ACCENT}; font-weight: bold; font-size: 10px;")
            lbl_cat.setAlignment(Qt.AlignCenter)
            cat_layout.addWidget(lbl_cat)
            
            grid_icons = QGridLayout()
            grid_icons.setAlignment(Qt.AlignCenter)
            for i, (champ, puntuacion, razon) in enumerate(champs[:4]):
                # Estrellas segun puntuacion (escala 1.0-10.0)
                if puntuacion >= 9.0: estrellas = "⭐⭐⭐⭐⭐"
                elif puntuacion >= 7.0: estrellas = "⭐⭐⭐⭐"
                elif puntuacion >= 5.0: estrellas = "⭐⭐⭐"
                elif puntuacion >= 3.0: estrellas = "⭐⭐"
                else: estrellas = "⭐"
                
                # Color segun puntuacion
                if puntuacion >= 8.0: color_pts = GREEN_WR
                elif puntuacion >= 5.0: color_pts = TEXT_GOLD
                elif puntuacion >= 3.0: color_pts = YELLOW_WR
                else: color_pts = RED_WR
                
                tooltip = (
                    f"{self._nombre_display(champ)}\n"
                    f"⭐ Puntuacion: {puntuacion}/10.0\n"
                    f"📊 {razon}"
                )
                self.renderizar_icono(champ, "champ", grid_icons, i // 2, i % 2,
                    tooltip, size=35)
                
                # Etiqueta de puntuación debajo del icono
                lbl_pts = QLabel(f"{puntuacion}")
                lbl_pts.setAlignment(Qt.AlignCenter)
                lbl_pts.setStyleSheet(f"color: {color_pts}; font-size: 9px; font-weight: bold; padding: 0px;")
                grid_icons.addWidget(lbl_pts, (i // 2) * 2 + 1, i % 2)  # fila impar debajo del icono
                
            cat_layout.addLayout(grid_icons)
            self.fr_picks_icons.addLayout(cat_layout, 0, col_idx)
            col_idx += 1

    def _dificultad_stars(self, champion):
        """Devuelve estrellas de dificultad (1-3) basadas en tags del campeon."""
        try:
            champ_key = champion.replace(" ", "").replace("'", "").replace(".", "").replace("&", "")
            champ_key = self.nombre_interno.get(champ_key, champ_key)
            tag = obtener_tag(champ_key)
            d = tag.get("difficulty", 2)
            return "⭐" * d
        except:
            return "⭐⭐"

    def _nombre_con_dificultad(self, champion):
        """Nombre del campeon con estrellas si mostrar_dificultad esta activo."""
        nombre = self._nombre_display(champion)
        if self.user_settings.get("mostrar_dificultad", True):
            return f"{nombre} {self._dificultad_stars(champion)}"
        return nombre

    def _actualizar_analisis_pro(self, aliados, enemigos):
        """Genera analisis macro avanzado: win conditions, objetivos, sinergias, itemizacion."""
        self.pnl_pro.setVisible(True)
        lines = []

        ad_al, ap_al, tanks_al = analizar_composicion(aliados)
        ad_en, ap_en, tanks_en = analizar_composicion(enemigos)

        poke_al = sum(1 for a in aliados if obtener_tag(a).get("damage_profile") == "poke")
        engage_al = sum(1 for a in aliados if obtener_tag(a).get("sub_class") in ("Vanguard","Catcher"))
        split_al = sum(1 for a in aliados if obtener_tag(a).get("sub_class")=="Skirmisher" and obtener_tag(a).get("scaling") in ("late","hyper"))
        engage_en = sum(1 for e in enemigos if obtener_tag(e).get("sub_class") in ("Vanguard","Catcher"))
        poke_en = sum(1 for e in enemigos if obtener_tag(e).get("damage_profile")=="poke")
        split_en = sum(1 for e in enemigos if obtener_tag(e).get("sub_class")=="Skirmisher" and obtener_tag(e).get("scaling") in ("late","hyper"))

        # Tipo de composicion
        if poke_al >= 2 and engage_al <= 1: comp_al = "Poke/Siege"
        elif engage_al >= 2 and tanks_al >= 2: comp_al = "Engage/Wombo"
        elif split_al >= 1: comp_al = "Split Push"
        elif tanks_al >= 3: comp_al = "Front-to-Back"
        else: comp_al = "Pick/Skirmish"

        if poke_en >= 2 and engage_en <= 1: comp_en = "Poke/Siege"
        elif engage_en >= 2 and tanks_en >= 2: comp_en = "Engage/Wombo"
        elif split_en >= 1: comp_en = "Split Push"
        elif tanks_en >= 3: comp_en = "Front-to-Back"
        else: comp_en = "Pick/Skirmish"

        lines.append("🎯 TU COMP: {}  |  ENEMIGO: {}".format(comp_al, comp_en))

        # Win condition
        if comp_al == "Poke/Siege" and comp_en in ("Engage/Wombo","Front-to-Back"):
            lines.append("🏆 WIN COND: Pokea antes de la pelea. No dejes que engageen. Asedia torres con rango.")
        elif comp_al == "Engage/Wombo" and comp_en in ("Poke/Siege","Pick/Skirmish"):
            lines.append("🏆 WIN COND: Busca el engage 5v5. Ellos colapsan contra all-in coordinado.")
        elif comp_al == "Split Push" and comp_en in ("Engage/Wombo","Front-to-Back"):
            lines.append("🏆 WIN COND: Evita 5v5. Presion lateral con el split pusher. Rotaciones rapidas.")
        elif comp_al == "Front-to-Back" and comp_en == "Pick/Skirmish":
            lines.append("🏆 WIN COND: Agrupaos y proteged al carry. No os separeis, os cazan.")
        else:
            esc_al = sum(1 for a in aliados if obtener_tag(a).get("scaling") in ("late","hyper"))
            esc_en = sum(1 for e in enemigos if obtener_tag(e).get("scaling") in ("late","hyper"))
            if esc_al > esc_en: lines.append("🏆 WIN COND: Escalan mejor. Juega seguro early, ganas a partir de 25 min.")
            elif esc_en > esc_al: lines.append("🏆 WIN COND: Acaba rápido. Ellos escalan mejor. Ventaja temprana y cierra.")
            elif tanks_al > tanks_en: lines.append("🏆 WIN COND: Su frontlane gana. Force objetivos, ellos no pueden contestar.")
            else: lines.append("🏆 WIN COND: Vision + picks. Controla la jungla enemiga y caza rotaciones.")

        # Prioridad de objetivos
        lines.append("\n📋 PRIORIDAD DE OBJETIVOS:")
        if tanks_al >= 3 or engage_al >= 2: lines.append("   🐉 Dragones - su frontlane domina el río")
        if split_al >= 1: lines.append("   🦀 Heraldo > Primeras 2 torres - libera al split pusher")
        if poke_al >= 2: lines.append("   🏰 Torres > Dragones - su rango asedia mejor")
        escalado_al = sum(1 for a in aliados if obtener_tag(a).get("scaling") in ("late","hyper"))
        if escalado_al >= 3: lines.append("   🛡️ Farm + Escalar > Objetivos tempranos")

        # Itemizacion counter
        lines.append("\n🛒 ITEMIZACION CLAVE:")
        ap_en_val = sum(1 for e in enemigos if obtener_dano(e) in ("AP","HYBRID"))
        ad_en_val = sum(1 for e in enemigos if obtener_dano(e) == "AD")
        cc_en = sum(obtener_nivel_cc(e) for e in enemigos)
        tanks_en_val = sum(1 for e in enemigos if es_tanque(e))
        cur = sum(1 for e in enemigos if e in {"Aatrox","Vladimir","Soraka","Swain","Sylas","Warwick","Briar","Fiora","Darius","Illaoi","DrMundo","Olaf"})
        if ap_en_val >= 3: lines.append("   🧪 Fuerza Naturaleza / Rostro Espiritual (mucha AP enemiga)")
        if ad_en_val >= 3: lines.append("   🛡️ Coraza de Espinas / Randuin (mucho AD)")
        if tanks_en_val >= 3: lines.append("   🗡️ Hoja del Rey / Lord Dominik (penetracion vs tanques)")
        if cc_en >= 12: lines.append("   ⛓️ Botas de Mercurio / Fajin (CC masivo)")
        if cur >= 2: lines.append("   🔥 Morellonomicón / Ejecutor (curaciones enemigas)")

        # Sinergias
        lines.append("\n⚡ SINERGIAS CLAVE:")
        if "Yasuo" in aliados:
            kn = [a for a in aliados if obtener_nivel_cc(a) >= 3 and obtener_tag(a).get("sub_class") in ("Vanguard","Catcher")]
            if kn: lines.append("   🌪️ Yasuo + {} = combo R garantizada".format(kn[0]))
        if "Orianna" in aliados:
            eng = [a for a in aliados if obtener_tag(a).get("sub_class") == "Vanguard"]
            if eng: lines.append("   ⚽ Orianna + {} = wombo combo R".format(eng[0]))
        if "Kalista" in aliados:
            supp = [a for a in aliados if es_soporte(a)]
            if supp: lines.append("   🤝 Kalista + {} = engage/doble knockup".format(supp[0]))

        self.lbl_pro.setText("\n".join(lines))

    # ================= META & BUILDS =================
    def armar_tab_counters(self):
        layout = QVBoxLayout(self.tab_counters)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(8)
        ctrl_layout.addWidget(QLabel("Línea:"))
        
        self.cb_rol_counter = QComboBox()
        self.cb_enemigo = QComboBox()
        ctrl_layout.addWidget(self.cb_rol_counter)
        ctrl_layout.addWidget(QLabel("Vs:"))
        ctrl_layout.addWidget(self.cb_enemigo)
        self.cb_rol_counter.addItems(UI_ROLES)
        self.cb_rol_counter.currentTextChanged.connect(self.actualizar_listas_counter)
        
        btn_analizar = QPushButton("ANALIZAR")
        btn_analizar.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_RED}; color: white; border: none; border-radius: 6px;
                           font-weight: bold; font-size: 11px; padding: 8px 18px; }}
            QPushButton:hover {{ background-color: {HOVER_GLOW}; }}
        """)
        btn_analizar.clicked.connect(self.buscar_counters)
        ctrl_layout.addWidget(btn_analizar)
        ctrl_layout.addStretch()
        
        layout.addLayout(ctrl_layout)
        
        # Split horizontal: tabla en izquierda, build visual en derecha
        split_layout = QHBoxLayout()
        split_layout.setSpacing(8)
        
        self.tree_counters = QTableWidget()
        self.tree_counters.setColumnCount(3)
        self.tree_counters.setHorizontalHeaderLabels(["Campeón Aliado", "Winrate %", "Partidas"])
        self.tree_counters.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tree_counters.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_counters.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree_counters.itemSelectionChanged.connect(self.mostrar_build_visual)
        self.tree_counters.verticalHeader().setDefaultSectionSize(40)
        self.tree_counters.setIconSize(QSize(28, 28))
        self.tree_counters.verticalHeader().setVisible(False)
        self.tree_counters.setStyleSheet("""
            QTableWidget { border: 1px solid #1e293b; border-radius: 4px; background-color: transparent; }
            QTableWidget::item { padding: 2px 6px; }
            QHeaderView::section { background-color: #152040; border: none; border-bottom: 1px solid #e63946; color: #e63946; font-weight: bold; padding: 6px; }
            QTableWidget::item:selected { background-color: #1e293b; }
        """)
        split_layout.addWidget(self.tree_counters, 1)
        
        self.panel_visual, self.l_visual = self.crear_panel("SETUP & BUILD ÓPTIMAS")
        self.frame_setup_visual = QVBoxLayout()
        self.frame_setup_visual.setAlignment(Qt.AlignTop)
        self.l_visual.addLayout(self.frame_setup_visual)
        split_layout.addWidget(self.panel_visual, 1)
        
        layout.addLayout(split_layout, 1)
        
        self.actualizar_listas_counter(UI_ROLES[0])

    def buscar_counters(self):
        """Lanza la búsqueda en hilo secundario para no congelar la UI."""
        if self._cargando_meta:
            return
        self._cargando_meta = True
        rol_api = ROL_TO_API[self.cb_rol_counter.currentText()]
        enemigo = self.cb_enemigo.currentText()
        threading.Thread(target=self._fetch_meta_builds, args=(rol_api, enemigo), daemon=True).start()

    def _fetch_meta_builds(self, rol_api, enemigo):
        """Hilo secundario: ejecuta todas las queries de Meta Builds."""
        try:
            resultados = obtener_counters(rol_api, enemigo, min_partidas=20)
            builds_data = {}
            conn = obtener_conexion()
            for champ, winrate, partidas in resultados:
                if winrate <= 50:
                    continue
                ids_start, ids_fin = obtener_top_items(champ, rol_api, enemigos=[enemigo], conn=conn)
                builds_data[champ] = {
                    "starters": ids_start,
                    "finales": ids_fin,
                    "runas": obtener_top_runas(champ, rol_api, conn=conn),
                    "spells": obtener_top_hechizos(champ, rol_api, conn=conn)
                }
            conn.close()
            self.meta_builds_listo.emit(resultados, builds_data, rol_api, enemigo)
        except Exception as e:
            print(f"[MetaBuilds] Error: {e}")
            self.meta_builds_listo.emit([], {}, rol_api, enemigo)

    def _on_meta_builds_listo(self, resultados, builds_data, rol_api, enemigo):
        """Hilo principal: pinta la tabla con los resultados ya calculados."""
        self._cargando_meta = False
        self.builds_actuales.clear()
        self.tree_counters.setRowCount(0)
        clear_layout(self.frame_setup_visual)

        if not resultados:
            QMessageBox.information(self, "Aviso", "Datos insuficientes. Ajusta tus filtros.")
            return

        self.builds_actuales = builds_data

        self.tree_counters.blockSignals(True)
        for champ, winrate, partidas in resultados:
            if winrate <= 50:
                continue
            row = self.tree_counters.rowCount()
            self.tree_counters.insertRow(row)
            item_champ = QTableWidgetItem(f"  {champ}")
            icon_path = self.descargar_imagen(champ, "champ")
            if icon_path:
                item_champ.setIcon(QIcon(icon_path))
            item_wr = QTableWidgetItem(f"{winrate}%")
            if winrate >= 52:
                item_wr.setForeground(QColor(GREEN_WR))
            elif winrate <= 48:
                item_wr.setForeground(QColor(RED_WR))
            self.tree_counters.setItem(row, 0, item_champ)
            self.tree_counters.setItem(row, 1, item_wr)
            self.tree_counters.setItem(row, 2, QTableWidgetItem(str(partidas)))
        self.tree_counters.blockSignals(False)

    def mostrar_build_visual(self):
        filas = self.tree_counters.selectedItems()
        if not filas: return
        champ = self.tree_counters.item(filas[0].row(), 0).text().strip()
        data = self.builds_actuales.get(champ, {})
        
        if data.get("runas"): 
            self.renderizar_setup_completo(champ, data["runas"], data.get("spells", []), data.get("starters", []), data.get("finales", []), self.frame_setup_visual, mostrar_botones=False)

    def armar_tab_ia(self):
        layout = QVBoxLayout(self.tab_ia)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        panel_ia, l_ia = self.crear_panel("CONFIGURACIÓN DEL MATCHUP")
        ctrls = QHBoxLayout()
        ctrls.setSpacing(8)
        self.cb_ia_rol = QComboBox()
        self.cb_ia_aliado = QComboBox()
        self.cb_ia_enemigo = QComboBox()
        ctrls.addWidget(QLabel("Línea:"))
        ctrls.addWidget(self.cb_ia_rol)
        ctrls.addWidget(QLabel("Tu Pick:"))
        ctrls.addWidget(self.cb_ia_aliado)
        lbl_vs = QLabel("VS")
        lbl_vs.setStyleSheet(f"color: {RED_WR}; font-weight: bold; font-size: 13px; margin: 0 4px;")
        ctrls.addWidget(lbl_vs)
        ctrls.addWidget(self.cb_ia_enemigo)
        self.cb_ia_rol.addItems(UI_ROLES)
        self.cb_ia_rol.currentTextChanged.connect(self.actualizar_listas_ia)
        
        btn_simular = QPushButton("SIMULAR ENFRENTAMIENTO")
        btn_simular.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_RED}; color: white; border: none; border-radius: 6px;
                           font-weight: bold; font-size: 11px; padding: 8px 16px; }}
            QPushButton:hover {{ background-color: {HOVER_GLOW}; }}
        """)
        btn_simular.clicked.connect(self.predecir_ia)
        ctrls.addWidget(btn_simular)
        
        l_ia.addLayout(ctrls)
        layout.addWidget(panel_ia)
        
        # ===== HUD DE RESULTADO =====
        hud_panel, l_hud = self.crear_panel("RESULTADO PREDICTIVO (IA)")
        l_hud.setAlignment(Qt.AlignTop)
        l_hud.setSpacing(8)
        
        batalla_layout = QHBoxLayout()
        batalla_layout.setSpacing(20)
        
        # Columna 1: Aliado
        col_aliado = QVBoxLayout()
        col_aliado.setAlignment(Qt.AlignCenter)
        col_aliado.setSpacing(6)
        fr_al = QFrame()
        fr_al.setObjectName("BuildCard")
        fr_al.setStyleSheet(f"QFrame#BuildCard {{ border: 1px solid {GREEN_WR}; border-radius: 10px; padding: 10px; background-color: #0a1a0f; }}")
        l_al = QVBoxLayout(fr_al)
        l_al.setAlignment(Qt.AlignCenter)
        self.img_aliado_1v1 = QLabel()
        self.img_aliado_1v1.setAlignment(Qt.AlignCenter)
        self.img_aliado_1v1.setFixedSize(100, 100)
        l_al.addWidget(self.img_aliado_1v1, alignment=Qt.AlignCenter)
        self.lbl_nombre_aliado_1v1 = QLabel("--")
        self.lbl_nombre_aliado_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_nombre_aliado_1v1.setStyleSheet(f"color: {GREEN_WR}; font-weight: bold; font-size: 12px;")
        l_al.addWidget(self.lbl_nombre_aliado_1v1)
        col_aliado.addWidget(fr_al)
        batalla_layout.addLayout(col_aliado, 1)
        
        # Columna 2: Centro
        col_centro = QVBoxLayout()
        col_centro.setSpacing(6)
        col_centro.setAlignment(Qt.AlignCenter)
        
        self.lbl_wr_1v1 = QLabel("50.0%")
        self.lbl_wr_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_wr_1v1.setStyleSheet(f"font-family: Impact; font-size: 42px; color: {YELLOW_WR};")
        col_centro.addWidget(self.lbl_wr_1v1)
        
        self.lbl_nivel_1v1 = QLabel("Selecciona campeones")
        self.lbl_nivel_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_nivel_1v1.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; font-weight: bold;")
        col_centro.addWidget(self.lbl_nivel_1v1)
        
        self.lbl_wr_real_1v1 = QLabel("")
        self.lbl_wr_real_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_wr_real_1v1.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        col_centro.addWidget(self.lbl_wr_real_1v1)
        
        # Barras comparativas compactas
        barras_frame = QFrame()
        barras_frame.setStyleSheet(f"background-color: {BG_CARD}; border-radius: 6px; padding: 8px;")
        barras_layout = QVBoxLayout(barras_frame)
        barras_layout.setSpacing(3)
        barras_layout.setContentsMargins(8, 6, 8, 6)
        
        for lbl_txt, bar_attr in [
            ("CC (Control)", "barra_cc"),
            ("Movilidad", "barra_movilidad"),
            ("Early Game", "barra_early"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl = QLabel(lbl_txt)
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; font-weight: bold;")
            lbl.setFixedWidth(80)
            row.addWidget(lbl)
            bar = QProgressBar()
            bar.setRange(0, 100); bar.setValue(50)
            bar.setTextVisible(False); bar.setFixedHeight(10)
            bar.setStyleSheet(self._estilo_barra_comparativa(50))
            setattr(self, bar_attr, bar)
            row.addWidget(bar, 1)
            barras_layout.addLayout(row)
        
        col_centro.addWidget(barras_frame)
        batalla_layout.addLayout(col_centro, 2)
        
        # Columna 3: Enemigo
        col_enemigo = QVBoxLayout()
        col_enemigo.setAlignment(Qt.AlignCenter)
        col_enemigo.setSpacing(6)
        fr_en = QFrame()
        fr_en.setObjectName("BuildCard")
        fr_en.setStyleSheet(f"QFrame#BuildCard {{ border: 1px solid {RED_WR}; border-radius: 10px; padding: 10px; background-color: #1a0a0f; }}")
        l_en = QVBoxLayout(fr_en)
        l_en.setAlignment(Qt.AlignCenter)
        self.img_enemigo_1v1 = QLabel()
        self.img_enemigo_1v1.setAlignment(Qt.AlignCenter)
        self.img_enemigo_1v1.setFixedSize(100, 100)
        l_en.addWidget(self.img_enemigo_1v1, alignment=Qt.AlignCenter)
        self.lbl_nombre_enemigo_1v1 = QLabel("--")
        self.lbl_nombre_enemigo_1v1.setAlignment(Qt.AlignCenter)
        self.lbl_nombre_enemigo_1v1.setStyleSheet(f"color: {RED_WR}; font-weight: bold; font-size: 12px;")
        l_en.addWidget(self.lbl_nombre_enemigo_1v1)
        col_enemigo.addWidget(fr_en)
        batalla_layout.addLayout(col_enemigo, 1)
        
        l_hud.addLayout(batalla_layout)
        
        # Análisis de la IA
        self.lbl_analisis_ia = QLabel("Selecciona los campeones y presiona Simular.")
        self.lbl_analisis_ia.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 12px; padding: 14px; background-color: {BG_CARD}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px;")
        self.lbl_analisis_ia.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.lbl_analisis_ia.setWordWrap(True)
        self.lbl_analisis_ia.setTextFormat(Qt.RichText)
        self.lbl_analisis_ia.setMinimumHeight(200)
        l_hud.addWidget(self.lbl_analisis_ia)
        layout.addWidget(hud_panel, 1)
        
        self.actualizar_listas_ia(UI_ROLES[0])

    def _estilo_barra_comparativa(self, valor):
        """Estilo para barras de tira y afloja: >50 verde (aliado gana), <50 rojo (enemigo gana)."""
        if valor >= 50:
            return f"""
                QProgressBar {{ background-color: #3b1018; border: 1px solid #5a1a28; border-radius: 4px; }}
                QProgressBar::chunk {{ background-color: {GREEN_WR}; border-radius: 3px; }}
            """
        else:
            return f"""
                QProgressBar {{ background-color: #0f172a; border: 1px solid #1a2744; border-radius: 4px; }}
                QProgressBar::chunk {{ background-color: {RED_WR}; border-radius: 3px; }}
            """

    def actualizar_listas_counter(self, value):
        if not value or value not in ROL_TO_API:
            return
        champs = obtener_campeones_por_rol(ROL_TO_API[value], min_partidas=20)
        self.cb_enemigo.clear()
        self.cb_enemigo.addItems(champs)

    def actualizar_listas_ia(self, value):
        if not value or value not in ROL_TO_API:
            return
        champs = obtener_campeones_por_rol(ROL_TO_API[value], min_partidas=20)
        self.cb_ia_aliado.clear()
        self.cb_ia_enemigo.clear()
        self.cb_ia_aliado.addItems(champs)
        self.cb_ia_enemigo.addItems(champs)
        if len(champs) >= 2: self.cb_ia_enemigo.setCurrentText(champs[1])

    def predecir_ia(self):
        rol_api = ROL_TO_API[self.cb_ia_rol.currentText()]
        aliado = self.cb_ia_aliado.currentText()
        enemigo = self.cb_ia_enemigo.currentText()
        
        if not aliado or not enemigo or not modelo_1v1.get(rol_api): return
        
        # ─── Imagenes y nombres ───
        ruta_al = self.descargar_imagen(aliado, "champ")
        ruta_en = self.descargar_imagen(enemigo, "champ")
        if ruta_al: self.img_aliado_1v1.setPixmap(QPixmap(ruta_al).scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if ruta_en: self.img_enemigo_1v1.setPixmap(QPixmap(ruta_en).scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.lbl_nombre_aliado_1v1.setText(self._nombre_display(aliado))
        self.lbl_nombre_enemigo_1v1.setText(self._nombre_display(enemigo))
        
        # === FEATURE ENGINEERING: mismo vector que en entrenamiento ===
        n = len(self.nombres_campeones_global)
        N_COMP = 15
        X = np.zeros(n * 2 + N_COMP)
        if aliado in self.nombres_campeones_global: 
            X[self.nombres_campeones_global.index(aliado)] = 1
        if enemigo in self.nombres_campeones_global: 
            X[n + self.nombres_campeones_global.index(enemigo)] = 1
        try:
            feats = extraer_features_comparativas(aliado, enemigo)
            X[n * 2:] = feats
        except Exception: pass
        
        # Prediccion IA cruda
        prob = modelo_1v1[rol_api].predict_proba(X.reshape(1, -1))[0][1] * 100
        
        # === DATOS REALES DE LA DB ===
        counters = obtener_counters(rol_api, enemigo, min_partidas=10)
        wr_real = None
        partidas_real = 0
        for c_name, wr, p in counters:
            if c_name == aliado:
                wr_real = wr
                partidas_real = p
                break
        
        # === FASE 2: FUSION Y AMPLIFICACION MATEMATICA ===
        if wr_real is not None:
            # Promedio ponderado: 40% IA + 60% datos reales
            prob_base = (prob * 0.4) + (wr_real * 0.6)
        else:
            prob_base = prob
        
        # Amplificar varianza para UI: alejar del 50%
        prob_final = 50 + ((prob_base - 50) * 1.8)
        prob_final = max(0, min(100, prob_final))
        
        # === NIVEL DE MATCHUP (umbrales calibrados) ===
        if prob_final > 54:
            nivel_color = GREEN_WR
            nivel_icono = "🔥"
            nivel_texto = "HARD COUNTER (Ventaja Absoluta)"
        elif prob_final >= 51.5:
            nivel_color = GREEN_WR
            nivel_icono = "✅"
            nivel_texto = "VENTAJA LIGERA"
        elif prob_final >= 48.5:
            nivel_color = YELLOW_WR
            nivel_icono = "⚔️"
            nivel_texto = "MATCHUP DE HABILIDAD (50/50)"
        else:
            nivel_color = RED_WR
            nivel_icono = "⚠️"
            nivel_texto = "MATCHUP DESFAVORABLE"
        
        # === ACTUALIZAR UI CENTRAL ===
        self.lbl_wr_1v1.setText(f"{prob_final:.1f}%")
        self.lbl_wr_1v1.setStyleSheet(f"font-family: Impact; font-size: 38px; color: {nivel_color};")
        self.lbl_nivel_1v1.setText(f"{nivel_icono} {nivel_texto}")
        self.lbl_nivel_1v1.setStyleSheet(f"color: {nivel_color}; font-size: 12px; font-weight: bold;")
        
        if wr_real is not None:
            real_color = GREEN_WR if wr_real >= 50 else RED_WR
            self.lbl_wr_real_1v1.setText(f"WR Real: {wr_real}% ({partidas_real} partidas)")
            self.lbl_wr_real_1v1.setStyleSheet(f"color: {real_color}; font-size: 10px;")
        else:
            self.lbl_wr_real_1v1.setText("(sin datos reales en BD)")
            self.lbl_wr_real_1v1.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        
        # === FASE 3: BARRAS COMPARATIVAS (TIRA Y AFLOJA) ===
        # NOTA: obtener_tag, obtener_nivel_cc ya importados a nivel modulo (linea 23)
        # NO usar import local dentro de la funcion (causa NameError en runtime)
        try:
            t_a = obtener_tag(aliado)
            t_e = obtener_tag(enemigo)
            
            # CC
            cc_a = obtener_nivel_cc(aliado)
            cc_e = obtener_nivel_cc(enemigo)
            val_cc = round((cc_a / max(0.1, cc_a + cc_e)) * 100)
            self.barra_cc.setValue(val_cc)
            self.barra_cc.setStyleSheet(self._estilo_barra_comparativa(val_cc))
            self.barra_cc.setToolTip(f"{aliado}: CC {cc_a}/5  |  {enemigo}: CC {cc_e}/5")
            
            # Movilidad
            mob_a = t_a.get("mobility", 2)
            mob_e = t_e.get("mobility", 2)
            val_mob = round((mob_a / max(0.1, mob_a + mob_e)) * 100)
            self.barra_movilidad.setValue(val_mob)
            self.barra_movilidad.setStyleSheet(self._estilo_barra_comparativa(val_mob))
            self.barra_movilidad.setToolTip(f"{aliado}: Movilidad {mob_a}/5  |  {enemigo}: Movilidad {mob_e}/5")
            
            # Early
            _EM = {"weak": 1, "neutral": 2, "strong": 3}
            early_a = _EM.get(t_a.get("early_power", "neutral"), 2)
            early_e = _EM.get(t_e.get("early_power", "neutral"), 2)
            val_early = round((early_a / max(0.1, early_a + early_e)) * 100)
            self.barra_early.setValue(val_early)
            self.barra_early.setStyleSheet(self._estilo_barra_comparativa(val_early))
            self.barra_early.setToolTip(f"{aliado}: Early {t_a.get('early_power','?')}  |  {enemigo}: Early {t_e.get('early_power','?')}")
            
        except Exception as e:
            print(f"[predecir_ia] Error en barras comparativas: {e}")
            # Fallback: barras a 50 (neutral) para no crashear
            for bar in [self.barra_cc, self.barra_movilidad, self.barra_early]:
                bar.setValue(50)
                bar.setStyleSheet(self._estilo_barra_comparativa(50))
        
        # === ANALISIS HTML (mantener el detalle abajo) ===
        _SM = {"early": 1, "mid": 2, "late": 3, "hyper": 4}
        scale_a = _SM.get(t_a.get("scaling", "mid"), 2)
        scale_e = _SM.get(t_e.get("scaling", "mid"), 2)
        
        def _barra_html(val_a, val_e, max_v, label):
            pct_a = min(100, int(val_a / max_v * 100))
            pct_e = min(100, int(val_e / max_v * 100))
            delta = val_a - val_e
            if delta > 0:
                delta_str = f'<span style="color:{GREEN_WR};">(+{delta})</span>'
            elif delta < 0:
                delta_str = f'<span style="color:{RED_WR};">({delta})</span>'
            else:
                delta_str = '<span style="color:#64748b;">(=)</span>'
            return (
                f'<tr>'
                f'<td width="140" style="color:{TEXT_MUTED};font-size:11px;padding:2px 6px;">{label}</td>'
                f'<td width="160"><div style="background:#1e293b;border-radius:3px;height:14px;width:100%;">'
                f'<div style="background:{GREEN_WR};height:14px;width:{pct_a}%;border-radius:3px 0 0 3px;"></div></div></td>'
                f'<td width="30" style="color:{TEXT_WHITE};font-size:11px;text-align:center;font-weight:700;">{val_a}</td>'
                f'<td width="20" style="text-align:center;">{delta_str}</td>'
                f'<td width="30" style="color:{TEXT_WHITE};font-size:11px;text-align:center;font-weight:700;">{val_e}</td>'
                f'<td width="160"><div style="background:#1e293b;border-radius:3px;height:14px;width:100%;">'
                f'<div style="background:{RED_WR};height:14px;width:{pct_e}%;border-radius:0 3px 3px 0;float:right;"></div></div></td>'
                f'</tr>'
            )
        
        html = f"""
        <div style="font-family:{FONT_FAMILY};font-size:12px;">
        <hr style="border:none;border-top:1px solid {BORDER_ACCENT};margin:10px 0;">
        <p style="color:{ACCENT_RED};font-weight:700;font-size:13px;letter-spacing:1px;margin:6px 0;">
            &#9889; STATS COMPARATIVAS
        </p>
        <p style="color:{TEXT_MUTED};font-size:10px;margin:2px 0;">
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{aliado[:10]:<10} <span style="color:{GREEN_WR};">verde</span> &nbsp;&#8594;&nbsp; DELTA &nbsp;&#8592;&nbsp; <span style="color:{RED_WR};">rojo</span> {enemigo[:10]:<10}
        </p>
        <table cellspacing="2" style="margin:8px 0;">
            {_barra_html(mob_a, mob_e, 5, "Movilidad")}
            {_barra_html(cc_a, cc_e, 5, "Control (CC)")}
            {_barra_html(early_a, early_e, 3, "Early Game")}
            {_barra_html(scale_a, scale_e, 4, "Escalado")}
        </table>
        <p style="color:{TEXT_MUTED};font-size:11px;margin:4px 0;">
            Daño: <b style="color:{ACCENT_TEAL};">{aliado} {t_a.get('damage_type','?')}</b>
            &nbsp;vs&nbsp;
            <b style="color:{YELLOW_WR};">{enemigo} {t_e.get('damage_type','?')}</b>
            &nbsp;&nbsp;|&nbsp;&nbsp;
            Clase: <b style="color:{ACCENT_TEAL};">{t_a.get('champion_class','?')}</b>
            &nbsp;vs&nbsp;
            <b style="color:{YELLOW_WR};">{t_e.get('champion_class','?')}</b>
        </p>
        <hr style="border:none;border-top:1px solid {BORDER_ACCENT};margin:10px 0;">
        <p style="color:{ACCENT_RED};font-weight:700;font-size:13px;letter-spacing:1px;margin:6px 0;">
            &#129504; QUE VE LA IA
        </p>
        <ul style="margin:4px 0;padding-left:18px;line-height:1.6;">"""
        
        try:
            insights = interpretar_features(aliado, enemigo)
            for ins in insights:
                if "Desventaja" in ins or "Déficit" in ins or "contra" in ins:
                    color = RED_WR
                elif "Ventaja" in ins or "Dominio" in ins or "mejor" in ins or "dicta" in ins:
                    color = GREEN_WR
                elif "hyper-carry" in ins:
                    color = YELLOW_WR
                else:
                    color = TEXT_MUTED
                html += f'<li style="color:{color};font-size:11px;">{ins}</li>'
        except Exception:
            html += f'<li style="color:{TEXT_MUTED};font-size:11px;">Análisis no disponible para este matchup.</li>'
        
        html += "</ul></div>"
        
        self.lbl_analisis_ia.setText(html)
        self.lbl_analisis_ia.setTextFormat(Qt.RichText)

    def armar_tab_bans(self):
        layout = QVBoxLayout(self.tab_bans)
        layout.setContentsMargins(10, 10, 10, 10)
        
        ctrls = QHBoxLayout()
        ctrls.addWidget(QLabel("Selecciona la Línea a Proteger:"))
        
        self.cbbanrol = QComboBox()
        self.cbbanrol.addItems(UI_ROLES)
        ctrls.addWidget(self.cbbanrol)

        self.rb_ban_global = QRadioButton("Global")
        self.rb_ban_personal = QRadioButton("Personal")
        self.rb_ban_global.setChecked(True)
        self.rb_ban_global.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 11px;")
        self.rb_ban_personal.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 11px;")
        ctrls.addWidget(self.rb_ban_global)
        ctrls.addWidget(self.rb_ban_personal)
        
        btn_analizar = QPushButton("ANALIZAR BANS DEL META")
        btn_analizar.clicked.connect(self.buscar_baneos)
        ctrls.addWidget(btn_analizar)
        ctrls.addStretch()
        layout.addLayout(ctrls)

        self.treebans = QTableWidget()
        self.treebans.setColumnCount(3)
        self.treebans.setHorizontalHeaderLabels(["Campeón", "Banrate Sugerido %", "Partidas Analizadas"])
        self.treebans.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.treebans.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.treebans.setSelectionMode(QAbstractItemView.NoSelection)
        self.treebans.verticalHeader().setDefaultSectionSize(45)
        self.treebans.setIconSize(QSize(35, 35))
        self.treebans.verticalHeader().setVisible(False)
        layout.addWidget(self.treebans, 1)  # Stretch para llenar espacio

    def buscar_baneos(self):
        self.treebans.setRowCount(0)
        modo_personal = self.rb_ban_personal.isChecked()

        if modo_personal and hasattr(self, 'historial_games') and self.historial_games:
            results = self._tierlist_personal(ROL_TO_API[self.cbbanrol.currentText()])
        else:
            results = obtenermejoresbaneos(ROL_TO_API[self.cbbanrol.currentText()], min_partidas=20)

        if not results:
            QMessageBox.information(self, "Aviso", "No hay datos suficientes para ese rol.")
            return
            
        for champ, banrate, partidas in results[:15]: 
            row = self.treebans.rowCount()
            self.treebans.insertRow(row)
            
            item_champ = QTableWidgetItem(f"  {champ}")
            icon_path = self.descargar_imagen(champ, "champ")
            if icon_path: item_champ.setIcon(QIcon(icon_path))
            item_champ.setToolTip(f"{champ}\nFrecuencia de pick: {banrate}%\n{partidas} partidas analizadas")
            
            item_ban = QTableWidgetItem(f"{banrate}%")
            item_ban.setForeground(QColor(RED_WR))
            
            self.treebans.setItem(row, 0, item_champ)
            self.treebans.setItem(row, 1, item_ban)
            self.treebans.setItem(row, 2, QTableWidgetItem(str(partidas)))

    def _tierlist_personal(self, rol_api):
        from collections import Counter
        champ_vs = Counter()
        for g in getattr(self, 'historial_games', []) or []:
            role = (g.get("role") or g.get("lane") or "").upper()
            api_role = role
            if role in ("SUPPORT",): api_role = "UTILITY"
            elif role in ("BOT", "ADC"): api_role = "BOTTOM"
            elif role in ("JUNGLA",): api_role = "JUNGLE"
            elif role in ("MID",): api_role = "MIDDLE"
            if api_role != rol_api:
                continue
            champ_list = g.get("enemyTeam", [])
            if not champ_list:
                continue
            for c in champ_list:
                name = c.get("championName") or c.get("championId", "")
                if name:
                    champ_vs[name] += 1
        total = sum(champ_vs.values())
        if total < 5:
            return []
        results = []
        for champ, count in champ_vs.most_common(15):
            rate = round(count / total * 100, 1)
            results.append((champ, rate, count))
        return results

    def _cargar_logros(self):
        try:
            if not hasattr(self, 'historial_games') or not self.historial_games:
                return
            logros_dict = evaluar_logros(self.historial_games)
            conseguidos = obtener_logros_conseguidos(logros_dict)

            # Clear previous logros
            while self.fr_logros.count():
                item = self.fr_logros.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not conseguidos:
                self.lbl_logros_text = QLabel("Sigue jugando para desbloquear logros...")
                self.lbl_logros_text.setStyleSheet("color: #64748b; font-size: 11px;")
                self.lbl_logros_text.setWordWrap(True)
                self.fr_logros.addWidget(self.lbl_logros_text)
            else:
                for lg in conseguidos:
                    lbl = QLabel(f"{lg['emoji']} {lg['nombre']}")
                    lbl.setStyleSheet("color: #e2e8f0; font-size: 11px; background: #1a2744; border-radius: 4px; padding: 2px 6px;")
                    lbl.setToolTip(lg['desc'])
                    self.fr_logros.addWidget(lbl)
            self.fr_logros.addStretch()
        except Exception as e:
            print(f"[Logros] Error: {e}")

if __name__ == "__main__":
    import signal
    app = QApplication(sys.argv)
    app.setApplicationName("NEXUS")
    app.setFont(QFont("Segoe UI", 10))

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    from setup import verificar_datos_iniciales
    if not verificar_datos_iniciales():
        from src.setup_wizard import SetupWizard
        wizard = SetupWizard()
        wizard.exec()
        if not wizard.success:
            sys.exit(1)
        from src.db_manager import inicializar_db
        inicializar_db()

    window = LoLRecommenderApp()
    window.show()
    sys.exit(app.exec())