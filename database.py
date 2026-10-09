import os
import time

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    class PostgresCursorWrapper:
        def __init__(self, cursor):
            self.cursor = cursor

        def execute(self, query, params=None):
            query_pg = query.replace("?", "%s")
            if params is not None:
                return self.cursor.execute(query_pg, params)
            return self.cursor.execute(query_pg)

        def fetchone(self):
            row = self.cursor.fetchone()
            return dict(row) if row else None

        def fetchall(self):
            rows = self.cursor.fetchall()
            return [dict(r) for r in rows] if rows else []

    class PostgresWrapper:
        def __init__(self, conn):
            self.conn = conn

        def cursor(self):
            return PostgresCursorWrapper(self.conn.cursor(cursor_factory=RealDictCursor))

        def commit(self):
            self.conn.commit()

        def close(self):
            self.conn.close()

    def get_connection():
        conn = psycopg2.connect(DATABASE_URL)
        return PostgresWrapper(conn)

    def init_db():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_verified INTEGER DEFAULT 1,
            verification_code TEXT,
            sub_expires_at BIGINT DEFAULT 0,
            hwid TEXT DEFAULT NULL,
            is_banned INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            created_at BIGINT NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS license_keys (
            id SERIAL PRIMARY KEY,
            key_code TEXT UNIQUE NOT NULL,
            days INTEGER NOT NULL,
            is_used INTEGER DEFAULT 0,
            used_by TEXT DEFAULT NULL,
            used_at BIGINT DEFAULT NULL,
            created_at BIGINT NOT NULL
        )
        """)
        conn.commit()
        conn.close()

else:
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), "marsclient.db")

    def get_connection():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_verified INTEGER DEFAULT 1,
            verification_code TEXT,
            sub_expires_at INTEGER DEFAULT 0,
            hwid TEXT DEFAULT NULL,
            is_banned INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS license_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_code TEXT UNIQUE NOT NULL,
            days INTEGER NOT NULL,
            is_used INTEGER DEFAULT 0,
            used_by TEXT DEFAULT NULL,
            used_at INTEGER DEFAULT NULL,
            created_at INTEGER NOT NULL
        )
        """)
        conn.commit()
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
