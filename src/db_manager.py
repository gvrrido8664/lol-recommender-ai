import os
import sys
import json
import time

import psycopg2
import psycopg2.errors
from psycopg2.extras import DictCursor


class ConexionDBError(Exception):
    """Error al conectar o consultar la base de datos PostgreSQL."""
    pass


def _get_base_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_data_dir():
    if getattr(sys, 'frozen', False):
        base = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'LoLRecommender')
    else:
        base = _get_base_dir()
    d = os.path.join(base, "data")
    os.makedirs(d, exist_ok=True)
    return d


BASE_DIR = _get_base_dir()
DATA_DIR = _get_data_dir()

# Mantenido para compatibilidad con código que espera estas variables.
# En modo PostgreSQL la ruta del archivo .db ya no se usa.
DB_PATH = os.path.join(DATA_DIR, "lol_data.db")


def _cargar_config():
    try:
        config_paths = ["config.json", os.path.join("..", "config.json")]
        for p in config_paths:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
    except Exception:
        pass
    return {}


def _obtener_db_url() -> str | None:
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url
    config = _cargar_config()
    url = config.get("DATABASE_URL", "")
    if url:
        return url
    return None


def obtener_conexion():
    url = _obtener_db_url()
    if not url:
        raise ConexionDBError(
            "DATABASE_URL no configurado. Agrega la URL de PostgreSQL en config.json "
            "o en la variable de entorno DATABASE_URL."
        )

    ultimo_error = None
    max_intentos = 3
    for intento in range(max_intentos):
        try:
            conn = psycopg2.connect(
                url,
                cursor_factory=DictCursor,
                connect_timeout=30,
                keepalives=1,
                keepalives_idle=60,
                keepalives_interval=10,
                keepalives_count=3,
                options='-c statement_timeout=30000',
            )
            conn.set_session(autocommit=False)
            return conn
        except psycopg2.OperationalError as e:
            ultimo_error = e
            if intento < max_intentos - 1:
                espera = 5 * (intento + 1)
                time.sleep(espera)

    raise ConexionDBError(
        f"No se pudo conectar a PostgreSQL tras {max_intentos} intentos.\n"
        f"Verifica tu conexion a internet y que el servidor este accesible.\n"
        f"Detalle: {str(ultimo_error).strip()}"
    )


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
    ]:
        cur.execute(f"""
            DO $$
            BEGIN
                ALTER TABLE {('participantes' if col != 'patch' else 'matches')}
                ADD COLUMN {col} {tipo};
            EXCEPTION
                WHEN duplicate_column THEN NULL;
            END $$;
        """)

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
        conn2 = obtener_conexion()
        conn2.execute("VACUUM")
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
               SUM(CASE WHEN p.win THEN 1 ELSE 0 END) as wins
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
