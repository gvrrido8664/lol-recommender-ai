import os
import sys
import json
import time
import threading

import psycopg2
import psycopg2.errors
import psycopg2.pool
from psycopg2.extras import DictCursor

from .config import cargar_config, DATA_DIR, BASE_DIR


class ConexionDBError(Exception):
    """Error al conectar o consultar la base de datos PostgreSQL."""
    pass


def _obtener_db_url() -> str | None:
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url
    config = cargar_config()
    url = config.get("DATABASE_URL", "")
    if url:
        return url
    return None


_PG_POOL = None
_PG_POOL_LOCK = threading.Lock()
_PG_MINCONN = 2
_PG_MAXCONN = 10


def _init_pool():
    global _PG_POOL
    if _PG_POOL is not None:
        return
    with _PG_POOL_LOCK:
        if _PG_POOL is not None:
            return
        url = _obtener_db_url()
        if not url:
            raise ConexionDBError("DATABASE_URL no configurado.")
        _PG_POOL = psycopg2.pool.ThreadedConnectionPool(
            _PG_MINCONN, _PG_MAXCONN, url,
            cursor_factory=DictCursor,
            connect_timeout=30,
            keepalives=1, keepalives_idle=60,
            keepalives_interval=10, keepalives_count=3,
            options='-c statement_timeout=30000',
        )


class _ConexionPooled:
    """Proxy: close() devuelve al pool en vez de cerrar el socket."""
    def __init__(self, real_conn):
        self._conn = real_conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        global _PG_POOL
        _PG_POOL.putconn(self._conn)

    def cursor(self, **kwargs):
        return self._conn.cursor(**kwargs)


def obtener_conexion():
    global _PG_POOL
    if _PG_POOL is None:
        _init_pool()
    real = _PG_POOL.getconn()
    real.set_session(autocommit=False)
    return _ConexionPooled(real)


def _db_tiene_datos():
    try:
        conn = obtener_conexion()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM matches")
        tiene = cur.fetchone()[0] > 1000
        conn.close()
        return tiene
    except Exception:
        return False


