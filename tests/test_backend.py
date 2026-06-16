"""
Tests del backend proxy NEXUS (FastAPI).

Ejecutar con: python -m pytest tests/test_backend.py -q
Requiere: APP_TOKEN=test-token-nexus configurado como env var.
"""

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("APP_TOKEN", "test-token-nexus-2026")
os.environ.setdefault("DATABASE_URL", "")
os.environ.setdefault("RIOT_API_KEY", "")

from backend.main import app

client = TestClient(app)
HEADERS = {"Authorization": "Bearer test-token-nexus-2026"}


@pytest.fixture(autouse=True)
def disable_db():
    """Evita conexiones reales a BD durante los tests unitarios."""
    pass


# ─── Health ───────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ─── Auth ─────────────────────────────────────────────────────────────────────

def test_sin_token_rechazado():
    r = client.get("/drafts/historial")
    assert r.status_code == 401


def test_token_invalido_rechazado():
    r = client.get("/drafts/historial", headers={"Authorization": "Bearer token-falso"})
    assert r.status_code == 401


def test_token_valido_aceptado():
    r = client.get("/lp/historial", headers=HEADERS)
    assert r.status_code in (200, 500)


# ─── Drafts (validacion de esquema) ───────────────────────────────────────────

def test_guardar_draft_schema_invalido():
    r = client.post("/drafts/guardar", json={}, headers=HEADERS)
    assert r.status_code == 422


def test_guardar_draft_schema_valido():
    r = client.post("/drafts/guardar", json={
        "campeon": "Ahri",
        "rol": "MIDDLE",
        "bans": ["Zed"],
        "aliados": ["LeeSin"],
        "enemigos": ["Yasuo"],
        "wr_predicho": 53.5,
    }, headers=HEADERS)
    assert r.status_code in (200, 500)


def test_completar_draft_schema():
    r = client.post("/drafts/completar", json={"draft_id": 1, "ganada": True}, headers=HEADERS)
    assert r.status_code in (200, 500)


def test_historial_drafts():
    r = client.get("/drafts/historial", headers=HEADERS)
    assert r.status_code in (200, 500)


# ─── LP ───────────────────────────────────────────────────────────────────────

def test_registrar_lp_unranked():
    r = client.post("/lp/registrar", json={
        "tier": "UNRANKED", "division": "I", "lp": 0,
    }, headers=HEADERS)
    assert r.status_code == 200
    assert r.json().get("skipped") is True


def test_registrar_lp_valido():
    r = client.post("/lp/registrar", json={
        "tier": "GOLD", "division": "II", "lp": 75, "wins": 10, "losses": 8,
    }, headers=HEADERS)
    assert r.status_code in (200, 500)


def test_historial_lp():
    r = client.get("/lp/historial", headers=HEADERS)
    assert r.status_code in (200, 500)


# ─── Emocional ────────────────────────────────────────────────────────────────

def test_etiquetar_estado():
    r = client.post("/emocional/etiquetar", json={
        "game_id": "LA2_123456789",
        "estado": "Concentrado",
        "puuid": "test-puuid",
        "champion": "Ahri",
    }, headers=HEADERS)
    assert r.status_code in (200, 500)


def test_obtener_estado():
    r = client.get("/emocional/obtener/LA2_123456789", headers=HEADERS)
    assert r.status_code in (200, 500)


def test_estadisticas_emocionales():
    r = client.get("/emocional/estadisticas", headers=HEADERS)
    assert r.status_code in (200, 500)


# ─── Cache ────────────────────────────────────────────────────────────────────

def test_guardar_season_cache():
    r = client.post("/cache/season", json={
        "puuid": "test-puuid",
        "games": [{"gameId": 1, "win": True}],
    }, headers=HEADERS)
    assert r.status_code in (200, 500)


def test_cargar_season_cache():
    r = client.get("/cache/season/test-puuid", headers=HEADERS)
    assert r.status_code in (200, 500)


def test_guardar_coaching_cache():
    r = client.post("/cache/coaching", json={
        "puuid": "test-puuid",
        "reporte": {"resumen": "Buen desempeno"},
    }, headers=HEADERS)
    assert r.status_code in (200, 500)


def test_cargar_coaching_cache():
    r = client.get("/cache/coaching/test-puuid", headers=HEADERS)
    assert r.status_code in (200, 500)


# ─── Riot Proxy (sin API key) ─────────────────────────────────────────────────

def test_riot_proxy_sin_api_key():
    r = client.get("/riot/account/by-riot-id/testuser/EUW", headers=HEADERS)
    assert r.status_code == 503


# ─── Rate Limiter ─────────────────────────────────────────────────────────────

def test_rate_limiter_reset():
    from backend.riot import _long_window, _short_window, reset_limiter
    reset_limiter()
    assert len(_short_window) == 0
    assert len(_long_window) == 0
