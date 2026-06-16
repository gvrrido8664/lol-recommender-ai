from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.auth import verificar_token
from backend.db import obtener_conexion
from psycopg2.extras import DictCursor

router = APIRouter(prefix="/emocional", tags=["emocional"])


class EmocionalBody(BaseModel):
    game_id: str
    estado: str
    puuid: str = ""
    champion: str = ""


@router.post("/etiquetar")
def etiquetar_estado_endpoint(body: EmocionalBody, _token: str = Depends(verificar_token)):
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO estado_emocional (game_id, puuid, champion, estado)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (game_id) DO UPDATE
               SET estado=EXCLUDED.estado, fecha_tag=CURRENT_TIMESTAMP""",
            (body.game_id, body.puuid, body.champion, body.estado),
        )
        cur.close()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/obtener/{game_id}")
def obtener_estado_endpoint(game_id: str, _token: str = Depends(verificar_token)):
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute("SELECT estado FROM estado_emocional WHERE game_id=%s", (game_id,))
        row = cur.fetchone()
        cur.close()
        return {"estado": row[0] if row else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/estadisticas")
def estadisticas_emocionales_endpoint(_token: str = Depends(verificar_token)):
    conn = obtener_conexion()
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute(
            """SELECT ee.estado, COUNT(*) as partidas,
                      SUM(CASE WHEN p.win=1 THEN 1 ELSE 0 END) as wins
               FROM estado_emocional ee
               JOIN participantes p ON p.match_id = ee.game_id AND p.champion = ee.champion
               GROUP BY ee.estado"""
        )
        rows = cur.fetchall()
        cur.close()
        result = {}
        for r in rows:
            p = r["partidas"]
            w = r["wins"]
            result[r["estado"]] = {"partidas": p, "wins": w, "wr": round(w / p * 100, 1) if p > 0 else 0}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
