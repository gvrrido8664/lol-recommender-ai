"""Superficie compartida de la UI: imports y datos a nivel de modulo.

Centraliza todo lo que los mixins de pestania (ui/tabs/) y app.py necesitan a
nivel de modulo, para que cada mixin haga simplemente `from ui.contexto import *`
sin repetir ~40 imports ni recomputar los diccionarios de datos.

Los diccionarios (ITEMS_DICT, RUNAS_DICT, ...) se computan UNA sola vez aqui
al importar el modulo, igual que antes ocurria en app.py.
"""

# ruff: noqa: F401, F403, E402

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from io import BytesIO

import joblib
import numpy as np
import requests
from PIL import Image
from PySide6.QtCore import QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedLayout,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.analizador_fatiga import analizar_fatiga
from src.coach import generar_reporte_coach
from src.db_manager import (
    DATA_DIR,
    cargar_coaching_cache,
    cargar_season_cache,
    completar_draft_resultado,
    etiquetar_estado_emocional,
    guardar_coaching_cache,
    guardar_draft,
    guardar_season_cache,
    inicializar_db,
    obtener_conexion,
    obtener_estadisticas_emocionales,
    obtener_estado_emocional,
    obtener_historial_drafts,
    obtener_historial_lp,
    registrar_lp,
)
from src.discord_rpc import actualizar_discord_rpc, detener_discord_rpc, iniciar_discord_rpc
from src.entrenador_ia import consejos_matchup, extraer_features_comparativas, interpretar_features
from src.lcu_api import LCUConnector
from src.logger import get_logger
from src.logros import LOGROS_DEFINICIONES, evaluar_logros, generar_insights_jugador, obtener_logros_conseguidos
from src.paths import (
    ASSETS_DIR,
    BASE_DIR,
    CHAMPS_DIR,
    CONFIG_DIR,
    ITEMS_DIR,
    PROFILE_ICONS_DIR,
    RUNAS_DIR,
    SPELLS_DIR,
    _get_writable_dir,
)
from src.perfil_jugador import (
    analizar_emocional_vs_wr,
    analizar_personalidad,
    detectar_habitos,
    generar_objetivos_semanales,
)
from src.recomendador import (
    analizar_composicion,
    calcular_winrate_5v5,
    obtener_campeones_por_rol,
    obtener_counters,
    obtener_items_situacionales,
    obtener_peores_matchups,
    obtener_top_hechizos,
    obtener_top_items,
    obtener_top_runas,
    obtener_winrate_global,
    obtenermejoresbaneos,
    recomendar_picks_vivo,
)
from src.riot_api import (
    cargar_campeones,
    cargar_hechizos,
    cargar_mapeo_ids,
    cargar_objetos,
    cargar_runas,
    obtener_version_actual,
)
from src.riot_public_api import RiotPublicAPI
from src.roles import API_TO_UI as API_TO_ROL
from src.roles import ROLES_UI as UI_ROLES
from src.roles import UI_TO_API as ROL_TO_API
from src.tags_champions import es_soporte, es_tanque, obtener_dano, obtener_nivel_cc, obtener_tag
from src.updater import check_for_update, set_current_version
from ui.components import BadgeLabel, EmptyStateWidget, ErrorBanner, LoadingOverlay
from ui.design import *
from ui.dialogs.lp_graph import LPGraphWidget
from ui.dialogs.postgame_dialog import PostGameDialog
from ui.dialogs.settings_dialog import SettingsDialog
from ui.helpers import (
    DEFAULT_SETTINGS,
    JUNGLA_ESTILO,
    MATCHUP_TIPS,
    SKILL_ORDERS,
    STAT_SHARDS,
    _jungla_estilo,
    ajustar_shards_adaptativos,
    cargar_settings,
    clear_layout,
    ejecutar_en_hilo,
    expandir_skill_order,
    exportar_reporte_html,
    guardar_settings,
    obtener_tip_matchup,
    obtener_tips_matchup,
    sugerir_pathing_jungla,
)

log = get_logger(__name__)

# ─── Modelos IA (disco local + fallback Supabase Storage) ────────────────
from src.config import STORAGE_MODELOS_URL


def _cargar_modelo(nombre_archivo, etiqueta):
    modelo = {}
    ruta_data = os.path.join(DATA_DIR, nombre_archivo)
    ruta_bundle = os.path.join(BASE_DIR, "data", nombre_archivo)

    # 1) Intentar desde DATA_DIR (writable cache — descargas)
    for ruta, origen in [(ruta_data, "data"), (ruta_bundle, "bundle")]:
        if os.path.exists(ruta):
            try:
                modelo = joblib.load(ruta)
                n = len(modelo) if isinstance(modelo, dict) else 1
                log.info("%s cargado desde %s: %d roles", etiqueta, origen, n)
                return modelo
            except Exception as e:
                log.warning("Error cargando %s desde %s: %s", nombre_archivo, origen, e)

    # 2) Descargar desde Supabase Storage a DATA_DIR
    try:
        url = f"{STORAGE_MODELOS_URL}/{nombre_archivo}"
        log.info("Descargando %s desde %s ...", etiqueta, url)
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(ruta_data, "wb") as f:
                f.write(r.content)
            modelo = joblib.load(ruta_data)
            n = len(modelo) if isinstance(modelo, dict) else 1
            log.info("%s descargado y cargado: %d roles", etiqueta, n)
        else:
            log.warning("No se pudo descargar %s: HTTP %d", nombre_archivo, r.status_code)
    except Exception as e:
        log.warning("No se pudo descargar %s: %s", nombre_archivo, e)

    if not modelo:
        log.warning("%s no disponible. El simulador 1v1 no funcionara.", etiqueta)
    return modelo


modelo_1v1 = _cargar_modelo("modelo_1v1.pkl", "Modelo 1v1")

ITEMS_DICT = cargar_objetos()
RUNAS_DICT = cargar_runas()
SPELLS_DICT = cargar_hechizos()
MAPEO_IDS_CAMPEONES = cargar_mapeo_ids()
