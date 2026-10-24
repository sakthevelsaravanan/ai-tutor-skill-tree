"""
Unit tests for Member 2 Session, Conversation, and Quiz Mastery Endpoints.
Uses FastAPI TestClient and isolated database mocks to verify all 5 required endpoints,
error handling, validation constraints, and database transaction/rollback mechanics.
"""

import sys
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch, MagicMock

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

# ------------------------------------------------------------
# 1. POST /api/sessions/start
# ------------------------------------------------------------

def test_start_session_success():
    """Verify session creation returns 201, UUID session_id, and correct default stage."""
    mock_user = {"user_id": 3, "full_name": "Alice Student", "role": "student"}
    mock_subject = {"subject_id": 1, "subject_name": "Data Structures & Algorithms"}
    mock_topic = {"topic_id": 105, "subject_id": 1, "topic_name": "Binary Search Trees"}

    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

    def mock_execute_one_fn(query, params=()):
        if "FROM USERS" in query:
            return mock_user
        if "FROM SUBJECTS" in query:
            return mock_subject
        if "FROM TOPICS" in query:
            return mock_topic
        return None

    fake_session_row = {
        "session_id": "test-uuid-1234",
        "user_id": 3,
        "subject_id": 1,
        "current_topic_id": 105,
        "current_stage": "topic",
        "quiz_difficulty": 1,
        "confused_count": 0,
        "started_at": "2026-10-24T10:00:00"
    }
    fake_cursor.fetchone.return_value = fake_session_row

    with patch("backend.routers.sessions.execute_one", side_effect=mock_execute_one_fn), \
         patch("backend.routers.sessions.get_transaction") as mock_tx:
        mock_tx.return_value.__enter__.return_value = fake_conn

        response = client.post("/api/sessions/start", json={
            "user_id": 3,
            "subject_id": 1,
            "current_topic_id": 105,
            "quiz_difficulty": 1
        })

    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data
    assert data["user_id"] == 3
    assert data["subject_id"] == 1
    assert data["current_topic_id"] == 105
    assert data["current_stage"] == "topic"
    assert data["quiz_difficulty"] == 1
    assert data["confused_count"] == 0

def test_start_session_user_not_found():
    """Verify 404 when referenced user does not exist."""
    with patch("backend.routers.sessions.execute_one", return_value=None):
        response = client.post("/api/sessions/start", json={
            "user_id": 9999,
            "subject_id": 1
        })
    assert response.status_code == 404
    assert "User with ID 9999" in response.json()["detail"]

def test_start_session_subject_not_found():
    """Verify 404 when referenced subject does not exist."""
    def mock_db(query, params=()):
        if "FROM USERS" in query:
            return {"user_id": 3}
        return None

    with patch("backend.routers.sessions.execute_one", side_effect=mock_db):
        response = client.post("/api/sessions/start", json={
            "user_id": 3,
            "subject_id": 9999
        })
    assert response.status_code == 404
    assert "Subject with ID 9999" in response.json()["detail"]

def test_start_session_invalid_topic_for_subject():
    """Verify 400 when topic belongs to a different subject domain."""
    def mock_db(query, params=()):
        if "FROM USERS" in query:
            return {"user_id": 3}
        if "FROM SUBJECTS" in query:
            return {"subject_id": 1, "subject_name": "DSA"}
        if "FROM TOPICS" in query:
            return {"topic_id": 201, "subject_id": 2, "topic_name": "CMOS Inverter"}
        return None

    with patch("backend.routers.sessions.execute_one", side_effect=mock_db):
        response = client.post("/api/sessions/start", json={
            "user_id": 3,
            "subject_id": 1,
            "current_topic_id": 201
        })
    assert response.status_code == 400
    assert "does not belong to subject 1" in response.json()["detail"]

# ------------------------------------------------------------
# 2. POST /api/sessions/message
# ------------------------------------------------------------

