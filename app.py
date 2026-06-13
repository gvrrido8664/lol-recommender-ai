"""NEXUS — entrada de la aplicacion (ventana principal).

La superficie compartida de imports y datos (Qt, src.*, diseno, helpers,
diccionarios de datos) vive en ui/contexto.py. Las pestanias se definen como
mixins en ui/tabs/ y se combinan en LoLRecommenderApp.
"""

from src.logger import init_logging
init_logging()

from ui.contexto import *

log = get_logger(__name__)

# Safe stdout/stderr para modo GUI (--windowed, sin consola) y encoding cp1252 en Windows
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')


# Pestanias como mixins (extraidas de app.py) -> ui/tabs/
from ui.tabs.tab_partida import PartidaTabMixin
from ui.tabs.tab_counters import CountersTabMixin
from ui.tabs.tab_ia import IATabMixin
from ui.tabs.tab_bans import BansTabMixin


class LoLRecommenderApp(PartidaTabMixin, CountersTabMixin, IATabMixin, BansTabMixin,
                        QMainWindow):
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

