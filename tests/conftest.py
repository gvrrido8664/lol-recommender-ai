import os
import sys
import sqlite3

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.adaptador_sqlite import AdaptadorConexion


@pytest.fixture
def mock_db(monkeypatch):
    """Reemplaza obtener_conexion con SQLite en memoria con adaptador psycopg2-compatible."""
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
            fecha TEXT DEFAULT CURRENT_TIMESTAMP,
            campeon TEXT NOT NULL,
            rol TEXT NOT NULL,
            bans TEXT DEFAULT '[]',
            aliados TEXT DEFAULT '[]',
            enemigos TEXT DEFAULT '[]',
            wr_predicho REAL,
            resultado TEXT DEFAULT 'desconocido',
            ganada INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS estado_emocional (
            game_id TEXT PRIMARY KEY,
            puuid TEXT DEFAULT '',
            champion TEXT DEFAULT '',
            estado TEXT NOT NULL,
            fecha_tag TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lp_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT DEFAULT CURRENT_TIMESTAMP,
            queue_type TEXT DEFAULT 'RANKED_SOLO_5x5',
            tier TEXT NOT NULL,
            division TEXT NOT NULL,
            lp INTEGER NOT NULL,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            UNIQUE(fecha, queue_type)
        )
    """)

    adaptador = AdaptadorConexion(conn)
    monkeypatch.setattr("src.db_manager.obtener_conexion", lambda: adaptador)
    yield adaptador
    adaptador.close()
    conn.close()
