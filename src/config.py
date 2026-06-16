import os
import sys
import json

def _obtener_dir_base():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _obtener_dir_datos():
    if getattr(sys, 'frozen', False):
        base = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'LoLRecommender')
    else:
        base = _obtener_dir_base()
    d = os.path.join(base, "data")
    os.makedirs(d, exist_ok=True)
    return d

BASE_DIR = _obtener_dir_base()
DATA_DIR = _obtener_dir_datos()

def cargar_config():
    try:
        # En .exe el config.json va en %APPDATA%/LoLRecommender (carpeta escribible);
        # en dev, en la raiz del proyecto. Tambien se acepta junto al ejecutable (CWD).
        appdata_cfg = os.path.join(os.path.dirname(DATA_DIR), "config.json")
        config_paths = ["config.json", os.path.join("..", "config.json"), appdata_cfg]
        for p in config_paths:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
    except Exception:
        pass
    return {}
