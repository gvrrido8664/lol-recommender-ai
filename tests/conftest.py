import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_db(monkeypatch):
    """Reemplaza obtener_conexion con SQLite en memoria para tests sin PostgreSQL."""
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id TEXT PRIMARY KEY,
            game_version TEXT,
            game_duration INTEGER,
            patch TEXT,
            fecha_descarga TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS drafts_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS estado_emocional (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            puuid TEXT,
            champion TEXT,
            estado TEXT NOT NULL,
            fecha_tag TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(game_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lp_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            queue_type TEXT NOT NULL DEFAULT 'RANKED_SOLO_5x5',
            tier TEXT NOT NULL,
            division TEXT NOT NULL,
            lp INTEGER NOT NULL,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0
        )
    """)

    monkeypatch.setattr("src.db_manager.obtener_conexion", lambda: conn)
    yield conn
    conn.close()
