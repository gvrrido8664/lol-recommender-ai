"""Superficie compartida de la UI: imports y datos a nivel de modulo.

Centraliza todo lo que los mixins de pestania (ui/tabs/) y app.py necesitan a
nivel de modulo, para que cada mixin haga simplemente `from ui.contexto import *`
sin repetir ~40 imports ni recomputar los diccionarios de datos.

Los diccionarios (ITEMS_DICT, RUNAS_DICT, ...) se computan UNA sola vez aqui
al importar el modulo, igual que antes ocurria en app.py.
"""

import json
import os
import sys
import requests
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date
from io import BytesIO
from PIL import Image
import numpy as np
import joblib

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
from src.db_manager import guardar_season_cache, cargar_season_cache
from src.db_manager import guardar_coaching_cache, cargar_coaching_cache
from src.riot_api import cargar_campeones, cargar_objetos, cargar_runas, cargar_mapeo_ids, cargar_hechizos, obtener_version_actual
from src.tags_champions import obtener_tag, obtener_nivel_cc, es_soporte, obtener_dano, es_tanque
from src.recomendador import (obtener_counters, obtener_top_items, obtener_campeones_por_rol,
                              obtener_top_runas, obtener_top_hechizos, obtenermejoresbaneos, obtener_peores_matchups,
                              recomendar_picks_vivo, calcular_winrate_5v5, analizar_composicion,
                              obtener_items_situacionales, obtener_winrate_global)
from src.roles import ROLES_UI as UI_ROLES, UI_TO_API as ROL_TO_API, API_TO_UI as API_TO_ROL
from src.lcu_api import LCUConnector
from src.analizador_fatiga import analizar_fatiga
from src.perfil_jugador import analizar_personalidad, detectar_habitos, generar_objetivos_semanales, analizar_emocional_vs_wr
from src.entrenador_ia import extraer_features_comparativas, interpretar_features, consejos_matchup
from src.overlay import OverlayWindow
from src.discord_rpc import iniciar_discord_rpc, detener_discord_rpc, actualizar_discord_rpc
from src.logros import evaluar_logros, obtener_logros_conseguidos, LOGROS_DEFINICIONES
from src.logger import get_logger
from src.updater import check_for_update, set_current_version

from src.paths import (BASE_DIR, ASSETS_DIR, ITEMS_DIR, RUNAS_DIR, CHAMPS_DIR,
                       SPELLS_DIR, PROFILE_ICONS_DIR, CONFIG_DIR, _get_writable_dir)
from src.coach import generar_reporte_coach

from ui.design import *
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.lp_graph import LPGraphWidget
from ui.dialogs.postgame_dialog import PostGameDialog
from ui.helpers import (clear_layout, cargar_settings, guardar_settings,
                        DEFAULT_SETTINGS, STAT_SHARDS, SKILL_ORDERS, JUNGLA_ESTILO,
                        _jungla_estilo, sugerir_pathing_jungla, ajustar_shards_adaptativos,
                        MATCHUP_TIPS, obtener_tip_matchup, obtener_tips_matchup)

log = get_logger(__name__)

# ─── Datos estaticos cargados una sola vez ───────────────────────────────
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
