import json
import os
import requests
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from src.roles import ROLES_UI as UI_ROLES, UI_TO_API as ROL_TO_API, API_TO_UI as API_TO_ROL
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

# Rutas centralizadas (antes inline aqui) -> src/paths.py
from src.paths import (BASE_DIR, ASSETS_DIR, ITEMS_DIR, RUNAS_DIR, CHAMPS_DIR,
                       SPELLS_DIR, PROFILE_ICONS_DIR, CONFIG_DIR, _get_writable_dir)

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

# Constantes de diseno (antes inline) -> ui/design.py
from ui.design import *
from src.coach import generar_reporte_coach
# Dialogos (antes inline) -> ui/dialogs/
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.lp_graph import LPGraphWidget
from ui.dialogs.postgame_dialog import PostGameDialog

# Helpers y datos puros (antes inline aqui) -> ui/helpers.py
from ui.helpers import (clear_layout, cargar_settings, guardar_settings,
                        DEFAULT_SETTINGS, STAT_SHARDS, SKILL_ORDERS, JUNGLA_ESTILO,
                        _jungla_estilo, sugerir_pathing_jungla, ajustar_shards_adaptativos,
                        MATCHUP_TIPS, obtener_tip_matchup, obtener_tips_matchup)


class LoLRecommenderApp(QMainWindow):
    lcu_task_finished = Signal(object, object, str, str)
    perfil_listo = Signal(dict)
    radar_listo = Signal(object)
    meta_builds_listo = Signal(list, dict, str, str)  # (resultados, builds_data, rol_api, enemigo)
    postgame_ready = Signal(dict)
    season_partial = Signal(list)  # streaming: batch de partidas de Riot descargadas
    db_listo = Signal(bool)  # inicializacion de la BD terminada en hilo de fondo (ok/fallo)

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
        self.season_partial.connect(self._on_season_partial)
        
        self.last_aliados = []
        self.last_enemigos = []
        self.last_my_champ = None
        self.last_my_role = None
        self.last_enemigo_lane = None
        self.current_skill_order = None
        self.perfil_cargado = False
        
        # Cache de imÃ¡genes descargadas para evitar HTTP repetidos
        self._cache_imagenes = {}
        self._cache_imagenes_lock = threading.Lock()

        # Post-game: cachÃ© de stats en vivo y control de fase
        self._last_game_stats = {}
        self._postgame_shown = False
        self._last_fase = None
        
        # Flags anti-freeze
        self._cargando_perfil = False
        self._actualizando_radar = False
        self._cargando_meta = False

        # inicializar_db() hace CREATE TABLE IF NOT EXISTS + migraciones y tarda
        # ~8s (handshake TLS a Render). Se ejecuta en un hilo de fondo para que la
        # ventana aparezca al instante en vez de congelarse en el arranque.
        # Las tablas ya existen en BD, asi que las queries durante este lapso
        # funcionan normalmente via el pool de conexiones.
        self._db_conectado = True  # optimista; se corrige si falla
        self.db_listo.connect(self._on_db_listo)
        threading.Thread(target=self._inicializar_db_background, daemon=True).start()

        self._limpiar_cache_antiguo()

        self.crear_interfaz()
        
        self.timer_lcu = QTimer(self)
        self.timer_lcu.timeout.connect(self.auto_detectar_lcu)
        self.timer_lcu.start(1500)
        
        # Timer para partida en vivo (cada 4s)
        self.timer_partida = QTimer(self)
        self.timer_partida.timeout.connect(self.actualizar_partida_vivo)
        self.timer_partida.start(4000)
        
        # In-game timer and hotkeys removed â€” feature was too buggy
        
        # â”€â”€â”€ SYSTEM TRAY + GLOBAL HOTKEYS â”€â”€â”€
        self._setup_tray()
        
        # Cache para post-game (eliminado â€” feature de in-game removida)

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

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # SYSTEM TRAY
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    
    def _setup_tray(self):
        """Configura el icono en la bandeja del sistema."""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("NEXUS // LoL Performance Engine")
        pm = QPixmap(32, 32); pm.fill(QColor(BORDER_ACCENT))
        from PySide6.QtGui import QPainter, QFont
        p = QPainter(pm); p.setFont(QFont("Segoe UI", 16, QFont.Bold))
        p.setPen(QColor("#ffffff")); p.drawText(pm.rect(), Qt.AlignCenter, "N"); p.end()
        self.tray_icon.setIcon(QIcon(pm))
        # Crear menÃº contextual
        tray_menu = QMenu()
        a_show = QAction("ðŸ“Š Mostrar / Ocultar", self)
        a_show.triggered.connect(self._tray_toggle)
        tray_menu.addAction(a_show)
        a_radar = QAction("ðŸ“¡ Ir a Radar", self)
        a_radar.triggered.connect(lambda: self.tabview.setCurrentIndex(2))
        tray_menu.addAction(a_radar)
        tray_menu.addSeparator()
        a_exit = QAction("âŒ Salir", self)
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
            
            /* â•â•â• PANELES / TARJETAS â•â•â• */
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
            
            /* â•â•â• BOTONES â•â•â• */
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
                background-color: {BG_CARD_HOVER}; 
                color: {BG_BORDER}; 
                border: 1px solid #334155; 
            }}
            
            /* â•â•â• PESTAÃ‘AS â•â•â• */
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
            
            /* â•â•â• COMBOBOX â•â•â• */
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
            
            /* â•â•â• TABLAS â•â•â• */
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
            
            /* â•â•â• BARRA DE PROGRESO â•â•â• */
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
            
            /* â•â•â• SCROLLBAR â•â•â• */
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 4px 2px 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: #2a3a5c;
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {ACCENT_RED};
            }}
            QScrollBar::handle:vertical:pressed {{
                background: #be123c;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 6px;
                margin: 2px 4px 2px 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: #2a3a5c;
                border-radius: 3px;
                min-width: 30px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {ACCENT_RED};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {BORDER_ACCENT};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            
            /* â•â•â• TOOLTIP â•â•â• */
            QToolTip {{
                background-color: {BG_PANEL};
                color: {TEXT_WHITE};
                border: 1px solid {BORDER_ACCENT};
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 11px;
            }}
            
            /* â•â•â• CHECKBOX â•â•â• */
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
            
            /* â•â•â• SPINBOX / SLIDER â•â•â• */
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
        btn_settings.setToolTip("ConfiguraciÃ³n de la app")
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

        self.tabview.addTab(self.tab_perfil, "ðŸ‘¤ MI PERFIL")
        self.tabview.addTab(self.tab_coaching, "ðŸŽ“ COACHING PRO")
        self.tabview.addTab(self.tab_vivo, "ðŸ“¡ RADAR EN VIVO")
        self.tabview.addTab(self.tab_partida, "ðŸŽ® PARTIDA EN VIVO")
        self.tabview.addTab(self.tab_counters, "ðŸ“Š META & BUILDS")
        self.tabview.addTab(self.tab_ia, "ðŸ¤– SIMULADOR 1v1")
        self.tabview.addTab(self.tab_bans, "ðŸš« TIER LIST DE BANS")

        self.armar_tab_perfil()
        self.armar_tab_coaching()
        self.armar_tab_vivo()
        self.armar_tab_partida()
        self.armar_tab_counters()
        self.armar_tab_ia()
        self.armar_tab_bans()
        
        self.tabview.setCurrentIndex(0)  # Abrir en MI PERFIL

    def descargar_imagen(self, id_elemento, tipo):
        cache_key = f"{tipo}_{id_elemento}"
        with self._cache_imagenes_lock:
            if cache_key in self._cache_imagenes:
                return self._cache_imagenes[cache_key]
        
        carpetas = {"runa": RUNAS_DIR, "champ": CHAMPS_DIR, "item": ITEMS_DIR, "spell": SPELLS_DIR, "profile": PROFILE_ICONS_DIR}
        ruta_local = os.path.join(carpetas.get(tipo, CHAMPS_DIR), f"{id_elemento}.png")
        if os.path.exists(ruta_local):
            with self._cache_imagenes_lock:
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
            with self._cache_imagenes_lock:
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
        lbl = QLabel("Selecciona un campeÃ³n para generar su Setup.")
        lbl.setStyleSheet("color: gray; font-style: italic; font-size: 14px;")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

    def _animar_boton(self, btn, text_original):
        btn.setText("Â¡Ã‰XITO! âœ”")
        btn.setStyleSheet(f"background-color: {GREEN_WR}; color: {BG_DARK}; font-weight: bold;")
        QTimer.singleShot(2000, lambda: self._restaurar_boton(btn, text_original))

    def _restaurar_boton(self, btn, text_original):
        btn.setText(text_original)
        if btn == self.btn_export_skills:
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {BG_CARD}; border: 1px solid {ACCENT_TEAL}; border-radius: 4px; color: {ACCENT_TEAL}; font-size: 11px; padding: 6px 16px; font-weight: bold; }}
                QPushButton:hover {{ background-color: #1a3a3a; }}
                QPushButton:disabled {{ color: {BG_BORDER}; border-color: {BG_CARD_HOVER}; }}
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
            return "Endpoint de item sets no disponible en esta versiÃ³n del cliente. Actualiza LoL o prueba otro mÃ©todo."
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

    # â”€â”€ Auto-import wrappers (sin botÃ³n, para modo automÃ¡tico) â”€â”€
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
            args=(lambda: self.lcu.importar_runas(ids_runas, nombre=f"LEA {campeon}"), btn, "Exportar a LoL", "AsegÃºrate de tener el cliente abierto."),
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
            args=(lambda: self.lcu.importar_hechizos(s1, s2), btn, "Exportar a LoL", "AsegÃºrate de estar en una sala de Draft."),
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
            QMessageBox.critical(self, "Error", "No hay ruta de habilidades para exportar.\nSelecciona un campeÃ³n primero.")
            return
        if not self.lcu or not self.lcu.port:
            QMessageBox.critical(self, "Error", "Cliente de LoL no detectado.\nAsegÃºrate de tener el cliente abierto.")
            return
        btn.setEnabled(False)
        self._btn_skills_original = btn.text()
        skill = self.current_skill_order
        threading.Thread(
            target=self._run_lcu_task,
            args=(lambda: self.lcu.importar_skill_order(skill), btn,
                  "âœ… Subido al Cliente",
                  "No se pudo subir la ruta de habilidades.\nAsegÃºrate de estar en selecciÃ³n de campeÃ³n."),
            daemon=True
        ).start()

    # ================= REDISEÃ‘O DE SETUP & BUILD ANTI-ESTIRAMIENTO =================
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

        # â”€â”€ CARD SITUACIONALES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if ids_sit:
            _PRIO_COLOR   = {1: "{RED_DANGER}", 2: "{YELLOW_WARNING}", 3: "{TEXT_SUBTLE}"}
            _PRIO_LABEL   = {1: "CRÃTICO", 2: "RECOMENDADO", 3: "OPCIONAL"}
            _CAT_LABEL    = {
                "anti_heal": "Anti-curaciÃ³n",  "anti_cc": "Anti-CC",
                "anti_ap": "Anti-AP",          "anti_ad": "Anti-AD",
                "anti_tank": "Anti-tanques",   "penetracion": "PenetraciÃ³n",
                "supervivencia": "Supervivencia",
            }

            card_sit = QFrame()
            card_sit.setObjectName("BuildCard")
            l_sit = QVBoxLayout(card_sit)
            l_sit.setSpacing(6)

            lbl_sit_t = QLabel("SITUACIONALES")
            lbl_sit_t.setStyleSheet(f"color: {YELLOW_WARNING}; font-weight: bold; font-size: 11px;")
            l_sit.addWidget(lbl_sit_t, alignment=Qt.AlignCenter)

            for sit in ids_sit[:5]:  # max 5 items para no saturar
                row_w = QWidget()
                row_l = QHBoxLayout(row_w)
                row_l.setContentsMargins(2, 2, 2, 2)
                row_l.setSpacing(6)

                # Icono del Ã­tem
                self.renderizar_icono(sit["id"], "item", row_l, size=32)

                # Texto: categorÃ­a + nombre + razÃ³n
                txt_w = QWidget()
                txt_l = QVBoxLayout(txt_w)
                txt_l.setContentsMargins(0, 0, 0, 0)
                txt_l.setSpacing(1)

                prio_col = _PRIO_COLOR.get(sit["prioridad"], "{TEXT_SUBTLE}")
                cat_txt  = _CAT_LABEL.get(sit["categoria"], sit["categoria"])
                lbl_cat = QLabel(f"<span style='color:{prio_col};font-weight:bold;font-size:9px;'>"
                                 f"{_PRIO_LABEL.get(sit['prioridad'],'')}</span>"
                                 f"<span style='color:{TEXT_MUTED};font-size:9px;'> Â· {cat_txt}</span>")
                lbl_cat.setTextFormat(Qt.RichText)
                txt_l.addWidget(lbl_cat)

                lbl_name = QLabel(f"{sit['nombre']}  <span style='color:{TEXT_SUBTLE};font-size:9px;'>{sit['coste']}g</span>")
                lbl_name.setStyleSheet("color: {TEXT_PRIMARY}; font-size: 10px; font-weight: bold;")
                lbl_name.setTextFormat(Qt.RichText)
                txt_l.addWidget(lbl_name)

                razon = sit["razon"]
                if len(razon) > 75:
                    razon = razon[:72] + "â€¦"
                lbl_razon = QLabel(razon)
                lbl_razon.setStyleSheet("color: {TEXT_MUTED}; font-size: 9px;")
                lbl_razon.setWordWrap(True)
                txt_l.addWidget(lbl_razon)

                row_l.addWidget(txt_w)
                row_l.addStretch()
                l_sit.addWidget(row_w)

            l_sit.addStretch()
            wrap_layout.addWidget(card_sit)

        parent_layout.addWidget(main_wrap)

    # ================= PESTAÃ‘A MI PERFIL DASHBOARD =================
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
        """Extrae el aÃ±o de una partida (gameCreationDate string o gameCreation timestamp)."""
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
        icons = {"IRON": "ðŸ”©", "BRONZE": "ðŸ¥‰", "SILVER": "ðŸ¥ˆ", "GOLD": "ðŸ¥‡",
                 "PLATINUM": "ðŸ’ ", "EMERALD": "ðŸ’š", "DIAMOND": "ðŸ’Ž",
                 "MASTER": "ðŸ‘‘", "GRANDMASTER": "ðŸ”¥", "CHALLENGER": "ðŸ†"}
        return icons.get(tier.upper(), "â“")

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
        self.lbl_soloq_tier = QLabel("âš”ï¸ --")
        self.lbl_soloq_tier.setStyleSheet(f"color: {ACCENT_RED}; font-weight: bold; font-size: 11px;")
        ranks_info.addWidget(self.lbl_soloq_tier)
        self.lbl_soloq_stats = QLabel("")
        self.lbl_soloq_stats.setStyleSheet("color: #8fa3b8; font-size: 9px;")
        ranks_info.addWidget(self.lbl_soloq_stats)
        self.lbl_flex_tier = QLabel("ðŸ›¡ï¸ --")
        self.lbl_flex_tier.setStyleSheet(f"color: {TEXT_GOLD}; font-weight: bold; font-size: 11px;")
        ranks_info.addWidget(self.lbl_flex_tier)
        self.lbl_flex_stats = QLabel("")
        self.lbl_flex_stats.setStyleSheet("color: #8fa3b8; font-size: 9px;")
        ranks_info.addWidget(self.lbl_flex_stats)
        id_card_layout.addLayout(ranks_info)
        
        self.col_id.addWidget(self.pnl_identity_card)
        
        # ===== ESTADÃSTICAS DE LA TEMPORADA (columna izquierda) =====
        self.pnl_season, self.l_season = self.crear_panel("ðŸ“Š ESTADÃSTICAS DE LA TEMPORADA")
        self.lbl_season_stats = QLabel("")
        self.lbl_season_stats.setVisible(False)
        self.l_season.addWidget(self.lbl_season_stats)
        self.tb_season_champs = QTableWidget()
        self.tb_season_champs.setColumnCount(4)
        self.tb_season_champs.setHorizontalHeaderLabels(["CampeÃ³n", "Partidas", "WR", "KDA"])
        self.tb_season_champs.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tb_season_champs.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.tb_season_champs.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.tb_season_champs.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.tb_season_champs.setColumnWidth(1, 62)
        self.tb_season_champs.setColumnWidth(2, 50)
        self.tb_season_champs.setColumnWidth(3, 70)
        self.tb_season_champs.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb_season_champs.setSelectionMode(QAbstractItemView.NoSelection)
        self.tb_season_champs.setShowGrid(False)
        self.tb_season_champs.setAlternatingRowColors(False)
        self.tb_season_champs.verticalHeader().setVisible(False)
        self.tb_season_champs.horizontalHeader().setVisible(True)
        self.tb_season_champs.verticalHeader().setDefaultSectionSize(52)
        self.tb_season_champs.setIconSize(QSize(28, 28))
        self.tb_season_champs.setMaximumHeight(340)
        self.tb_season_champs.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))
        self.tb_season_champs.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tb_season_champs.setStyleSheet("""
            QTableWidget { border: none; background-color: transparent; }
            QHeaderView::section { background-color: #152040; border: none; border-bottom: 1px solid #c89b3c; color: #c89b3c; font-weight: bold; padding: 4px; font-size: 10px; }
            QTableWidget::item { border-bottom: 1px solid #1e2535; padding: 0px; }
        """)
        self.tb_season_champs.verticalScrollBar().valueChanged.connect(self._on_scroll_season)
        self.l_season.addWidget(self.tb_season_champs)
        self.col_id.addWidget(self.pnl_season)
        
        # ===== PANEL DE FATIGA (columna izquierda, abajo) =====
        self.pnl_fatiga, self.l_fatiga = self.crear_panel("ðŸ§  ESTADO MENTAL")
        self.l_fatiga.setAlignment(Qt.AlignTop)
        self.l_fatiga.setSpacing(6)
        self.l_fatiga.setContentsMargins(12, 12, 12, 12)
        
        fr_estado = QFrame()
        fr_estado.setObjectName("InnerPanel")
        l_estado = QHBoxLayout(fr_estado)
        l_estado.setContentsMargins(8, 6, 8, 6)
        l_estado.setSpacing(10)
        l_estado.setAlignment(Qt.AlignLeft)
        
        self.lbl_fatiga_icono = QLabel("â³")
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

        # â”€â”€ PANEL LP HISTORY â”€â”€
        self.pnl_lp, self.l_lp = self.crear_panel("ðŸ“ˆ EVOLUCIÃ“N DE LP (30 DÃAS)")
        lp_header = QHBoxLayout()
        self.cb_lp_queue = QComboBox()
        self.cb_lp_queue.addItems(["Solo/DÃºo", "Flex"])
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
        
        # ===== COLUMNA DERECHA: ESTADÃSTICAS + PERFIL + HISTORIAL =====
        self.col_hist = QVBoxLayout()
        self.col_hist.setAlignment(Qt.AlignTop)
        self.col_hist.setSpacing(6)
        
        # 1. Tarjetas de estadÃ­sticas (KDA / WR / MÃ¡s jugado / Mejor WR)
        self.fr_stats_cards = QHBoxLayout()
        self.fr_stats_cards.setSpacing(6)
        
        self.card_wr, self.lbl_card_wr_val = self._crear_stat_card("ðŸ“Š WINRATE", "--%", GREEN_WR)
        self.fr_stats_cards.addWidget(self.card_wr, 1)
        
        self.card_kda, self.lbl_card_kda_val = self._crear_stat_card("âš”ï¸ KDA", "--", ACCENT_TEAL)
        self.fr_stats_cards.addWidget(self.card_kda, 1)
        
        self.card_most, self.lbl_card_most_val = self._crear_stat_card("ðŸ”¥ +JUGADO", "--", BORDER_ACCENT)
        self.fr_stats_cards.addWidget(self.card_most, 1)
        
        self.card_best, self.lbl_card_best_val = self._crear_stat_card("ðŸ† MEJOR WR", "--", GREEN_WR)
        self.fr_stats_cards.addWidget(self.card_best, 1)
        
        self.col_hist.addLayout(self.fr_stats_cards)
        
        # WR POR LÃNEA
        self.pnl_wr_rol, self.l_wr_rol = self.crear_panel("WINRATE POR LÃNEA")
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
        
        # Filtro por campeÃ³n, modo y temporada
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
        
        # Stack: historial table + overlay vacÃ­o
        self.historial_stack = QFrame()
        hs_layout = QStackedLayout(self.historial_stack)
        hs_layout.setStackingMode(QStackedLayout.StackAll)
        
        self.tb_historial = QTableWidget()
        self.tb_historial.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.tb_historial.setColumnCount(7)
        self.tb_historial.setHorizontalHeaderLabels(["CampeÃ³n", "Resultado", "K/D/A", "CS", "Dur.", "Modo", "Fecha"])
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
        self.tb_historial.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tb_historial.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        hs_layout.addWidget(self.tb_historial)
        
        self.lbl_historial_vacio = QLabel(
            '<div style="text-align: center; padding: 40px;">'
            '<p style="font-size: 36px; margin: 0;">ðŸ“œ</p>'
            '<p style="font-size: 14px; color: {TEXT_SUBTLE}; margin: 8px 0 0 0;">Esperando datos del cliente...</p>'
            '<p style="font-size: 11px; color: {BG_BORDER}; margin: 4px 0 0 0;">Conecta al cliente de LoL para ver tu historial de partidas.</p>'
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
        self.lbl_logros_text.setStyleSheet("color: {TEXT_SUBTLE}; font-size: 11px;")
        self.lbl_logros_text.setWordWrap(True)
        self.fr_logros.addWidget(self.lbl_logros_text)
        self.fr_logros.addStretch()
        self.col_hist.addLayout(self.fr_logros)

        self.tb_historial.verticalScrollBar().valueChanged.connect(self._on_scroll_historial)
        
        l_pnl.addLayout(self.col_hist, 65)
        layout.addWidget(self.pnl_perfil)

    def armar_tab_coaching(self):
        """PestaÃ±a COACHING PRO con scroll, perfil de jugador y reporte de coaching completo."""
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
        
        # â”€â”€ Saludo inicial â”€â”€
        lbl_espera = QLabel(
            '<div style="font-family: \'Segoe UI\', Arial, sans-serif; text-align: center; padding: 30px;">'
            '<p style="font-size: 48px; margin: 0;">ðŸŽ“</p>'
            '<p style="font-size: 16px; color: #e63946; font-weight: 700; margin: 12px 0 4px 0;">COACHING PRO</p>'
            '<p style="font-size: 12px; color: {TEXT_MUTED}; margin: 0; line-height: 1.6;">'
            'Conecta al cliente de LoL para recibir tu anÃ¡lisis personalizado.<br><br>'
            'AquÃ­ encontrarÃ¡s:<br>'
            'ðŸ§˜ FilosofÃ­a de juego y mentalidad<br>'
            'ðŸ“‹ AuditorÃ­a de champion pool<br>'
            'ðŸ¦¾ PrÃ¡ctica deliberada personalizada<br>'
            'âš”ï¸ AnÃ¡lisis de farmeo y fase de lÃ­neas<br>'
            'ðŸ›¡ï¸ GestiÃ³n de muertes y toma de decisiones<br>'
            'ðŸ‘ï¸ Control de visiÃ³n<br>'
            'ðŸ§Š Sistema de juego por bloques (3 partidas)<br>'
            'ðŸ§  GestiÃ³n de fatiga y sesiones<br>'
            'ðŸ’š Tips de salud mental y fisiologÃ­a<br>'
            'ðŸ’¬ Consejos personalizados de tu coach</p>'
            '<p style="font-size: 10px; color: {TEXT_SUBTLE}; margin: 14px 0 0 0; font-style: italic;">'
            'âœ¨ "Cuando cambia tu forma de pensar el LoL, cambia todo lo demÃ¡s."</p>'
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
        """Puebla la pestaÃ±a de coaching con el reporte completo y empÃ¡tico."""
        if not hasattr(self, 'historial_games') or not self.historial_games:
            self._mostrar_coaching_vacio()
            return
        try:
            # Obtener nombre del invocador
            nombre = "Invocador"
            if hasattr(self, 'lbl_sum_name'):
                nombre = self.lbl_sum_name.text().replace("âœ“ ", "").strip()
                if nombre == "Esperando al Cliente...":
                    nombre = "Invocador"
            
            # Datos de fatiga para el reporte
            datos_fatiga = None
            if hasattr(self, 'historial_games') and self.historial_games:
                try:
                    datos_fatiga = analizar_fatiga(self.historial_games)
                except: pass
            
            # Datos de personalidad, hÃ¡bitos y objetivos
            datos_extra = self._generar_datos_perfil_jugador()
            
            reporte = generar_reporte_coach(self.historial_games, nombre, datos_extra, datos_fatiga)
            self._renderizar_coaching(reporte, datos_extra)
        except Exception as e:
            print(f"[_actualizar_coaching] Error: {e}")
            import traceback
            traceback.print_exc()
    
    def _generar_datos_perfil_jugador(self):
        """Genera datos de personalidad, hÃ¡bitos y objetivos sin tocar UI."""
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
                '<p style="font-size: 48px; margin: 0;">ðŸŽ“</p>'
                '<p style="font-size: 16px; color: #e63946; font-weight: 700; margin: 12px 0 4px 0;">COACHING PRO</p>'
                '<p style="font-size: 12px; color: {TEXT_MUTED}; margin: 0; line-height: 1.6;">'
                'Conecta al cliente de LoL para recibir tu anÃ¡lisis personalizado.<br><br>'
                'AquÃ­ encontrarÃ¡s:<br>'
                'ðŸ§˜ FilosofÃ­a de juego y mentalidad<br>'
                'ðŸ“‹ AuditorÃ­a de champion pool<br>'
                'âš”ï¸ AnÃ¡lisis de farmeo y fase de lÃ­neas<br>'
                'ðŸ›¡ï¸ GestiÃ³n de muertes y toma de decisiones<br>'
                'ðŸ‘ï¸ Control de visiÃ³n<br>'
                'ðŸ§  GestiÃ³n de fatiga y sesiones<br>'
                'ðŸ’¬ Consejos personalizados de tu coach</p>'
                '<p style="font-size: 10px; color: {TEXT_SUBTLE}; margin: 14px 0 0 0; font-style: italic;">'
                'âœ¨ "Cuando cambia tu forma de pensar el LoL, cambia todo lo demÃ¡s."</p>'
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
                    border: 1px solid {BG_CARD_HOVER}; 
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
            lbl.setStyleSheet("background: transparent; border: none; color: {TEXT_SECONDARY}; font-size: 12px;")
            l.addWidget(lbl)
            return card
        
        # â”€â”€ 1. Resumen inicial â”€â”€
        resumen = reporte.get("resumen", "")
        if resumen:
            self.coaching_scroll_content.addWidget(_crear_card(resumen, ACCENT_RED))
        
        # â”€â”€ 2. Estilo de juego (personalidad) â”€â”€
        if datos_extra and datos_extra.get("personalidad"):
            pers = datos_extra["personalidad"]
            estilo = pers.get("estilo", "NEUTRAL")
            perfil_texto = pers.get("perfil", "")
            detalles = pers.get("detalles", {})
            
            colores_estilo = {"AGRESIVO": ACCENT_RED, "CONSISTENTE": GREEN_WR, "CONTROL": ACCENT_TEAL, "BALANCEADO": TEXT_GOLD}
            color_estilo = colores_estilo.get(estilo, TEXT_WHITE)
            
            pers_html = f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7;">
            <p style="font-size: 14px; color: {color_estilo}; margin: 0 0 8px 0;"><b>ðŸŽ¯ Tu estilo: {estilo}</b></p>
            <p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0 0 8px 0;">{perfil_texto}</p>
            <p style="font-size: 11px; color: {TEXT_SUBTLE}; margin: 0;">KDA: {detalles.get('avg_kda','?')} Â· Clase preferida: {detalles.get('clase_predominante','?')} Â· Partidas: {detalles.get('total_games','?')}</p>
            </div>"""
            self.coaching_scroll_content.addWidget(_crear_card(pers_html, color_estilo))
        
        # â”€â”€ 3. Insights / hÃ¡bitos â”€â”€
        if datos_extra and datos_extra.get("insights"):
            insights = datos_extra["insights"]
            if insights and insights[0] != "âš ï¸ Necesitas al menos 5 partidas para detectar patrones.":
                ins_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
                ins_html += '<p style="font-size: 13px; color: #2dd4bf; margin: 0 0 6px 0;"><b>ðŸ” Lo que detectÃ© en tu juego:</b></p>'
                for ins in insights[:5]:
                    ins_html += f'<p style="font-size: 11px; color: {TEXT_SECONDARY}; margin: 3px 0;">â€¢ {ins}</p>'
                ins_html += '</div>'
                self.coaching_scroll_content.addWidget(_crear_card(ins_html, "#2dd4bf"))
        
        # â”€â”€ 4. Secciones de anÃ¡lisis â”€â”€
        secciones = reporte.get("secciones", [])
        for sec in secciones:
            color_borde = sec.get("color", BORDER_SUBTLE)
            html = f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.7;">
            <p style="font-size: 13px; color: {color_borde}; font-weight: 700; margin: 0 0 6px 0;">
            {sec.get('icono', 'ðŸ“Š')} {sec.get('titulo', '')}
            </p>
            {sec.get('html', '')}
            </div>"""
            self.coaching_scroll_content.addWidget(_crear_card(html, color_borde, "14px"))
        
        # â”€â”€ 5. Objetivos semanales â”€â”€
        if datos_extra and datos_extra.get("objetivos"):
            objs = datos_extra["objetivos"]
            if objs and "Juega al menos 5 partidas" not in objs[0]:
                obj_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
                obj_html += '<p style="font-size: 13px; color: #e63946; margin: 0 0 6px 0;"><b>ðŸŽ¯ Tus objetivos para esta semana:</b></p>'
                for obj in objs:
                    obj_html += f'<p style="font-size: 11px; color: {TEXT_SECONDARY}; margin: 3px 0;">ðŸŽ¯ {obj}</p>'
                obj_html += '</div>'
                self.coaching_scroll_content.addWidget(_crear_card(obj_html, "#e63946"))
        
        # â”€â”€ 6. Rendimiento emocional â”€â”€
        if datos_extra and datos_extra.get("emocional"):
            emocional = datos_extra["emocional"]
            if emocional:
                emo_html = '<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;">'
                emo_html += '<p style="font-size: 13px; color: {YELLOW_WARNING}; margin: 0 0 6px 0;"><b>ðŸ“Š Rendimiento por estado de Ã¡nimo:</b></p>'
                emoji_map = {"Concentrado": "ðŸ”¥", "Normal": "ðŸ˜", "Tilted": "ðŸ˜¤", "Cansado": "ðŸ˜´"}
                for estado, data in sorted(emocional.items(), key=lambda x: x[1].get("wr", 0), reverse=True):
                    wr_e = data.get("wr", 0)
                    n = data.get("partidas", 0)
                    emoji = emoji_map.get(estado, "â“")
                    color_wr = "{GREEN_SUCCESS}" if wr_e >= 50 else "{RED_DANGER}"
                    emo_html += f'<p style="font-size: 11px; color: {TEXT_SECONDARY}; margin: 2px 0;">{emoji} {estado}: <b style="color:{color_wr};">{wr_e}% WR</b> ({n} partidas)</p>'
                emo_html += '<p style="font-size: 10px; color: {TEXT_SUBTLE}; margin: 6px 0 0 0;">ðŸ’¡ Etiqueta tus partidas en MI PERFIL para ver estadÃ­sticas emocionales.</p>'
                emo_html += '</div>'
                self.coaching_scroll_content.addWidget(_crear_card(emo_html, "{YELLOW_WARNING}"))
        
        # â”€â”€ 7. Consejo final â”€â”€
        consejo = reporte.get("consejo_final", "")
        if consejo:
            consejo_html = f'<div style="font-family: \'Segoe UI\', Arial, sans-serif; line-height: 1.7;"><p style="font-size: 13px; color: {TEXT_PRIMARY}; margin: 0 0 6px 0;"><b>ðŸ’¬ Mensaje de tu coach:</b></p><p style="font-size: 12px; color: {TEXT_SECONDARY}; margin: 0; font-style: italic;">{consejo}</p></div>'
            self.coaching_scroll_content.addWidget(_crear_card(consejo_html, ACCENT_RED))
        
        # AÃ±adir stretch al final
        self.coaching_scroll_content.addStretch()

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # RIOT API â€” PARTIDAS DE LA TEMPORADA (para _fetch_perfil)
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _riot_resolve_puuid(self, game_name: str, tag_line: str):
        """Obtiene el PUUID nuevo (match v5) desde el riot id (gameName#tagLine).
        Si no hay tag_line, no hace fallback falso â€” devuelve None."""
        api_key, region, routing = self._riot_get_config()
        if not api_key or not game_name:
            return None
        if not tag_line:
            return None
        tag = tag_line
        try:
            url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag}"
            res = requests.get(url, headers={"X-Riot-Token": api_key}, timeout=10)
            if res.status_code == 200:
                puuid = res.json().get("puuid")
                print(f"[RiotAPI] PUUID resuelto: {game_name}#{tag} -> {puuid}")
                return puuid
            else:
                print(f"[RiotAPI] HTTP {res.status_code} resolviendo PUUID para {game_name}#{tag}")
        except Exception as e:
            print(f"[RiotAPI] Error resolviendo PUUID: {e}")
        return None

    def _riot_get_config(self):
        """Obtiene api_key, region y routing para llamadas a Riot API."""
        api_key = self.lcu.obtener_api_key_local()
        if not api_key:
            return None, None, None
        region = (self.lcu.obtener_region_local() or "la2").lower()
        routing = "americas" if region in ("la1","la2","na1","br1","oc1","la","lan","las","na","br") else \
                  "europe"   if region in ("euw1","eun1","tr1","ru","euw","eune","tr")             else \
                  "sea"      if region in ("ph2","sg2","th2","tw2","vn2")                           else "asia"
        print(f"[RiotAPI] Region={region}, Routing={routing}")
        return api_key, region, routing

    def _riot_fetch_match_ids(self, puuid: str):
        """Pagina la API de Riot para obtener TODOS los match IDs de la temporada actual.
        Usa count=100, start desde 0 incrementando de 100 en 100, con filtro startTime.
        Rompe cuando la API devuelve []."""
        api_key, region, routing = self._riot_get_config()
        if not api_key:
            return []
        from datetime import timezone as tz
        ahora = datetime.now(tz.utc)
        start_time = int(datetime(ahora.year, 1, 1, tzinfo=tz.utc).timestamp())
        all_ids = []
        offset = 0
        base_url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        hdrs = {"X-Riot-Token": api_key}
        print(f"[RiotAPI] Paginando IDs (region={region}, routing={routing}, startTime={start_time})")
        while True:
            url = f"{base_url}?start={offset}&count=100&startTime={start_time}"
            try:
                res = requests.get(url, headers=hdrs, timeout=15)
                if res.status_code == 429:
                    retry_after = res.headers.get("Retry-After", "10")
                    print(f"[RiotAPI] Rate limit, esperando {retry_after}s...")
                    time.sleep(int(retry_after))
                    continue
                if res.status_code == 400:
                    body = res.text[:300]
                    print(f"[RiotAPI] HTTP 400: {body}")
                    if "startTime" in body.lower() or "parameter" in body.lower():
                        url = f"{base_url}?start={offset}&count=100"
                        print(f"[RiotAPI] Reintentando sin startTime...")
                        res = requests.get(url, headers=hdrs, timeout=15)
                    else:
                        break
                if res.status_code != 200:
                    print(f"[RiotAPI] HTTP {res.status_code} en listado (start={offset})")
                    break
                batch = res.json()
                if not batch:
                    break
                all_ids.extend(batch)
                if len(batch) < 100:
                    break
                offset += 100
            except Exception as e:
                print(f"[RiotAPI] Error obteniendo IDs (start={offset}): {e}")
                break
        print(f"[RiotAPI] {len(all_ids)} IDs de partida obtenidos")
        return all_ids

    def _riot_convert_match(self, raw: dict, my_puuid: str = ""):
        """Convierte una partida de formato Riot API v5 al formato interno de la app.
        Filtra SOLO al participante que coincide con my_puuid y lo pone en [0]."""
        info = raw.get("info", {})
        my_stats = None
        for p in info.get("participants", []):
            if my_puuid and p.get("puuid", "") != my_puuid:
                continue
            my_stats = {
                "championId": int(p.get("championId", 0)),
                "championName": p.get("championName", ""),
                "teamPosition": p.get("teamPosition", ""),
                "puuid": p.get("puuid", ""),
                "stats": {
                    "win": p.get("win", False),
                    "kills": p.get("kills", 0),
                    "deaths": p.get("deaths", 0),
                    "assists": p.get("assists", 0),
                    "totalMinionsKilled": p.get("totalMinionsKilled", 0),
                    "neutralMinionsKilled": p.get("neutralMinionsKilled", 0),
                    "totalDamageDealtToChampions": p.get("totalDamageDealtToChampions", 0),
                    "totalDamageTaken": p.get("totalDamageTaken", 0),
                    "goldEarned": p.get("goldEarned", 0),
                    "visionScore": p.get("visionScore", 0),
                    "wardsPlaced": p.get("wardsPlaced", 0),
                    "visionWardsBoughtInGame": p.get("visionWardsBoughtInGame", 0),
                    "pentaKills": p.get("pentaKills", 0),
                    "tripleKills": p.get("tripleKills", 0),
                    "turretKills": p.get("turretKills", 0),
                    "dragonKills": p.get("dragonKills", 0),
                    "baronKills": p.get("baronKills", 0),
                    "timeCCingOthers": p.get("timeCCingOthers", 0),
                    "firstBloodKill": p.get("firstBloodKill", False),
                }
            }
            break
        if not my_stats:
            return None
        game_creation_ms = info.get("gameCreation", 0)
        game_creation_ts = game_creation_ms / 1000 if game_creation_ms else 0
        return {
            "gameId": raw.get("metadata", {}).get("matchId", ""),
            "gameCreation": game_creation_ts,
            "gameCreationDate": datetime.fromtimestamp(game_creation_ts).strftime("%b %d, %Y %I:%M:%S %p") if game_creation_ts else "",
            "gameDuration": info.get("gameDuration", 0),
            "gameMode": info.get("gameMode", "CLASSIC"),
            "participants": [my_stats],
        }

    def _riot_fetch_one_match(self, match_id: str, my_puuid: str = ""):
        """Descarga UNA partida de Riot API. Con backoff exponencial + Retry-After."""
        api_key, region, routing = self._riot_get_config()
        if not api_key:
            return None
        hdrs = {"X-Riot-Token": api_key}
        url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        for intento in range(4):
            try:
                res = requests.get(url, headers=hdrs, timeout=10)
                if res.status_code == 429:
                    retry = int(res.headers.get("Retry-After", 2 ** intento))
                    time.sleep(min(retry, 15))
                    continue
                if res.status_code == 200:
                    return self._riot_convert_match(res.json(), my_puuid)
                if res.status_code == 404:
                    return None
            except Exception:
                time.sleep(2 ** intento)
        return None

    def _riot_fetch_matches(self, match_ids: list, my_puuid: str = "", max_matches: int = None):
        """Descarga partidas de Riot API en PARALELO (6 workers).
        my_puuid filtra SOLO al jugador correcto. max_matches=None = todas."""
        api_key, region, routing = self._riot_get_config()
        if not api_key:
            return []
        total_ids = len(match_ids)
        if max_matches:
            match_ids = match_ids[:max_matches]
        if not match_ids:
            return []
        print(f"[RiotAPI] Descargando {len(match_ids)}/{total_ids} partidas (6 workers)...")
        games = []
        downloaded = 0
        errores = 0
        t_start = time.time()
        last_emit = 0
        BATCH_EMIT = 30
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(self._riot_fetch_one_match, mid, my_puuid): mid for mid in match_ids}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        games.append(result)
                        downloaded += 1
                    else:
                        errores += 1
                except Exception:
                    errores += 1
                total = downloaded + errores
                if downloaded - last_emit >= BATCH_EMIT:
                    batch = games[last_emit:downloaded]
                    if batch:
                        self.season_partial.emit(list(batch))
                    last_emit = downloaded
                    elapsed = time.time() - t_start
                    print(f"[RiotAPI] {total}/{len(match_ids)} ({(total/len(match_ids)*100):.0f}%) +{len(batch)} en {elapsed:.0f}s")
        if last_emit < downloaded:
            batch = games[last_emit:]
            if batch:
                self.season_partial.emit(list(batch))
        elapsed = time.time() - t_start
        pct = len(match_ids) / max(1, elapsed)
        print(f"[RiotAPI] {downloaded} OK, {errores} err en {elapsed:.0f}s ({pct:.0f}/s)")
        return games

    def _get_season_cache_path(self, puuid: str):
        """Ruta del archivo de cache JSON para partidas de temporada."""
        import sys as _sys
        if getattr(_sys, 'frozen', False):
            base = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'LoLRecommender', 'cache')
        else:
            base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(base, exist_ok=True)
        safe_puuid = puuid.replace("-", "_")
        return os.path.join(base, f"season_cache_{safe_puuid}.json")

    def _inicializar_db_background(self):
        """Inicializa la BD en un hilo de fondo. No toca la UI: solo emite la senal."""
        from src.db_manager import ConexionDBError
        try:
            inicializar_db()
            self.db_listo.emit(True)
        except ConexionDBError as e:
            print(f"[NEXUS] ERROR de conexion a PostgreSQL: {e}")
            print("[NEXUS] La app funcionara con funcionalidad limitada.")
            print("[NEXUS] Verifica tu conexion a internet y que el servidor este accesible.")
            self.db_listo.emit(False)
        except Exception as e:
            print(f"[NEXUS] Error inesperado inicializando BD: {e}")
            self.db_listo.emit(False)

    def _on_db_listo(self, ok: bool):
        """Handler en el hilo de UI cuando termina la inicializacion de la BD."""
        self._db_conectado = ok

    def _limpiar_cache_antiguo(self):
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        if not os.path.isdir(cache_dir):
            return
        try:
            ahora = time.time()
            eliminados = 0
            for fname in os.listdir(cache_dir):
                if not fname.startswith("season_cache_") or not fname.endswith(".json"):
                    continue
                fpath = os.path.join(cache_dir, fname)
                if ahora - os.path.getmtime(fpath) > 86400:
                    os.remove(fpath)
                    eliminados += 1
            if eliminados:
                print(f"[Cache] Limpiados {eliminados} archivos de cache obsoletos")
        except Exception as e:
            print(f"[Cache] Error limpiando: {e}")

    def _load_season_cache(self, puuid: str):
        """Carga partidas desde cache JSON si es de hoy. Retorna lista o None."""
        cache_path = self._get_season_cache_path(puuid)
        if not os.path.exists(cache_path):
            return None
        try:
            mtime = os.path.getmtime(cache_path)
            age_hours = (time.time() - mtime) / 3600
            if age_hours > 24:
                return None
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"[Cache] Cargadas {len(data)} partidas desde cache ({age_hours:.1f}h de antiguedad)")
            return data
        except Exception as e:
            print(f"[Cache] Error cargando: {e}")
        return None

    def _save_season_cache(self, puuid: str, games: list):
        """Guarda partidas en cache JSON."""
        if not games or len(games) < 10:
            return
        try:
            cache_path = self._get_season_cache_path(puuid)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(games, f)
            print(f"[Cache] Guardadas {len(games)} partidas en cache")
        except Exception as e:
            print(f"[Cache] Error guardando: {e}")

    def _riot_season_background(self, puuid: str, all_games: list, game_name: str, tag_line: str):
        """Ejecutado en hilo separado: descarga partidas de Riot SIN bloquear la UI.
        Usa streaming via season_partial para mostrar datos mientras llegan."""
        try:
            # Intentar cache primero
            cached = self._load_season_cache(puuid)
            if cached:
                existing_gids = set()
                for g in all_games:
                    gid = str(g.get("gameId", ""))
                    if not gid:
                        gid = f"{g.get('gameCreationDate','')}_{g.get('gameDuration',0)}"
                    existing_gids.add(gid)
                nuevos_cache = [g for g in cached if self._gid_or_fallback(g) and self._gid_or_fallback(g) not in existing_gids]
                if nuevos_cache:
                    self.season_partial.emit(nuevos_cache)
                    print(f"[RiotAPI] Cache: +{len(nuevos_cache)} partidas streaming")
                return

            # Resolver PUUID nuevo
            riot_puuid = puuid
            new_puuid = self._riot_resolve_puuid(game_name, tag_line)
            if new_puuid and new_puuid != puuid:
                riot_puuid = new_puuid

            # Descargar IDs + partidas (my_puuid = el usado para obtener IDs)
            riot_ids = self._riot_fetch_match_ids(riot_puuid)
            if riot_ids:
                riot_games = self._riot_fetch_matches(riot_ids, my_puuid=riot_puuid)
                # Guardar cache (usar puuid original del LCU, no el resuelto)
                self._save_season_cache(puuid, riot_games)
        except Exception as e:
            print(f"[RiotAPI] Error en background: {e}")

    @staticmethod
    def _gid_or_fallback(g):
        gid = str(g.get("gameId", ""))
        if not gid:
            gid = f"{g.get('gameCreationDate','')}_{g.get('gameDuration',0)}"
        return gid

    # ================= CARGA DE PERFIL (HILO SEGUNDARIO) =================
    def _fetch_perfil(self):
        """Se ejecuta en hilo secundario. Recoge TODOS los datos de LCU sin tocar UI.
        Incluye reintentos con backoff porque la API de LCU tarda unos segundos en
        estar disponible tras abrir el cliente."""
        data = {"ok": False}
        try:
            # â”€â”€ Fase 1: Perfil base (con reintentos, la API puede no estar lista) â”€â”€
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
            
            # â”€â”€ Fase 2: Ligas (con reintentos â€” la API de ranked tarda en arrancar) â”€â”€
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
            
            # â”€â”€ Fase 3: MaestrÃ­as (no fatal si falla) â”€â”€
            maestrias = []
            try:
                maestrias = self.lcu.obtener_maestrias()
            except Exception as e:
                print(f"[_fetch_perfil] Error obteniendo maestrÃ­as (no fatal): {e}")
            data["maestrias"] = maestrias[:3] if maestrias else []
            
            # â”€â”€ Fase 4: Historial (con reintentos, no fatal si falla) â”€â”€
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
            
            # â”€â”€ Fase 5: Season stats (paginaciÃ³n completa para toda la temporada) â”€â”€
            all_games = list(historial) if historial else []

            def _gid(g):
                gid = str(g.get("gameId", "") or "")
                if not gid:
                    gid = f"{g.get('gameCreationDate','')}_{g.get('gameDuration',0)}"
                return gid

            if all_games and self.lcu and self.lcu.port:
                try:
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

            # Emitir YA los datos del LCU â€” no esperar a Riot API
            data["ok"] = perfil_ok
            self.perfil_listo.emit(data)

            # â”€â”€ Fase 6: Riot API (background, no bloquea la UI) â”€â”€
            if puuid and len(all_games) < 500:
                game_name = perfil.get("gameName") or perfil.get("displayName", "").split("#")[0]
                tag_line = perfil.get("tagLine") or ""
                threading.Thread(
                    target=self._riot_season_background,
                    args=(puuid, all_games, game_name, tag_line),
                    daemon=True
                ).start()

        except Exception as e:
            print(f"[_fetch_perfil] Error crÃ­tico: {e}")
            data["ok"] = False
            self.perfil_listo.emit(data)

    def _on_perfil_listo(self, data):
        """Se ejecuta en el hilo principal. Actualiza la UI con los datos ya recogidos."""
        self._cargando_perfil = False
        
        if not data.get("ok") or not data.get("perfil"):
            print(f"[_on_perfil_listo] Datos insuficientes (ok={data.get('ok')}), se reintentarÃ¡.")
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

            # Registrar LP del dÃ­a y actualizar grÃ¡fica
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
            # Guardar all_games_season si viene del fetch (paginaciÃ³n ya hecha en hilo secundario)
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

        # DEDUP robusto usando _gid_or_fallback
        seen_gids = set()
        unique = []
        for g in games:
            gid = self._gid_or_fallback(g)
            if gid and gid not in seen_gids:
                seen_gids.add(gid)
                unique.append(g)
        if len(unique) < len(games):
            print(f"[Historial] DEDUP: {len(games)} -> {len(unique)} partidas")
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

        # --- WR POR LÃNEA (1 sola query para todos los campeones) ---
        conn = obtener_conexion()
        cur = conn.cursor()
        
        # Recoger campeones Ãºnicos del historial
        champs_hist = list(set(
            self.procesar_nombre_champ(str(g.get("participants", [{}])[0].get("championId", "0")), "0") or "?"
            for g in self.historial_games
        ))
        
        # 1 sola query: rol mÃ¡s frecuente de cada campeÃ³n
        rol_por_champ = {}
        if champs_hist:
            placeholders = ",".join(["%s"] * len(champs_hist))
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

        # --- ESTADÃSTICAS DE LA SEASON + FATIGA ---
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

        # â”€â”€â”€ FASE 4: COACHING PRO â”€â”€â”€
        self._actualizar_coaching()

        # â”€â”€â”€ FASE 5: LOGROS â”€â”€â”€
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
                self.lbl_insights_title.setText("ðŸ” INSIGHTS DETECTADOS")
                self.lbl_insights.setText("\n".join(f"â€¢ {i}" for i in insights[:5]))
            
            # 3. Objetivos semanales
            objetivos = generar_objetivos_semanales(games)
            if objetivos:
                self.lbl_objetivos_title.setText("ðŸŽ¯ OBJETIVOS SEMANALES")
                self.lbl_objetivos.setText("\n".join(objetivos))
            
            # 4. Cruce emocional vs WR
            emocional = analizar_emocional_vs_wr(games)
            if emocional:
                self.lbl_emocional_title.setText("ðŸ“Š RENDIMIENTO POR ESTADO")
                lineas = []
                emoji_map = {"Concentrado": "ðŸ”¥", "Normal": "ðŸ˜", "Tilted": "ðŸ˜¤", "Cansado": "ðŸ˜´"}
                for estado, data in sorted(emocional.items(), key=lambda x: x[1].get("wr", 0), reverse=True):
                    wr_e = data.get("wr", 0)
                    n = data.get("partidas", 0)
                    emoji = emoji_map.get(estado, "â“")
                    lineas.append(f"{emoji} {estado}: {wr_e}% WR ({n} partidas)")
                self.lbl_emocional_stats.setText("\n".join(lineas) if lineas else "Etiqueta tus partidas para ver estadÃ­sticas")
        except Exception as e:
            print(f"[_actualizar_perfil_jugador] Error: {e}")

    def _actualizar_grafica_lp(self):
        """Refresca la grÃ¡fica de LP con los datos de la cola seleccionada."""
        if not hasattr(self, "lp_graph"):
            return
        queue_map = {"Solo/DÃºo": "RANKED_SOLO_5x5", "Flex": "RANKED_FLEX_SR"}
        queue = queue_map.get(self.cb_lp_queue.currentText(), "RANKED_SOLO_5x5")
        try:
            history = obtener_historial_lp(queue, dias=30)
            self.lp_graph.set_data(history)
        except Exception as e:
            print(f"[LP Graph] Error: {e}")

    def _analizar_fatiga(self):
        """Analiza fatiga/tilt desde el historial de la LCU y actualiza el dashboard premium."""
        if not hasattr(self, 'historial_games') or not self.historial_games:
            self.lbl_fatiga_icono.setText("ðŸ“Š")
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
                mensaje = "ðŸŒ… Â¡No has jugado hoy! EstÃ¡s en tu mejor momento."
                recomendacion = "La mente estÃ¡ fresca y los reflejos listos. Calienta con un normal o salta directo a ranked. Hoy es tu dÃ­a."
            else:
                fatiga = analizar_fatiga(games_hoy)
                estado = fatiga.get("estado", "neutral")
                mensaje = fatiga.get("mensaje", "Sin datos")
                recomendacion = fatiga.get("recomendacion", "")
            
            emojis = {"fresh": "ðŸ”¥", "neutral": "âš–ï¸", "tired": "ðŸ¥±", "tilted": "ðŸ’¢"}
            colores = {"fresh": GREEN_WR, "neutral": ACCENT_TEAL, "tired": YELLOW_WR, "tilted": RED_WR}
            textos_color = {"fresh": "#064e3b", "neutral": "#134e4a", "tired": "#713f12", "tilted": "#7f1d1d"}
            textos = {"fresh": "Ã“PTIMO", "neutral": "NEUTRAL", "tired": "CANSADO", "tilted": "TILTEADO"}
            
            emoji = emojis.get(estado, "ðŸ”¥")
            color = colores.get(estado, GREEN_WR)
            bar_color = colores.get(estado, GREEN_WR)
            bar_bg = textos_color.get(estado, "#064e3b")
            estado_txt = textos.get(estado, "Ã“PTIMO")
            
            self.lbl_fatiga_icono.setText(emoji)
            self.lbl_fatiga_icono.setStyleSheet("font-size: 28px; padding: 0px;")
            self.lbl_fatiga_estado.setText(estado_txt)
            self.lbl_fatiga_estado.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
            self.lbl_fatiga_barra.setStyleSheet(f"background-color: {bar_color}; border-radius: 2px;")
            
            if recomendacion:
                self.lbl_fatiga_consejo.setText(f"ðŸ’¡ {recomendacion}")
            else:
                self.lbl_fatiga_consejo.setText(mensaje)
            self.lbl_fatiga_consejo.setStyleSheet("color: #8fa3b8; font-size: 10px; padding: 2px 6px 4px 6px;")
        except Exception as e:
            print(f"[_analizar_fatiga] Error: {e}")
            self.lbl_fatiga_icono.setText("âŒ")
            self.lbl_fatiga_icono.setStyleSheet("font-size: 28px; padding: 0px;")
            self.lbl_fatiga_estado.setText("ERROR")
            self.lbl_fatiga_estado.setStyleSheet(f"color: {RED_WR}; font-size: 16px; font-weight: bold;")
            self.lbl_fatiga_consejo.setText("No se pudo analizar el estado mental.")
            self.lbl_fatiga_consejo.setStyleSheet("color: #8fa3b8; font-size: 10px; padding: 2px 6px 4px 6px;")

    def _on_scroll_historial(self, value):
        """Scroll infinito: carga mas partidas cuando el usuario llega al final."""
        # Si ya hay 100+, no cargar mas (el LCU no tiene datos adicionales)
        if hasattr(self, 'historial_games') and len(self.historial_games) >= 100:
            return
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
            if current >= 200: return
            perfil = self.lcu.obtener_perfil()
            if not perfil: return
            puuid = perfil.get("puuid")
            if not puuid: return
            
            nuevas = self.lcu.obtener_historial_extendido(inicio=current, cantidad=50)
            if not nuevas: return
            
            # DEDUP robusto usando mismo criterio que _renderizar_historial
            existing_ids = {self._gid_or_fallback(g) for g in self.historial_games}
            really_new = [g for g in nuevas if self._gid_or_fallback(g) and self._gid_or_fallback(g) not in existing_ids]
            
            if really_new:
                self.historial_games.extend(really_new)
                # Re-ordenar todo para mantener orden por fecha
                self._renderizar_historial(self.historial_games)
            else:
                self._cargando_historial = False
                return
        finally:
            self._cargando_historial = False

    def _append_games_to_table(self, games):
        """AÃ±ade partidas a la tabla sin borrar las existentes."""
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

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # MOTOR EMOCIONAL â€” ETIQUETADO DE PARTIDAS (NEXUS)
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _crear_widget_emocional(self, game_id: str, champ_name: str, estado_actual: str = None):
        """Crea un widget con 4 botones de estado emocional para una fila del historial."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        estados = [
            ("ðŸ”¥", "Concentrado", "{RED_DANGER}", "Concentrado: enfoque total"),
            ("ðŸ˜", "Normal", "{TEXT_SUBTLE}", "Normal: estado neutro"),
            ("ðŸ˜¤", "Tilted", "{YELLOW_WARNING}", "Tilted: frustrado"),
            ("ðŸ˜´", "Cansado", "#3b82f6", "Cansado: fatiga"),
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
                    QPushButton {{ background-color: transparent; color: {BG_BORDER}; border: 1px solid {BG_CARD_HOVER}; 
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
        """Filtra la tabla de historial por campeÃ³n, modo y temporada."""
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
        self.lbl_radar_tip = QLabel("ðŸ’¡ <b>Consejo:</b> En Champ Select, prioriza counter-pickear a tu rival de lÃ­nea. Revisa runas y hechizos recomendados abajo.")
        self.lbl_radar_tip.setWordWrap(True)
        self.lbl_radar_tip.setTextFormat(Qt.RichText)
        self.lbl_radar_tip.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; padding: 6px 10px; background-color: {BG_DARK}; border: 1px solid {BG_CARD_HOVER}; border-left: 3px solid {ACCENT_TEAL}; border-radius: 4px; margin-bottom: 2px;")
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
        
        self.panel_bans_vivo, self.l_bans_vivo = self.crear_panel("Bans Sugeridos (Tu LÃ­nea)")
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
        
        self.lbl_rol_vivo = QLabel("ASIGNACIÃ“N PENDIENTE")
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
        self.panel_skills, self.l_skills = self.crear_panel("ðŸ“– RUTA DE HABILIDADES")
        self.lbl_skill_order = QLabel("Selecciona un campeÃ³n")
        self.lbl_skill_order.setAlignment(Qt.AlignCenter)
        self.lbl_skill_order.setStyleSheet(f"color: {ACCENT_TEAL}; font-size: 16px; font-weight: bold; padding: 8px;")
        self.l_skills.addWidget(self.lbl_skill_order)
        self.btn_export_skills = QPushButton("ðŸ“¤ Subir orden al Cliente")
        self.btn_export_skills.setStyleSheet(f"""
            QPushButton {{ background-color: {BG_CARD}; border: 1px solid {ACCENT_TEAL}; border-radius: 4px; color: {ACCENT_TEAL}; font-size: 11px; padding: 6px 16px; font-weight: bold; }}
            QPushButton:hover {{ background-color: #1a3a3a; }}
            QPushButton:disabled {{ color: {BG_BORDER}; border-color: {BG_CARD_HOVER}; }}
        """)
        self.btn_export_skills.clicked.connect(lambda: self.accion_importar_skill_order(self.btn_export_skills))
        self.btn_export_skills.setVisible(False)
        self.l_skills.addWidget(self.btn_export_skills, alignment=Qt.AlignCenter)
        l_center.addWidget(self.panel_skills)

        # â”€â”€ PANEL PATHING JUNGLA (solo visible cuando rol = JUNGLA) â”€â”€
        self.pnl_pathing, self.l_pathing = self.crear_panel("ðŸ—ºï¸ PATHING DE JUNGLA")
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
        """Solo hace operaciones rÃ¡pidas (leer lockfile). El trabajo pesado (HTTP)
        se lanza en hilos secundarios para no congelar la UI."""
        conectado = self.lcu.conectar()
        
        if not conectado:
            # Cliente cerrado o lockfile desapareciÃ³ â†’ resetear todo
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
            self.lbl_estado_lcu.setText("âœ“ ENLAZADO AL CLIENTE DE LOL")
            self.lbl_estado_lcu.setStyleSheet(f"color: {GREEN_WR}; font-weight: bold; font-size: 14px;")
            # PequeÃ±a pausa: la API HTTP del cliente tarda ~2s en estar lista tras
            # aparecer el lockfile. Sin esto, el primer fetch falla y el usuario
            # pensarÃ­a que la app no funciona.
            time.sleep(1.5)
        
        # Cargar perfil en hilo secundario (si no estÃ¡ ya cargÃ¡ndose)
        if not self.perfil_cargado and not self._cargando_perfil:
            self._cargando_perfil = True
            threading.Thread(target=self._fetch_perfil, daemon=True).start()
        
        # Actualizar radar/draft en hilo secundario (si no estÃ¡ ya actualizÃ¡ndose)
        if not self._actualizando_radar:
            self._actualizando_radar = True
            threading.Thread(target=self._fetch_radar, daemon=True).start()
        
        # Auto-switch de pestaÃ±as segun fase del juego + notificaciones
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
                    self.tray_icon.showMessage("NEXUS", "Partida terminada â€” Ver analisis", QIcon(), 4000)
                    # Marcar ultimo draft como completado
                    try:
                        if hasattr(self, '_draft_id_actual') and self._draft_id_actual:
                            completar_draft_resultado(self._draft_id_actual, None)
                            self._draft_id_actual = None
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
        Si no hay draft activo, simplemente se salta la actualizaciÃ³n SIN desconectar."""
        self._actualizando_radar = False
        
        if not self.radar_activo:
            return
        
        if not draft:
            # No hay sesiÃ³n de draft activa â†’ no desconectar, solo esperar
            return
        
        try:
            rol_api = self.lcu.obtener_mi_rol(draft)
            rol_ui = API_TO_ROL.get(rol_api, "MID")
            self.lbl_rol_vivo.setText(f"LÃNEA ASIGNADA: {rol_ui}")

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
                self._cache_rol_tipico_lock = threading.Lock()
            if rol_api not in self._cache_rol_tipico or not self._cache_rol_tipico.get(rol_api):
                with self._cache_rol_tipico_lock:
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
                # 1. Por CLASE del campeon (mas fiable: Marksmanâ†’BOTTOM, Supportâ†’UTILITY, etc.)
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
                
                # 2. Por rol tipico en BD (cache) â€” con tiebreaker: el mas frecuente en este rol
                if not enemigo_lane:
                    cache_rol = self._cache_rol_tipico.get(rol_api, set())
                    candidatos_cache = []
                    conn_radar = obtener_conexion()
                    try:
                        cur = conn_radar.cursor()
                        placeholders = ",".join(["?"] * len(enemigos_procesados))
                        champs_list = [champ for champ, pos, idx in enemigos_procesados]
                        cur.execute(
                            f"SELECT champion, COUNT(*) as cnt FROM participantes "
                            f"WHERE champion IN ({placeholders}) AND team_position = ? "
                            f"GROUP BY champion",
                            champs_list + [rol_api]
                        )
                        freq_map = {row["champion"]: row["cnt"] for row in cur.fetchall()}
                    except Exception:
                        freq_map = {}
                    finally:
                        conn_radar.close()
                    for champ, pos, idx in enemigos_procesados:
                        if champ in cache_rol:
                            freq = freq_map.get(champ, 0)
                            candidatos_cache.append((champ, freq))
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
                self.lbl_ally_stats.setText(f"DaÃ±o AD: {ad_al}% | DaÃ±o AP: {ap_al}% | Frontlane: {tanks_al}")
                ad_en, ap_en, tanks_en = analizar_composicion(picks_en_db)
                self.lbl_enemy_stats.setText(f"DaÃ±o AD: {ad_en}% | DaÃ±o AP: {ap_en}% | Frontlane: {tanks_en}")
                
                self.mostrar_picks_vivo(rol_api, picks_al_db, picks_en_db)

                # Actualizar counters si cambia el rival de linea (aunque no haya cambiado mi pick)
                if enemigo_lane != self.last_enemigo_lane:
                    self._actualizar_counters_vivo(rol_api, enemigo_lane)

                if len(picks_al_db) == 5 and len(picks_en_db) == 5:
                    wr = calcular_winrate_5v5(picks_al_db, picks_en_db, pos_al, pos_en)
                    color = GREEN_WR if wr > 52 else RED_WR if wr < 48 else YELLOW_WR
                    tendencia = "â†‘ Ventaja de Sinergia" if wr > 52 else "â†“ Desventaja de Draft" if wr < 48 else "â‰ˆ Matchup Equilibrado"
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
                            self._draft_id_actual = guardar_draft(mi_campeon, rol_api, bans_actuales, picks_al, picks_en, wr)
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
                            f"ðŸš« Baneo sugerido: {self._nombre_display(ban)}\nðŸ“Š WR rival: {wr}% en {partidas} partidas", size=35)
                else: 
                    lbl_noban = QLabel("Sin recomendaciones")
                    lbl_noban.setStyleSheet("color: gray;")
                    self.fr_bans_icons_vivo.addWidget(lbl_noban)

                # â”€â”€ COUNTER PICKS contra el rival de linea â”€â”€
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

                    # Auto-import segun configuraciÃ³n
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
                    self.lbl_skill_order.setText("Selecciona un campeÃ³n")
                    self.btn_export_skills.setVisible(False)
            # â”€â”€ PATHING JUNGLA â”€â”€
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
                self.lbl_pathing_inicio.setText(f"ðŸ Inicio: {pathing.get('inicio', '')}")
                self.lbl_pathing_ruta.setText(f"ðŸ“ Ruta: {pathing.get('ruta', '')}")
                self.lbl_pathing_gank.setText(f"ðŸ—¡ï¸ Gank: {pathing.get('prioridad_gank', '')}")
                vs = pathing.get("vs_jungla", "")
                self.lbl_pathing_vs.setText(vs)
                self.lbl_pathing_vs.setVisible(bool(vs))
                self.pnl_pathing.setVisible(True)
            else:
                self.pnl_pathing.setVisible(False)

            # Actualizar tip segÃºn estado del draft
            if mi_campeon and enemigo_lane:
                self.lbl_radar_tip.setText(
                    f"âš¡ <b>Coach:</b> Juegas <b>{self._nombre_display(mi_campeon)}</b> vs <b>{self._nombre_display(enemigo_lane)}</b>. "
                    f"Revisa los counters, runas y hechizos abajo. Â¡Buena suerte!"
                )
            elif mi_campeon and not enemigo_lane:
                self.lbl_radar_tip.setText(
                    f"ðŸŽ¯ <b>Coach:</b> Pickeaste {self._nombre_display(mi_campeon)}. Revisa el setup recomendado abajo. "
                    f"Prioriza runas y objetos segÃºn la composiciÃ³n enemiga."
                )
            elif not mi_campeon and len(picks_al) > 0:
                self.lbl_radar_tip.setText(
                    "ðŸ’¡ <b>Coach:</b> Espera a ver el pick rival antes de elegir. "
                    "Mientras, revisa los bans sugeridos y la composiciÃ³n de tu equipo."
                )
            else:
                self.lbl_radar_tip.setText(
                    "ðŸ’¡ <b>Coach:</b> En Champ Select, prioriza counter-pickear a tu rival de lÃ­nea. "
                    "Revisa runas y hechizos recomendados abajo."
                )

            # Tips de matchup especÃ­ficos
            if enemigo_lane:
                enemy_db = self._nombre_db(enemigo_lane) or enemigo_lane
                tips = obtener_tips_matchup(enemy_db)
                if tips:
                    tips_html = "  |  ".join(f"â€¢ {t}" for t in tips[:2])
                    self.lbl_matchup_tips.setText(
                        f"ðŸ—¡ï¸ <b>vs {self._nombre_display(enemigo_lane)}:</b>  {tips_html}"
                    )
                    self.lbl_matchup_tips.setVisible(True)
                else:
                    self.lbl_matchup_tips.setVisible(False)
            else:
                self.lbl_matchup_tips.setVisible(False)
        except Exception:
            pass

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # PARTIDA EN VIVO (Porofessor-style)
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def armar_tab_partida(self):
        layout = QVBoxLayout(self.tab_partida)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Header
        self.lbl_partida_header = QLabel("ðŸŽ® Esperando partida...\n\nLos datos apareceran cuando entres a la Grieta")
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

        # â”€â”€ Aliados â”€â”€
        self.tb_partida_aliados = QTableWidget()
        self.tb_partida_aliados.setColumnCount(4)
        self.tb_partida_aliados.setHorizontalHeaderLabels(["Campeon", "KDA", "CS", "Comentario"])
        self._estilizar_tabla_partida(self.tb_partida_aliados, "{BG_DARK}")
        tablas_layout.addWidget(self.tb_partida_aliados)

        # â”€â”€ Enemigos â”€â”€
        self.tb_partida_enemigos = QTableWidget()
        self.tb_partida_enemigos.setColumnCount(4)
        self.tb_partida_enemigos.setHorizontalHeaderLabels(["Campeon", "KDA", "CS", "Comentario"])
        self._estilizar_tabla_partida(self.tb_partida_enemigos, "#1a0a0f")
        tablas_layout.addWidget(self.tb_partida_enemigos)

        layout.addLayout(tablas_layout, 1)

        # ComposiciÃ³n
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
            QHeaderView::section {{ background-color: {BG_DARK}; color: {TEXT_MUTED}; font-size: 10px; padding: 3px; border: none; }}
        """)

    def actualizar_partida_vivo(self):
        """Actualiza la pestaÃ±a de partida en vivo con datos del LiveClient."""
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
                self.lbl_partida_header.setText("ðŸ Partida terminada\n\nRevisa tu perfil para ver el analisis")
                # Mostrar post-game una sola vez por partida (al transicionar desde InProgress)
                if not self._postgame_shown and self._last_fase in ("InProgress", "GameStart"):
                    self._postgame_shown = True
                    threading.Thread(target=self._preparar_postgame, daemon=True).start()
            else:
                # Nueva fase de lobby â†’ resetear para la prÃ³xima partida
                self._postgame_shown = False
                self.lbl_partida_header.setText("ðŸŽ® Esperando partida...\n\nLos datos apareceran cuando entres a la Grieta")
            self._last_fase = fase
            return

        # EntrÃ³ a una partida nueva â†’ resetear el flag
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
            self.lbl_partida_header.setText("â³ Entrando a la Grieta...\n\nLos datos apareceran al iniciar la partida")

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
            self.lbl_partida_kda.setText(f"ðŸ”¥ Tu {cname}: {k}/{d}/{a}")
            self.lbl_partida_cs.setText(f"CS: {cs} ({cs_min:.1f}/min)")
            # Cachear para post-game (actualizamos siempre para tener el estado mÃ¡s reciente)
            self._last_game_stats = {
                "champion": cname, "kills": k, "deaths": d, "assists": a,
                "cs": cs, "game_time": game_time,
            }
        else:
            self.lbl_partida_kda.setText("ðŸ”¥ Tu: (buscando...)")
            self.lbl_partida_cs.setText("CS: --")

        # Tablas aliados/enemigos
        self._llenar_tabla_partida(self.tb_partida_aliados, aliados, "ðŸ”µ ALIADOS", "{BG_DARK}", yo)
        self._llenar_tabla_partida(self.tb_partida_enemigos, enemigos, "ðŸ”´ ENEMIGOS", "#1a0a0f", yo)

        # Alimentar overlay si estÃ¡ activado
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
                    f"âš”ï¸ Aliados: AD {ad_a}% / AP {ap_a}% ({tk_a} front)  |  "
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
            self.lbl_partida_kda.setText(f"ðŸŽ® En partida con {cname} (datos basicos LCU)")
            self._last_game_stats = {"champion": cname, "kills": 0, "deaths": 0, "assists": 0, "cs": 0, "game_time": 0}
        else:
            self.lbl_partida_kda.setText("ðŸŽ® Partida en vivo (datos basicos LCU)")
        self.lbl_partida_cs.setText("CS: --")
        self.lbl_partida_timer.setText("--:--")

        aliados = [j for j in jugadores if j.get("team") == "ORDER"]
        enemigos = [j for j in jugadores if j.get("team") == "CHAOS"]

        self._llenar_tabla_partida_lcu(self.tb_partida_aliados, aliados, "ðŸ”µ ALIADOS", "{BG_DARK}")
        self._llenar_tabla_partida_lcu(self.tb_partida_enemigos, enemigos, "ðŸ”´ ENEMIGOS", "#1a0a0f")

        a_nombres = [self.procesar_nombre_champ(str(j.get("championId", 0)), "0") for j in aliados if self.procesar_nombre_champ(str(j.get("championId", 0)), "0")]
        e_nombres = [self.procesar_nombre_champ(str(j.get("championId", 0)), "0") for j in enemigos if self.procesar_nombre_champ(str(j.get("championId", 0)), "0")]
        if len(a_nombres) >= 3 and len(e_nombres) >= 3:
            try:
                ad_a, ap_a, tk_a = analizar_composicion(a_nombres)
                ad_e, ap_e, tk_e = analizar_composicion(e_nombres)
                self.lbl_partida_comp.setText(
                    f"âš”ï¸ Aliados: AD {ad_a}% / AP {ap_a}% ({tk_a} front)  |  "
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
                positives.append(f"âš”ï¸ {k} kills â€” excelente presencia ofensiva")
            if d <= 2 and game_time >= 600:
                positives.append(f"ðŸ›¡ï¸ Solo {d} muertes â€” muy buena supervivencia")
            if a >= 10:
                positives.append(f"ðŸ¤ {a} asistencias â€” gran impacto en equipo")
            if cs_min >= 7.5 and game_time >= 600:
                positives.append(f"ðŸŒ¾ {cs_min:.1f} CS/min â€” farmeo solido")
            if k > avg_k * 1.3:
                positives.append(f"ðŸ“ˆ +{k - int(avg_k)} kills sobre tu media ({avg_k:.0f})")
            if d < avg_d * 0.7 and d <= avg_d:
                positives.append(f"ðŸ“‰ -{int(avg_d) - d} muertes bajo tu media ({avg_d:.0f})")
            if k + a >= 20:
                positives.append(f"ðŸŽ¯ {k + a} de participacion â€” muy activo en el mapa")
            if stats.get("vision_score", 0) >= 30:
                positives.append(f"ðŸ‘ï¸ {stats['vision_score']} de vision â€” buen control de mapa")
            if stats.get("penta", 0) >= 1:
                positives.append("ðŸ”¥ PENTAKILL â€” partida legendaria")
            if stats.get("first_blood", False):
                positives.append("âš¡ First Blood â€” ventaja temprana")

            # Puntos debiles
            if d >= 7:
                negatives.append(f"âš ï¸ {d} muertes â€” demasiadas, revisa tu posicionamiento")
            if d > avg_d * 1.5:
                negatives.append(f"ðŸ“Š +{d - int(avg_d)} muertes sobre tu media â€” partida atipica o tilt")
            if cs_min < 5.0 and game_time >= 600:
                negatives.append(f"ðŸ“‰ CS/min bajo ({cs_min:.1f}) â€” practica el farmeo")
            if k + a < d * 1.5 and game_time >= 600:
                negatives.append(f"ðŸ“‰ Baja participacion â€” K+A ({k + a}) vs D ({d})")
            if stats.get("vision_score", 0) < 5 and game_time >= 900:
                negatives.append(f"ðŸ”¦ Poca vision ({stats.get('vision_score', 0)}) â€” compra wards de control")
            if d >= 3 and k == 0 and game_time >= 600:
                negatives.append("ðŸ˜“ Sin kills â€” enfocate en jugadas seguras")
            if cs_min < 3.5 and game_time >= 900:
                negatives.append("ðŸš« Farmeo muy bajo â€” prioriza las oleadas de minions")

            # Consejos de mejora
            if negatives:
                tips.append("Consejo: " + negatives[0].split("â€”")[-1].strip() if "â€”" in negatives[0] else negatives[0])
            if d >= 5:
                tips.append("Juega mas conservador si vas detras y espera los powerspikes de tu campeon")
            if k + a < 5 and game_time >= 900:
                tips.append("Intenta rotar mas para ayudar a tu equipo en objetivos (dragon, heraldo)")
            if cs_min < 6.0:
                tips.append("Dedica 10 min en practica de herramientas a farmear bajo torre")
            if result == "Derrota" and k >= 8:
                tips.append("Aunque perdiste, tu desempeno ofensivo fue bueno. Revisa decisiones macro")
            if result == "Victoria" and d >= 7:
                tips.append("Buen resultado pero cuidado con las muertes â€” en partidas mas dificiles te castigaran")

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
        """Muestra el diÃ¡logo de post-game en el hilo principal."""
        try:
            dlg = PostGameDialog(stats, parent=self)
            dlg.coaching_requested.connect(self._ir_a_coaching)
            dlg.show()
        except Exception as e:
            print(f"[PostGame] Error mostrando diÃ¡logo: {e}")

    def _on_season_partial(self, batch: list):
        """Recibe un lote de partidas de Riot API (hilo principal via signal).
        Las aÃ±ade a all_games_season y refresca incrementalmente la tabla de season."""
        try:
            if not hasattr(self, 'all_games_season'):
                self.all_games_season = []
            # DEDUP contra lo que ya tenemos
            seen = set()
            for g in self.all_games_season:
                gid = str(g.get("gameId", ""))
                if not gid:
                    gid = f"{g.get('gameCreationDate','')}_{g.get('gameDuration',0)}"
                seen.add(gid)
            nuevos = 0
            for g in batch:
                gid = str(g.get("gameId", ""))
                if not gid:
                    gid = f"{g.get('gameCreationDate','')}_{g.get('gameDuration',0)}"
                if gid and gid not in seen:
                    seen.add(gid)
                    self.all_games_season.append(g)
                    nuevos += 1
            if nuevos > 0:
                self._cargar_stats_season()
        except Exception as e:
            print(f"[SeasonPartial] Error: {e}")

    def _ir_a_coaching(self):
        """Navega a la pestaÃ±a de Coaching."""
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
                    cur.execute("SELECT ROUND(SUM(win)*100.0/COUNT(*),1) FROM participantes WHERE champion=%s", (cname,))
                    r = cur.fetchone()
                    if r and r[0]:
                        wr = f"{float(r[0])}%"
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
                    cur.execute("SELECT ROUND(SUM(win)*100.0/COUNT(*),1) FROM participantes WHERE champion=%s", (cname,))
                    r = cur.fetchone()
                    if r and r[0]:
                        wr = f"{float(r[0])}%"
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
            cur.execute("SELECT COUNT(*), ROUND(AVG(kills),1), ROUND(AVG(deaths),1) FROM participantes WHERE champion=%s", (champion,))
            r = cur.fetchone()
            if r:
                total = int(r[0] or 0)
                avg_k = float(r[1] or 0)
                avg_d = float(r[2] or 0)
            else:
                total, avg_k, avg_d = 0, 0.0, 0.0

            comentarios = []
            color = "{TEXT_MUTED}"  # default gray

            if total < 5:
                comentarios.append("1a vez?")
                color = "{TEXT_SUBTLE}"
            else:
                if avg_d and avg_d >= 6:
                    comentarios.append("Muchas muertes")
                if avg_k and avg_k >= 7:
                    comentarios.append("Buenas kills")

            # KDA actual
            if k + d + a > 0:
                if kda_val >= 5:
                    comentarios.append("ðŸ”¥ En fuego")
                    color = GREEN_WR
                elif kda_val >= 3:
                    comentarios.append("âœ… SÃ³lido")
                    color = GREEN_WR
                elif kda_val < 1.0:
                    comentarios.append("ðŸ’€ Feedeando")
                    color = RED_WR
                elif d >= 5:
                    comentarios.append("âš ï¸ FrÃ¡gil")
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
                            comentarios.append("ðŸ”¥ Racha buena")
                            color = GREEN_WR
                        elif w_count <= 1:
                            comentarios.append("â„ï¸ Racha mala")
                            color = RED_WR if total > 10 else color
                except:
                    pass

            if not comentarios:
                comentarios.append("â€”")

            return " Â· ".join(comentarios), color
        except:
            return "â€”", "{TEXT_MUTED}"
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
                    border: 1px solid {BG_CARD_HOVER};
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
            lbl_name.setStyleSheet("font-weight: bold; font-size: 12px; color: {TEXT_PRIMARY};")
            card_layout.addWidget(lbl_name)
            card_layout.addStretch()
            layout.addWidget(card)

    def _cargar_stats_season(self):
        """Carga estadisticas de la season. Procesa todas las partidas en memoria,
        guarda la lista completa en self._season_champ_data y renderiza los primeros 15.
        El resto se carga bajo demanda via scroll (lazy loading)."""
        if not hasattr(self, 'all_games_season') or not self.all_games_season:
            if hasattr(self, 'historial_games') and self.historial_games:
                self.all_games_season = list(self.historial_games)
            else:
                return
        try:
            all_games = self.all_games_season
            # DEDUP
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
            # Computar stats por campeon (todos, con CS y duracion)
            champ_stats = {}
            for g in unique_games:
                part = g.get("participants", [{}])[0]
                stats = part.get("stats", {})
                cid = str(part.get("championId", "0"))
                cname = self.procesar_nombre_champ(cid, "0") or "?"
                if cname == "?":
                    continue
                if cname not in champ_stats:
                    champ_stats[cname] = {
                        "wins": 0, "games": 0, "kills": 0, "deaths": 0, "assists": 0,
                        "total_cs": 0, "total_duration": 0,
                    }
                cs = champ_stats[cname]
                cs["games"] += 1
                if stats.get("win", False):
                    cs["wins"] += 1
                cs["kills"] += stats.get("kills", 0)
                cs["deaths"] += stats.get("deaths", 0)
                cs["assists"] += stats.get("assists", 0)
                cs["total_cs"] += stats.get("totalMinionsKilled", 0) + stats.get("neutralMinionsKilled", 0)
                cs["total_duration"] += g.get("gameDuration", 0)

            # Ordenar por partidas descendente y guardar lista completa
            sorted_champs = sorted(champ_stats.items(), key=lambda x: x[1]["games"], reverse=True)
            self._season_champ_data = []
            for cname, cs in sorted_champs:
                self._season_champ_data.append({
                    "name": cname,
                    "games": cs["games"],
                    "wins": cs["wins"],
                    "kills": cs["kills"],
                    "deaths": cs["deaths"],
                    "assists": cs["assists"],
                    "total_cs": cs["total_cs"],
                    "total_duration": cs["total_duration"],
                })
            print(f"[_cargar_stats_season] {len(unique_games)} partidas, {len(self._season_champ_data)} campeones totales")
            # Cargar primeros 15 (o menos si hay pocos)
            self._season_offset = 0
            self._cargando_season = False
            self.tb_season_champs.setRowCount(0)
            self._append_champs_season(count=15)
        except Exception as e:
            print(f"[_cargar_stats_season] Error: {e}")

    def _crear_fila_champ_season(self, champ: dict, max_games: int):
        """Construye los 4 widgets de celda para una fila de campeon en la tabla de season."""
        cname = champ["name"]
        games = champ["games"]
        wins = champ["wins"]
        kills = champ["kills"]
        deaths = champ["deaths"]
        assists = champ["assists"]
        total_cs = champ["total_cs"]
        total_dur = max(champ["total_duration"], 1)
        wr_val = round(wins * 100 / games, 1) if games > 0 else 0
        kda_val = round((kills + assists) / max(1, deaths), 2)
        cs_min = round(total_cs / (total_dur / 60), 1)
        bar_pct = int((games / max(1, max_games)) * 100)
        wr_color = GREEN_WR if wr_val >= 50 else RED_WR

        # â”€â”€ Col 0: Icono + Nombre + CS â”€â”€
        w0 = QWidget()
        w0.setStyleSheet("background: transparent;")
        l0 = QHBoxLayout(w0)
        l0.setContentsMargins(4, 3, 4, 3)
        l0.setSpacing(6)
        icon_lbl = QLabel()
        icon_path = self.descargar_imagen(cname, "champ")
        if icon_path:
            icon_lbl.setPixmap(QPixmap(icon_path).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_lbl.setFixedSize(28, 28)
        l0.addWidget(icon_lbl)
        txt_vbox = QVBoxLayout()
        txt_vbox.setContentsMargins(0, 0, 0, 0)
        txt_vbox.setSpacing(0)
        lbl_name = QLabel(self._nombre_con_dificultad(cname))
        lbl_name.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 11px; font-weight: bold; background: transparent;")
        txt_vbox.addWidget(lbl_name)
        lbl_cs = QLabel(f"CS {total_cs} ({cs_min}/min)")
        lbl_cs.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 8px; background: transparent;")
        txt_vbox.addWidget(lbl_cs)
        l0.addLayout(txt_vbox, 1)

        # â”€â”€ Col 1: Partidas + mini barra â”€â”€
        w1 = QWidget()
        w1.setStyleSheet("background: transparent;")
        l1 = QVBoxLayout(w1)
        l1.setContentsMargins(2, 5, 2, 5)
        l1.setSpacing(2)
        lbl_games = QLabel(str(games))
        lbl_games.setAlignment(Qt.AlignCenter)
        lbl_games.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 13px; font-weight: bold; background: transparent;")
        l1.addWidget(lbl_games)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(bar_pct)
        bar.setTextVisible(False)
        bar.setFixedHeight(3)
        bar.setStyleSheet(f"""
            QProgressBar {{ background: #1a2332; border: none; border-radius: 1px; }}
            QProgressBar::chunk {{ background: {ACCENT_TEAL}; border-radius: 1px; }}
        """)
        l1.addWidget(bar)

        # â”€â”€ Col 2: WR % â”€â”€
        w2 = QLabel(f"{wr_val}%")
        w2.setAlignment(Qt.AlignCenter)
        w2.setStyleSheet(f"color: {wr_color}; font-size: 14px; font-weight: bold; background: transparent; padding: 4px;")

        # â”€â”€ Col 3: KDA ratio + K/D/A â”€â”€
        w3 = QWidget()
        w3.setStyleSheet("background: transparent;")
        l3 = QVBoxLayout(w3)
        l3.setContentsMargins(2, 3, 2, 3)
        l3.setSpacing(0)
        lbl_kda = QLabel(f"{kda_val}:1")
        lbl_kda.setAlignment(Qt.AlignCenter)
        lbl_kda.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 11px; font-weight: bold; background: transparent;")
        l3.addWidget(lbl_kda)
        kda_detail = QLabel()
        kda_detail.setAlignment(Qt.AlignCenter)
        kda_detail.setTextFormat(Qt.RichText)
        avg_k = round(kills / max(1, games))
        avg_d = round(deaths / max(1, games))
        avg_a = round(assists / max(1, games))
        kda_detail.setText(
            f"<span style='color:{GREEN_WR};font-size:9px;'>{avg_k}</span>"
            f"<span style='color:{TEXT_MUTED};font-size:9px;'>/</span>"
            f"<span style='color:{RED_WR};font-size:9px;'>{avg_d}</span>"
            f"<span style='color:{TEXT_MUTED};font-size:9px;'>/</span>"
            f"<span style='color:{YELLOW_WR};font-size:9px;'>{avg_a}</span>"
        )
        l3.addWidget(kda_detail)

        return w0, w1, w2, w3

    def _append_champs_season(self, count=15):
        """AÃ±ade los siguientes 'count' campeones a la tabla sin limpiar."""
        if not hasattr(self, '_season_champ_data') or not self._season_champ_data:
            return
        data = self._season_champ_data
        offset = self._season_offset
        end = min(offset + count, len(data))
        if offset >= len(data):
            return
        max_games = data[0]["games"] if data else 1
        for i in range(offset, end):
            champ = data[i]
            w0, w1, w2, w3 = self._crear_fila_champ_season(champ, max_games)
            r = self.tb_season_champs.rowCount()
            self.tb_season_champs.insertRow(r)
            self.tb_season_champs.setCellWidget(r, 0, w0)
            self.tb_season_champs.setCellWidget(r, 1, w1)
            self.tb_season_champs.setCellWidget(r, 2, w2)
            self.tb_season_champs.setCellWidget(r, 3, w3)
            self.tb_season_champs.setRowHeight(r, 52)
        self._season_offset = end
        if end >= len(data):
            print(f"[_cargar_stats_season] Todos los {len(data)} campeones cargados")

    def _on_scroll_season(self, value):
        """Detecta scroll cercano al final y carga mas campeones."""
        sb = self.tb_season_champs.verticalScrollBar()
        if sb.maximum() > 0 and value >= int(sb.maximum() * 0.80):
            if not hasattr(self, '_cargando_season'):
                self._cargando_season = False
            if self._cargando_season:
                return
            self._cargando_season = True
            try:
                self._append_champs_season(count=15)
            finally:
                self._cargando_season = False

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
                if puntuacion >= 9.0: estrellas = "â­â­â­â­â­"
                elif puntuacion >= 7.0: estrellas = "â­â­â­â­"
                elif puntuacion >= 5.0: estrellas = "â­â­â­"
                elif puntuacion >= 3.0: estrellas = "â­â­"
                else: estrellas = "â­"
                
                # Color segun puntuacion
                if puntuacion >= 8.0: color_pts = GREEN_WR
                elif puntuacion >= 5.0: color_pts = TEXT_GOLD
                elif puntuacion >= 3.0: color_pts = YELLOW_WR
                else: color_pts = RED_WR
                
                tooltip = (
                    f"{self._nombre_display(champ)}\n"
                    f"â­ Puntuacion: {puntuacion}/10.0\n"
                    f"ðŸ“Š {razon}"
                )
                self.renderizar_icono(champ, "champ", grid_icons, i // 2, i % 2,
                    tooltip, size=35)
                
                # Etiqueta de puntuaciÃ³n debajo del icono
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
            return "â­" * d
        except:
            return "â­â­"

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

        lines.append("ðŸŽ¯ TU COMP: {}  |  ENEMIGO: {}".format(comp_al, comp_en))

        # Win condition
        if comp_al == "Poke/Siege" and comp_en in ("Engage/Wombo","Front-to-Back"):
            lines.append("ðŸ† WIN COND: Pokea antes de la pelea. No dejes que engageen. Asedia torres con rango.")
        elif comp_al == "Engage/Wombo" and comp_en in ("Poke/Siege","Pick/Skirmish"):
            lines.append("ðŸ† WIN COND: Busca el engage 5v5. Ellos colapsan contra all-in coordinado.")
        elif comp_al == "Split Push" and comp_en in ("Engage/Wombo","Front-to-Back"):
            lines.append("ðŸ† WIN COND: Evita 5v5. Presion lateral con el split pusher. Rotaciones rapidas.")
        elif comp_al == "Front-to-Back" and comp_en == "Pick/Skirmish":
            lines.append("ðŸ† WIN COND: Agrupaos y proteged al carry. No os separeis, os cazan.")
        else:
            esc_al = sum(1 for a in aliados if obtener_tag(a).get("scaling") in ("late","hyper"))
            esc_en = sum(1 for e in enemigos if obtener_tag(e).get("scaling") in ("late","hyper"))
            if esc_al > esc_en: lines.append("ðŸ† WIN COND: Escalan mejor. Juega seguro early, ganas a partir de 25 min.")
            elif esc_en > esc_al: lines.append("ðŸ† WIN COND: Acaba rÃ¡pido. Ellos escalan mejor. Ventaja temprana y cierra.")
            elif tanks_al > tanks_en: lines.append("ðŸ† WIN COND: Su frontlane gana. Force objetivos, ellos no pueden contestar.")
            else: lines.append("ðŸ† WIN COND: Vision + picks. Controla la jungla enemiga y caza rotaciones.")

        # Prioridad de objetivos
        lines.append("\nðŸ“‹ PRIORIDAD DE OBJETIVOS:")
        if tanks_al >= 3 or engage_al >= 2: lines.append("   ðŸ‰ Dragones - su frontlane domina el rÃ­o")
        if split_al >= 1: lines.append("   ðŸ¦€ Heraldo > Primeras 2 torres - libera al split pusher")
        if poke_al >= 2: lines.append("   ðŸ° Torres > Dragones - su rango asedia mejor")
        escalado_al = sum(1 for a in aliados if obtener_tag(a).get("scaling") in ("late","hyper"))
        if escalado_al >= 3: lines.append("   ðŸ›¡ï¸ Farm + Escalar > Objetivos tempranos")

        # Itemizacion counter
        lines.append("\nðŸ›’ ITEMIZACION CLAVE:")
        ap_en_val = sum(1 for e in enemigos if obtener_dano(e) in ("AP","HYBRID"))
        ad_en_val = sum(1 for e in enemigos if obtener_dano(e) == "AD")
        cc_en = sum(obtener_nivel_cc(e) for e in enemigos)
        tanks_en_val = sum(1 for e in enemigos if es_tanque(e))
        cur = sum(1 for e in enemigos if e in {"Aatrox","Vladimir","Soraka","Swain","Sylas","Warwick","Briar","Fiora","Darius","Illaoi","DrMundo","Olaf"})
        if ap_en_val >= 3: lines.append("   ðŸ§ª Fuerza Naturaleza / Rostro Espiritual (mucha AP enemiga)")
        if ad_en_val >= 3: lines.append("   ðŸ›¡ï¸ Coraza de Espinas / Randuin (mucho AD)")
        if tanks_en_val >= 3: lines.append("   ðŸ—¡ï¸ Hoja del Rey / Lord Dominik (penetracion vs tanques)")
        if cc_en >= 12: lines.append("   â›“ï¸ Botas de Mercurio / Fajin (CC masivo)")
        if cur >= 2: lines.append("   ðŸ”¥ MorellonomicÃ³n / Ejecutor (curaciones enemigas)")

        # Sinergias
        lines.append("\nâš¡ SINERGIAS CLAVE:")
        if "Yasuo" in aliados:
            kn = [a for a in aliados if obtener_nivel_cc(a) >= 3 and obtener_tag(a).get("sub_class") in ("Vanguard","Catcher")]
            if kn: lines.append("   ðŸŒªï¸ Yasuo + {} = combo R garantizada".format(kn[0]))
        if "Orianna" in aliados:
            eng = [a for a in aliados if obtener_tag(a).get("sub_class") == "Vanguard"]
            if eng: lines.append("   âš½ Orianna + {} = wombo combo R".format(eng[0]))
        if "Kalista" in aliados:
            supp = [a for a in aliados if es_soporte(a)]
            if supp: lines.append("   ðŸ¤ Kalista + {} = engage/doble knockup".format(supp[0]))

        self.lbl_pro.setText("\n".join(lines))

    # ================= META & BUILDS =================
    def armar_tab_counters(self):
        layout = QVBoxLayout(self.tab_counters)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(8)
        ctrl_layout.addWidget(QLabel("LÃ­nea:"))
        
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
        self.tree_counters.setHorizontalHeaderLabels(["CampeÃ³n Aliado", "Winrate %", "Partidas"])
        self.tree_counters.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tree_counters.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_counters.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree_counters.itemSelectionChanged.connect(self.mostrar_build_visual)
        self.tree_counters.verticalHeader().setDefaultSectionSize(40)
        self.tree_counters.setIconSize(QSize(28, 28))
        self.tree_counters.verticalHeader().setVisible(False)
        self.tree_counters.setStyleSheet("""
            QTableWidget { border: 1px solid {BG_CARD_HOVER}; border-radius: 4px; background-color: transparent; }
            QTableWidget::item { padding: 2px 6px; }
            QHeaderView::section { background-color: #152040; border: none; border-bottom: 1px solid #e63946; color: #e63946; font-weight: bold; padding: 6px; }
            QTableWidget::item:selected { background-color: {BG_CARD_HOVER}; }
        """)
        split_layout.addWidget(self.tree_counters, 1)
        
        self.panel_visual, self.l_visual = self.crear_panel("SETUP & BUILD Ã“PTIMAS")
        self.frame_setup_visual = QVBoxLayout()
        self.frame_setup_visual.setAlignment(Qt.AlignTop)
        self.l_visual.addLayout(self.frame_setup_visual)
        split_layout.addWidget(self.panel_visual, 1)
        
        layout.addLayout(split_layout, 1)
        
        self.actualizar_listas_counter(UI_ROLES[0])

    def buscar_counters(self):
        """Lanza la bÃºsqueda en hilo secundario para no congelar la UI."""
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
        
        panel_ia, l_ia = self.crear_panel("CONFIGURACIÃ“N DEL MATCHUP")
        ctrls = QHBoxLayout()
        ctrls.setSpacing(8)
        self.cb_ia_rol = QComboBox()
        self.cb_ia_aliado = QComboBox()
        self.cb_ia_enemigo = QComboBox()
        ctrls.addWidget(QLabel("LÃ­nea:"))
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
        
        # AnÃ¡lisis de la IA
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
                QProgressBar {{ background-color: {BG_DARK}; border: 1px solid #1a2744; border-radius: 4px; }}
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
        
        # â”€â”€â”€ Imagenes y nombres â”€â”€â”€
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
            nivel_icono = "ðŸ”¥"
            nivel_texto = "HARD COUNTER (Ventaja Absoluta)"
        elif prob_final >= 51.5:
            nivel_color = GREEN_WR
            nivel_icono = "âœ…"
            nivel_texto = "VENTAJA LIGERA"
        elif prob_final >= 48.5:
            nivel_color = YELLOW_WR
            nivel_icono = "âš”ï¸"
            nivel_texto = "MATCHUP DE HABILIDAD (50/50)"
        else:
            nivel_color = RED_WR
            nivel_icono = "âš ï¸"
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
                delta_str = '<span style="color:{TEXT_SUBTLE};">(=)</span>'
            return (
                f'<tr>'
                f'<td width="140" style="color:{TEXT_MUTED};font-size:11px;padding:2px 6px;">{label}</td>'
                f'<td width="160"><div style="background:{BG_CARD_HOVER};border-radius:3px;height:14px;width:100%;">'
                f'<div style="background:{GREEN_WR};height:14px;width:{pct_a}%;border-radius:3px 0 0 3px;"></div></div></td>'
                f'<td width="30" style="color:{TEXT_WHITE};font-size:11px;text-align:center;font-weight:700;">{val_a}</td>'
                f'<td width="20" style="text-align:center;">{delta_str}</td>'
                f'<td width="30" style="color:{TEXT_WHITE};font-size:11px;text-align:center;font-weight:700;">{val_e}</td>'
                f'<td width="160"><div style="background:{BG_CARD_HOVER};border-radius:3px;height:14px;width:100%;">'
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
            DaÃ±o: <b style="color:{ACCENT_TEAL};">{aliado} {t_a.get('damage_type','?')}</b>
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
                if "Desventaja" in ins or "DÃ©ficit" in ins or "contra" in ins:
                    color = RED_WR
                elif "Ventaja" in ins or "Dominio" in ins or "mejor" in ins or "dicta" in ins:
                    color = GREEN_WR
                elif "hyper-carry" in ins:
                    color = YELLOW_WR
                else:
                    color = TEXT_MUTED
                html += f'<li style="color:{color};font-size:11px;">{ins}</li>'
        except Exception:
            html += f'<li style="color:{TEXT_MUTED};font-size:11px;">AnÃ¡lisis no disponible para este matchup.</li>'
        
        html += "</ul></div>"
        
        self.lbl_analisis_ia.setText(html)
        self.lbl_analisis_ia.setTextFormat(Qt.RichText)

    def armar_tab_bans(self):
        layout = QVBoxLayout(self.tab_bans)
        layout.setContentsMargins(10, 10, 10, 10)
        
        ctrls = QHBoxLayout()
        ctrls.addWidget(QLabel("Selecciona la LÃ­nea a Proteger:"))
        
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
        self.treebans.setHorizontalHeaderLabels(["CampeÃ³n", "Banrate Sugerido %", "Partidas Analizadas"])
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
                self.lbl_logros_text.setStyleSheet("color: {TEXT_SUBTLE}; font-size: 11px;")
                self.lbl_logros_text.setWordWrap(True)
                self.fr_logros.addWidget(self.lbl_logros_text)
            else:
                for lg in conseguidos:
                    lbl = QLabel(f"{lg['emoji']} {lg['nombre']}")
                    lbl.setStyleSheet("color: {TEXT_LIGHT}; font-size: 11px; background: #1a2744; border-radius: 4px; padding: 2px 6px;")
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
        from src.db_manager import inicializar_db, ConexionDBError
        try:
            inicializar_db()
        except ConexionDBError:
            pass

    window = LoLRecommenderApp()
    window.show()
    sys.exit(app.exec())