def inicializar_db():
    conn = obtener_conexion()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id TEXT PRIMARY KEY,
            game_version TEXT,
            game_duration INTEGER,
            patch TEXT,
            fecha_descarga TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS participantes (
            id SERIAL PRIMARY KEY,
            match_id TEXT,
            champion TEXT NOT NULL,
            team_position TEXT NOT NULL,
            team INTEGER NOT NULL,
            win INTEGER NOT NULL,
            items TEXT,
            runes TEXT,
            spells TEXT,
            kills INTEGER,
            deaths INTEGER,
            assists INTEGER,
            FOREIGN KEY (match_id) REFERENCES matches (match_id) ON DELETE CASCADE
        )
    """)

    for col, tipo in [
        ("patch", "TEXT"),
        ("runes", "TEXT"),
        ("spells", "TEXT"),
        ("kills", "INTEGER"),
        ("deaths", "INTEGER"),
        ("assists", "INTEGER"),
        ("items_order", "TEXT"),  # secuencia de compra real (del timeline)
        ("item_timeline", "JSONB"),  # [{iid, ts}, ...] con timestamps reales de compra
    ]:
        tabla = 'participantes' if col != 'patch' else 'matches'
        cur.execute(f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS {col} {tipo}")

    cur.execute("""
        DO $$
        BEGIN
            ALTER TABLE participantes
            DROP CONSTRAINT IF EXISTS uq_participante_match_champ_team;
            ALTER TABLE participantes
            ADD CONSTRAINT uq_participante_match_champ_team
            UNIQUE (match_id, champion, team);
        EXCEPTION
            WHEN undefined_table THEN NULL;
            WHEN undefined_column THEN NULL;
        END $$;
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_champion ON participantes(champion);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_position ON participantes(team_position);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_match_id ON participantes(match_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_win ON participantes(win);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_champ_pos ON participantes(champion, team_position);")
    # Índices adicionales para acelerar consultas frecuentes (anti-freeze)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pos_champ ON participantes(team_position, champion);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_champ_match ON participantes(champion, match_id);")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS estado_emocional (
            id SERIAL PRIMARY KEY,
            game_id TEXT NOT NULL,
            puuid TEXT,
            champion TEXT,
            estado TEXT NOT NULL CHECK(estado IN ('Concentrado', 'Normal', 'Tilted', 'Cansado')),
            fecha_tag TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(game_id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_emocional_estado ON estado_emocional(estado);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_emocional_game ON estado_emocional(game_id);")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_cache (
            puuid TEXT PRIMARY KEY,
            season_games JSONB,
            coaching_report JSONB,
            season_ts TIMESTAMP,
            coaching_ts TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("Base de datos PostgreSQL operativa y actualizada con KDA, Parches, Hechizos y Motor Emocional.")


def limpiar_base_de_datos():
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("DELETE FROM participantes")
    cur.execute("DELETE FROM matches")
    conn.commit()
    conn.close()
    print("Base de datos limpiada.")


def purgar_parches_antiguos(parche_actual: str):
    conn = obtener_conexion()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM matches")
    total_antes = cur.fetchone()[0]

    cur.execute("""
        DELETE FROM matches
        WHERE game_version NOT LIKE %s
           OR game_version IS NULL
    """, (f"{parche_actual}.%",))
    eliminadas = cur.rowcount
    conn.commit()
    conn.close()

    if eliminadas > 0:
        print(f"  [PURGA] {eliminadas:,} partidas antiguas eliminadas.")
        try:
            conn2 = obtener_conexion()
            conn2.autocommit = True
            cur2 = conn2.cursor()
            cur2.execute("VACUUM")
            conn2.close()
        except Exception:
            pass

    print(f"  [PURGA] Base de datos: {total_antes:,} -> {total_antes - eliminadas:,} partidas")
    return eliminadas, 0


def compactar_base_de_datos():
    conn = obtener_conexion()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM matches WHERE match_id NOT IN (
            SELECT DISTINCT match_id FROM participantes
        )
    """)
    huerfanas = cur.rowcount

    cur.execute("SELECT COUNT(*) FROM matches")
    total = cur.fetchone()[0]
    if total > 5000:
        cur.execute("""
            DELETE FROM matches WHERE match_id IN (
                SELECT match_id FROM matches
                WHERE fecha_descarga < NOW() - INTERVAL '6 months'
                ORDER BY fecha_descarga ASC
                LIMIT %s
            )
        """, (total - 5000,))
        antiguas = cur.rowcount
    else:
        antiguas = 0

    conn.commit()

    print(f"  Huérfanas eliminadas: {huerfanas}")
    print(f"  Antiguas eliminadas: {antiguas}")
    print(f"  Compactando archivo...")
    cur.execute("VACUUM")
    conn.close()

    print("Base de datos compactada.")


# ─── MOTOR EMOCIONAL (NEXUS) ───

def etiquetar_estado_emocional(game_id: str, estado: str, puuid: str = "", champion: str = ""):
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO estado_emocional (game_id, puuid, champion, estado)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT(game_id) DO UPDATE SET estado=EXCLUDED.estado, fecha_tag=CURRENT_TIMESTAMP
    """, (str(game_id), puuid, champion, estado))
    conn.commit()
    conn.close()


def obtener_estado_emocional(game_id: str) -> str | None:
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM estado_emocional WHERE game_id=%s", (str(game_id),))
    row = cur.fetchone()
    conn.close()
    return row["estado"] if row else None


def obtener_estadisticas_emocionales() -> dict:
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT ee.estado, COUNT(*) as partidas,
               SUM(CASE WHEN p.win = 1 THEN 1 ELSE 0 END) as wins
        FROM estado_emocional ee
        JOIN participantes p ON p.match_id = ee.game_id AND p.champion = ee.champion
        GROUP BY ee.estado
    """)
    stats = {}
    for row in cur.fetchall():
        estado = row["estado"]
        partidas = int(row["partidas"] or 0)
        wins = int(row["wins"] or 0)
        stats[estado] = {
            "partidas": partidas,
            "wins": wins,
            "wr": round(wins / partidas * 100, 1) if partidas > 0 else 0
        }
    conn.close()
    return stats


# ─── TRACKING DE LP / MMR ───

def _crear_tabla_lp_history():
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lp_history (
            id SERIAL PRIMARY KEY,
            fecha TEXT NOT NULL,
            queue_type TEXT NOT NULL DEFAULT 'RANKED_SOLO_5x5',
            tier TEXT NOT NULL,
            division TEXT NOT NULL,
            lp INTEGER NOT NULL,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0
        )
    """)
    cur.execute("DROP INDEX IF EXISTS idx_lp_fecha")
    cur.execute("DELETE FROM lp_history WHERE id NOT IN (SELECT MAX(id) FROM lp_history GROUP BY fecha, queue_type)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lp_unique ON lp_history(fecha, queue_type)")
    conn.commit()
    conn.close()


