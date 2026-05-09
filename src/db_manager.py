import sqlite3
import os

# Definimos la ruta de la base de datos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "lol_data.db")

def obtener_conexion():
    """Crea y retorna una conexión optimizada a la base de datos."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    
    # Optimizaciones de rendimiento para SQLite
    conn.execute("PRAGMA journal_mode=WAL;") # Permite lectura y escritura simultánea
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")  # Activa las relaciones de llaves foráneas
    
    # Para poder acceder a las columnas por nombre en lugar de índice
    conn.row_factory = sqlite3.Row 
    return conn

def inicializar_db():
    """Crea la estructura de tablas e índices si no existen."""
    conn = obtener_conexion()
    cur = conn.cursor()

    print("🏗️ Inicializando arquitectura de la base de datos...")

    # Tabla 1: Información general de la partida
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id TEXT PRIMARY KEY,
            game_version TEXT,
            game_duration INTEGER,
            fecha_descarga TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabla 2: Información detallada de los 10 jugadores de cada partida
    cur.execute("""
        CREATE TABLE IF NOT EXISTS participantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT,
            champion TEXT NOT NULL,
            team_position TEXT NOT NULL,
            team INTEGER NOT NULL,
            win INTEGER NOT NULL,
            items TEXT,
            FOREIGN KEY (match_id) REFERENCES matches (match_id) ON DELETE CASCADE
        )
    """)

    # 🚀 ÍNDICES DE RENDIMIENTO 🚀
    # Estos índices son el secreto para que los cálculos de Winrate y Counters sean instantáneos
    cur.execute("CREATE INDEX IF NOT EXISTS idx_champion ON participantes(champion);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_position ON participantes(team_position);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_match_id ON participantes(match_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_win ON participantes(win);")

    conn.commit()
    conn.close()
    print("✅ Base de datos 'lol_data.db' creada y optimizada correctamente.")

def limpiar_base_de_datos():
    """(Opcional) Borra todos los registros en caso de necesitar un reinicio limpio."""
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("DELETE FROM participantes")
    cur.execute("DELETE FROM matches")
    conn.commit()
    conn.close()
    print("🗑️ Base de datos limpiada.")

# Para probar la creación de la base de datos directamente
if __name__ == "__main__":
    inicializar_db()