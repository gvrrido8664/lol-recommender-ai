import json
import os
import requests
import threading
from io import BytesIO
from PIL import Image
import numpy as np
import joblib
import sys

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QGridLayout, QLabel, QPushButton, 
                               QComboBox, QTabWidget, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QFrame, QMessageBox, QAbstractItemView, QProgressBar)
from PySide6.QtGui import QPixmap, QFont, QColor, QIcon
from PySide6.QtCore import Qt, QTimer, QSize, Signal

from src.db_manager import DATA_DIR
from src.riot_api import cargar_campeones, cargar_objetos, cargar_runas, cargar_mapeo_ids, cargar_hechizos, obtener_version_actual
from src.recomendador import (obtener_counters, obtener_top_items, obtener_campeones_por_rol, 
                              obtener_top_runas, obtener_top_hechizos, obtenermejoresbaneos, obtener_peores_matchups, 
                              recomendar_picks_vivo, calcular_winrate_5v5, analizar_composicion)
from src.lcu_api import LCUConnector

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
ITEMS_DIR = os.path.join(ASSETS_DIR, "items")
RUNAS_DIR = os.path.join(ASSETS_DIR, "runas")
CHAMPS_DIR = os.path.join(ASSETS_DIR, "champs")
SPELLS_DIR = os.path.join(ASSETS_DIR, "spells")
PROFILE_ICONS_DIR = os.path.join(ASSETS_DIR, "profile_icons")

for d in [ITEMS_DIR, RUNAS_DIR, CHAMPS_DIR, SPELLS_DIR, PROFILE_ICONS_DIR]:
    os.makedirs(d, exist_ok=True)

modelo_1v1 = joblib.load("data/modelo_1v1.pkl") if os.path.exists("data/modelo_1v1.pkl") else {}
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