try:
    _crear_tabla_lp_history()
except ConexionDBError:
    pass


def registrar_lp(tier: str, division: str, lp: int, wins: int = 0, losses: int = 0,
                 queue_type: str = "RANKED_SOLO_5x5"):
    if not tier or tier.upper() in ("UNRANKED", "NONE", ""):
        return
    from datetime import date
    fecha = str(date.today())
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO lp_history (fecha, queue_type, tier, division, lp, wins, losses)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fecha, queue_type) DO NOTHING
    """, (fecha, queue_type, tier.upper(), division.upper(), int(lp), int(wins), int(losses)))
    cur.execute("""
        UPDATE lp_history SET tier=%s, division=%s, lp=%s, wins=%s, losses=%s
        WHERE fecha=%s AND queue_type=%s
    """, (tier.upper(), division.upper(), int(lp), int(wins), int(losses), fecha, queue_type))
    conn.commit()
    conn.close()


def obtener_historial_lp(queue_type: str = "RANKED_SOLO_5x5", dias: int = 30) -> list:
    TIER_BASE = {
        "IRON": 0, "BRONZE": 400, "SILVER": 800, "GOLD": 1200,
        "PLATINUM": 1600, "EMERALD": 2000, "DIAMOND": 2400,
        "MASTER": 2800, "GRANDMASTER": 2800, "CHALLENGER": 2800,
    }
    DIV_OFFSET = {"I": 300, "II": 200, "III": 100, "IV": 0, "": 0}
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT fecha, tier, division, lp, wins, losses
        FROM lp_history
        WHERE queue_type=%s AND fecha >= (CURRENT_DATE - (%s || ' days')::INTERVAL)::TEXT
        ORDER BY fecha ASC
    """, (queue_type, str(dias)))
    rows = cur.fetchall()
    conn.close()
    resultado = []
    for r in rows:
        base = TIER_BASE.get(r["tier"], 0)
        offset = DIV_OFFSET.get(r["division"], 0)
        lp_total = base + offset + r["lp"]
        resultado.append({
            "fecha": r["fecha"],
            "tier": r["tier"],
            "division": r["division"],
            "lp": r["lp"],
            "lp_total": lp_total,
            "wins": r["wins"],
            "losses": r["losses"],
        })
    return resultado


