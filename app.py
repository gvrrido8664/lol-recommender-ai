import json
import os
import requests
import threading
import time
from io import BytesIO
from PIL import Image
import numpy as np
import joblib
import sys

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QGridLayout, QLabel, QPushButton, 
                               QComboBox, QTabWidget, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QFrame, QMessageBox, QAbstractItemView, QProgressBar, QCheckBox, QDialog, QDialogButtonBox, QSlider, QSpinBox)
from PySide6.QtGui import QPixmap, QFont, QColor, QIcon
from PySide6.QtCore import Qt, QTimer, QSize, Signal

from src.db_manager import DATA_DIR, obtener_conexion
from src.riot_api import cargar_campeones, cargar_objetos, cargar_runas, cargar_mapeo_ids, cargar_hechizos, obtener_version_actual
from src.tags_champions import obtener_tag, obtener_nivel_cc, es_soporte, obtener_dano, es_tanque
from src.recomendador import (obtener_counters, obtener_top_items, obtener_campeones_por_rol, 
                              obtener_top_runas, obtener_top_hechizos, obtenermejoresbaneos, obtener_peores_matchups, 
                              recomendar_picks_vivo, calcular_winrate_5v5, analizar_composicion)
from src.lcu_api import LCUConnector

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# PyInstaller: cuando es .exe, los datos están en _MEIPASS
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
ITEMS_DIR = os.path.join(ASSETS_DIR, "items")
RUNAS_DIR = os.path.join(ASSETS_DIR, "runas")
CHAMPS_DIR = os.path.join(ASSETS_DIR, "champs")
SPELLS_DIR = os.path.join(ASSETS_DIR, "spells")
PROFILE_ICONS_DIR = os.path.join(ASSETS_DIR, "profile_icons")

for d in [ITEMS_DIR, RUNAS_DIR, CHAMPS_DIR, SPELLS_DIR, PROFILE_ICONS_DIR]:
    os.makedirs(d, exist_ok=True)

modelo_1v1 = {}
ruta_modelo = os.path.join(BASE_DIR, "data", "modelo_1v1.pkl")
if os.path.exists(ruta_modelo):
    try:
        modelo_1v1 = joblib.load(ruta_modelo)
        print(f"[App] Modelo 1v1 cargado: {len(modelo_1v1)} roles")
    except Exception as e:
        print(f"[App] Error cargando modelo 1v1: {e}")
else:
    print(f"[App] AVISO: No se encuentra {ruta_modelo}. El simulador 1v1 no funcionará.")
ITEMS_DICT = cargar_objetos()
RUNAS_DICT = cargar_runas()
SPELLS_DICT = cargar_hechizos()
MAPEO_IDS_CAMPEONES = cargar_mapeo_ids()

UI_ROLES = ["TOP", "JUNGLA", "MID", "ADC", "SUPPORT"]
ROL_TO_API = {"TOP": "TOP", "JUNGLA": "JUNGLE", "MID": "MIDDLE", "ADC": "BOTTOM", "SUPPORT": "UTILITY"}
API_TO_ROL = {"TOP": "TOP", "JUNGLE": "JUNGLA", "MIDDLE": "MID", "BOTTOM": "ADC", "UTILITY": "SUPPORT"}

BG_DARK = "#010a13"      
BG_PANEL = "#0a1428"     
BORDER_GOLD = "#c89b3c"  
TEXT_WHITE = "#ffffff"   
TEXT_GOLD = "#f0e6d2"    
ACCENT_BLUE = "#0ac8b9"  
RED_WR = "#ff4e50"
GREEN_WR = "#00e676"
YELLOW_WR = "#f9a826"
ALLY_BG = "#0b1b3d"      
ENEMY_BG = "#3d0b13"     

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
    "frecuencia_ingame": 5000,
    "sonidos": False,
    "modo_principiante": False,
    "modo_profesional": False,
    "recordatorios_partida": True,
    "mostrar_dificultad": True,
    "tooltips_grandes": False,
}

def cargar_settings():
    try:
        with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
            saved = json.load(f)
            return {**DEFAULT_SETTINGS, **saved.get("user_settings", {})}
    except: return dict(DEFAULT_SETTINGS)

