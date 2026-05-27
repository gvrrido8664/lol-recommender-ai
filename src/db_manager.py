import sqlite3
import os
import sys

def _get_base_dir():
    """Resuelve la raíz del proyecto tanto en desarrollo como en .exe de PyInstaller."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = _get_base_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "lol_data.db")

def obtener_conexion():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;") 
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")  
    conn.row_factory = sqlite3.Row 
    return conn

def inicializar_db():
    conn = obtener_conexion()
    cur = conn.cursor()

    print("🏗️ Inicializando arquitectura de la base de datos...")

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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # Migración de estructura segura (si la BD ya existía, le agrega las columnas nuevas sin borrar los datos)
    try:
        cur.execute("ALTER TABLE matches ADD COLUMN patch TEXT")
    except sqlite3.OperationalError: pass
    
    try:
        cur.execute("ALTER TABLE participantes ADD COLUMN runes TEXT")
    except sqlite3.OperationalError: pass

    try:
        cur.execute("ALTER TABLE participantes ADD COLUMN spells TEXT")
    except sqlite3.OperationalError: pass

    try:
        cur.execute("ALTER TABLE participantes ADD COLUMN kills INTEGER")
    except sqlite3.OperationalError: pass

    try:
        cur.execute("ALTER TABLE participantes ADD COLUMN deaths INTEGER")
    except sqlite3.OperationalError: pass

    try:
        cur.execute("ALTER TABLE participantes ADD COLUMN assists INTEGER")
    except sqlite3.OperationalError: pass


    cur.execute("CREATE INDEX IF NOT EXISTS idx_champion ON participantes(champion);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_position ON participantes(team_position);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_match_id ON participantes(match_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_win ON participantes(win);")

    conn.commit()
    conn.close()
    print("✅ Base de datos 'lol_data.db' operativa y actualizada con KDA, Parches y Hechizos.")

def limpiar_base_de_datos():
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("DELETE FROM participantes")
    cur.execute("DELETE FROM matches")
    conn.commit()
    conn.close()
    print("🗑️ Base de datos limpiada.")

def compactar_base_de_datos():
    """Reduce el tamaño del archivo .db eliminando espacio vacío interno (VACUUM).
       También limpia datos antiguos que ya no sirven para entrenar."""
    conn = obtener_conexion()
    cur = conn.cursor()
    
    # 1. Eliminar partidas sin participantes (huérfanas)
    cur.execute("""
        DELETE FROM matches WHERE match_id NOT IN (
            SELECT DISTINCT match_id FROM participantes
        )
    """)
    huerfanas = cur.rowcount
    
    # 2. Eliminar partidas muy antiguas (>6 meses) si hay más de 5000
    cur.execute("SELECT COUNT(*) FROM matches")
    total = cur.fetchone()[0]
    if total > 5000:
        cur.execute("""
            DELETE FROM matches WHERE match_id IN (
                SELECT match_id FROM matches 
                WHERE fecha_descarga < datetime('now', '-6 months')
                ORDER BY fecha_descarga ASC
                LIMIT ?
            )
        """, (total - 5000,))
        antiguas = cur.rowcount
    else:
        antiguas = 0
    
    conn.commit()
    
    # 3. Compactar archivo (recupera espacio libre)
    print(f"  🧹 Huérfanas eliminadas: {huerfanas}")
    print(f"  🕒 Antiguas eliminadas: {antiguas}")
    print(f"  📦 Compactando archivo...")
    cur.execute("VACUUM")
    conn.close()
    
    # Mostrar reducción
    tamaño_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    print(f"✅ Base de datos compactada: {tamaño_mb:.2f} MB")

if __name__ == "__main__":
    inicializar_db()