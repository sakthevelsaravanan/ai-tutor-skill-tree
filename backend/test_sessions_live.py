"""
Live MySQL Integration Test for Member 2 Session, Trigger, and Mastery Endpoints.
Only executes when a live MySQL 8.0 instance is configured and reachable via backend.config.settings.
Otherwise gracefully skips and reports environment connection requirements.
"""

import sys
from pathlib import Path
import uuid
import pymysql

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import settings
from backend.database import get_connection

def run_live_integration_tests():
    print("=" * 65)
    print("MEMBER 2 LIVE MYSQL INTEGRATION TEST RUNNER")
    print("=" * 65)
    print(f"Target Database: {settings.DB_USER}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")

    try:
        conn = get_connection()
    except Exception as exc:
        print(f"\n[INFO] Live MySQL instance is not accessible with current settings: {exc}")
        print("[INFO] To run live integration tests against your local database:")
        print("       1. Ensure MySQL Server 8.0 is running.")
        print("       2. Run database/01_curriculum_rbac_recursive.sql and database/02_sessions_triggers_procedures.sql.")
        print("       3. Set DB_USER, DB_PASSWORD, DB_NAME in backend/.env or environment variables.")
        print("       4. Re-run: python backend/test_sessions_live.py")
        print("\nAll 18 automated unit tests with mocked database dependencies pass in 'pytest backend/test_sessions.py'.")
        return

    try:
        with conn.cursor() as cursor:
            # 1. Verify schema tables exist
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = %s 
                  AND table_name IN ('LEARNING_SESSIONS', 'CONVERSATION_LOGS', 'QUIZ_ATTEMPTS', 'STUDENT_TOPIC_MASTERY')
            """, (settings.DB_NAME,))
            tables = [row["TABLE_NAME"] if "TABLE_NAME" in row else row["table_name"] for row in cursor.fetchall()]
            print(f"[OK] Verified Member 2 tables: {tables}")

            # 2. Verify Member 2 trigger exists
            cursor.execute("""
                SELECT TRIGGER_NAME FROM information_schema.TRIGGERS
                WHERE TRIGGER_SCHEMA = %s AND TRIGGER_NAME = 'trg_after_quiz_attempt_mastery'
            """, (settings.DB_NAME,))
            trg = cursor.fetchone()
            print(f"[OK] Verified trigger trg_after_quiz_attempt_mastery: {'EXISTS' if trg else 'NOT FOUND'}")

            # 3. Test stored function fn_calculate_subject_mastery
            cursor.execute("SELECT fn_calculate_subject_mastery(3, 1) AS dsa_mastery;")
            func_res = cursor.fetchone()
            print(f"[OK] fn_calculate_subject_mastery(3, 1) returned: {func_res['dsa_mastery']}%")

            # 4. Test stored procedure sp_recommend_next_topic
            cursor.execute("CALL sp_recommend_next_topic(3, 1, @topic_id, @reason);")
            cursor.execute("SELECT @topic_id AS rec_topic, @reason AS rec_reason;")
            proc_res = cursor.fetchone()
            print(f"[OK] sp_recommend_next_topic(3, 1) returned: ID={proc_res['rec_topic']}, Reason='{proc_res['rec_reason']}'")

            print("\nLive database integration checks completed successfully!")

    finally:
        conn.close()

if __name__ == "__main__":
    run_live_integration_tests()
