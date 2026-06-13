"""
Mapeo unificado de roles UI ↔ API ↔ posiciones equivalentes.

Antes disperso en:
  - app.py:99-101  (UI_ROLES, ROL_TO_API, API_TO_ROL)
  - recomendador.py:544-549 (pos_equivalentes)

Usar desde cualquier modulo:
    from src.roles import a_api, a_ui, normalizar_posicion, ROLES_UI, ROLES_API
"""

ROLES_UI = ["TOP", "JUNGLA", "MID", "ADC", "SUPPORT"]
ROLES_API = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]

UI_TO_API = {"TOP": "TOP", "JUNGLA": "JUNGLE", "MID": "MIDDLE", "ADC": "BOTTOM", "SUPPORT": "UTILITY"}
API_TO_UI = {"TOP": "TOP", "JUNGLE": "JUNGLA", "MIDDLE": "MID", "BOTTOM": "ADC", "UTILITY": "SUPPORT"}

POS_EQUIVALENTES = {
    "TOP": "TOP", "JUNGLE": "JUNGLE", "JUNGLA": "JUNGLE",
    "MIDDLE": "MIDDLE", "MID": "MIDDLE",
    "BOTTOM": "BOTTOM", "ADC": "BOTTOM",
    "UTILITY": "UTILITY", "SUPPORT": "UTILITY",
}

def a_api(rol_ui: str) -> str:
    return UI_TO_API.get(rol_ui.upper(), rol_ui.upper())

def a_ui(rol_api: str) -> str:
    return API_TO_UI.get(rol_api.upper(), rol_api.upper())

def normalizar_posicion(rol: str) -> str:
    return POS_EQUIVALENTES.get(rol.upper(), rol.upper())

def posiciones_equivalentes(pos_a: str, pos_b: str) -> bool:
    return normalizar_posicion(pos_a) == normalizar_posicion(pos_b)
