from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.auth import verificar_token
from backend.db import obtener_conexion
from psycopg2.extras import DictCursor

router = APIRouter(prefix="/drafts", tags=["drafts"])


class DraftGuardar(BaseModel):
    campeon: str
    rol: str
    bans: list[str] = []
    aliados: list[str] = []
    enemigos: list[str] = []
    wr_predicho: float = 50.0


class DraftCompletar(BaseModel):
    draft_id: int
    ganada: bool | None = None


@router.post("/guardar")
def guardar_draft_endpoint(body: DraftGuardar, _token: str = Depends(verificar_token)):
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO drafts_history (campeon, rol, bans, aliados, enemigos, wr_predicho)
               VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
               RETURNING id""",
            (body.campeon, body.rol, body.bans, body.aliados, body.enemigos, body.wr_predicho),
        )
        row = cur.fetchone()
        cur.close()
        return {"draft_id": row[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/completar")
def completar_draft_endpoint(body: DraftCompletar, _token: str = Depends(verificar_token)):
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        if body.ganada is not None:
            cur.execute(
                "UPDATE drafts_history SET resultado='completada', ganada=%s WHERE id=%s",
                (body.ganada, body.draft_id),
            )
        else:
            cur.execute(
                "UPDATE drafts_history SET resultado='completada' WHERE id=%s",
                (body.draft_id,),
            )
        cur.close()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/historial")
def historial_drafts_endpoint(limite: int = 20, _token: str = Depends(verificar_token)):
    conn = obtener_conexion()
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute(
            """SELECT id, fecha, campeon, rol, bans, aliados, enemigos,
                      wr_predicho, resultado, ganada
               FROM drafts_history ORDER BY id DESC LIMIT %s""",
            (limite,),
        )
        rows = cur.fetchall()
        cur.close()
        return [
            {
                "id": r["id"],
                "fecha": r["fecha"].isoformat() if r["fecha"] else None,
                "campeon": r["campeon"],
                "rol": r["rol"],
                "bans": r["bans"],
                "aliados": r["aliados"],
                "enemigos": r["enemigos"],
                "wr_predicho": r["wr_predicho"],
                "resultado": r["resultado"],
                "ganada": r["ganada"],
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