def _crear_tabla_drafts():
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS drafts_history (
            id SERIAL PRIMARY KEY,
            fecha TEXT NOT NULL,
            campeon TEXT,
            rol TEXT,
            bans TEXT,
            aliados TEXT,
            enemigos TEXT,
            wr_predicho REAL,
            resultado TEXT DEFAULT 'pendiente',
            ganada INTEGER
        )
    """)
    conn.commit()
    conn.close()


try:
    _crear_tabla_drafts()
except ConexionDBError:
    pass


def guardar_draft(campeon, rol, bans, aliados, enemigos, wr_predicho):
    from datetime import date
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO drafts_history (fecha, campeon, rol, bans, aliados, enemigos, wr_predicho)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (str(date.today()), campeon, rol, json.dumps(bans), json.dumps(aliados), json.dumps(enemigos), wr_predicho))
    draft_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return draft_id


def completar_draft_resultado(draft_id, ganada):
    conn = obtener_conexion()
    cur = conn.cursor()
    if ganada is None:
        cur.execute(
            "UPDATE drafts_history SET resultado = 'completada' WHERE id = %s",
            (draft_id,)
        )
    else:
        cur.execute(
            "UPDATE drafts_history SET resultado = %s, ganada = %s WHERE id = %s",
            ("victoria" if ganada else "derrota", 1 if ganada else 0, draft_id)
        )
    conn.commit()
    conn.close()


def obtener_historial_drafts(limite=20):
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT fecha, campeon, rol, bans, aliados, enemigos, wr_predicho, resultado, ganada
        FROM drafts_history ORDER BY id DESC LIMIT %s
    """, (limite,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def guardar_season_cache(puuid, games):
    if not puuid or not games or len(games) < 10:
        return
    try:
        conn = obtener_conexion()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO player_cache (puuid, season_games, season_ts)
            VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
            ON CONFLICT (puuid) DO UPDATE SET
                season_games = EXCLUDED.season_games,
                season_ts = CURRENT_TIMESTAMP
        """, (puuid, json.dumps(games, default=str)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[SeasonCache] Error guardando en BD: {e}")


def cargar_season_cache(puuid):
    if not puuid:
        return None
    try:
        conn = obtener_conexion()
        cur = conn.cursor()
        cur.execute("""
            SELECT season_games, season_ts FROM player_cache WHERE puuid = %s
        """, (puuid,))
        row = cur.fetchone()
        conn.close()
        if not row or not row["season_games"]:
            return None
        ts = row["season_ts"]
        if ts:
            age_h = (time.time() - ts.timestamp()) / 3600
            if age_h > 24:
                return None
        return row["season_games"] if isinstance(row["season_games"], list) else json.loads(row["season_games"])
    except Exception as e:
        print(f"[SeasonCache] Error cargando de BD: {e}")
        return None


def guardar_coaching_cache(puuid, reporte, datos_extra=None):
    if not puuid or not reporte:
        return
    try:
        conn = obtener_conexion()
        cur = conn.cursor()
        payload = {"_ts": time.time(), "reporte": reporte}
        if datos_extra:
            payload["datos_extra"] = {
                "personalidad": datos_extra.get("personalidad"),
                "insights": datos_extra.get("insights"),
                "objetivos": datos_extra.get("objetivos"),
                "emocional": datos_extra.get("emocional"),
            }
        cur.execute("""
            INSERT INTO player_cache (puuid, coaching_report, coaching_ts)
            VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
            ON CONFLICT (puuid) DO UPDATE SET
                coaching_report = EXCLUDED.coaching_report,
                coaching_ts = CURRENT_TIMESTAMP
        """, (puuid, json.dumps(payload, default=str)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[CoachingCache] Error guardando en BD: {e}")


def cargar_coaching_cache(puuid):
    if not puuid:
        return None
    try:
        conn = obtener_conexion()
        cur = conn.cursor()
        cur.execute("""
            SELECT coaching_report, coaching_ts FROM player_cache WHERE puuid = %s
        """, (puuid,))
        row = cur.fetchone()
        conn.close()
        if not row or not row["coaching_report"]:
            return None
        ts = row["coaching_ts"]
        if ts:
            age_h = (time.time() - ts.timestamp()) / 3600
            if age_h > 24:
                return None
        return row["coaching_report"] if isinstance(row["coaching_report"], dict) else json.loads(row["coaching_report"])
    except Exception as e:
        print(f"[CoachingCache] Error cargando de BD: {e}")
        return None


if __name__ == "__main__":
    inicializar_db()