def test_save_message_success():
    """Verify saving conversation message persists with correct role and returns 201."""
    mock_session = {
        "session_id": "test-uuid-1234",
        "current_topic_id": 105,
        "current_stage": "explore"
    }

    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor
    fake_cursor.lastrowid = 42
    fake_cursor.fetchone.return_value = {
        "log_id": 42,
        "session_id": "test-uuid-1234",
        "topic_id": 105,
        "role": "user",
        "stage": "explore",
        "content": "How does deletion work in a BST?",
        "created_at": "2026-10-24T10:05:00"
    }

    with patch("backend.routers.sessions.execute_one", return_value=mock_session), \
         patch("backend.routers.sessions.get_transaction") as mock_tx:
        mock_tx.return_value.__enter__.return_value = fake_conn

        response = client.post("/api/sessions/message", json={
            "session_id": "test-uuid-1234",
            "content": "How does deletion work in a BST?",
            "role": "user"
        })

    assert response.status_code == 201
    data = response.json()
    assert data["log_id"] == 42
    assert data["session_id"] == "test-uuid-1234"
    assert data["stage"] == "explore"
    assert data["role"] == "user"
    assert data["content"] == "How does deletion work in a BST?"

def test_save_message_session_not_found():
    """Verify 404 when referencing a nonexistent session."""
    with patch("backend.routers.sessions.execute_one", return_value=None):
        response = client.post("/api/sessions/message", json={
            "session_id": "nonexistent-session",
            "content": "Hello AI tutor"
        })
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

def test_save_message_blank_content():
    """Verify 400 when message content is blank or whitespace."""
    mock_session = {"session_id": "test-uuid-1234", "current_topic_id": 101, "current_stage": "topic"}
    with patch("backend.routers.sessions.execute_one", return_value=mock_session):
        response = client.post("/api/sessions/message", json={
            "session_id": "test-uuid-1234",
            "content": "   "
        })
    assert response.status_code == 400
    assert "blank" in response.json()["detail"]

# ------------------------------------------------------------
# 3. POST /api/sessions/quiz-attempt
# ------------------------------------------------------------

def test_record_quiz_attempt_mastered():
    """
    Verify recording a high-score attempt updates stage to explore,
    resets confused_count, and returns MASTERED status.
    """
    mock_session = {
        "session_id": "test-uuid-1234",
        "user_id": 3,
        "subject_id": 1,
        "current_topic_id": 105,
        "quiz_difficulty": 2,
        "confused_count": 1,
        "current_stage": "quiz"
    }

    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor
    fake_cursor.lastrowid = 101

    # Simulate trigger result and attempted_at timestamp
    fake_cursor.fetchone.side_effect = [
        {"mastery_status": "MASTERED"},
        {"attempted_at": MagicMock(isoformat=lambda: "2026-10-24T10:10:00")}
    ]

    with patch("backend.routers.sessions.execute_one", side_effect=[mock_session, {"user_id": 3}, {"topic_id": 105}]), \
         patch("backend.routers.sessions.get_transaction") as mock_tx:
        mock_tx.return_value.__enter__.return_value = fake_conn

        response = client.post("/api/sessions/quiz-attempt", json={
            "session_id": "test-uuid-1234",
            "mcq_score": 3,
            "check_score": 5,
            "verdict": "UNDERSTOOD"
        })

    assert response.status_code == 201
    data = response.json()
    assert data["attempt_id"] == 101
    assert data["verdict"] == "UNDERSTOOD"
    assert data["next_stage"] == "explore"
    assert data["mastery_status"] == "MASTERED"

def test_record_quiz_attempt_confused():
    """
    Verify recording a confused attempt advances stage to clarify
    and reflects trigger updating status to NEEDS_PREREQ_REVIEW.
    """
    mock_session = {
        "session_id": "test-uuid-1234",
        "user_id": 3,
        "subject_id": 1,
        "current_topic_id": 105,
        "quiz_difficulty": 2,
        "confused_count": 0,
        "current_stage": "quiz"
    }

    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor
    fake_cursor.lastrowid = 102

    fake_cursor.fetchone.side_effect = [
        {"mastery_status": "NEEDS_PREREQ_REVIEW"},
        {"attempted_at": MagicMock(isoformat=lambda: "2026-10-24T10:15:00")}
    ]

    with patch("backend.routers.sessions.execute_one", side_effect=[mock_session, {"user_id": 3}, {"topic_id": 105}]), \
         patch("backend.routers.sessions.get_transaction") as mock_tx:
        mock_tx.return_value.__enter__.return_value = fake_conn

        response = client.post("/api/sessions/quiz-attempt", json={
            "session_id": "test-uuid-1234",
            "mcq_score": 0,
            "check_score": 1,
            "verdict": "CONFUSED"
        })

    assert response.status_code == 201
    data = response.json()
    assert data["attempt_id"] == 102
    assert data["verdict"] == "CONFUSED"
    assert data["next_stage"] == "clarify"
    assert data["mastery_status"] == "NEEDS_PREREQ_REVIEW"

