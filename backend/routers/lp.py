from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.auth import verificar_token
from backend.db import obtener_conexion
from psycopg2.extras import DictCursor

router = APIRouter(prefix="/lp", tags=["lp"])


class RegistrarLPBody(BaseModel):
    tier: str
    division: str
    lp: int
    wins: int = 0
    losses: int = 0
    queue_type: str = "RANKED_SOLO_5x5"


@router.post("/registrar")
def registrar_lp_endpoint(body: RegistrarLPBody, _token: str = Depends(verificar_token)):
    if body.tier.upper() in ("", "UNRANKED", "NONE"):
        return {"ok": True, "skipped": True}
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO lp_history (tier, division, lp, wins, losses, queue_type)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (fecha, queue_type) DO NOTHING""",
            (body.tier, body.division, body.lp, body.wins, body.losses, body.queue_type),
        )
        cur.execute(
            "UPDATE lp_history SET tier=%s, division=%s, lp=%s, wins=%s, losses=%s WHERE fecha=%s AND queue_type=%s",
            (body.tier, body.division, body.lp, body.wins, body.losses, "CURRENT_DATE", body.queue_type),
        )
        cur.close()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/historial")
def historial_lp_endpoint(queue_type: str = "RANKED_SOLO_5x5", _token: str = Depends(verificar_token)):
    conn = obtener_conexion()
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute(
            "SELECT fecha, tier, division, lp, wins, losses FROM lp_history WHERE queue_type=%s ORDER BY fecha ASC",
            (queue_type,),
        )
        rows = cur.fetchall()
        cur.close()
        result = []
        for r in rows:
            tier_vals = {"IRON": 0, "BRONZE": 400, "SILVER": 800, "GOLD": 1200, "PLATINUM": 1600, "EMERALD": 2000, "DIAMOND": 2400, "MASTER": 2800, "GRANDMASTER": 2800, "CHALLENGER": 2800}
            base = tier_vals.get(r["tier"].upper(), 0)
            div = r.get("division", "I")
            try:
                div_num = int("".join(filter(str.isdigit, div))) if div else 1
            except ValueError:
                div_num = 1
            lp_total = base + (max(0, 4 - div_num) * 100 if r["tier"].upper() not in ("MASTER", "GRANDMASTER", "CHALLENGER") else 0) + r.get("lp", 0)
            result.append({
                "fecha": r["fecha"].isoformat() if hasattr(r["fecha"], "isoformat") else str(r["fecha"]),
                "tier": r["tier"],
                "division": r["division"],
                "lp": r["lp"],
                "lp_total": lp_total,
                "wins": r["wins"],
                "losses": r["losses"],
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
