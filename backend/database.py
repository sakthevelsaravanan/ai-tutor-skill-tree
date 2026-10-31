"""
Relational Database Layer & Connection Management.

Provides high-performance database connectivity:
1. Primary Database: MySQL 8.0 via PyMySQL with DictCursor for dictionary row mapping.
2. Fallback Engine: Seamless SQLite fallback (ai_tutor_fallback.db) for offline demonstration
   if MySQL server is unreachable.
3. Transaction Management: get_transaction context manager for ACID transactions (BEGIN, COMMIT, ROLLBACK).
4. Helper Wrappers:
   - execute_query: Returns list of matching row dicts.
   - execute_one: Returns single matching row dict or None.
   - execute_dml: Executes INSERT/UPDATE/DELETE and returns lastrowid or rowcount.
   - call_procedure: Invokes stored procedures (e.g. sp_recommend_next_topic).
"""

from contextlib import contextmanager
import pymysql
from pymysql.cursors import DictCursor
from backend.config import settings
from backend.fallback_db import get_fallback_connection

_USE_MYSQL = None

def is_mysql_active() -> bool:
    global _USE_MYSQL
    if _USE_MYSQL is None:
        try:
            conn = pymysql.connect(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                database=settings.DB_NAME,
                connect_timeout=1
            )
            conn.close()
            _USE_MYSQL = True
        except Exception:
            _USE_MYSQL = False
    return _USE_MYSQL

def get_mysql_connection():
    return pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        cursorclass=DictCursor,
        autocommit=True
    )

def get_connection():
    if is_mysql_active():
        return get_mysql_connection()
    return get_fallback_connection()

@contextmanager
def get_transaction():
    """
    Context manager providing a transactional connection with autocommit disabled.
    Automatically commits on normal completion or rolls back on exception.
    """
    if is_mysql_active():
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
    else:
        conn = get_fallback_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

def execute_query(query: str, params: tuple = None) -> list:
    if is_mysql_active():
        conn = get_mysql_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchall()
        finally:
            conn.close()
    else:
        conn = get_fallback_connection()
        try:
            cur = conn.cursor()
            sqlite_q = query.replace("%s", "?")
            cur.execute(sqlite_q, params or ())
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

def execute_one(query: str, params: tuple = None) -> dict:
    if is_mysql_active():
        conn = get_mysql_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchone()
        finally:
            conn.close()
    else:
        conn = get_fallback_connection()
        try:
            cur = conn.cursor()
            sqlite_q = query.replace("%s", "?")
            cur.execute(sqlite_q, params or ())
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

def execute_dml(query: str, params: tuple = None) -> int:
    if is_mysql_active():
        conn = get_mysql_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params or ())
                conn.commit()
                return cursor.lastrowid or cursor.rowcount
        finally:
            conn.close()
    else:
        conn = get_fallback_connection()
        try:
            cur = conn.cursor()
            sqlite_q = query.replace("%s", "?")
            cur.execute(sqlite_q, params or ())
            conn.commit()
            return cur.lastrowid or cur.rowcount
        finally:
            conn.close()

def call_procedure(proc_name: str, args: tuple = ()) -> list:
    """Execute a stored procedure that returns a result set."""
    if is_mysql_active():
        conn = get_mysql_connection()
        try:
            with conn.cursor() as cursor:
                cursor.callproc(proc_name, args)
                return cursor.fetchall()
        finally:
            conn.close()
    return []
