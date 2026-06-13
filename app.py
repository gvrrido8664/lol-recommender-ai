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
from ui.theme_qss import hoja_estilos_global
from ui.tabs.tab_perfil import PerfilTabMixin
from ui.tabs.tab_coaching import CoachingTabMixin
from ui.tabs.tab_vivo import VivoTabMixin
from ui.tabs.tab_partida import PartidaTabMixin
from ui.tabs.tab_counters import CountersTabMixin
from ui.tabs.tab_ia import IATabMixin
from ui.tabs.tab_bans import BansTabMixin


class LoLRecommenderApp(PerfilTabMixin, CoachingTabMixin, VivoTabMixin, PartidaTabMixin,
                        CountersTabMixin, IATabMixin, BansTabMixin, QMainWindow):
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
        
        # Cache de imágenes descargadas para evitar HTTP repetidos
        self._cache_imagenes = {}
        self._cache_imagenes_lock = threading.Lock()

        # Post-game: caché de stats en vivo y control de fase
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
        self.setStyleSheet(hoja_estilos_global())

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
            _PRIO_COLOR   = {1: "{RED_DANGER}", 2: "{YELLOW_WARNING}", 3: "{TEXT_SUBTLE}"}
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
            lbl_sit_t.setStyleSheet(f"color: {YELLOW_WARNING}; font-weight: bold; font-size: 11px;")
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

                prio_col = _PRIO_COLOR.get(sit["prioridad"], "{TEXT_SUBTLE}")
                cat_txt  = _CAT_LABEL.get(sit["categoria"], sit["categoria"])
                lbl_cat = QLabel(f"<span style='color:{prio_col};font-weight:bold;font-size:9px;'>"
                                 f"{_PRIO_LABEL.get(sit['prioridad'],'')}</span>"
                                 f"<span style='color:{TEXT_MUTED};font-size:9px;'> · {cat_txt}</span>")
                lbl_cat.setTextFormat(Qt.RichText)
                txt_l.addWidget(lbl_cat)

                lbl_name = QLabel(f"{sit['nombre']}  <span style='color:{TEXT_SUBTLE};font-size:9px;'>{sit['coste']}g</span>")
                lbl_name.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 10px; font-weight: bold;")
                lbl_name.setTextFormat(Qt.RichText)
                txt_l.addWidget(lbl_name)

                razon = sit["razon"]
                if len(razon) > 75:
                    razon = razon[:72] + "…"
                lbl_razon = QLabel(razon)
                lbl_razon.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px;")
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