def guardar_settings(settings):
    try:
        config = {}
        if os.path.exists(os.path.join(BASE_DIR, "config.json")):
            with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
                config = json.load(f)
        config["user_settings"] = settings
        with open(os.path.join(BASE_DIR, "config.json"), "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except: return False

class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings.copy()
        self.setWindowTitle("⚙️ Configuración")
        self.resize(520, 620)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {BG_DARK}; }}
            QLabel {{ color: {TEXT_WHITE}; font-size: 12px; background: transparent; }}
            QCheckBox {{ color: {TEXT_WHITE}; font-size: 12px; spacing: 8px; padding: 1px 0; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; }}
            QSpinBox {{ background-color: #1a2b4c; color: {TEXT_WHITE}; border: 1px solid {BORDER_GOLD}; padding: 3px; max-width: 80px; }}
        """)
        layout = QVBoxLayout(self); layout.setSpacing(6)

        title = QLabel("⚙️ CONFIGURACIÓN DE LA APP")
        title.setStyleSheet(f"color: {BORDER_GOLD}; font-weight: bold; font-size: 16px;")
        layout.addWidget(title)

        def _seccion(texto):
            lbl = QLabel(texto)
            lbl.setStyleSheet(f"color: {ACCENT_BLUE}; font-weight: bold; font-size: 12px; margin-top: 6px; padding: 3px 0; border-bottom: 1px solid #1e3050;")
            layout.addWidget(lbl)

        def _check(texto, key, desc=""):
            cb = QCheckBox(texto)
            cb.setChecked(self.settings.get(key, True))
            layout.addWidget(cb)
            if desc:
                lbl_desc = QLabel(f"      {desc}")
                lbl_desc.setStyleSheet("color: #4a6080; font-size: 10px; margin-left: 8px;")
                layout.addWidget(lbl_desc)
            return cb

        # ── CONEXIÓN ──
        _seccion("🔌 CONEXIÓN (afecta: MI PERFIL, RADAR, IN-GAME)")
        self.cb_auto = _check("Auto-detectar League of Legends al abrir", "auto_deteccion",
            "Busca el cliente de LoL solo. Si lo apagas, no se conecta automaticamente.")
        layout.addWidget(QLabel("   Cada cuantos ms actualiza el Radar:"))
        self.spin_radar = QSpinBox(); self.spin_radar.setRange(500, 5000); self.spin_radar.setSingleStep(500)
        self.spin_radar.setValue(self.settings.get("frecuencia_radar", 1500)); layout.addWidget(self.spin_radar)
        layout.addWidget(QLabel("   Cada cuantos ms actualiza el In-Game:"))
        self.spin_ingame = QSpinBox(); self.spin_ingame.setRange(1000, 15000); self.spin_ingame.setSingleStep(1000)
        self.spin_ingame.setValue(self.settings.get("frecuencia_ingame", 5000)); layout.addWidget(self.spin_ingame)

        # ── MI PERFIL ──
        _seccion("👤 MI PERFIL (afecta: pestaña MI PERFIL)")
        self.cb_dificultad = _check("Estrellas de dificultad en campeones ⭐ ⭐⭐ ⭐⭐⭐", "mostrar_dificultad",
            "Garen ⭐ (facil), Zed ⭐⭐⭐ (dificil). Te ayuda a elegir que aprender.")

        # ── RADAR ──
        _seccion("📡 RADAR EN VIVO (afecta: pestaña RADAR, fase de seleccion de campeon)")
        self.cb_explica = _check("Explicaciones de 'por que' en cada sugerencia", "mostrar_explicaciones",
            "Ej: 'Flash porque da movilidad'. Si lo apagas, solo ves los datos sin texto.")

        # ── IN-GAME ──
        _seccion("🎮 IN-GAME (afecta: pestaña IN-GAME, durante la partida)")
        self.cb_spikes = _check("Power Spikes: nivel clave de cada campeon", "mostrar_power_spikes",
            "Ej: 'Nv.6 All-in'. Te avisa cuando un campeon enemigo se vuelve peligroso.")
        self.cb_recordatorios = _check("Consejos visibles durante la partida", "recordatorios_partida",
            "Ej: 'Wardea el rio a los 2:30'. Aparecen abajo en la pantalla IN-GAME.")

        # ── ASISTENCIA ──
        _seccion("🎓 ASISTENCIA (afecta: varias pestañas)")
        self.cb_principiante = _check("🧑‍🎓 Modo Principiante", "modo_principiante",
            "Tips extra en lenguaje simple. Si sos nuevo, activalo.")
        self.cb_pro = _check("🏆 Modo Profesional", "modo_profesional",
            "Analisis tactico: win conditions, sinergias, prioridad de objetivos.")
        self.cb_tooltips = _check("Tooltips grandes con explicaciones extra", "tooltips_grandes",
            "Al pasar el mouse sobre iconos muestra descripciones mas detalladas.")

        # ── EXTRA ──
        _seccion("⚡ EXTRA (general)")
        self.cb_sonido = _check("Sonidos de alerta al detectar partida o cambios", "sonidos",
            "Suena al conectarse al cliente, detectar draft o iniciar partida.")

        layout.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_settings(self):
        return {"auto_deteccion": self.cb_auto.isChecked(), "mostrar_power_spikes": self.cb_spikes.isChecked(),
                "mostrar_explicaciones": self.cb_explica.isChecked(), "sonidos": self.cb_sonido.isChecked(),
                "frecuencia_radar": self.spin_radar.value(), "frecuencia_ingame": self.spin_ingame.value(),
                "modo_principiante": self.cb_principiante.isChecked(), "modo_profesional": self.cb_pro.isChecked(),
                "recordatorios_partida": self.cb_recordatorios.isChecked(),
                "mostrar_dificultad": self.cb_dificultad.isChecked(), "tooltips_grandes": self.cb_tooltips.isChecked()}

class LoLRecommenderApp(QMainWindow):
    lcu_task_finished = Signal(object, object, str, str)
    perfil_listo = Signal(dict)
    radar_listo = Signal(object)
    meta_builds_listo = Signal(list, str, str)  # (resultados, rol_api, enemigo)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoL Esports Analytics Pro - V1.0")
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
        
        self.last_aliados = []
        self.last_enemigos = []
        self.last_my_champ = None
        self.last_my_role = None
        self.perfil_cargado = False
        
        # Cache de imágenes descargadas para evitar HTTP repetidos
        self._cache_imagenes = {}
        
        # Flags anti-freeze
        self._cargando_perfil = False
        self._actualizando_radar = False
        self._cargando_meta = False

        self.crear_interfaz()
        
        self.timer_lcu = QTimer(self)
        self.timer_lcu.timeout.connect(self.auto_detectar_lcu)
        self.timer_lcu.start(1500)
        
        # Timer para detectar partida en vivo (cada 5s)
        self.timer_ingame = QTimer(self)
        self.timer_ingame.timeout.connect(self.actualizar_ingame)
        self.timer_ingame.start(5000)

    def aplicar_estilos(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {BG_DARK}; }}
            QWidget {{ color: {TEXT_WHITE}; font-family: Helvetica; font-size: 12px; }}
            QFrame#Panel {{ background-color: {BG_PANEL}; border: 1px solid {BORDER_GOLD}; border-radius: 10px; padding: 4px; }}
            QFrame#CardAlly {{ background-color: {ALLY_BG}; border: 1px solid {BORDER_GOLD}; border-radius: 6px; }}
            QFrame#CardEnemy {{ background-color: {ENEMY_BG}; border: 1px solid {BORDER_GOLD}; border-radius: 6px; }}
            QFrame#BuildCard {{ background-color: #0b1b30; border: 1px solid #1e3a5f; border-radius: 8px; }}
            QFrame#BuildCard:hover {{ border: 1px solid {BORDER_GOLD}; }}
            QLabel {{ border: none; background: transparent; }}
            QPushButton {{ background-color: #1a2b4c; color: {TEXT_WHITE}; border: 1px solid {BORDER_GOLD}; border-radius: 5px; padding: 7px 14px; font-weight: bold; font-size: 12px; }}
            QPushButton:hover {{ background-color: {ACCENT_BLUE}; color: {BG_DARK}; }}
            QPushButton:disabled {{ background-color: #1a2b4c; color: #555; border: 1px solid #555; }}
            
            /* TABS ESTILIZADOS PROFESIONALES */
            QTabWidget::pane {{ border: 1px solid {BORDER_GOLD}; background-color: {BG_PANEL}; border-radius: 10px; border-top-left-radius: 0px; }}
            QTabBar::tab {{ background: #1a2b4c; color: {TEXT_WHITE}; padding: 12px 28px; border: 1px solid {BORDER_GOLD}; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; font-weight: bold; font-size: 12px; }}
            QTabBar::tab:selected {{ background: {BG_PANEL}; color: {ACCENT_BLUE}; border-bottom: 2px solid {BG_PANEL}; }}
            QTabBar::tab:hover:!selected {{ background: #253a5e; }}
            
            QComboBox {{ background-color: #1a2b4c; color: {TEXT_WHITE}; border: 1px solid {BORDER_GOLD}; padding: 5px; border-radius: 4px; font-size: 12px; }}
            QComboBox:hover {{ border: 1px solid {ACCENT_BLUE}; }}
            QComboBox QAbstractItemView {{ background-color: #0d1b38; color: {TEXT_WHITE}; selection-background-color: {BORDER_GOLD}; selection-color: {BG_DARK}; }}
            QTableWidget {{ background-color: {BG_PANEL}; alternate-background-color: #0b1b30; color: {TEXT_WHITE}; gridline-color: transparent; border: 1px solid {BORDER_GOLD}; border-radius: 8px; font-size: 12px; outline: 0; }}
            QTableWidget::item {{ padding: 4px 6px; border-bottom: 1px solid #162040; }}
            QTableWidget::item:selected {{ background-color: {BORDER_GOLD}; color: {BG_DARK}; }}
            QHeaderView::section {{ background-color: #152040; color: {BORDER_GOLD}; font-weight: bold; padding: 8px; border: none; border-bottom: 2px solid {BORDER_GOLD}; font-size: 11px; }}
            QProgressBar {{ border: 1px solid {BORDER_GOLD}; border-radius: 5px; text-align: center; background-color: transparent; color: white; font-weight: bold; font-size: 12px; }}
            QProgressBar::chunk {{ background-color: {GREEN_WR}; border-radius: 5px; }}
        """)

    def crear_panel(self, text=""):
        fr = QFrame()
        fr.setObjectName("Panel")
        layout = QVBoxLayout(fr)
        layout.setAlignment(Qt.AlignTop)
        if text:
            lbl = QLabel(text.upper())
            lbl.setStyleSheet(f"color: {ACCENT_BLUE}; font-weight: bold; font-size: 12px;")
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
        header_lbl = QLabel("LOL ESPORTS ANALYTICS")
        header_lbl.setStyleSheet(f"color: {BORDER_GOLD}; font-family: Impact; font-size: 28px;")
        header_lbl.setAlignment(Qt.AlignCenter)
        header_row.addStretch()
        header_row.addWidget(header_lbl)
        header_row.addStretch()
        
        btn_settings = QPushButton(" ⚙ ")
        btn_settings.setFixedSize(34, 34)
        btn_settings.setCursor(Qt.PointingHandCursor)
        btn_settings.setToolTip("Configuración de la app")
        btn_settings.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: 1px solid #2a3050; border-radius: 17px;
                           font-size: 15px; color: #4a5070; }}
            QPushButton:hover {{ border: 1px solid {BORDER_GOLD}; color: {BORDER_GOLD}; }}
        """)
        btn_settings.clicked.connect(self.abrir_settings)
        header_row.addWidget(btn_settings)
        main_layout.addLayout(header_row)

        self.tabview = QTabWidget()
        self.tabview.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {BORDER_GOLD}; background-color: {BG_PANEL}; border-radius: 6px; }}
            QTabBar::tab {{ background: #111a2e; color: #6a7a90; padding: 8px 16px; border: 1px solid #1a2540;
                           border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px;
                           margin-right: 1px; font-size: 11px; min-width: 90px; }}
            QTabBar::tab:selected {{ background: {BG_PANEL}; color: {ACCENT_BLUE}; border-bottom: 2px solid {BG_PANEL};
                                    font-weight: bold; }}
            QTabBar::tab:hover:!selected {{ background: #1a2844; color: #8a9ab0; }}
        """)
        main_layout.addWidget(self.tabview)

        self.tab_perfil = QWidget()
        self.tab_vivo = QWidget()
        self.tab_counters = QWidget()
        self.tab_ia = QWidget()
        self.tab_bans = QWidget()
        self.tab_ingame = QWidget()

        self.tabview.addTab(self.tab_perfil, "👤 MI PERFIL")
        self.tabview.addTab(self.tab_vivo, "📡 RADAR EN VIVO")
        self.tabview.addTab(self.tab_ingame, "🎮 IN-GAME")
        self.tabview.addTab(self.tab_counters, "📊 META & BUILDS")
        self.tabview.addTab(self.tab_ia, "🤖 SIMULADOR 1v1")
        self.tabview.addTab(self.tab_bans, "🚫 TIER LIST DE BANS")

        self.armar_tab_perfil()
        self.armar_tab_vivo()
        self.armar_tab_ingame()
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
        btn.setEnabled(False)
        threading.Thread(
            target=self._run_lcu_task,
            args=(lambda: self.lcu.importar_hechizos(ids_spells[0], ids_spells[1]), btn, "Exportar a LoL", "Asegúrate de estar en una sala de Draft."),
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
                    ids_start,
                    ids_core
                ),
                btn,
                "Crear Item Set en LoL",
                "No se pudo inyectar el Item Set."
            ),
            daemon=True
        ).start()

    # ================= REDISEÑO DE SETUP & BUILD ANTI-ESTIRAMIENTO =================
    def renderizar_setup_completo(self, campeon, ids_runas, ids_spells, ids_start, ids_core, parent_layout, mostrar_botones=True):
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
        lbl_r.setStyleSheet(f"color: {BORDER_GOLD}; font-weight: bold; font-size: 11px;")
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
        lbl_s.setStyleSheet(f"color: {BORDER_GOLD}; font-weight: bold; font-size: 11px;")
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
        lbl_i1.setStyleSheet(f"color: {BORDER_GOLD}; font-weight: bold; font-size: 10px;")
        l_items.addWidget(lbl_i1, alignment=Qt.AlignCenter)
        
        w_start = QWidget()
        grid_start = QHBoxLayout(w_start)
        grid_start.setContentsMargins(0,0,0,0)
        grid_start.setAlignment(Qt.AlignCenter)
        if ids_start:
            for i_id in ids_start: self.renderizar_icono(i_id, "item", grid_start, 0, 0, size=40)
        l_items.addWidget(w_start)
        
        lbl_i2 = QLabel("CORE BUILD")
        lbl_i2.setStyleSheet(f"color: {BORDER_GOLD}; font-weight: bold; font-size: 10px; padding-top: 10px;")
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

        parent_layout.addWidget(main_wrap)

    # ================= PESTAÑA MI PERFIL DASHBOARD =================
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
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.pnl_perfil = QWidget()
        l_pnl = QHBoxLayout(self.pnl_perfil)
        l_pnl.setAlignment(Qt.AlignTop)
        
        # ===== COLUMNA IZQUIERDA: IDENTIDAD + RANKS + MAESTRÍAS =====
        self.col_id = QVBoxLayout()
        self.col_id.setAlignment(Qt.AlignTop)
        
        # Icono de perfil
        self.lbl_prof_icon = QLabel()
        self.lbl_prof_icon.setAlignment(Qt.AlignCenter)
        self.col_id.addWidget(self.lbl_prof_icon, alignment=Qt.AlignCenter)
        
        # Nombre de invocador
        self.lbl_sum_name = QLabel("Esperando al Cliente...")
        self.lbl_sum_name.setStyleSheet(f"color: {BORDER_GOLD}; font-size: 22px; font-weight: bold;")
        self.lbl_sum_name.setAlignment(Qt.AlignCenter)
        self.col_id.addWidget(self.lbl_sum_name, alignment=Qt.AlignCenter)
        
        # Nivel
        self.lbl_sum_lvl = QLabel("Nivel: --")
        self.lbl_sum_lvl.setStyleSheet("color: #8fa3b8; font-size: 14px;")
        self.lbl_sum_lvl.setAlignment(Qt.AlignCenter)
        self.col_id.addWidget(self.lbl_sum_lvl, alignment=Qt.AlignCenter)
        
        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {BORDER_GOLD}; max-height: 1px; margin: 8px 20px;")
        self.col_id.addWidget(sep)
        
        # ===== PANEL DE RANKS =====
        self.pnl_ranks, self.l_ranks = self.crear_panel("LIGAS ACTUALES")
        self.l_ranks.setSpacing(10)
        
        # SoloQ
        self.fr_soloq = QHBoxLayout()
        self.lbl_soloq_icon = QLabel("⚔️")
        self.lbl_soloq_icon.setStyleSheet("font-size: 30px;")
        self.fr_soloq.addWidget(self.lbl_soloq_icon)
        self.fr_soloq_info = QVBoxLayout()
        self.lbl_soloq_tier = QLabel("Solo/Duo\n--")
        self.lbl_soloq_tier.setStyleSheet(f"color: {ACCENT_BLUE}; font-weight: bold; font-size: 14px;")
        self.lbl_soloq_tier.setAlignment(Qt.AlignLeft)
        self.fr_soloq_info.addWidget(self.lbl_soloq_tier)
        self.lbl_soloq_stats = QLabel("")
        self.lbl_soloq_stats.setStyleSheet("color: #8fa3b8; font-size: 10px;")
        self.fr_soloq_info.addWidget(self.lbl_soloq_stats)
        self.fr_soloq.addLayout(self.fr_soloq_info)
        self.fr_soloq.addStretch()
        self.l_ranks.addLayout(self.fr_soloq)
        
        # Flex
        self.fr_flex = QHBoxLayout()
        self.lbl_flex_icon = QLabel("🛡️")
        self.lbl_flex_icon.setStyleSheet("font-size: 30px;")
        self.fr_flex.addWidget(self.lbl_flex_icon)
        self.fr_flex_info = QVBoxLayout()
        self.lbl_flex_tier = QLabel("Flex\n--")
        self.lbl_flex_tier.setStyleSheet(f"color: {TEXT_GOLD}; font-weight: bold; font-size: 14px;")
        self.lbl_flex_tier.setAlignment(Qt.AlignLeft)
        self.fr_flex_info.addWidget(self.lbl_flex_tier)
        self.lbl_flex_stats = QLabel("")
        self.lbl_flex_stats.setStyleSheet("color: #8fa3b8; font-size: 10px;")
        self.fr_flex_info.addWidget(self.lbl_flex_stats)
        self.fr_flex.addLayout(self.fr_flex_info)
        self.fr_flex.addStretch()
        self.l_ranks.addLayout(self.fr_flex)
        
        self.col_id.addWidget(self.pnl_ranks)
        
        # ===== PANEL DE MAESTRÍAS =====
        self.pnl_mastery, self.l_mastery = self.crear_panel("MEJORES CAMPEONES")
        self.fr_mastery = QHBoxLayout()
        self.l_mastery.addLayout(self.fr_mastery)
        self.col_id.addWidget(self.pnl_mastery)
        
        l_pnl.addLayout(self.col_id, 1)
        
        # ===== COLUMNA DERECHA: ESTADÍSTICAS + HISTORIAL =====
        self.col_hist = QVBoxLayout()
        self.col_hist.setAlignment(Qt.AlignTop)
        self.col_hist.setSpacing(8)
        
        # Tarjetas de estadísticas (KDA / WR / Más jugado / Mejor WR)
        self.fr_stats_cards = QHBoxLayout()
        self.fr_stats_cards.setSpacing(8)
        
        self.card_wr, self.lbl_card_wr_val = self._crear_stat_card("📊 WINRATE", "--%", GREEN_WR)
        self.fr_stats_cards.addWidget(self.card_wr, 1)
        
        self.card_kda, self.lbl_card_kda_val = self._crear_stat_card("⚔️ KDA", "--", ACCENT_BLUE)
        self.fr_stats_cards.addWidget(self.card_kda, 1)
        
        self.card_most, self.lbl_card_most_val = self._crear_stat_card("🔥 +JUGADO", "--", BORDER_GOLD)
        self.fr_stats_cards.addWidget(self.card_most, 1)
        
        self.card_best, self.lbl_card_best_val = self._crear_stat_card("🏆 MEJOR WR", "--", GREEN_WR)
        self.fr_stats_cards.addWidget(self.card_best, 1)
        
        self.col_hist.addLayout(self.fr_stats_cards)
        
        # ===== WR POR LÍNEA =====
        self.pnl_wr_rol, self.l_wr_rol = self.crear_panel("WINRATE POR LÍNEA (últimas 20 partidas)")
        self.fr_wr_rol = QHBoxLayout()
        self.fr_wr_rol.setSpacing(4)
        self.labels_wr_rol = {}  # {"TOP": QLabel, ...}
        for rol in UI_ROLES:
            lbl = QLabel(f"{rol}\n--")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size: 10px; color: #8fa3b8; padding: 4px;")
            self.fr_wr_rol.addWidget(lbl)
            self.labels_wr_rol[rol] = lbl
        self.l_wr_rol.addLayout(self.fr_wr_rol)
        self.col_hist.addWidget(self.pnl_wr_rol)

        # ===== ESTADÍSTICAS DE LA SEASON (LCU) =====
        self.pnl_season, self.l_season = self.crear_panel("📊 ESTADÍSTICAS DE LA TEMPORADA")
        self.lbl_season_stats = QLabel("Conecta al cliente de LoL para ver tus estadísticas de la season")
        self.lbl_season_stats.setStyleSheet("color: #8fa3b8; font-size: 11px; padding: 4px;")
        self.lbl_season_stats.setWordWrap(True)
        self.l_season.addWidget(self.lbl_season_stats)
        self.tb_season_champs = QTableWidget()
        self.tb_season_champs.setColumnCount(4)
        self.tb_season_champs.setHorizontalHeaderLabels(["Campeón", "Partidas", "WR", "KDA"])
        self.tb_season_champs.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tb_season_champs.setMaximumHeight(180)
        self.tb_season_champs.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb_season_champs.setSelectionMode(QAbstractItemView.NoSelection)
        self.l_season.addWidget(self.tb_season_champs)
        self.col_hist.addWidget(self.pnl_season)
        
        # Filtro por campeón y modo de juego
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
        self.fr_filtro.addStretch()
        self.col_hist.addLayout(self.fr_filtro)
        
        # Historial
        lbl_h = QLabel("HISTORIAL RECIENTE (20 PARTIDAS)")
        lbl_h.setStyleSheet(f"color: {ACCENT_BLUE}; font-weight: bold; font-size: 13px; margin-top: 4px;")
        self.col_hist.addWidget(lbl_h)
        
        self.tb_historial = QTableWidget()
        self.tb_historial.setColumnCount(6)
        self.tb_historial.setHorizontalHeaderLabels(["Campeón", "Resultado", "K/D/A", "CS", "Dur.", "Modo"])
        self.tb_historial.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tb_historial.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb_historial.setSelectionMode(QAbstractItemView.NoSelection)
        self.tb_historial.verticalHeader().setDefaultSectionSize(38)
        self.tb_historial.setIconSize(QSize(28, 28))
        self.tb_historial.verticalHeader().setVisible(False)
        self.col_hist.addWidget(self.tb_historial, 1)  # Stretch factor 1 para que ocupe el espacio restante
        
        l_pnl.addLayout(self.col_hist, 2)
        layout.addWidget(self.pnl_perfil)

    # ================= CARGA DE PERFIL (HILO SEGUNDARIO) =================
    def _fetch_perfil(self):
        """Se ejecuta en hilo secundario. Recoge TODOS los datos de LCU sin tocar UI."""
        data = {"ok": False}
        try:
            perfil = self.lcu.obtener_perfil()
            if not perfil:
                self._cargando_perfil = False
                return
            data["perfil"] = perfil
            
            # Ligas
            ligas = self.lcu.obtener_ligas()
            data["ligas"] = ligas
            
            # Maestrías (top 3)
            maestrias = self.lcu.obtener_maestrias()
            data["maestrias"] = maestrias[:3] if maestrias else []
            
            # Historial (con reintentos: a veces no está listo inmediatamente tras login)
            puuid = perfil.get("puuid")
            historial = None
            if puuid:
                for intento in range(3):
                    historial = self.lcu.obtener_historial(puuid)
                    if historial:
                        break
                    if intento < 2:
                        time.sleep(2)  # esperar antes de reintentar
            data["historial"] = historial
            
            data["ok"] = True
        except Exception as e:
            print(f"[_fetch_perfil] Error: {e}")
            data["ok"] = False
        finally:
            # Emitir señal para que el hilo principal actualice la UI
            self.perfil_listo.emit(data)

    def _on_perfil_listo(self, data):
        """Se ejecuta en el hilo principal. Actualiza la UI con los datos ya recogidos."""
        self._cargando_perfil = False
        
        if not data.get("ok") or not data.get("perfil"):
            return
        
        perfil = data["perfil"]
        self.perfil_cargado = True
        
        # --- Nombre y nivel ---
        display_name = perfil.get("displayName") or perfil.get("gameName") or perfil.get("summonerName") or perfil.get("name") or "Invocador"
        tagline = perfil.get("tagLine")
        if tagline and tagline not in display_name:
            display_name = f"{display_name}#{tagline}"
        self.lbl_sum_name.setText(display_name)
        self.lbl_sum_lvl.setText(f"Nivel: {perfil.get('summonerLevel', '--')}")
        
        # --- Icono de perfil ---
        icon_id = perfil.get("profileIconId")
        ruta_icon = self.descargar_imagen(icon_id, "profile")
        if ruta_icon:
            self.lbl_prof_icon.setPixmap(QPixmap(ruta_icon).scaled(110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation))

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

        def _format_rank(rank_data, lbl_tier, lbl_stats):
            if not rank_data or not rank_data.get("tier"):
                lbl_tier.setText("--")
                lbl_stats.setText("Sin clasificar")
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
            lbl_tier.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14px;")
            if w + l > 0:
                wr = round(w / (w + l) * 100)
                lbl_stats.setText(f"{lp} PL  •  {w}V / {l}D  •  {wr}% WR")
            else:
                lbl_stats.setText(f"{lp} PL  •  {w}V / {l}D")

        _format_rank(ranked_solo, self.lbl_soloq_tier, self.lbl_soloq_stats)
        _format_rank(ranked_flex, self.lbl_flex_tier, self.lbl_flex_stats)

        # --- Maestrías ---
        maestrias = data.get("maestrias", [])
        clear_layout(self.fr_mastery)
        if maestrias:
            for m in maestrias:
                cid = str(m.get("championId"))
                c_name = self.procesar_nombre_champ(cid, 0)
                lvl = m.get("championLevel")
                puntos = f"{m.get('championPoints', 0):,}"
                card_m = QWidget()
                card_m_ly = QVBoxLayout(card_m)
                card_m_ly.setContentsMargins(4, 4, 4, 4)
                card_m_ly.setAlignment(Qt.AlignCenter)
                self.renderizar_icono(c_name, "champ", card_m_ly, size=42)
                lbl = QLabel(f"Nv.{lvl}\n{puntos} pts")
                lbl.setStyleSheet("font-size: 9px; color: #8fa3b8;")
                lbl.setAlignment(Qt.AlignCenter)
                card_m_ly.addWidget(lbl)
                self.fr_mastery.addWidget(card_m)

        # --- Historial ---
        historial = data.get("historial")
        if not historial:
            self.lbl_card_wr_val.setText("--%")
            self.lbl_card_kda_val.setText("--")
            self.lbl_card_most_val.setText("--")
            self.lbl_card_best_val.setText("--")
            self.cb_filtro_champ.clear()
            self.cb_filtro_champ.addItem("Todos los campeones")
            return
        
        games = historial.get("games", {}).get("games", [])
        self.historial_games = games
        self.tb_historial.setRowCount(0)
        
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
            modo_juego = g.get("gameMode", "Draft")
            if modo_juego == "CLASSIC": modo_juego = "Ranked"
            self.tb_historial.setItem(row, 0, item_c)
            self.tb_historial.setItem(row, 1, item_w)
            self.tb_historial.setItem(row, 2, QTableWidgetItem(f"{k}/{d}/{a}"))
            self.tb_historial.setItem(row, 3, QTableWidgetItem(str(cs)))
            self.tb_historial.setItem(row, 4, QTableWidgetItem(duration_min))
            self.tb_historial.setItem(row, 5, QTableWidgetItem(modo_juego))

        # --- Tarjetas de estadísticas ---
        if total_games > 0:
            wr = round((victorias / total_games) * 100)
            kda = round((total_k + total_a) / max(1, total_d), 2)
            avg_k = round(total_k / total_games, 1)
            avg_d = round(total_d / total_games, 1)
            avg_a = round(total_a / total_games, 1)
            self.lbl_card_wr_val.setText(f"{wr}%")
            self.lbl_card_kda_val.setText(f"{kda}")
            self.lbl_card_kda_val.setToolTip(f"Promedio: {avg_k}/{avg_d}/{avg_a} por partida")
            most_played = max(champ_stats, key=lambda c: champ_stats[c]["games"])
            most_g = champ_stats[most_played]["games"]
            self.lbl_card_most_val.setText(most_played[:10])
            self.lbl_card_most_val.setStyleSheet(f"color: {BORDER_GOLD}; font-size: 16px; font-weight: bold;")
            self.lbl_card_most_val.setToolTip(f"{most_g} partidas jugadas con {most_played}")
            best_wr_champs = {c: s for c, s in champ_stats.items() if s["games"] >= 2}
            if best_wr_champs:
                best_champ = max(best_wr_champs, key=lambda c: best_wr_champs[c]["wins"] / best_wr_champs[c]["games"])
                best_wr = round(champ_stats[best_champ]["wins"] / champ_stats[best_champ]["games"] * 100)
                self.lbl_card_best_val.setText(f"{best_champ[:10]}")
                self.lbl_card_best_val.setStyleSheet(f"color: {GREEN_WR}; font-size: 16px; font-weight: bold;")
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

        # --- ESTADÍSTICAS DE LA SEASON (BD LOCAL) ---
        self._cargar_stats_season()

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
            "Ranked" if g.get("gameMode", "") == "CLASSIC" else g.get("gameMode", "Normal")
            for g in self.historial_games
        ))
        self.cb_filtro_modo.blockSignals(True)
        self.cb_filtro_modo.clear()
        self.cb_filtro_modo.addItem("Todos los modos")
        self.cb_filtro_modo.addItems(modos_usados)
        self.cb_filtro_modo.blockSignals(False)

    def filtrar_historial(self, _=None):
        """Filtra la tabla de historial por campeón Y modo de juego."""
        if not hasattr(self, 'historial_games') or not self.historial_games:
            return
        filtro_champ = self.cb_filtro_champ.currentText()
        filtro_modo = self.cb_filtro_modo.currentText()
        
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

            win = stats.get("win", False)
            k = stats.get("kills", 0)
            d = stats.get("deaths", 0)
            a = stats.get("assists", 0)
            cs = stats.get("totalMinionsKilled", 0) + stats.get("neutralMinionsKilled", 0)
            duration_sec = g.get("gameDuration", 0)
            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"

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
        self.lbl_rol_vivo.setStyleSheet(f"color: {BORDER_GOLD}; font-weight: bold; font-size: 18px;")
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
        draft_layout.addWidget(col_center, 3)

        self.col_ally, l_ally = self.crear_panel("Aliados")
        self.lbl_ally_stats = QLabel("AD: --% | AP: --% | Tanks: 0")
        self.lbl_ally_stats.setStyleSheet(f"color: {ACCENT_BLUE}; font-weight: bold;")
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
        self.timer_ingame.setInterval(self.user_settings.get("frecuencia_ingame", 5000))
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
        
        # Cargar perfil en hilo secundario (si no está ya cargándose)
        if not self.perfil_cargado and not self._cargando_perfil:
            self._cargando_perfil = True
            threading.Thread(target=self._fetch_perfil, daemon=True).start()
        
        # Actualizar radar/draft en hilo secundario (si no está ya actualizándose)
        if not self._actualizando_radar:
            self._actualizando_radar = True
            threading.Thread(target=self._fetch_radar, daemon=True).start()

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
                return mapa.get(p, p) if p in posiciones or p in mapa else (posiciones[len(picks_en)] if len(picks_en) < 5 else "MIDDLE")

            enemigos_procesados = []
            for idx, j in enumerate(draft.get("theirTeam", [])):
                champ = self.procesar_nombre_champ(j.get("championId", 0), j.get("championPickIntent", 0))
                if champ:
                    picks_en.append(champ)
                    pos = _normalizar_pos(j.get("assignedPosition", ""))
                    pos_en.append(pos)
                    enemigos_procesados.append((champ, pos, idx))
                    if pos == rol_api:
                        enemigo_lane = champ
            # Fallback por indice si no encontro por posicion
            if not enemigo_lane:
                mi_idx = next((i for i, j in enumerate(draft.get("myTeam", [])) if j.get("cellId") == mi_celda), 0)
                for champ, pos, idx in enemigos_procesados:
                    if idx == mi_idx and mi_idx < 5:
                        enemigo_lane = champ
                        break
                
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

                if len(picks_al_db) == 5 and len(picks_en_db) == 5:
                    wr = calcular_winrate_5v5(picks_al_db, picks_en_db, pos_al, pos_en)
                    color = GREEN_WR if wr > 52 else RED_WR if wr < 48 else YELLOW_WR
                    tendencia = "↑ Ventaja de Sinergia" if wr > 52 else "↓ Desventaja de Draft" if wr < 48 else "≈ Matchup Equilibrado"
                    self.lbl_wr_numero.setText(f"{wr}%")
                    self.lbl_wr_numero.setStyleSheet(f"color: {color}; font-family: Impact; font-size: 42px;")
                    self.lbl_wr_razon.setText(tendencia)
                    self.lbl_wr_razon.setStyleSheet(f"color: {color}; font-style: italic;")

            if mi_campeon != self.last_my_champ or rol_api != self.last_my_role:
                self.last_my_champ = mi_campeon
                self.last_my_role = rol_api
                
                clear_layout(self.fr_bans_icons_vivo)
                if mi_campeon: 
                    self.panel_bans_vivo.label_title.setText(
                        f"BANS SI PICKEO {self._nombre_display(mi_campeon).upper()}"
                    )
                    bans_sugeridos = obtener_peores_matchups(mi_campeon, rol_api, min_partidas=20)
                else: 
                    self.panel_bans_vivo.label_title.setText(f"BANS SUGERIDOS ({rol_ui})")
                    bans_sugeridos = obtenermejoresbaneos(rol_api, min_partidas=20)

                bans_filtrados = [b for b, wr, p in bans_sugeridos if b not in self.last_aliados and b not in self.last_enemigos][:4]
                if bans_filtrados:
                    for i, ban in enumerate(bans_filtrados): 
                        self.renderizar_icono(ban, "champ", self.fr_bans_icons_vivo, 0, i,
                            f"Ban: {self._nombre_display(ban)}\nWR enemigo: consultar DB", size=35)
                else: 
                    lbl_noban = QLabel("Sin recomendaciones")
                    lbl_noban.setStyleSheet("color: gray;")
                    self.fr_bans_icons_vivo.addWidget(lbl_noban)

                # ── COUNTER PICKS contra el rival de linea ──
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
                    # Dropdown manual para pickear rival
                    if not hasattr(self, 'cb_rival_manual'):
                        self.cb_rival_manual = QComboBox()
                        self.cb_rival_manual.setMinimumWidth(100)
                        self.cb_rival_manual.addItem("Seleccionar rival...")
                        self.cb_rival_manual.addItems(sorted(self.nombres_campeones_global))
                        self.cb_rival_manual.currentTextChanged.connect(
                            lambda t: self._actualizar_counters_manual(rol_api, t) if t != "Seleccionar rival..." else None
                        )
                        self.l_counters_vivo.addWidget(self.cb_rival_manual)

                if mi_campeon:
                    ids_runas = obtener_top_runas(mi_campeon, rol_api)
                    ids_spells = obtener_top_hechizos(mi_campeon, rol_api)
                    ids_start, ids_core = obtener_top_items(mi_campeon, rol_api, enemigos=self.last_enemigos)
                    self.renderizar_setup_completo(mi_campeon, ids_runas, ids_spells, ids_start, ids_core, self.fr_runas_icons_vivo)
                else: 
                    self.inicializar_panel_setup(self.fr_runas_icons_vivo)
        except Exception as e:
            pass

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
            card.setObjectName("CardAlly" if is_ally else "CardEnemy")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(10, 5, 10, 5)
            
            icon_layout = QGridLayout()
            self.renderizar_icono(champ, "champ", icon_layout, 0, 0, size=35)
            card_layout.addLayout(icon_layout)
            
            # Mostrar nombre en espanol para la UI
            lbl_name = QLabel(self._nombre_display(champ))
            lbl_name.setStyleSheet("font-weight: bold; font-size: 14px;")
            card_layout.addWidget(lbl_name)
            card_layout.addStretch()
            layout.addWidget(card)

    def _cargar_stats_season(self):
        """Carga estadisticas de la season del USUARIO desde LCU (ranked + historial extendido)."""
        if not self.lcu or not self.lcu.port:
            self.lbl_season_stats.setText("Abre el cliente de LoL para ver tus estadísticas de la season")
            return
        try:
            # Obtener stats de ranked (wins/losses por queue)
            ranked = self.lcu.obtener_ranked_stats()
            if ranked and ranked.get("queues"):
                soloq = ranked["queues"].get("RANKED_SOLO_5x5", {})
                if soloq:
                    wins = soloq.get("wins", soloq.get("winCount", 0))
                    losses = soloq.get("losses", soloq.get("lossCount", 0))
                    total = wins + losses
                    wr = round(wins * 100 / total, 1) if total > 0 else 0
                    tier = soloq.get("tier", "?"); div = soloq.get("division", soloq.get("rank", ""))
                    self.lbl_season_stats.setText(
                        f"🏆 SoloQ: {tier} {div} — {total} partidas ({wins}V/{losses}D) — {wr}% WR\n"
                        f"📊 Datos de la season actual desde el cliente de LoL"
                    )
                else:
                    self.lbl_season_stats.setText("🎮 Juega partidas ranked para ver tus estadísticas")

            # Top campeones desde historial extendido (pagina hasta 500 partidas)
            all_games = []
            for offset in range(0, 500, 100):
                batch = self.lcu.obtener_historial_extendido(cantidad=100, inicio=offset)
                if not batch: break
                all_games.extend(batch)
                if len(batch) < 100: break  # no hay mas partidas
            self.tb_season_champs.setRowCount(0)
            if all_games:
                champ_stats = {}
                for g in all_games:
                    part = g.get("participants", [{}])[0]
                    stats = part.get("stats", {})
                    cid = str(part.get("championId", "0"))
                    cname = self.procesar_nombre_champ(cid, "0") or "?"
                    if cname not in champ_stats:
                        champ_stats[cname] = {"wins": 0, "games": 0, "kills": 0, "deaths": 0, "assists": 0}
                    cs = champ_stats[cname]; cs["games"] += 1
                    if stats.get("win", False): cs["wins"] += 1
                    cs["kills"] += stats.get("kills", 0)
                    cs["deaths"] += stats.get("deaths", 0)
                    cs["assists"] += stats.get("assists", 0)
                
                top = sorted(champ_stats.items(), key=lambda x: x[1]["games"], reverse=True)[:8]
                for cname, cs in top:
                    row = self.tb_season_champs.rowCount(); self.tb_season_champs.insertRow(row)
                    wr_c = round(cs["wins"] * 100 / cs["games"], 1) if cs["games"] > 0 else 0
                    kda = round((cs["kills"] + cs["assists"]) / max(1, cs["deaths"]), 1)
                    item_c = QTableWidgetItem(f"  {self._nombre_con_dificultad(cname)}")
                    icon = self.descargar_imagen(cname, "champ")
                    if icon: item_c.setIcon(QIcon(icon))
                    self.tb_season_champs.setItem(row, 0, item_c)
                    self.tb_season_champs.setItem(row, 1, QTableWidgetItem(str(cs["games"])))
                    item_w = QTableWidgetItem(f"{wr_c}%")
                    item_w.setForeground(QColor(GREEN_WR if wr_c >= 50 else RED_WR))
                    self.tb_season_champs.setItem(row, 2, item_w)
                    self.tb_season_champs.setItem(row, 3, QTableWidgetItem(str(kda)))
        except Exception as e:
            self.lbl_season_stats.setText(f"Error: {e}")

    def mostrar_picks_vivo(self, rol, aliados, enemigos):
        clear_layout(self.fr_picks_icons)
        sugerencias = recomendar_picks_vivo(rol, aliados, enemigos)
        col_idx = 0
        
        for categoria, champs in sugerencias.items():
            if not champs: continue
            
            cat_layout = QVBoxLayout()
            cat_layout.setAlignment(Qt.AlignTop)
            lbl_cat = QLabel(categoria)
            lbl_cat.setStyleSheet(f"color: {BORDER_GOLD}; font-weight: bold; font-size: 10px;")
            lbl_cat.setAlignment(Qt.AlignCenter)
            cat_layout.addWidget(lbl_cat)
            
            grid_icons = QGridLayout()
            grid_icons.setAlignment(Qt.AlignCenter)
            for i, (champ, wr, razon) in enumerate(champs[:4]): 
                self.renderizar_icono(champ, "champ", grid_icons, i // 2, i % 2,
                    f"{self._nombre_display(champ)}\nWR Esperado: {wr}%\nPor qué: {razon}", size=35)
                
            cat_layout.addLayout(grid_icons)
            self.fr_picks_icons.addLayout(cat_layout, 0, col_idx)
            col_idx += 1

    # ================= IN-GAME =================
    def armar_tab_ingame(self):
        layout = QVBoxLayout(self.tab_ingame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.lbl_ingame_status = QLabel("🎮 Esperando partida...\nAbre una partida de LoL para ver datos en vivo")
        self.lbl_ingame_status.setAlignment(Qt.AlignCenter)
        self.lbl_ingame_status.setStyleSheet("color: gray; font-size: 16px; padding: 40px;")
        layout.addWidget(self.lbl_ingame_status)

        # Panel de recordatorios (visible solo si esta activado)
        self.pnl_recordatorios = QFrame()
        self.pnl_recordatorios.setObjectName("Panel")
        rlayout = QVBoxLayout(self.pnl_recordatorios)
        self.lbl_recordatorios = QLabel("⏰ CONSEJOS DE PARTIDA")
        self.lbl_recordatorios.setStyleSheet(f"color: {ACCENT_BLUE}; font-weight: bold; font-size: 12px;")
        rlayout.addWidget(self.lbl_recordatorios)
        self.fr_recordatorios = QHBoxLayout()
        rlayout.addLayout(self.fr_recordatorios)
        self.pnl_recordatorios.setVisible(False)
        layout.addWidget(self.pnl_recordatorios)

        # Tabla de jugadores
        self.tb_ingame = QTableWidget()
        self.tb_ingame.setColumnCount(7)
        self.tb_ingame.setHorizontalHeaderLabels(["Campeón", "Invocador", "WR", "KDA", "Racha", "Power Spike", "Tips"])
        self.tb_ingame.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tb_ingame.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb_ingame.setSelectionMode(QAbstractItemView.NoSelection)
        self.tb_ingame.verticalHeader().setDefaultSectionSize(42)
        self.tb_ingame.verticalHeader().setVisible(False)
        self.tb_ingame.setVisible(False)
        layout.addWidget(self.tb_ingame)

        # Stats de composicion
        self.lbl_ingame_comp = QLabel("")
        self.lbl_ingame_comp.setAlignment(Qt.AlignCenter)
        self.lbl_ingame_comp.setStyleSheet("color: #8fa3b8; font-size: 12px; margin-top: 8px;")
        layout.addWidget(self.lbl_ingame_comp)

        # Panel de analisis profesional
        self.pnl_pro, self.l_pro = self.crear_panel("🏆 ANÁLISIS PRO (MACRO)")
        self.lbl_pro = QLabel("Activa el Modo Profesional en ⚙️ para ver análisis macro avanzado")
        self.lbl_pro.setStyleSheet("color: #8fa3b8; font-size: 12px; padding: 8px;")
        self.lbl_pro.setWordWrap(True)
        self.l_pro.addWidget(self.lbl_pro)
        self.pnl_pro.setVisible(False)
        layout.addWidget(self.pnl_pro)

    def actualizar_ingame(self):
        """Detecta si hay partida en vivo y actualiza la tabla de jugadores con KDA, rachas y power spikes."""
        if not self.lcu or not self.lcu.port:
            return
        fase = self.lcu.obtener_fase_juego()
        if fase != "InProgress":
            self.lbl_ingame_status.setVisible(True)
            self.lbl_ingame_status.setText("🎮 Esperando partida...")
            self.tb_ingame.setVisible(False)
            self.lbl_ingame_comp.setText("")
            return

        jugadores = self.lcu.obtener_summoners_partida()
        if not jugadores:
            self.lbl_ingame_status.setText("🎮 Partida detectada - cargando jugadores...")
            return

        self.lbl_ingame_status.setVisible(False)
        self.tb_ingame.setVisible(True)

        aliados_raw = [j for j in jugadores if j.get("team") == "ORDER"]
        enemigos_raw = [j for j in jugadores if j.get("team") == "CHAOS"]
        mi_nombre = self.lcu.obtener_nombre_invocador()

        self.tb_ingame.setRowCount(0)

        for team_name, team_players, bg in [("🔵 ALIADOS", aliados_raw, ALLY_BG), ("🔴 ENEMIGOS", enemigos_raw, ENEMY_BG)]:
            row = self.tb_ingame.rowCount()
            self.tb_ingame.insertRow(row)
            hdr = QTableWidgetItem(team_name)
            hdr.setBackground(QColor(bg))
            hdr.setForeground(QColor(BORDER_GOLD))
            font = hdr.font(); font.setBold(True); hdr.setFont(font)
            self.tb_ingame.setItem(row, 0, hdr)
            for c in range(1, self.tb_ingame.columnCount()):
                empty = QTableWidgetItem("")
                empty.setBackground(QColor(bg))
                self.tb_ingame.setItem(row, c, empty)

            for j in team_players:
                cid = int(j.get("championId", 0))
                cname = self.procesar_nombre_champ(str(cid), "0") or "?"
                sname = j.get("summonerName", j.get("summonerId", "???"))
                
                # Stats desde BD local
                wr, kda, streak, total_g = self._stats_jugador_champ(cname)
                
                # Dificultad
                stars = self._dificultad_stars(cname)
                
                # Power spike info
                spike = self._power_spike_champ(cname) if self.user_settings.get("mostrar_power_spikes", True) else ""
                
                # Tips para principiantes
                tips = self._tips_principiante(cname) if self.user_settings.get("modo_principiante", False) else ""

                row = self.tb_ingame.rowCount()
                self.tb_ingame.insertRow(row)

                # Campeon + maestria + dificultad
                mastery = ""
                if sname == mi_nombre or j.get("summonerId", "") == mi_nombre:
                    ml = self.lcu.obtener_maestria_champ(cid)
                    mastery = f" ⭐{ml}" if ml > 0 else ""
                diff_display = f" {stars}" if self.user_settings.get("mostrar_dificultad", True) else ""
                item_c = QTableWidgetItem(f"  {self._nombre_display(cname)}{mastery}{diff_display}")
                icon_p = self.descargar_imagen(cname, "champ")
                if icon_p: item_c.setIcon(QIcon(icon_p))
                self.tb_ingame.setItem(row, 0, item_c)

                # Invocador
                self.tb_ingame.setItem(row, 1, QTableWidgetItem(sname))

                # WR del champ
                item_wr = QTableWidgetItem(wr)
                if wr != "--":
                    try:
                        wr_val = int(wr.replace("%",""))
                        item_wr.setForeground(QColor(GREEN_WR if wr_val >= 50 else RED_WR))
                    except: pass
                self.tb_ingame.setItem(row, 2, item_wr)

                # KDA
                self.tb_ingame.setItem(row, 3, QTableWidgetItem(kda))
                item_kda = self.tb_ingame.item(row, 3)
                if kda != "--":
                    try:
                        kda_val = float(kda)
                        item_kda.setForeground(QColor(GREEN_WR if kda_val >= 2.0 else YELLOW_WR if kda_val >= 1.0 else RED_WR))
                    except: pass

                # Racha
                item_streak = QTableWidgetItem(streak)
                if "🔥" in streak: item_streak.setForeground(QColor(GREEN_WR))
                elif "❄️" in streak: item_streak.setForeground(QColor(RED_WR))
                self.tb_ingame.setItem(row, 4, item_streak)

                # Power Spike
                self.tb_ingame.setItem(row, 5, QTableWidgetItem(spike))

                # Tips principiante
                item_tips = QTableWidgetItem(tips)
                item_tips.setForeground(QColor("#8fa3b8"))
                self.tb_ingame.setItem(row, 6, item_tips)

        # Recordatorios de partida para principiantes
        self._actualizar_recordatorios()
        
        # Analisis profesional (macro)
        if self.user_settings.get("modo_profesional", False) and len(aliados_nombres) == 5 and len(enemigos_nombres) == 5:
            self._actualizar_analisis_pro(aliados_nombres, enemigos_nombres)
        else:
            self.pnl_pro.setVisible(False)

        # Composicion
        aliados_nombres = [self.procesar_nombre_champ(str(j.get("championId",0)),"0") for j in aliados_raw if self.procesar_nombre_champ(str(j.get("championId",0)),"0")]
        enemigos_nombres = [self.procesar_nombre_champ(str(j.get("championId",0)),"0") for j in enemigos_raw if self.procesar_nombre_champ(str(j.get("championId",0)),"0")]
        if len(aliados_nombres) == 5 and len(enemigos_nombres) == 5:
            ad, ap, tanks = analizar_composicion(aliados_nombres)
            ade, ape, tankse = analizar_composicion(enemigos_nombres)
            self.lbl_ingame_comp.setText(
                f"ALIADOS: AD {ad}% / AP {ap}% ({tanks} front)  |  "
                f"ENEMIGOS: AD {ade}% / AP {ape}% ({tankse} front)"
            )

    def _stats_jugador_champ(self, champion):
        """Devuelve (WR, KDA, racha, total_partidas) para un campeon desde la BD local."""
        try:
            conn = obtener_conexion()
            cur = conn.cursor()
            # WR
            cur.execute("SELECT COUNT(*), SUM(win) FROM participantes WHERE champion=? AND win IS NOT NULL", (champion,))
            row = cur.fetchone()
            total = row[0] or 0
            wins = row[1] or 0
            wr = f"{round(wins*100/total, 1)}%" if total > 0 else "--"
            # KDA
            cur.execute("SELECT AVG(kills), AVG(deaths), AVG(assists) FROM participantes WHERE champion=? AND kills IS NOT NULL", (champion,))
            row = cur.fetchone()
            if row and row[0] is not None:
                kda = round((row[0] + row[2]) / max(1, row[1]), 1) if row[1] else 0
                kda_str = f"{kda:.1f}"
            else:
                kda_str = "--"
            # Racha: ultimas 5 partidas ordenadas por fecha
            cur.execute("""SELECT p.win FROM participantes p JOIN matches m ON p.match_id=m.match_id 
                          WHERE p.champion=? ORDER BY m.fecha_descarga DESC LIMIT 5""", (champion,))
            wins_list = [r[0] for r in cur.fetchall()]
            if wins_list:
                consec_w = 0; consec_l = 0
                for w in wins_list:
                    if w: consec_w += 1
                    else: break
                for w in wins_list:
                    if not w: consec_l += 1
                    else: break
                if consec_w >= 3: streak = f"🔥 {consec_w}V"
                elif consec_l >= 3: streak = f"❄️ {consec_l}D"
                else: streak = f"{sum(wins_list)}V/{len(wins_list)-sum(wins_list)}D"
            else:
                streak = "--"
            conn.close()
            return wr, kda_str, streak, total
        except:
            return "--", "--", "--", 0

    def _power_spike_champ(self, champion):
        """Devuelve info de power spike basada en niveles clave (conocimiento publico del juego, no viola TOS)."""
        spikes = {
            "Darius": "Nv.6 All-in", "Garen": "Nv.6 Ejecutar", "Riven": "Nv.3 Trade",
            "Irelia": "Nv.2/Q full", "Fiora": "Nv.6 Duelo", "Jax": "Nv.6 Powerspike",
            "Renekton": "Nv.3 Fury", "Sett": "Nv.3 W max", "Aatrox": "Nv.4 Q max",
            "Camille": "Nv.6 R锁定", "Malphite": "Nv.6 R engage", "Ornn": "Nv.6 R team",
            "Yasuo": "Nv.6 R combo", "Yone": "Nv.6 E+R", "Zed": "Nv.6 All-in",
            "Akali": "Nv.6 R gap", "Katarina": "Nv.6 Reset", "Talon": "Nv.2 First blood",
            "Fizz": "Nv.3 Trade", "Ekko": "Nv.6 R save", "Sylas": "Nv.6 R steal",
            "Ahri": "Nv.6 R charm", "Lux": "Nv.6 R laser", "Syndra": "Nv.6 R burst",
            "Kassadin": "Nv.16 Hyper", "Kayle": "Nv.16 Hyper", "Vladimir": "Nv.9 Teamfight",
            "Jinx": "Nv.6 R global", "Draven": "Nv.2 Aggro", "Caitlyn": "Nv.6 R snipe",
            "Vayne": "Nv.6 Invis", "KaiSa": "Nv.6/Evolve", "Ezreal": "Nv.6 R snipe",
            "LeeSin": "Nv.6 R kick", "Elise": "Nv.3 Gank", "Nidalee": "Nv.3 Gank",
            "Shaco": "Nv.3 Gank", "Evelynn": "Nv.6 Stealth", "Rengar": "Nv.6 R hunt",
            "KhaZix": "Nv.6 Evolve", "Kayn": "Nv.6 Forma", "Nocturne": "Nv.6 R dive",
            "Vi": "Nv.6 R lock", "JarvanIV": "Nv.6 R arena", "Sejuani": "Nv.6 R stun",
            "Amumu": "Nv.6 R stun", "Zac": "Nv.6 R bounce", "Hecarim": "Nv.6 R fear",
            "Leona": "Nv.2 Engage", "Nautilus": "Nv.2 Hook", "Thresh": "Nv.2 Hook",
            "Blitzcrank": "Nv.2 Hook", "Pyke": "Nv.2 Hook", "Alistar": "Nv.2 W+Q",
            "Rakan": "Nv.6 R charm", "Bard": "Nv.6 R save", "Lulu": "Nv.6 R save",
            "Soraka": "Nv.6 R global", "Janna": "Nv.6 R heal", "Nami": "Nv.6 R wave",
        }
        return spikes.get(champion, f"Nv.6 Spike")

    def _dificultad_stars(self, champion):
        """Devuelve estrellas de dificultad (1-3) basadas en tags del campeon."""
        try:
            tag = obtener_tag(champion)
            d = tag.get("difficulty", 2)
            return "⭐" * d
        except: return "⭐⭐"

    def _nombre_con_dificultad(self, champion):
        """Nombre del campeon con estrellas si mostrar_dificultad esta activo."""
        nombre = self._nombre_display(champion)
        if self.user_settings.get("mostrar_dificultad", True):
            return f"{nombre} {self._dificultad_stars(champion)}"
        return nombre

    def _tooltip_size(self):
        """Tamano de tooltip segun setting tooltips_grandes."""
        return 55 if self.user_settings.get("tooltips_grandes", False) else 35

    def _tips_principiante(self, champion):
        """Devuelve consejos basicos para jugadores nuevos que no conocen al campeon."""
        tips = {
            "Garen": "Gira y cura. Facil, aguanta mucho.",
            "Darius": "Cuidado con su pasiva de sangrado. No pelees cuerpo a cuerpo.",
            "Malphite": "Su R aturde en area. Sepárate de tu equipo.",
            "Yasuo": "Esquiva su Q (tornado). No pelees entre súbditos.",
            "Zed": "Cuidado nivel 6. Su R ejecuta. Compra Zhonyas si eres AP.",
            "Katarina": "No te pares sobre sus dagas. Cancela su R con CC.",
            "Blitzcrank": "Escóndete detrás de súbditos. Su Q es un gancho.",
            "Lux": "Esquiva su Q (raíz). Si te atrapa, usa su R.",
            "MasterYi": "No puede ser ralentizado en R. Necesitas CC fuerte.",
            "Teemo": "Compra lentes de visión (oráculo) para sus hongos.",
            "Shaco": "Cuidado con sus cajas en arbustos. El original ataca mas fuerte.",
            "Evelynn": "Invisible nivel 6. Wardi su jungla, no tu linea.",
            "Leona": "Mucho CC. Si te engancha, estas muerto. Manten distancia.",
            "Morgana": "Su E bloquea CC. Rompe el escudo antes de enganchar.",
        }
        return tips.get(champion, "")

    def _actualizar_recordatorios(self):
        """Muestra recordatorios utiles durante la partida basados en tiempo (no viola TOS)."""
        if not self.user_settings.get("recordatorios_partida", True):
            self.pnl_recordatorios.setVisible(False)
            return
        self.pnl_recordatorios.setVisible(True)
        clear_layout(self.fr_recordatorios)
        recordatorios = [
            "🛡️ Wardea el río a los 2:30 (posible gank)",
            "👢 No olvides comprar botas antes del minuto 8-10",
            "🐉 Primer dragón ~5:00. Ayuda a tu jungla con visión",
            "📊 Mira el mapa cada 5 segundos (minimapa)",
            "⚠️ Si no ves al jungla enemigo, asume que viene a tu línea",
            "💀 Si vas 0-2, juega seguro bajo torre y farmea",
        ]
        for r in recordatorios:
            lbl = QLabel(r)
            lbl.setStyleSheet("color: #8fa3b8; font-size: 10px; padding: 2px 8px;")
            self.fr_recordatorios.addWidget(lbl)

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
            if esc_al > esc_en: lines.append("🏆 WIN COND: Escalais mejor. Juega seguro early, ganas a partir de 25 min.")
            elif esc_en > esc_al: lines.append("🏆 WIN COND: Acaba rapido. Ellos escalan mejor. Ventaja temprana y cierra.")
            elif tanks_al > tanks_en: lines.append("🏆 WIN COND: Vuestro frontlane gana. Forza objectives, ellos no pueden contestar.")
            else: lines.append("🏆 WIN COND: Vision + picks. Controla la jungla enemiga y caza rotaciones.")

        # Prioridad de objetivos
        lines.append("\n📋 PRIORIDAD DE OBJETIVOS:")
        if tanks_al >= 3 or engage_al >= 2: lines.append("   🐉 Dragones - vuestro frontlane domina el rio")
        if split_al >= 1: lines.append("   🦀 Heraldo > Primeras 2 torres - libera al split pusher")
        if poke_al >= 2: lines.append("   🏰 Torres > Dragones - vuestro rango asedia mejor")
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
        layout.setSpacing(6)
        
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("Línea:"))
        
        self.cb_rol_counter = QComboBox()
        self.cb_rol_counter.addItems(UI_ROLES)
        self.cb_rol_counter.currentTextChanged.connect(self.actualizar_listas_counter)
        ctrl_layout.addWidget(self.cb_rol_counter)
        
        ctrl_layout.addWidget(QLabel("Vs:"))
        self.cb_enemigo = QComboBox()
        ctrl_layout.addWidget(self.cb_enemigo)
        
        btn_analizar = QPushButton("ANALIZAR")
        btn_analizar.clicked.connect(self.buscar_counters)
        ctrl_layout.addWidget(btn_analizar)
        ctrl_layout.addStretch()
        
        layout.addLayout(ctrl_layout)
        
        self.tree_counters = QTableWidget()
        self.tree_counters.setColumnCount(3)
        self.tree_counters.setHorizontalHeaderLabels(["Campeón Aliado", "Winrate %", "Partidas Analizadas"])
        self.tree_counters.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tree_counters.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_counters.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree_counters.itemSelectionChanged.connect(self.mostrar_build_visual)
        self.tree_counters.verticalHeader().setDefaultSectionSize(40)
        self.tree_counters.setIconSize(QSize(30, 30))
        self.tree_counters.verticalHeader().setVisible(False)
        layout.addWidget(self.tree_counters, 1)  # La tabla ocupa espacio proporcional
        
        self.panel_visual, self.l_visual = self.crear_panel("Setup & Build Óptimas")
        self.frame_setup_visual = QVBoxLayout()
        self.frame_setup_visual.setAlignment(Qt.AlignTop)
        self.l_visual.addLayout(self.frame_setup_visual)
        layout.addWidget(self.panel_visual, 1)

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
            self.meta_builds_listo.emit(resultados, rol_api, enemigo)
        except Exception as e:
            print(f"[MetaBuilds] Error: {e}")
            self.meta_builds_listo.emit([], rol_api, enemigo)

    def _on_meta_builds_listo(self, resultados, rol_api, enemigo):
        """Hilo principal: pinta la tabla con los resultados ya calculados."""
        self._cargando_meta = False
        self.builds_actuales.clear()
        self.tree_counters.setRowCount(0)
        clear_layout(self.frame_setup_visual)

        if not resultados:
            QMessageBox.information(self, "Aviso", "Datos insuficientes. Ajusta tus filtros.")
            return

        for champ, winrate, partidas in resultados[:6]:
            ids_start, ids_fin = obtener_top_items(champ, rol_api, enemigos=[enemigo])
            self.builds_actuales[champ] = {
                "starters": ids_start,
                "finales": ids_fin,
                "runas": obtener_top_runas(champ, rol_api),
                "spells": obtener_top_hechizos(champ, rol_api)
            }
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
        layout.setSpacing(6)
        panel_ia, l_ia = self.crear_panel("Configuración del Matchup")
        
        ctrls = QHBoxLayout()
        ctrls.addWidget(QLabel("Línea:"))
        self.cb_ia_rol = QComboBox()
        self.cb_ia_rol.addItems(UI_ROLES)
        self.cb_ia_rol.currentTextChanged.connect(self.actualizar_listas_ia)
        ctrls.addWidget(self.cb_ia_rol)
        
        ctrls.addWidget(QLabel("Tu Pick:"))
        self.cb_ia_aliado = QComboBox()
        ctrls.addWidget(self.cb_ia_aliado)
        
        lbl_vs = QLabel("VS")
        lbl_vs.setStyleSheet(f"color: {RED_WR}; font-weight: bold;")
        ctrls.addWidget(lbl_vs)
        
        self.cb_ia_enemigo = QComboBox()
        ctrls.addWidget(self.cb_ia_enemigo)
        
        btn_simular = QPushButton("SIMULAR ENFRENTAMIENTO")
        btn_simular.clicked.connect(self.predecir_ia)
        ctrls.addWidget(btn_simular)
        
        l_ia.addLayout(ctrls)
        layout.addWidget(panel_ia)
        
        hud_panel, l_hud = self.crear_panel("Resultado Predictivo (AI)")
        l_hud.setAlignment(Qt.AlignCenter)
        batalla_layout = QHBoxLayout()
        batalla_layout.setSpacing(20)
        
        self.img_aliado_1v1 = QLabel()
        self.img_aliado_1v1.setAlignment(Qt.AlignCenter)
        batalla_layout.addWidget(self.img_aliado_1v1)
        
        centro_layout = QVBoxLayout()
        lbl_vs_grande = QLabel("VS")
        lbl_vs_grande.setStyleSheet(f"color: {BORDER_GOLD}; font-family: Impact; font-size: 50px;")
        lbl_vs_grande.setAlignment(Qt.AlignCenter)
        centro_layout.addWidget(lbl_vs_grande)
        
        self.barra_wr = QProgressBar()
        self.barra_wr.setRange(0, 100)
        self.barra_wr.setValue(50)
        self.barra_wr.setTextVisible(True)
        self.barra_wr.setFormat("%p% Winrate para tu Pick")
        self.barra_wr.setFixedHeight(30)
        centro_layout.addWidget(self.barra_wr)
        
        batalla_layout.addLayout(centro_layout)
        
        self.img_enemigo_1v1 = QLabel()
        self.img_enemigo_1v1.setAlignment(Qt.AlignCenter)
        batalla_layout.addWidget(self.img_enemigo_1v1)
        
        l_hud.addLayout(batalla_layout)
        
        self.lbl_analisis_ia = QLabel("Selecciona los campeones y presiona Simular.")
        self.lbl_analisis_ia.setStyleSheet(f"color: {ACCENT_BLUE}; font-style: italic; font-size: 16px; padding: 20px;")
        self.lbl_analisis_ia.setAlignment(Qt.AlignCenter)
        self.lbl_analisis_ia.setWordWrap(True)
        l_hud.addWidget(self.lbl_analisis_ia)
        layout.addWidget(hud_panel, 1)  # El panel de resultados ocupa el espacio restante

        self.actualizar_listas_ia(UI_ROLES[0])

    def actualizar_listas_counter(self, value):
        champs = obtener_campeones_por_rol(ROL_TO_API[value], min_partidas=20)
        self.cb_enemigo.clear()
        self.cb_enemigo.addItems(champs)

    def actualizar_listas_ia(self, value):
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
        
        ruta_al = self.descargar_imagen(aliado, "champ")
        ruta_en = self.descargar_imagen(enemigo, "champ")
        if ruta_al: self.img_aliado_1v1.setPixmap(QPixmap(ruta_al).scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if ruta_en: self.img_enemigo_1v1.setPixmap(QPixmap(ruta_en).scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        
        # === PREDICCIÓN DEL MODELO ML ===
        n = len(self.nombres_campeones_global)
        X = np.zeros(n * 2)
        if aliado in self.nombres_campeones_global: X[self.nombres_campeones_global.index(aliado)] = 1
        if enemigo in self.nombres_campeones_global: X[n + self.nombres_campeones_global.index(enemigo)] = 1
            
        prob = modelo_1v1[rol_api].predict_proba(X.reshape(1, -1))[0][1] * 100
        self.barra_wr.setValue(int(prob))
        if prob >= 50: self.barra_wr.setStyleSheet(f"QProgressBar {{ border: 1px solid {BORDER_GOLD}; border-radius: 5px; text-align: center; background-color: {RED_WR}; color: {BG_DARK}; font-weight: bold; font-size: 14px;}} QProgressBar::chunk {{ background-color: {GREEN_WR}; border-radius: 5px; }}")
        else: self.barra_wr.setStyleSheet(f"QProgressBar {{ border: 1px solid {BORDER_GOLD}; border-radius: 5px; text-align: center; background-color: {GREEN_WR}; color: {TEXT_WHITE}; font-weight: bold; font-size: 14px;}} QProgressBar::chunk {{ background-color: {RED_WR}; border-radius: 5px; }}")
        
        # === DATOS REALES DE LA DB ===
        counters = obtener_counters(rol_api, enemigo, min_partidas=10)
        wr_real = None
        partidas_real = 0
        for c_name, wr, p in counters:
            if c_name == aliado:
                wr_real = wr
                partidas_real = p
                break
        
        # === ANÁLISIS POR CLASE DE CAMPEÓN ===
        tags_al = self.champs_dict.get(aliado, {}).get("tags", [])
        tags_en = self.champs_dict.get(enemigo, {}).get("tags", [])
        
        # Construir consejos tácticos según clases
        consejos = []
        
        # Relaciones clásicas de clase
        if "Assassin" in tags_al and "Mage" in tags_en:
            consejos.append("🔥 Asesino vs Mago: Tienes ventaja en all-ins rápidos. Busca el flanqueo post-nivel 6 y castiga cada vez que gaste su CC.")
        elif "Assassin" in tags_al and "Marksman" in tags_en:
            consejos.append("🎯 Asesino vs Tirador: No dejes que te kitee. Entra con definitiva y burst, si alargas el trade pierdes.")
        elif "Mage" in tags_al and "Assassin" in tags_en:
            consejos.append("🛡️ Mago vs Asesino: Juega bajo torre, guarda tu CC para cuando salte. Rush Zhonyas y respeta el nivel 6.")
        elif "Tank" in tags_al and "Assassin" in tags_en:
            consejos.append("🧱 Tanque vs Asesino: No puede matarte en una rotación. Forcéalo a gastar habilidades en ti y sobrevive para que tu equipo limpie.")
        elif "Marksman" in tags_al and "Tank" in tags_en:
            consejos.append("🏹 Tirador vs Tanque: Compra Dominio del Señor pronto. Kitea hacia atrás, no te quedes cuerpo a cuerpo.")
        elif "Mage" in tags_al and "Tank" in tags_en:
            consejos.append("📜 Mago vs Tanque: Pokea sin parar. No tienes kill pressure 1v1 temprano, enfócate en farmear y escalar.")
        elif "Fighter" in tags_al and "Marksman" in tags_en:
            consejos.append("⚔️ Luchador vs Tirador: Cierra la distancia con gap-closer. Una vez encima ganas el trade extendido.")
        elif "Marksman" in tags_al and "Fighter" in tags_en:
            consejos.append("🏃 Tirador vs Luchador: Mantén la distancia máxima. Si te alcanza con su gap-closer, retrocede de inmediato.")
        elif "Support" in tags_al:
            consejos.append("🤝 Soporte: No busques duelos 1v1. Tu valor está en peel, visión y rotaciones para tu equipo.")
        
        # Consejos genéricos según la clase aliada
        if not consejos:
            if "Assassin" in tags_al:
                consejos.append("🗡️ Roaming: No te cases con la línea. Empuja y busca kills en otros carriles.")
            elif "Mage" in tags_al:
                consejos.append("📚 Control de oleadas: Farmea seguro y escala. Tu poder está en teamfights.")
            elif "Fighter" in tags_al:
                consejos.append("💪 Duelista: Busca trades cortos frecuentes. Controla el arbusto para zonear.")
            elif "Tank" in tags_al:
                consejos.append("🛡️ Frontlane: Absorbe presión y facilita ganks. No necesitas kills para ganar la línea.")
            elif "Marksman" in tags_al:
                consejos.append("🎯 Posicionamiento: Esquiva skillshots y farmea. Castiga cada error de posición enemigo.")
        
        # === CONSTRUIR TEXTO FINAL ===
        if prob > 55:
            nivel = "✅ VENTAJA CLARA"
            detalle = f"Tu {aliado} contrarresta mecánicamente a {enemigo}."
        elif prob >= 45:
            nivel = "⚔️ MATCHUP DE HABILIDAD"
            detalle = f"Enfrentamiento muy equilibrado. Ganará el que mejor controle oleadas, visión y rotaciones."
        else:
            nivel = "⚠️ MATCHUP DESFAVORABLE"
            detalle = f"{enemigo} tiene ventaja estadística. Juega seguro, prioriza farm y busca outscale."
        
        # Cabecera con datos
        partes = [f"{nivel} ({prob:.1f}% WR estimado)"]
        partes.append(detalle)
        
        if wr_real is not None:
            color_wr = GREEN_WR if wr_real >= 50 else RED_WR
            partes.append(f"📊 Dato real: {wr_real}% WR en {partidas_real} partidas analizadas en {self.cb_ia_rol.currentText()}.")
        
        if consejos:
            partes.append("")
            partes.append("💡 CONSEJOS TÁCTICOS:")
            for c in consejos:
                partes.append(f"  {c}")
        
        # Añadir consejos de build según matchup
        if prob < 45:
            partes.append("")
            partes.append("🛒 Recomendación de build: Prioriza componentes defensivos (Resistencias/Vida).")
            partes.append("📋 En early: Farmea bajo torre, no arriesgues trades innecesarios.")
        elif prob > 55:
            partes.append("")
            partes.append("🛒 Recomendación de build: Rush daño ofensivo para snowballear la ventaja.")
            partes.append("📋 En early: Zonéalo del farm, castiga cada vez que intente last-hitear.")
        
        self.lbl_analisis_ia.setText("\n".join(partes))

    def armar_tab_bans(self):
        layout = QVBoxLayout(self.tab_bans)
        layout.setContentsMargins(10, 10, 10, 10)
        
        ctrls = QHBoxLayout()
        ctrls.addWidget(QLabel("Selecciona la Línea a Proteger:"))
        
        self.cbbanrol = QComboBox()
        self.cbbanrol.addItems(UI_ROLES)
        ctrls.addWidget(self.cbbanrol)
        
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
        resultados = obtenermejoresbaneos(ROL_TO_API[self.cbbanrol.currentText()], min_partidas=20)
        
        if not resultados: 
            QMessageBox.information(self, "Aviso", "No hay datos suficientes para ese rol.")
            return
            
        for champ, banrate, partidas in resultados[:15]: 
            row = self.treebans.rowCount()
            self.treebans.insertRow(row)
            
            item_champ = QTableWidgetItem(f"  {champ}")
            icon_path = self.descargar_imagen(champ, "champ")
            if icon_path: item_champ.setIcon(QIcon(icon_path))
            
            item_ban = QTableWidgetItem(f"{banrate}%")
            item_ban.setForeground(QColor(RED_WR))
            
            self.treebans.setItem(row, 0, item_champ)
            self.treebans.setItem(row, 1, item_ban)
            self.treebans.setItem(row, 2, QTableWidgetItem(str(partidas)))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LoLRecommenderApp()
    window.show()
    sys.exit(app.exec())