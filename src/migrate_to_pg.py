"""
Script de migración de datos: SQLite → PostgreSQL.
Uso: python -m src.migrate_to_pg

Requisitos:
  - DATABASE_URL configurado en config.json
  - Archivo SQLite lol_data.db existente en data/
  - psycopg2-binary instalado
"""
import sqlite3
import os
import sys
import json
from psycopg2.extras import execute_values

_HECHO = False

def _check_deps():
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2-binary no instalado. Ejecuta: pip install psycopg2-binary")
        sys.exit(1)


def _resolver_paths():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base, "data")
    sqlite_db = os.path.join(data_dir, "lol_data.db")
    cola_db = os.path.join(data_dir, "cola_exploracion.db")
    config_json = os.path.join(base, "config.json")

    if not os.path.exists(config_json):
        config_json = "config.json"

    return base, data_dir, sqlite_db, cola_db, config_json


def _cargar_pg_url(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    url = cfg.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL no encontrado en config.json")
        sys.exit(1)
    return url


def _conectar_pg(url):
    import psycopg2
    conn = psycopg2.connect(url)
    conn.set_session(autocommit=False)
    return conn


def migrar():
    global _HECHO
    if _HECHO:
        print("Migración ya ejecutada. No se repite por seguridad.")
        return

    _check_deps()
    import psycopg2

    base, data_dir, sqlite_db, cola_db, config_path = _resolver_paths()

    print("═" * 60)
    print("  MIGRACIÓN SQLite → PostgreSQL")
    print("═" * 60)

    if not os.path.exists(sqlite_db):
        print(f"  SQLite DB no encontrada: {sqlite_db}")
        print("  Nada que migrar.")
        _HECHO = True
        return

    size_mb = os.path.getsize(sqlite_db) / (1024 * 1024)
    print(f"  Origen  : {sqlite_db} ({size_mb:.1f} MB)")
    pg_url = _cargar_pg_url(config_path)
    # Omitir la contraseña del log
    safe_url = pg_url.split("@")[-1] if "@" in pg_url else pg_url
    print(f"  Destino : PostgreSQL ({safe_url})")

    sl_conn = sqlite3.connect(sqlite_db)
    sl_conn.row_factory = sqlite3.Row

    print("\n  Creando schema en PostgreSQL...")
    from src.db_manager import inicializar_db
    inicializar_db()

    pg_conn = _conectar_pg(pg_url)

    cur_pg = pg_conn.cursor()
    cur_pg.execute("""
        CREATE TABLE IF NOT EXISTS cola (
            puuid TEXT PRIMARY KEY,
            fecha_agregado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            procesado INTEGER DEFAULT 0
        )
    """)
    cur_pg.execute("""
        CREATE TABLE IF NOT EXISTS checkpoint (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            total_descargadas INTEGER DEFAULT 0,
            total_errores INTEGER DEFAULT 0,
            fecha_checkpoint TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur_pg.execute("SELECT 1 FROM checkpoint")
    if not cur_pg.fetchone():
        cur_pg.execute("INSERT INTO checkpoint(id, total_descargadas, total_errores) VALUES(1, 0, 0)")
    pg_conn.commit()
    cur_pg.close()
    print("    cola + checkpoint: ok")

    try:
        _migrar_matches(sl_conn, pg_conn)
        _migrar_participantes(sl_conn, pg_conn)
        _migrar_estado_emocional(sl_conn, pg_conn)
        _migrar_lp_history(sl_conn, pg_conn)
        _migrar_drafts_history(sl_conn, pg_conn)
        _migrar_cola(sl_conn, pg_conn, cola_db)
        _migrar_checkpoint(sl_conn, pg_conn, cola_db)

        print("\n" + "═" * 60)
        print("  MIGRACIÓN COMPLETADA")
        print("═" * 60)

        _HECHO = True
    finally:
        sl_conn.close()
        pg_conn.close()


def _batch_insert(cur, table, columns, rows, conflict_columns=None, batch_size=1000):
    if not rows:
        return 0
    cols = ", ".join(columns)
    template = "(" + ", ".join(["%s"] * len(columns)) + ")"
    if conflict_columns:
        conflict = f"({', '.join(conflict_columns)})"
        query = f"INSERT INTO {table} ({cols}) VALUES %s ON CONFLICT {conflict} DO NOTHING"
    else:
        query = f"INSERT INTO {table} ({cols}) VALUES %s"
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        execute_values(cur, query, batch, template=template)
        total += len(batch)
    return total


def _migrar_matches(sl, pg):
    rows = sl.execute("SELECT match_id, game_version, game_duration, patch, fecha_descarga FROM matches").fetchall()
    if not rows:
        print("    matches: 0 filas (vacía)")
        return
    cur = pg.cursor()
    n = _batch_insert(cur, "matches",
                      ["match_id", "game_version", "game_duration", "patch", "fecha_descarga"],
                      [tuple(r) for r in rows],
                      conflict_columns=["match_id"])
    pg.commit()
    cur.close()
    print(f"    matches: {n} filas")


def _migrar_participantes(sl, pg):
    rows = sl.execute("""
        SELECT match_id, champion, team_position, team, win, items, runes, spells, kills, deaths, assists
        FROM participantes
    """).fetchall()
    if not rows:
        print("    participantes: 0 filas (vacía)")
        return
    cur = pg.cursor()

    converted = []
    for r in rows:
        rlist = list(r)
        converted.append(tuple(rlist))

    n = _batch_insert(cur, "participantes",
                      ["match_id", "champion", "team_position", "team", "win", "items", "runes", "spells", "kills", "deaths", "assists"],
                      converted)
    pg.commit()
    cur.close()
    print(f"    participantes: {n} filas")


def _migrar_estado_emocional(sl, pg):
    rows = sl.execute("SELECT game_id, puuid, champion, estado, fecha_tag FROM estado_emocional").fetchall()
    if not rows:
        print("    estado_emocional: 0 filas (vacía)")
        return
    cur = pg.cursor()
    n = _batch_insert(cur, "estado_emocional",
                      ["game_id", "puuid", "champion", "estado", "fecha_tag"],
                      [tuple(r) for r in rows],
                      conflict_columns=["game_id"])
    pg.commit()
    cur.close()
    print(f"    estado_emocional: {n} filas")


def _migrar_lp_history(sl, pg):
    rows = sl.execute("SELECT fecha, queue_type, tier, division, lp, wins, losses FROM lp_history").fetchall()
    if not rows:
        print("    lp_history: 0 filas (vacía)")
        return
    cur = pg.cursor()
    n = _batch_insert(cur, "lp_history",
                      ["fecha", "queue_type", "tier", "division", "lp", "wins", "losses"],
                      [tuple(r) for r in rows],
                      conflict_columns=["fecha", "queue_type"])
    pg.commit()
    cur.close()
    print(f"    lp_history: {n} filas")


def _migrar_drafts_history(sl, pg):
    rows = sl.execute("""
        SELECT fecha, campeon, rol, bans, aliados, enemigos, wr_predicho, resultado, ganada
        FROM drafts_history
    """).fetchall()
    if not rows:
        print("    drafts_history: 0 filas (vacía)")
        return
    cur = pg.cursor()

    converted = []
    for r in rows:
        rlist = list(r)
        converted.append(tuple(rlist))

    n = _batch_insert(cur, "drafts_history",
                      ["fecha", "campeon", "rol", "bans", "aliados", "enemigos", "wr_predicho", "resultado", "ganada"],
                      converted)
    pg.commit()
    cur.close()
    print(f"    drafts_history: {n} filas")


def _migrar_cola(sl, pg, cola_db):
    if not os.path.exists(cola_db):
        print("    cola: BD de cola no existe (opcional)")
        return
    sl_cola = sqlite3.connect(cola_db)
    try:
        rows = sl_cola.execute("SELECT puuid, fecha_agregado, procesado FROM cola").fetchall()
    except Exception:
        print("    cola: 0 filas (tabla no encontrada)")
        sl_cola.close()
        return
    sl_cola.close()
    if not rows:
        print("    cola: 0 filas (vacía)")
        return
    cur = pg.cursor()
    n = _batch_insert(cur, "cola",
                      ["puuid", "fecha_agregado", "procesado"],
                      [tuple(r) for r in rows],
                      conflict_columns=["puuid"])
    pg.commit()
    cur.close()
    print(f"    cola: {n} filas")


def _migrar_checkpoint(sl, pg, cola_db):
    if not os.path.exists(cola_db):
        print("    checkpoint: BD de cola no existe (opcional)")
        return
    sl_cola = sqlite3.connect(cola_db)
    try:
        row = sl_cola.execute("SELECT total_descargadas, total_errores, fecha_checkpoint FROM checkpoint WHERE id=1").fetchone()
    except Exception:
        print("    checkpoint: tabla no encontrada")
        sl_cola.close()
        return
    sl_cola.close()
    if not row:
        print("    checkpoint: sin datos")
        return

    cur = pg.cursor()

    cur.execute("SELECT 1 FROM checkpoint WHERE id=1")
    exists = cur.fetchone() is not None

    if exists:
        cur.execute("""
            UPDATE checkpoint
            SET total_descargadas = %s, total_errores = %s, fecha_checkpoint = %s
            WHERE id = 1
        """, (row[0], row[1], row[2]))
    else:
        cur.execute("""
            INSERT INTO checkpoint (id, total_descargadas, total_errores, fecha_checkpoint)
            VALUES (1, %s, %s, %s)
        """, (row[0], row[1], row[2]))

    pg.commit()
    cur.close()
    print("    checkpoint: ok")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    migrar()
