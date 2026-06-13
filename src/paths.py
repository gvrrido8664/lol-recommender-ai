"""Rutas centralizadas de la aplicacion.

Fuente unica de verdad para BASE_DIR, directorios de cache y la carpeta
escribible de configuracion. Antes estaban inline al inicio de app.py.

Comportamiento identico al original:
- BASE_DIR: en dev = raiz del proyecto; en .exe frozen = sys._MEIPASS.
- Directorio escribible: en dev = raiz del proyecto; en .exe = %APPDATA%/LoLRecommender.
- Cache: en dev = ./assets; en .exe = %APPDATA%/LoLRecommender/assets.
"""

import os
import sys

# PyInstaller: cuando es .exe, los datos estan en _MEIPASS.
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    # En dev BASE_DIR es la raiz del proyecto (carpeta padre de src/).
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_writable_dir():
    """Devuelve un directorio escribible para config/user data.
    En desarrollo: raiz del proyecto.
    En .exe frozen: %APPDATA%/LoLRecommender."""
    if getattr(sys, 'frozen', False):
        d = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'LoLRecommender')
    else:
        d = BASE_DIR
    os.makedirs(d, exist_ok=True)
    return d


ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# Cuando es .exe, los directorios de cache van a %APPDATA% (Program Files es solo lectura).
if getattr(sys, 'frozen', False):
    _CACHE_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'LoLRecommender', 'assets')
else:
    _CACHE_DIR = ASSETS_DIR

ITEMS_DIR = os.path.join(_CACHE_DIR, "items")
RUNAS_DIR = os.path.join(_CACHE_DIR, "runas")
CHAMPS_DIR = os.path.join(_CACHE_DIR, "champs")
SPELLS_DIR = os.path.join(_CACHE_DIR, "spells")
PROFILE_ICONS_DIR = os.path.join(_CACHE_DIR, "profile_icons")

for _d in [ITEMS_DIR, RUNAS_DIR, CHAMPS_DIR, SPELLS_DIR, PROFILE_ICONS_DIR]:
    os.makedirs(_d, exist_ok=True)

CONFIG_DIR = _get_writable_dir()
