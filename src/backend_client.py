"""
Cliente HTTP para el backend proxy de NEXUS.

Reemplaza las conexiones directas a PostgreSQL y a la API de Riot.
Todas las funciones tienen los mismos nombres y firmas que sus equivalentes
en src/db_manager.py y src/riot_public_api.py para facilitar la migracion.
"""

import json
import os

import requests


def _cargar_config_json():
    try:
        from src.paths import BASE_DIR
        ruta = os.path.join(BASE_DIR, "config.json")
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


_cfg = _cargar_config_json()
URL_BASE = os.environ.get("NEXUS_BACKEND_URL", _cfg.get("NEXUS_BACKEND_URL", "http://localhost:8000"))
TOKEN = os.environ.get("NEXUS_APP_TOKEN", _cfg.get("NEXUS_APP_TOKEN", ""))


def _headers():
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }


def _post(path, json_data):
    try:
        r = requests.post(f"{URL_BASE}{path}", json=json_data, headers=_headers(), timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _get(path, params=None):
    try:
        r = requests.get(f"{URL_BASE}{path}", params=params, headers=_headers(), timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# ─── Drafts ──────────────────────────────────────────────────────────────────

def guardar_draft(campeon, rol, bans, aliados, enemigos, wr_predicho):
    res = _post("/drafts/guardar", {
        "campeon": campeon,
        "rol": rol,
        "bans": list(bans),
        "aliados": list(aliados),
        "enemigos": list(enemigos),
        "wr_predicho": float(wr_predicho),
    })
    return res["draft_id"] if res else None


def completar_draft_resultado(draft_id, ganada):
    _post("/drafts/completar", {"draft_id": draft_id, "ganada": ganada})


def obtener_historial_drafts(limite=20):
    res = _get("/drafts/historial", {"limite": limite})
    return res if res else []


# ─── LP ───────────────────────────────────────────────────────────────────────

def registrar_lp(tier, division, lp, wins=0, losses=0, queue_type="RANKED_SOLO_5x5"):
    _post("/lp/registrar", {
        "tier": tier,
        "division": division,
        "lp": lp,
        "wins": wins,
        "losses": losses,
        "queue_type": queue_type,
    })


def obtener_historial_lp(queue_type="RANKED_SOLO_5x5"):
    res = _get("/lp/historial", {"queue_type": queue_type})
    return res if res else []


# ─── Estado Emocional ─────────────────────────────────────────────────────────

def etiquetar_estado_emocional(game_id, estado, puuid="", champion=""):
    _post("/emocional/etiquetar", {
        "game_id": game_id,
        "estado": estado,
        "puuid": puuid,
        "champion": champion,
    })


def obtener_estado_emocional(game_id):
    res = _get(f"/emocional/obtener/{game_id}")
    return res.get("estado") if res else None


def obtener_estadisticas_emocionales():
    res = _get("/emocional/estadisticas")
    return res if res else {}


# ─── Cache ────────────────────────────────────────────────────────────────────

def guardar_season_cache(puuid, games):
    _post("/cache/season", {"puuid": puuid, "games": games})


def cargar_season_cache(puuid):
    res = _get(f"/cache/season/{puuid}")
    if res and res.get("games"):
        import json
        return json.dumps(res["games"])
    return None


def guardar_coaching_cache(puuid, reporte, datos_extra=None):
    _post("/cache/coaching", {"puuid": puuid, "reporte": reporte, "datos_extra": datos_extra})


def cargar_coaching_cache(puuid):
    res = _get(f"/cache/coaching/{puuid}")
    if res and res.get("reporte"):
        return res["reporte"]
    return None


# ─── Riot API Proxy ───────────────────────────────────────────────────────────

def riot_get(url_path, params=None):
    return _get(f"/riot{url_path}", params)


# ─── Health ───────────────────────────────────────────────────────────────────

def health():
    try:
        r = requests.get(f"{URL_BASE}/health", timeout=5)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None
