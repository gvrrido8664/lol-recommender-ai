import threading
import psycopg2
import psycopg2.pool
from psycopg2.extras import DictCursor

from backend.config import DATABASE_URL

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_lock = threading.Lock()


def _init_pool():
    global _pool
    with _lock:
        if _pool is not None:
            return
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL no configurada")
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=8,
            dsn=DATABASE_URL,
            connect_timeout=15,
            options="-c statement_timeout=30000",
        )


def obtener_conexion():
    if _pool is None:
        _init_pool()
    return _ConexionPooled(_pool)


class _ConexionPooled:
    def __init__(self, pool):
        self._pool = pool
        self._conn = pool.getconn()
        self._conn.set_session(autocommit=True)
        self._closed = False

    def cursor(self, **kwargs):
        return self._conn.cursor(**kwargs)

    def close(self):
        if not self._closed:
            self._closed = True
            self._pool.putconn(self._conn)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def inicializar_db():
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS drafts_history (
                id SERIAL PRIMARY KEY,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                campeon TEXT NOT NULL,
                rol TEXT NOT NULL,
                bans JSONB DEFAULT '[]',
                aliados JSONB DEFAULT '[]',
                enemigos JSONB DEFAULT '[]',
                wr_predicho DOUBLE PRECISION,
                resultado TEXT DEFAULT 'desconocido',
                ganada BOOLEAN
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS estado_emocional (
                game_id TEXT PRIMARY KEY,
                puuid TEXT DEFAULT '',
                champion TEXT DEFAULT '',
                estado TEXT NOT NULL,
                fecha_tag TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lp_history (
                id SERIAL PRIMARY KEY,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tier TEXT NOT NULL,
                division TEXT NOT NULL,
                lp INTEGER NOT NULL,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                queue_type TEXT DEFAULT 'RANKED_SOLO_5x5',
                lp_total INTEGER DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS player_cache (
                puuid TEXT PRIMARY KEY,
                season_games JSONB,
                season_ts TIMESTAMP,
                coaching_report JSONB,
                coaching_ts TIMESTAMP
            )
            """
        )
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lp_unique ON lp_history(fecha, queue_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_emocional_estado ON estado_emocional(estado)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cache_puuid ON player_cache(puuid)")
        cur.close()
    finally:
        conn.close()
