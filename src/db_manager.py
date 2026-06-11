import os
import sys
import json
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2.pool import SimpleConnectionPool

def _get_base_dir():
    """Resuelve la raíz del proyecto tanto en desarrollo como en .exe de PyInstaller."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _get_data_dir():
    """Devuelve un directorio de datos escribible."""
    if getattr(sys, 'frozen', False):
        base = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'LoLRecommender')
    else:
        base = _get_base_dir()
    d = os.path.join(base, "data")
    os.makedirs(d, exist_ok=True)
    return d

BASE_DIR = _get_base_dir()
DATA_DIR = _get_data_dir()
DB_PATH = os.path.join(DATA_DIR, "lol_data.db")  # Aún lo usamos por compatibilidad en algunas rutas

_pool = None

def _get_pool():
    global _pool
    if _pool is None:
        try:
            config_paths = [os.path.join(BASE_DIR, "config.json"), os.path.join(BASE_DIR, "..", "config.json")]
            db_url = ""
            for p in config_paths:
                if os.path.exists(p):
                    with open(p, "r", encoding="utf-8") as f:
                        config = json.load(f)
                        db_url = config.get("DATABASE_URL", "")
                        break
            _pool = SimpleConnectionPool(1, 20, db_url)
        except Exception as e:
            print("Error initializing connection pool:", e)
    return _pool

class PooledConnection:
    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool

    def cursor(self, *args, **kwargs):
        kwargs['cursor_factory'] = DictCursor
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._pool.putconn(self._conn)

def obtener_conexion():
    pool = _get_pool()
    if pool:
        conn = pool.getconn()
        return PooledConnection(conn, pool)
    raise Exception("Could not get a connection from the pool.")

def _db_tiene_datos():
    """Devuelve True si la BD tiene datos reales."""
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
            match_id TEXT REFERENCES matches (match_id) ON DELETE CASCADE,
            champion TEXT NOT NULL,
            team_position TEXT NOT NULL,
            team INTEGER NOT NULL,
            win INTEGER NOT NULL,
            items TEXT,
            runes TEXT,
            spells TEXT,
            kills INTEGER,
            deaths INTEGER,
            assists INTEGER
        )
    """)
    conn.commit()

    # Migración de estructura segura
    def safe_alter(query):
        try:
            cur.execute(query)
            conn.commit()
        except Exception:
            conn.rollback()

    safe_alter("ALTER TABLE matches ADD COLUMN patch TEXT")
    safe_alter("ALTER TABLE participantes ADD COLUMN runes TEXT")
    safe_alter("ALTER TABLE participantes ADD COLUMN spells TEXT")
    safe_alter("ALTER TABLE participantes ADD COLUMN kills INTEGER")
    safe_alter("ALTER TABLE participantes ADD COLUMN deaths INTEGER")
    safe_alter("ALTER TABLE participantes ADD COLUMN assists INTEGER")

    # Índices
    safe_alter("CREATE INDEX idx_champion ON participantes(champion);")
    safe_alter("CREATE INDEX idx_position ON participantes(team_position);")
    safe_alter("CREATE INDEX idx_match_id ON participantes(match_id);")
    safe_alter("CREATE INDEX idx_win ON participantes(win);")
    safe_alter("CREATE INDEX idx_champ_pos ON participantes(champion, team_position);")

    # ─── TABLA DE ESTADO EMOCIONAL (NEXUS) ───
    cur.execute("""
        CREATE TABLE IF NOT EXISTS estado_emocional (
            id SERIAL PRIMARY KEY,
            game_id TEXT UNIQUE NOT NULL,
            puuid TEXT,
            champion TEXT,
            estado TEXT NOT NULL CHECK(estado IN ('Concentrado', 'Normal', 'Tilted', 'Cansado')),
            fecha_tag TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    safe_alter("CREATE INDEX idx_emocional_estado ON estado_emocional(estado);")
    safe_alter("CREATE INDEX idx_emocional_game ON estado_emocional(game_id);")

    conn.close()
    print("[OK] Base de datos 'nexus_d0ro' operativa y actualizada con KDA, Parches, Hechizos y Motor Emocional.")

def limpiar_base_de_datos():
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("DELETE FROM participantes")
    cur.execute("DELETE FROM matches")
    conn.commit()
    conn.close()
    print("🗑️ Base de datos limpiada.")

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
        print(f"  [PURGA] {eliminadas:,} partidas antiguas eliminadas. Compactando base de datos...")
        conn2 = obtener_conexion()
        conn2._conn.autocommit = True
        try:
            conn2.cursor().execute("VACUUM")
        except Exception as e:
            print("Vacuum error:", e)
        conn2._conn.autocommit = False
        conn2.close()
    
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
    conn.close()
    
    print(f"  🧹 Huérfanas eliminadas: {huerfanas}")
    print(f"  🕒 Antiguas eliminadas: {antiguas}")
    print(f"  📦 Compactando archivo...")
    
    conn2 = obtener_conexion()
    conn2._conn.autocommit = True
    try:
        conn2.cursor().execute("VACUUM")
    except Exception as e:
        pass
    conn2._conn.autocommit = False
    conn2.close()
    print(f"✅ Base de datos compactada.")

# ═══════════════════════════════════════════════════════════════
# MOTOR EMOCIONAL (NEXUS)
# ═══════════════════════════════════════════════════════════════

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
               SUM(CASE WHEN p.win=1 THEN 1 ELSE 0 END) as wins
        FROM estado_emocional ee
        JOIN participantes p ON p.match_id = ee.game_id AND p.champion = ee.champion
        GROUP BY ee.estado
    """)
    stats = {}
    for row in cur.fetchall():
        estado = row["estado"]
        partidas = row["partidas"]
        wins = row["wins"] or 0
        stats[estado] = {
            "partidas": partidas,
            "wins": wins,
            "wr": round(wins / partidas * 100, 1) if partidas > 0 else 0
        }
    conn.close()
    return stats

