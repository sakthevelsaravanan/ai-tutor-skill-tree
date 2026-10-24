from contextlib import contextmanager
import pymysql
from pymysql.cursors import DictCursor
from backend.config import settings

def get_connection():
    return pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        cursorclass=DictCursor,
        autocommit=True
    )

@contextmanager
def get_transaction():
    """
    Context manager providing a transactional connection with autocommit disabled.
    Automatically commits on normal completion or rolls back on exception.
    """
    conn = pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        cursorclass=DictCursor,
        autocommit=False
    )
    try:
        conn.begin()
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def execute_query(query: str, params: tuple = None) -> list:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()
    finally:
        conn.close()

def execute_one(query: str, params: tuple = None) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchone()
    finally:
        conn.close()

def execute_dml(query: str, params: tuple = None) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            conn.commit()
            return cursor.lastrowid or cursor.rowcount
    finally:
        conn.close()

def call_procedure(proc_name: str, args: tuple = ()) -> list:
    """Execute a stored procedure that returns a result set."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.callproc(proc_name, args)
            return cursor.fetchall()
    finally:
        conn.close()