class LoLRecommenderApp(QMainWindow):
    lcu_task_finished = Signal(object, object, str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoL Esports Analytics Pro - V6.0 (PySide6)")
        self.resize(1500, 950)
        self.aplicar_estilos()

        self.champs_dict = cargar_campeones()
        self.nombres_campeones_global = sorted(list(set([data["nombre"] for data in self.champs_dict.values()])))
        self.nombre_a_id_img = {v.get("nombre"): k for k, v in self.champs_dict.items()}
        self.nombre_a_id_img["Wukong"] = "MonkeyKing"
        self.nombre_a_id_img["MaestroYi"] = "MasterYi"
        self.nombre_a_id_img["KhaZix"] = "Khazix"

        self.version_juego = obtener_version_actual()
        self.builds_actuales = {}
        self.lcu = LCUConnector()
        self.radar_activo = False
        self.lcu_task_finished.connect(self._on_lcu_task_finished)
        
        self.last_aliados = []
        self.last_enemigos = []
        self.last_my_champ = None
        self.last_my_role = None
        self.perfil_cargado = False

        self.crear_interfaz()
        
        self.timer_lcu = QTimer(self)
        self.timer_lcu.timeout.connect(self.auto_detectar_lcu)
        self.timer_lcu.start(1500)

    def aplicar_estilos(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {BG_DARK}; }}
            QWidget {{ color: {TEXT_WHITE}; font-family: Helvetica; }}
            QFrame#Panel {{ background-color: {BG_PANEL}; border: 1px solid {BORDER_GOLD}; border-radius: 8px; }}
            QFrame#CardAlly {{ background-color: {ALLY_BG}; border: 1px solid {BORDER_GOLD}; border-radius: 5px; }}
            QFrame#CardEnemy {{ background-color: {ENEMY_BG}; border: 1px solid {BORDER_GOLD}; border-radius: 5px; }}
            QFrame#BuildCard {{ background-color: #0d1b38; border: 1px solid #1a2b4c; border-radius: 6px; }}
            QLabel {{ border: none; background: transparent; }}
            QPushButton {{ background-color: #1a2b4c; color: {TEXT_WHITE}; border: 1px solid {BORDER_GOLD}; border-radius: 4px; padding: 6px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {ACCENT_BLUE}; color: {BG_DARK}; }}
            
            /* TABS ESTILIZADOS PROFESIONALES */
            QTabWidget::pane {{ border: 1px solid {BORDER_GOLD}; background-color: {BG_PANEL}; border-radius: 8px; border-top-left-radius: 0px; }}
            QTabBar::tab {{ background: #1a2b4c; color: {TEXT_WHITE}; padding: 12px 30px; border: 1px solid {BORDER_GOLD}; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; font-weight: bold; font-size: 13px; }}
            QTabBar::tab:selected {{ background: {BG_PANEL}; color: {ACCENT_BLUE}; border-bottom: 2px solid {BG_PANEL}; }}
            
            QComboBox {{ background-color: #1a2b4c; color: {TEXT_WHITE}; border: 1px solid {BORDER_GOLD}; padding: 5px; border-radius: 4px; }}
            QTableWidget {{ background-color: {BG_PANEL}; alternate-background-color: #0d1b38; color: {TEXT_WHITE}; gridline-color: transparent; border: 1px solid {BORDER_GOLD}; border-radius: 8px; font-size: 14px; outline: 0; }}
            QTableWidget::item {{ padding: 5px; border-bottom: 1px solid #1a2b4c; }}
            QTableWidget::item:selected {{ background-color: {BORDER_GOLD}; color: {BG_DARK}; }}
            QHeaderView::section {{ background-color: #1a2b4c; color: {BORDER_GOLD}; font-weight: bold; padding: 8px; border: none; border-bottom: 2px solid {BORDER_GOLD}; }}
            QProgressBar {{ border: 1px solid {BORDER_GOLD}; border-radius: 5px; text-align: center; background-color: {RED_WR}; color: white; font-weight: bold; }}
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

        header_lbl = QLabel("LOL ESPORTS ANALYTICS")
        header_lbl.setStyleSheet(f"color: {BORDER_GOLD}; font-family: Impact; font-size: 32px;")
        header_lbl.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header_lbl)

        self.tabview = QTabWidget()
        main_layout.addWidget(self.tabview)

        self.tab_perfil = QWidget()
        self.tab_vivo = QWidget()
        self.tab_counters = QWidget()
        self.tab_ia = QWidget()
        self.tab_bans = QWidget()

        self.tabview.addTab(self.tab_perfil, "👤 MI PERFIL")
        self.tabview.addTab(self.tab_vivo, "📡 RADAR EN VIVO")
        self.tabview.addTab(self.tab_counters, "📊 META & BUILDS")
        self.tabview.addTab(self.tab_ia, "🤖 SIMULADOR 1v1")
        self.tabview.addTab(self.tab_bans, "🚫 TIER LIST DE BANS")

        self.armar_tab_perfil()
        self.armar_tab_vivo()
        self.armar_tab_counters()
        self.armar_tab_ia()
        self.armar_tab_bans()
        
        self.tabview.setCurrentIndex(1) 

    def descargar_imagen(self, id_elemento, tipo):
        carpetas = {"runa": RUNAS_DIR, "champ": CHAMPS_DIR, "item": ITEMS_DIR, "spell": SPELLS_DIR, "profile": PROFILE_ICONS_DIR}
        ruta_local = os.path.join(carpetas.get(tipo), f"{id_elemento}.png")
        if os.path.exists(ruta_local): return ruta_local
        try:
            if tipo == "runa": url = f"https://ddragon.leagueoflegends.com/cdn/img/{RUNAS_DICT.get(str(id_elemento), {}).get('icono', '')}"
            elif tipo == "spell": url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/spell/{SPELLS_DICT.get(str(id_elemento), {}).get('icono', '')}"
            elif tipo == "champ": url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/champion/{self.nombre_a_id_img.get(id_elemento, id_elemento)}.png"
            elif tipo == "profile": url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/profileicon/{id_elemento}.png"
            else: url = f"https://ddragon.leagueoflegends.com/cdn/{self.version_juego}/img/item/{id_elemento}.png"
                
            resp = requests.get(url)
            resp.raise_for_status()
            with open(ruta_local, "wb") as f: f.write(resp.content)
            return ruta_local
        except: return None

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
    def renderizar_setup_completo(self, campeon, ids_runas, ids_spells, ids_start, ids_core, parent_layout):
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

        # ESPACIADOR QUE EMPUJA EL BOTÓN HACIA ABAJO
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
        
        # ESPACIADOR QUE EMPUJA EL BOTÓN HACIA ABAJO
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

        # ESPACIADOR QUE EMPUJA EL BOTÓN HACIA ABAJO
        l_items.addStretch()

        btn_items = QPushButton("Crear Item Set")
        btn_items.clicked.connect(lambda: self.accion_importar_items(campeon, ids_start, ids_core, btn_items))
        l_items.addWidget(btn_items, alignment=Qt.AlignBottom)
        wrap_layout.addWidget(card_items)

        parent_layout.addWidget(main_wrap)

    # ================= PESTAÑA MI PERFIL DASHBOARD =================
    def armar_tab_perfil(self):
        layout = QVBoxLayout(self.tab_perfil)
        
        self.pnl_perfil = QWidget()
        l_pnl = QHBoxLayout(self.pnl_perfil)
        l_pnl.setAlignment(Qt.AlignTop)
        
        # Columna Izquierda: Identidad y Maestría
        self.col_id = QVBoxLayout()
        self.col_id.setAlignment(Qt.AlignTop)
        
        self.lbl_prof_icon = QLabel()
        self.col_id.addWidget(self.lbl_prof_icon, alignment=Qt.AlignCenter)
        
        self.lbl_sum_name = QLabel("Esperando al Cliente...")
        self.lbl_sum_name.setStyleSheet(f"color: {BORDER_GOLD}; font-size: 24px; font-weight: bold;")
        self.col_id.addWidget(self.lbl_sum_name, alignment=Qt.AlignCenter)
        
        self.lbl_sum_lvl = QLabel("Nivel: --")
        self.lbl_sum_lvl.setStyleSheet("color: gray; font-size: 16px;")
        self.col_id.addWidget(self.lbl_sum_lvl, alignment=Qt.AlignCenter)

        self.lbl_rank_solo = QLabel("SoloQ: --")
        self.lbl_rank_solo.setStyleSheet(f"color: {ACCENT_BLUE}; font-weight: bold; font-size: 14px;")
        self.col_id.addWidget(self.lbl_rank_solo, alignment=Qt.AlignCenter)

        self.lbl_rank_flex = QLabel("Flex: --")
        self.lbl_rank_flex.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 12px;")
        self.col_id.addWidget(self.lbl_rank_flex, alignment=Qt.AlignCenter)
        
        # Panel de Campeones Más Jugados
        self.pnl_mastery, self.l_mastery = self.crear_panel("Mejores Campeones")
        self.fr_mastery = QHBoxLayout()
        self.l_mastery.addLayout(self.fr_mastery)
        self.col_id.addWidget(self.pnl_mastery)

        # Resumen KDA Historial
        self.pnl_kda, self.l_kda = self.crear_panel("Resumen Reciente (20 Partidas)")
        self.lbl_resumen_kda = QLabel("--")
        self.lbl_resumen_kda.setStyleSheet("font-size: 14px; padding: 10px;")
        self.l_kda.addWidget(self.lbl_resumen_kda)
        self.col_id.addWidget(self.pnl_kda)

        l_pnl.addLayout(self.col_id, 1)
        
        # Columna Derecha: Historial
        self.col_hist = QVBoxLayout()
        lbl_h = QLabel("HISTORIAL RECIENTE")
        lbl_h.setStyleSheet(f"color: {ACCENT_BLUE}; font-weight: bold; font-size: 14px;")
        self.col_hist.addWidget(lbl_h)
        
        self.tb_historial = QTableWidget()
        self.tb_historial.setColumnCount(4)
        self.tb_historial.setHorizontalHeaderLabels(["Campeón", "Resultado", "K/D/A", "Modo"])
        self.tb_historial.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tb_historial.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb_historial.setSelectionMode(QAbstractItemView.NoSelection)
        self.tb_historial.verticalHeader().setDefaultSectionSize(40)
        self.tb_historial.setIconSize(QSize(30, 30))
        self.tb_historial.verticalHeader().setVisible(False)
        self.col_hist.addWidget(self.tb_historial)
        
        l_pnl.addLayout(self.col_hist, 2)
        layout.addWidget(self.pnl_perfil)

    def cargar_datos_perfil(self):
        if self.perfil_cargado: return
        perfil = self.lcu.obtener_perfil()
        if not perfil: return
        
        self.perfil_cargado = True
        display_name = perfil.get("displayName") or perfil.get("gameName") or perfil.get("summonerName") or perfil.get("name") or "Invocador"
        tagline = perfil.get("tagLine")
        if tagline and tagline not in display_name:
            display_name = f"{display_name}#{tagline}"
        self.lbl_sum_name.setText(display_name)
        self.lbl_sum_lvl.setText(f"Nivel: {perfil.get('summonerLevel', '--')}")
        
        icon_id = perfil.get("profileIconId")
        ruta_icon = self.descargar_imagen(icon_id, "profile")
        if ruta_icon:
            self.lbl_prof_icon.setPixmap(QPixmap(ruta_icon).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # Cargar Liga (Fix)
        ligas = self.lcu.obtener_ligas()
        queues = []
        if isinstance(ligas, dict):
            if "queues" in ligas:
                queues = ligas["queues"]
            elif "queueMap" in ligas and isinstance(ligas["queueMap"], dict):
                queues = [
                    {**v, "queueType": k}
                    for k, v in ligas["queueMap"].items()
                    if isinstance(v, dict)
                ]
        elif isinstance(ligas, list):
            queues = ligas

        for queue in queues:
            tier = queue.get("tier") or queue.get("rank") or queue.get("division") or ""
            div = queue.get("division") or queue.get("rankDivision") or ""
            lp = queue.get("leaguePoints") or queue.get("lp") or 0
            queue_type = str(queue.get("queueType") or queue.get("queueId") or queue.get("rankQueueType") or queue.get("queue") or "").upper()
            
            if tier and tier not in ["NONE", "UNRANKED", ""]:
                text = f"{tier} {div} ({lp} PL)"
            else:
                text = "Unranked"

            if "SOLO" in queue_type and "FLEX" not in queue_type:
                self.lbl_rank_solo.setText(f"SoloQ: {text}")
            elif "FLEX" in queue_type:
                self.lbl_rank_flex.setText(f"Flex: {text}")

        # Cargar Maestrias (Fix LCU Endpoint Local Player)
        maestrias = self.lcu.obtener_maestrias()
        clear_layout(self.fr_mastery)
        if maestrias:
            for m in maestrias[:3]: # Solo top 3
                cid = str(m.get("championId"))
                c_name = self.procesar_nombre_champ(cid, 0)
                lvl = m.get("championLevel")
                puntos = f"{m.get('championPoints', 0):,}"
                
                card_m = QWidget()
                card_m_ly = QVBoxLayout(card_m)
                card_m_ly.setAlignment(Qt.AlignCenter)
                self.renderizar_icono(c_name, "champ", card_m_ly, size=40)
                lbl = QLabel(f"Lvl {lvl}\n{puntos}")
                lbl.setStyleSheet("font-size: 10px; color: gray;")
                lbl.setAlignment(Qt.AlignCenter)
                card_m_ly.addWidget(lbl)
                self.fr_mastery.addWidget(card_m)

        # Cargar Historial (Fix "CLASSIC")
        historial = self.lcu.obtener_historial(perfil.get("puuid"))
        if not historial: return
        
        games = historial.get("games", {}).get("games", [])
        self.tb_historial.setRowCount(0)
        
        total_k = 0; total_d = 0; total_a = 0; victorias = 0; total_games = 0
        
        for g in games:
            part_info = g.get("participants", [{}])[0]
            stats = part_info.get("stats", {})
            champ_id = str(part_info.get("championId", "0"))
            champ_name = self.procesar_nombre_champ(champ_id, "0") or "Desconocido"
            
            win = stats.get("win", False)
            k = stats.get("kills", 0); d = stats.get("deaths", 0); a = stats.get("assists", 0)
            
            total_k += k; total_d += d; total_a += a; total_games += 1
            if win: victorias += 1
            
            row = self.tb_historial.rowCount()
            self.tb_historial.insertRow(row)
            
            item_c = QTableWidgetItem(f"  {champ_name}")
            icon_p = self.descargar_imagen(champ_name, "champ")
            if icon_p: item_c.setIcon(QIcon(icon_p))
            
            item_w = QTableWidgetItem("VICTORIA" if win else "DERROTA")
            item_w.setForeground(QColor(GREEN_WR if win else RED_WR))
            
            # Cambiar CLASSIC por Ranked/Draft
            modo_juego = g.get("gameMode", "Draft")
            if modo_juego == "CLASSIC": modo_juego = "Ranked/Draft"
            
            self.tb_historial.setItem(row, 0, item_c)
            self.tb_historial.setItem(row, 1, item_w)
            self.tb_historial.setItem(row, 2, QTableWidgetItem(f"{k} / {d} / {a}"))
            self.tb_historial.setItem(row, 3, QTableWidgetItem(modo_juego))

        if total_games > 0:
            kda_ratio = round((total_k + total_a) / max(1, total_d), 2)
            wr = round((victorias / total_games) * 100)
            color_wr = GREEN_WR if wr >= 50 else RED_WR
            resumen_html = f"""
            <span style='color: white;'>Winrate Reciente:</span> <span style='color: {color_wr}; font-weight: bold;'>{wr}%</span><br>
            <span style='color: white;'>Promedio KDA:</span> <span style='color: {BORDER_GOLD}; font-weight: bold;'>{round(total_k/total_games,1)} / {round(total_d/total_games,1)} / {round(total_a/total_games,1)}</span><br>
            <span style='color: white;'>Ratio KDA:</span> <span style='color: {ACCENT_BLUE}; font-weight: bold;'>{kda_ratio}</span>
            """
            self.lbl_resumen_kda.setText(resumen_html)

    # ================= RADAR EN VIVO =================
    def armar_tab_vivo(self):
        layout = QVBoxLayout(self.tab_vivo)
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
        
        self.panel_bans_vivo, self.l_bans_vivo = self.crear_panel("Bans Sugeridos (Tu Línea)")
        self.fr_bans_icons_vivo = QHBoxLayout()
        self.l_bans_vivo.addLayout(self.fr_bans_icons_vivo)
        l_enemy.addStretch() 
        l_enemy.addWidget(self.panel_bans_vivo)
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
        l_center.addWidget(self.panel_sugerencias)
        
        self.panel_runas_vivo, self.l_runas_vivo = self.crear_panel("Setup Recomendado Integral")
        self.fr_runas_icons_vivo = QVBoxLayout()
        self.fr_runas_icons_vivo.setAlignment(Qt.AlignTop)
        self.l_runas_vivo.addLayout(self.fr_runas_icons_vivo)
        l_center.addWidget(self.panel_runas_vivo, 1)
        self.inicializar_panel_setup(self.fr_runas_icons_vivo)
        draft_layout.addWidget(col_center, 2)

        self.col_ally, l_ally = self.crear_panel("Aliados")
        self.lbl_ally_stats = QLabel("AD: --% | AP: --% | Tanks: 0")
        self.lbl_ally_stats.setStyleSheet(f"color: {ACCENT_BLUE}; font-weight: bold;")
        l_ally.addWidget(self.lbl_ally_stats)
        self.fr_aliados_picks = QVBoxLayout()
        l_ally.addLayout(self.fr_aliados_picks)
        l_ally.addStretch() 
        draft_layout.addWidget(self.col_ally, 1)
        
        layout.addLayout(draft_layout)

    def auto_detectar_lcu(self):
        if not self.radar_activo:
            if self.lcu.conectar():
                self.radar_activo = True
                self.lbl_estado_lcu.setText("✓ ENLAZADO AL CLIENTE DE LOL")
                self.lbl_estado_lcu.setStyleSheet(f"color: {GREEN_WR}; font-weight: bold; font-size: 14px;")
                self.cargar_datos_perfil() 
            else:
                self.lbl_estado_lcu.setText("Buscando Cliente de LoL... (Abre el juego)")
                self.lbl_estado_lcu.setStyleSheet(f"color: {YELLOW_WR}; font-weight: bold; font-size: 14px;")
        else:
            self.actualizar_radar_loop()

    def procesar_nombre_champ(self, cid, intent):
        final_id = str(cid) if str(cid) != "0" else str(intent)
        if final_id != "0": return "Wukong" if MAPEO_IDS_CAMPEONES.get(final_id) == "MonkeyKing" else MAPEO_IDS_CAMPEONES.get(final_id, "Desconocido")
        return None

    def actualizar_radar_loop(self):
        if not self.radar_activo: return
        try:
            draft = self.lcu.obtener_sesion_draft()
            if draft:
                rol_api = self.lcu.obtener_mi_rol(draft)
                rol_ui = API_TO_ROL.get(rol_api, "MID")
                self.lbl_rol_vivo.setText(f"LÍNEA ASIGNADA: {rol_ui}")

                picks_al, picks_en = [], []
                mi_campeon = None
                mi_celda = draft.get("localPlayerCellId")

                for j in draft.get("myTeam", []):
                    champ = self.procesar_nombre_champ(j.get("championId", 0), j.get("championPickIntent", 0))
                    if champ: picks_al.append(champ)
                    if j.get("cellId") == mi_celda: mi_campeon = champ
                    
                for j in draft.get("theirTeam", []):
                    champ = self.procesar_nombre_champ(j.get("championId", 0), j.get("championPickIntent", 0))
                    if champ: picks_en.append(champ)
                    
                if picks_al != self.last_aliados or picks_en != self.last_enemigos:
                    self.last_aliados, self.last_enemigos = picks_al.copy(), picks_en.copy()
                    
                    self.mostrar_equipo_vivo(self.fr_aliados_picks, picks_al, is_ally=True)
                    self.mostrar_equipo_vivo(self.fr_enemigos_picks, picks_en, is_ally=False)
                    
                    ad_al, ap_al, tanks_al, _ = analizar_composicion(picks_al)
                    self.lbl_ally_stats.setText(f"Daño AD: {ad_al}% | Daño AP: {ap_al}% | Frontlane: {tanks_al}")
                    ad_en, ap_en, tanks_en, _ = analizar_composicion(picks_en)
                    self.lbl_enemy_stats.setText(f"Daño AD: {ad_en}% | Daño AP: {ap_en}% | Frontlane: {tanks_en}")
                    
                    self.mostrar_picks_vivo(rol_api, picks_al, picks_en)

                    if len(picks_al) == 5 and len(picks_en) == 5:
                        wr = calcular_winrate_5v5(picks_al, picks_en)
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
                        self.panel_bans_vivo.label_title.setText(f"BANS SUGERIDOS (VS {mi_campeon.upper()})")
                        bans_sugeridos = obtener_peores_matchups(mi_campeon, rol_api, min_partidas=20)
                    else: 
                        self.panel_bans_vivo.label_title.setText(f"BANS SUGERIDOS ({rol_ui})")
                        bans_sugeridos = obtenermejoresbaneos(rol_api, min_partidas=20)

                    bans_filtrados = [b for b, wr, p in bans_sugeridos if b not in self.last_aliados and b not in self.last_enemigos][:4]
                    if bans_filtrados:
                        for i, ban in enumerate(bans_filtrados): 
                            self.renderizar_icono(ban, "champ", self.fr_bans_icons_vivo, 0, i, f"Prioridad Ban: {ban}", size=35)
                    else: 
                        lbl_noban = QLabel("Sin recomendaciones")
                        lbl_noban.setStyleSheet("color: gray;")
                        self.fr_bans_icons_vivo.addWidget(lbl_noban)

                    if mi_campeon:
                        ids_runas = obtener_top_runas(mi_campeon, rol_api)
                        ids_spells = obtener_top_hechizos(mi_campeon, rol_api)
                        ids_start, ids_core = obtener_top_items(mi_campeon, rol_api)
                        self.renderizar_setup_completo(mi_campeon, ids_runas, ids_spells, ids_start, ids_core, self.fr_runas_icons_vivo)
                    else: 
                        self.inicializar_panel_setup(self.fr_runas_icons_vivo)
            else:
                if self.last_my_champ != "FORZAR_INICIO":
                    self.radar_activo = False
                    self.perfil_cargado = False
                    self.last_aliados = []
                    self.last_enemigos = []
                    self.last_my_champ = "FORZAR_INICIO"
                    self.lbl_estado_lcu.setText("Buscando Cliente de LoL... (Abre el juego)")
                    self.lbl_estado_lcu.setStyleSheet(f"color: {YELLOW_WR}; font-weight: bold; font-size: 14px;")

        except Exception as e: pass

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
            
            lbl_name = QLabel(champ)
            lbl_name.setStyleSheet("font-weight: bold; font-size: 14px;")
            card_layout.addWidget(lbl_name)
            card_layout.addStretch()
            layout.addWidget(card)

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
                self.renderizar_icono(champ, "champ", grid_icons, i // 2, i % 2, f"{champ}\nWR Esperado: {wr}%\nPor qué: {razon}", size=35)
                
            cat_layout.addLayout(grid_icons)
            self.fr_picks_icons.addLayout(cat_layout, 0, col_idx)
            col_idx += 1

    # ================= META & BUILDS =================
    def armar_tab_counters(self):
        layout = QVBoxLayout(self.tab_counters)
        
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
        self.tree_counters.setMinimumHeight(150) # FIX: Permite que crezca segun espacio disponible
        self.tree_counters.verticalHeader().setDefaultSectionSize(40)
        self.tree_counters.setIconSize(QSize(30, 30))
        self.tree_counters.verticalHeader().setVisible(False)
        layout.addWidget(self.tree_counters)
        
        self.panel_visual, self.l_visual = self.crear_panel("Setup & Build Óptimas")
        self.frame_setup_visual = QVBoxLayout()
        self.frame_setup_visual.setAlignment(Qt.AlignTop)
        self.l_visual.addLayout(self.frame_setup_visual)
        layout.addWidget(self.panel_visual, 1)

        self.actualizar_listas_counter(UI_ROLES[0])

    def buscar_counters(self):
        rol_api = ROL_TO_API[self.cb_rol_counter.currentText()]
        enemigo = self.cb_enemigo.currentText()
        self.builds_actuales.clear() 
        self.tree_counters.setRowCount(0)
        clear_layout(self.frame_setup_visual)

        resultados = obtener_counters(rol_api, enemigo, min_partidas=20)
        if not resultados: 
            QMessageBox.information(self, "Aviso", "Datos insuficientes. Ajusta tus filtros.")
            return

        for champ, winrate, partidas in resultados[:6]:
            ids_start, ids_fin = obtener_top_items(champ, rol_api)
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
            if icon_path: item_champ.setIcon(QIcon(icon_path))
            
            item_wr = QTableWidgetItem(f"{winrate}%")
            if winrate >= 52: item_wr.setForeground(QColor(GREEN_WR))
            elif winrate <= 48: item_wr.setForeground(QColor(RED_WR))
            
            self.tree_counters.setItem(row, 0, item_champ)
            self.tree_counters.setItem(row, 1, item_wr)
            self.tree_counters.setItem(row, 2, QTableWidgetItem(str(partidas)))

    def mostrar_build_visual(self):
        filas = self.tree_counters.selectedItems()
        if not filas: return
        champ = self.tree_counters.item(filas[0].row(), 0).text().strip()
        data = self.builds_actuales.get(champ, {})
        
        if data.get("runas"): 
            self.renderizar_setup_completo(champ, data["runas"], data.get("spells", []), data.get("starters", []), data.get("finales", []), self.frame_setup_visual)

    def armar_tab_ia(self):
        layout = QVBoxLayout(self.tab_ia)
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
        batalla_layout = QHBoxLayout()
        
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
        layout.addWidget(hud_panel, 1)

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
        
        n = len(self.nombres_campeones_global)
        X = np.zeros(n * 2)
        if aliado in self.nombres_campeones_global: X[self.nombres_campeones_global.index(aliado)] = 1
        if enemigo in self.nombres_campeones_global: X[n + self.nombres_campeones_global.index(enemigo)] = 1
            
        prob = modelo_1v1[rol_api].predict_proba(X.reshape(1, -1))[0][1] * 100
        self.barra_wr.setValue(int(prob))
        if prob >= 50: self.barra_wr.setStyleSheet(f"QProgressBar {{ border: 1px solid {BORDER_GOLD}; border-radius: 5px; text-align: center; background-color: {RED_WR}; color: {BG_DARK}; font-weight: bold; font-size: 14px;}} QProgressBar::chunk {{ background-color: {GREEN_WR}; border-radius: 5px; }}")
        else: self.barra_wr.setStyleSheet(f"QProgressBar {{ border: 1px solid {BORDER_GOLD}; border-radius: 5px; text-align: center; background-color: {GREEN_WR}; color: {TEXT_WHITE}; font-weight: bold; font-size: 14px;}} QProgressBar::chunk {{ background-color: {RED_WR}; border-radius: 5px; }}")
        
        tags_al = self.champs_dict.get(aliado, {}).get("tags", [])
        tags_en = self.champs_dict.get(enemigo, {}).get("tags", [])
        
        if prob > 55: text = f"✅ VENTAJA CLARA ({prob:.1f}%): El kit de {aliado} contrarresta mecánicamente a {enemigo}." + (" Especialmente fuerte como Asesino vs Mago." if "Assassin" in tags_al and "Mage" in tags_en else "")
        elif prob < 45: text = f"⚠️ MATCHUP PELIGROSO ({prob:.1f}%): {enemigo} tiene ventaja estadística pura. Prioriza la supervivencia y el escalado."
        else: text = f"⚔️ MATCHUP DE HABILIDAD ({prob:.1f}%): Choque muy equilibrado. El ganador se decidirá por control de oleadas y rotaciones."
            
        self.lbl_analisis_ia.setText(text)

    def armar_tab_bans(self):
        layout = QVBoxLayout(self.tab_bans)
        
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
        layout.addWidget(self.treebans)

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