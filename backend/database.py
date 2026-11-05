"""PostgreSQL connections. Failures are explicit; no silent fallback."""
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
from backend.config import settings

def get_connection():
    return psycopg.connect(host=settings.DB_HOST, port=settings.DB_PORT,
                          user=settings.DB_USER, password=settings.DB_PASSWORD,
                          dbname=settings.DB_NAME, row_factory=dict_row, connect_timeout=5)

@contextmanager
def get_transaction():
    with get_connection() as conn:
        yield conn

def execute_query(query: str, params=None) -> list:
    with get_connection() as conn:
        return conn.execute(query, params or ()).fetchall()

def execute_one(query: str, params=None):
    with get_connection() as conn:
        return conn.execute(query, params or ()).fetchone()

def execute_dml(query: str, params=None) -> int:
    with get_connection() as conn:
        result = conn.execute(query, params or ())
        if result.description:
            row = result.fetchone()
            return next(iter(row.values())) if row else 0
        return result.rowcount
