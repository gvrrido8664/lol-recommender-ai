import sqlite3
import os
import sys

def _get_base_dir():
    """Resuelve la raíz del proyecto tanto en desarrollo como en .exe de PyInstaller."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _get_data_dir():
    """Devuelve un directorio de datos escribible.
    En desarrollo: data/ junto al código.
    En .exe frozen: %APPDATA%/LoLRecommender/data para que sea escribible."""
    if getattr(sys, 'frozen', False):
        base = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'LoLRecommender')
    else:
        base = _get_base_dir()
    d = os.path.join(base, "data")
    os.makedirs(d, exist_ok=True)
    return d

BASE_DIR = _get_base_dir()
DATA_DIR = _get_data_dir()
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

    # ─── TABLA DE ESTADO EMOCIONAL (NEXUS) ───
    cur.execute("""
        CREATE TABLE IF NOT EXISTS estado_emocional (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    print("✅ Base de datos 'lol_data.db' operativa y actualizada con KDA, Parches, Hechizos y Motor Emocional.")

def limpiar_base_de_datos():
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("DELETE FROM participantes")
    cur.execute("DELETE FROM matches")
    conn.commit()
    conn.close()
    print("🗑️ Base de datos limpiada.")

def purgar_parches_antiguos(parche_actual: str):
    """
    Elimina todas las partidas de parches anteriores al actual.
    Riot formatea versiones como '16.11.1' o '16.11.xxx'.
    Esta función borra todo lo que NO empiece con 'parche_actual.'.
    Luego ejecuta VACUUM para recuperar el espacio en disco.
    
    Args:
        parche_actual: str como '16.11' (mayor.menor)
    
    Returns:
        tuple[int, float]: (partidas_eliminadas, tamaño_mb_despues)
    """
    conn = obtener_conexion()
    cur = conn.cursor()
    
    # Contar antes
    cur.execute("SELECT COUNT(*) FROM matches")
    total_antes = cur.fetchone()[0]
    
    # Obtener tamaño antes
    try:
        size_antes = os.path.getsize(DB_PATH) / (1024 * 1024)
    except:
        size_antes = 0
    
    # Eliminar partidas cuyo game_version NO empieza con el parche actual
    # Ej: parche_actual='16.11' → borra versiones como '16.10.x', '14.4.x', etc.
    # El ON DELETE CASCADE borra automáticamente los participantes asociados.
    cur.execute("""
        DELETE FROM matches 
        WHERE game_version NOT LIKE ? 
           OR game_version IS NULL
    """, (f"{parche_actual}.%",))
    eliminadas = cur.rowcount
    conn.commit()
    
    # Cerrar conexión antes de VACUUM (SQLite lo requiere en ciertos modos)
    conn.close()
    
    # VACUUM: desfragmenta y recupera espacio en disco
    # Se ejecuta en conexión separada sin row_factory para evitar conflictos
    if eliminadas > 0:
        print(f"  [PURGA] {eliminadas:,} partidas antiguas eliminadas. Compactando base de datos...")
        conn2 = sqlite3.connect(DB_PATH)
        conn2.execute("PRAGMA journal_mode=WAL")
        conn2.execute("VACUUM")
        conn2.close()
    
    # Tamaño después
    try:
        size_despues = os.path.getsize(DB_PATH) / (1024 * 1024)
    except:
        size_despues = 0
    
    ahorro = size_antes - size_despues
    print(f"  [PURGA] Base de datos: {total_antes:,} -> {total_antes - eliminadas:,} partidas")
    print(f"  [PURGA] Disco: {size_antes:.1f} MB -> {size_despues:.1f} MB (ahorro: {ahorro:.1f} MB)")
    
    return eliminadas, size_despues

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

# ═══════════════════════════════════════════════════════════════
# MOTOR EMOCIONAL (NEXUS)
# ═══════════════════════════════════════════════════════════════

def etiquetar_estado_emocional(game_id: str, estado: str, puuid: str = "", champion: str = ""):
    """Guarda o actualiza el estado emocional de una partida."""
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO estado_emocional (game_id, puuid, champion, estado)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(game_id) DO UPDATE SET estado=excluded.estado, fecha_tag=CURRENT_TIMESTAMP
    """, (str(game_id), puuid, champion, estado))
    conn.commit()
    conn.close()

def obtener_estado_emocional(game_id: str) -> str | None:
    """Obtiene el estado emocional de una partida específica."""
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM estado_emocional WHERE game_id=?", (str(game_id),))
    row = cur.fetchone()
    conn.close()
    return row["estado"] if row else None

def obtener_estadisticas_emocionales() -> dict:
    """Devuelve estadísticas agregadas del estado emocional vs winrate (desde matches en BD).
    Retorna un dict con {estado: {'partidas': N, 'wins': N, 'wr': %}}."""
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

if __name__ == "__main__":
    inicializar_db()