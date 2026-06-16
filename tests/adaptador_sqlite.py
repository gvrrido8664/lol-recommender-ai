"""
Adaptador SQLite que emula la interfaz de psycopg2 para tests sin PostgreSQL.

Traduce:
  - %s → ? (placeholders)
  - ::jsonb → (eliminado, SQLite no necesita cast)
  - RETURNING id → cursor.lastrowid
  - DictCursor → sqlite3.Row
  - fetchone/fetchall → tuplas/dicts segun cursor_factory
"""

import re
import sqlite3


def _traducir_sql(sql: str) -> str:
    sql = sql.replace("%s", "?")
    sql = sql.replace("%S", "?")
    sql = re.sub(r"::jsonb\b", "", sql)
    return sql


class AdaptadorCursor:
    def __init__(self, conn, cursor_factory=None):
        self._conn = conn
        if cursor_factory and cursor_factory.__name__ == "DictCursor":
            conn.row_factory = sqlite3.Row
        self._cur = conn.cursor()
        self._lastrowid = None

    def execute(self, sql, params=None):
        translated = _traducir_sql(sql)
        if params is None:
            self._cur.execute(translated)
        else:
            self._cur.execute(translated, params)
        self._lastrowid = self._cur.lastrowid

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        if self._conn.row_factory is sqlite3.Row:
            return dict(row)
        return row

    def fetchall(self):
        rows = self._cur.fetchall()
        if self._conn.row_factory is sqlite3.Row:
            return [dict(r) for r in rows]
        return rows

    def close(self):
        self._cur.close()

    @property
    def lastrowid(self):
        return self._lastrowid


class AdaptadorConexion:
    def __init__(self, sqlite_conn):
        self._conn = sqlite_conn
        self._closed = False

    def cursor(self, cursor_factory=None):
        return AdaptadorCursor(self._conn, cursor_factory)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if not self._closed:
            self._closed = True