def test_record_quiz_attempt_invalid_scores():
    """Verify validation errors when mcq_score or check_score violate boundary constraints."""
    # mcq_score > 3
    resp = client.post("/api/sessions/quiz-attempt", json={
        "session_id": "test-uuid-1234",
        "mcq_score": 4
    })
    assert resp.status_code == 422

    # check_score < 1
    resp2 = client.post("/api/sessions/quiz-attempt", json={
        "session_id": "test-uuid-1234",
        "check_score": 0
    })
    assert resp2.status_code == 422

# ------------------------------------------------------------
# 4. GET /api/sessions/recommend/{user_id}/{subject_id}
# ------------------------------------------------------------

def test_recommend_next_topic_found():
    """Verify stored procedure sp_recommend_next_topic returns topic recommendation."""
    mock_user = {"user_id": 3, "full_name": "Alice"}
    mock_subject = {"subject_id": 1, "subject_name": "DSA"}
    mock_topic = {
        "topic_id": 105,
        "topic_name": "Binary Search Trees",
        "difficulty_level": 2,
        "visual_type": "iframe",
        "embed_url": "https://visualgo.net/en/bst"
    }

    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor
    fake_cursor.fetchone.return_value = {
        "recommended_topic_id": 105,
        "recommendation_reason": "Continuity: Resuming in-progress topic."
    }

    def mock_db(query, params=()):
        if "FROM USERS" in query:
            return mock_user
        if "FROM SUBJECTS" in query:
            return mock_subject
        if "FROM TOPICS" in query:
            return mock_topic
        return None

    with patch("backend.routers.sessions.execute_one", side_effect=mock_db), \
         patch("backend.routers.sessions.get_connection", return_value=fake_conn):

        response = client.get("/api/sessions/recommend/3/1")

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 3
    assert data["subject_id"] == 1
    assert data["recommended_topic_id"] == 105
    assert "Continuity" in data["recommendation_reason"]
    assert data["topic"]["topic_name"] == "Binary Search Trees"

def test_recommend_next_topic_completed():
    """Verify recommendation when all topics are mastered returns null topic and complete message."""
    mock_user = {"user_id": 3, "full_name": "Alice"}
    mock_subject = {"subject_id": 1, "subject_name": "DSA"}

    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor
    fake_cursor.fetchone.return_value = {
        "recommended_topic_id": None,
        "recommendation_reason": "Complete: No eligible unmastered topic found."
    }

    def mock_db(query, params=()):
        if "FROM USERS" in query:
            return mock_user
        if "FROM SUBJECTS" in query:
            return mock_subject
        return None

    with patch("backend.routers.sessions.execute_one", side_effect=mock_db), \
         patch("backend.routers.sessions.get_connection", return_value=fake_conn):

        response = client.get("/api/sessions/recommend/3/1")

    assert response.status_code == 200
    data = response.json()
    assert data["recommended_topic_id"] is None
    assert "Complete" in data["recommendation_reason"]
    assert data["topic"] is None

# ------------------------------------------------------------
# 5. GET /api/sessions/mastery/{user_id}/{subject_id}
# ------------------------------------------------------------

def test_calculate_subject_mastery_success():
    """Verify stored function fn_calculate_subject_mastery returns calculated percentage."""
    mock_user = {"user_id": 3, "full_name": "Alice"}
    mock_subject = {"subject_id": 1, "subject_name": "Data Structures & Algorithms"}

    def mock_db(query, params=()):
        if "FROM USERS" in query:
            return mock_user
        if "FROM SUBJECTS" in query:
            return mock_subject
        if "fn_calculate_subject_mastery" in query:
            return {"mastery_percentage": Decimal("66.67")}
        return None

    with patch("backend.routers.sessions.execute_one", side_effect=mock_db):
        response = client.get("/api/sessions/mastery/3/1")

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 3
    assert data["subject_id"] == 1
    assert data["subject_name"] == "Data Structures & Algorithms"
    assert data["mastery_percentage"] == 66.67

