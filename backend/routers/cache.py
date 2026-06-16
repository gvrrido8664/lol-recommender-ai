from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.auth import verificar_token
from backend.db import obtener_conexion
from psycopg2.extras import DictCursor
import json

router = APIRouter(prefix="/cache", tags=["cache"])


class SeasonCacheBody(BaseModel):
    puuid: str
    games: list


@router.post("/season")
def guardar_season_endpoint(body: SeasonCacheBody, _token: str = Depends(verificar_token)):
    if not body.puuid or len(body.games) < 10:
        return {"ok": True, "skipped": True}
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO player_cache (puuid, season_games, season_ts)
               VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
               ON CONFLICT (puuid) DO UPDATE
               SET season_games=EXCLUDED.season_games, season_ts=CURRENT_TIMESTAMP""",
            (body.puuid, json.dumps(body.games)),
        )
        cur.close()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/season/{puuid}")
def cargar_season_endpoint(puuid: str, _token: str = Depends(verificar_token)):
    conn = obtener_conexion()
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT season_games, season_ts FROM player_cache WHERE puuid=%s", (puuid,))
        row = cur.fetchone()
        cur.close()
        if row and row["season_games"]:
            return {"games": row["season_games"], "ts": row["season_ts"].isoformat() if row["season_ts"] else None}
        return {"games": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


class CoachingCacheBody(BaseModel):
    puuid: str
    reporte: dict
    datos_extra: dict | None = None


@router.post("/coaching")
def guardar_coaching_endpoint(body: CoachingCacheBody, _token: str = Depends(verificar_token)):
    if not body.puuid or not body.reporte:
        return {"ok": True, "skipped": True}
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO player_cache (puuid, coaching_report, coaching_ts)
               VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
               ON CONFLICT (puuid) DO UPDATE
               SET coaching_report=EXCLUDED.coaching_report, coaching_ts=CURRENT_TIMESTAMP""",
            (body.puuid, json.dumps(body.reporte)),
        )
        cur.close()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/coaching/{puuid}")
def cargar_coaching_endpoint(puuid: str, _token: str = Depends(verificar_token)):
    conn = obtener_conexion()
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT coaching_report, coaching_ts FROM player_cache WHERE puuid=%s", (puuid,))
        row = cur.fetchone()
        cur.close()
        if row and row["coaching_report"]:
            return {"reporte": row["coaching_report"], "ts": row["coaching_ts"].isoformat() if row["coaching_ts"] else None}
        return {"reporte": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