# ═══════════════════════════════════════════════════════════════
# TRACKING DE LP / MMR
# ═══════════════════════════════════════════════════════════════

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
            losses INTEGER DEFAULT 0,
            UNIQUE(fecha, queue_type)
        )
    """)
    conn.commit()
    # Eliminamos recreación de índices manual ya que pusimos UNIQUE arriba
    conn.close()

try:
    _crear_tabla_lp_history()
except Exception:
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
        ON CONFLICT (fecha, queue_type) DO UPDATE SET 
            tier=EXCLUDED.tier, division=EXCLUDED.division, 
            lp=EXCLUDED.lp, wins=EXCLUDED.wins, losses=EXCLUDED.losses
    """, (fecha, queue_type, tier.upper(), division.upper(), int(lp), int(wins), int(losses)))
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
        WHERE queue_type=%s AND fecha >= CAST(CURRENT_DATE - CAST(%s || ' days' AS INTERVAL) AS TEXT)
        ORDER BY fecha ASC
    """, (queue_type, dias))
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
except Exception:
    pass

def guardar_draft(campeon, rol, bans, aliados, enemigos, wr_predicho):
    from datetime import date
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO drafts_history (fecha, campeon, rol, bans, aliados, enemigos, wr_predicho)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
    """, (str(date.today()), campeon, rol, json.dumps(bans), json.dumps(aliados), json.dumps(enemigos), wr_predicho))
    draft_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return draft_id

def completar_draft_resultado(fecha, ganada):
    conn = obtener_conexion()
    cur = conn.cursor()
    if ganada is None:
        cur.execute("""
            UPDATE drafts_history SET resultado = 'completada'
            WHERE id = (
                SELECT id FROM drafts_history
                WHERE fecha = %s AND resultado = 'pendiente'
                ORDER BY id DESC LIMIT 1
            )
        """, (fecha,))
    else:
        cur.execute("""
            UPDATE drafts_history SET resultado = %s, ganada = %s
            WHERE id = (
                SELECT id FROM drafts_history
                WHERE fecha = %s AND resultado = 'pendiente'
                ORDER BY id DESC LIMIT 1
            )
        """, ("victoria" if ganada else "derrota", 1 if ganada else 0, fecha))
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

if __name__ == "__main__":
    inicializar_db()