def test_calculate_subject_mastery_user_not_found():
    """Verify 404 when querying mastery for nonexistent user."""
    with patch("backend.routers.sessions.execute_one", return_value=None):
        response = client.get("/api/sessions/mastery/999/1")
    assert response.status_code == 404
    assert "User with ID 999" in response.json()["detail"]

# ------------------------------------------------------------
# 6. Existing Routes Integrity Check
# ------------------------------------------------------------

def test_existing_system_routes_preserved():
    """Verify existing root, health, and auth endpoints function without regression."""
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    root_data = root_resp.json()
    assert root_data["status"] == "online"
    assert "sessions" in root_data["endpoints"]

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json() == {"status": "healthy"}

    roles_resp = client.get("/api/auth/roles")
    assert roles_resp.status_code == 200
    roles_data = roles_resp.json()
    assert "student" in roles_data["roles"]
    assert "instructor" in roles_data["roles"]

# ------------------------------------------------------------
# 7. Database Error Handling & Rollback
# ------------------------------------------------------------

def test_database_error_handling_and_rollback():
    """Verify that a database error during session start produces a 500 status and does not crash."""
    import pymysql

    mock_user = {"user_id": 3, "role": "student"}
    mock_subject = {"subject_id": 1, "subject_name": "DSA"}

    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor
    fake_cursor.execute.side_effect = pymysql.OperationalError(2003, "Can't connect to MySQL server")

    with patch("backend.routers.sessions.execute_one", side_effect=[mock_user, mock_subject]), \
         patch("backend.routers.sessions.get_transaction") as mock_tx:
        mock_tx.return_value.__enter__.return_value = fake_conn

        response = client.post("/api/sessions/start", json={
            "user_id": 3,
            "subject_id": 1
        })

    assert response.status_code == 500
    assert "Database error" in response.json()["detail"]

# ------------------------------------------------------------
# 8. Supplementary Endpoints: Details & User Sessions
# ------------------------------------------------------------

def test_get_session_details_success():
    """Verify GET /api/sessions/{session_id} returns session metadata and logs."""
    fake_session = {
        "session_id": "test-uuid-1234",
        "user_id": 3,
        "student_name": "Alice Student",
        "subject_id": 1,
        "subject_name": "DSA",
        "current_topic_id": 105,
        "current_topic_name": "Binary Search Trees",
        "current_stage": "quiz",
        "quiz_difficulty": 2,
        "confused_count": 0,
        "started_at": "2026-10-24T10:00:00",
        "updated_at": "2026-10-24T10:10:00"
    }
    fake_messages = [
        {"log_id": 1, "session_id": "test-uuid-1234", "topic_id": 105, "role": "user", "stage": "topic", "content": "Hello", "created_at": "2026-10-24T10:01:00"}
    ]
    fake_attempts = [
        {"attempt_id": 10, "session_id": "test-uuid-1234", "user_id": 3, "topic_id": 105, "difficulty_level": 2, "mcq_score": 3, "check_score": 5, "verdict": "UNDERSTOOD", "attempted_at": "2026-10-24T10:05:00"}
    ]

    with patch("backend.routers.sessions.execute_one", return_value=fake_session), \
         patch("backend.routers.sessions.execute_query", side_effect=[fake_messages, fake_attempts]):

        response = client.get("/api/sessions/test-uuid-1234")

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "test-uuid-1234"
    assert len(data["messages"]) == 1
    assert len(data["quiz_attempts"]) == 1

def test_get_user_sessions_success():
    """Verify GET /api/sessions/user/{user_id} lists all sessions for a student."""
    fake_user_sessions = [
        {
            "session_id": "session-1",
            "subject_id": 1,
            "subject_name": "DSA",
            "current_topic_id": 105,
            "topic_name": "BST",
            "current_stage": "quiz",
            "quiz_difficulty": 1,
            "confused_count": 0,
            "started_at": "2026-10-24T09:00:00",
            "updated_at": "2026-10-24T09:30:00"
        }
    ]

    with patch("backend.routers.sessions.execute_query", return_value=fake_user_sessions):
        response = client.get("/api/sessions/user/3")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["session_id"] == "session-1"

