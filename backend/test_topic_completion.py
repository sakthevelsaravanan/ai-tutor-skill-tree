import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import execute_dml, execute_query, execute_one

client = TestClient(app)

STUDENT_A = 3  # Roshan Kumar
STUDENT_B = 4  # Sakthevel Saravanan
NON_EXISTENT_USER = 99999
NON_EXISTENT_TOPIC = 99999

@pytest.fixture(autouse=True)
def cleanup_completions():
    # Preserve any pre-existing demo data for the shared fixture students.
    original_rows = execute_query(
        "SELECT user_id, topic_id, completed_at FROM STUDENT_TOPIC_COMPLETIONS WHERE user_id IN (%s, %s)",
        (STUDENT_A, STUDENT_B)
    )
    execute_dml("DELETE FROM STUDENT_TOPIC_COMPLETIONS WHERE user_id IN (%s, %s)", (STUDENT_A, STUDENT_B))
    yield
    execute_dml("DELETE FROM STUDENT_TOPIC_COMPLETIONS WHERE user_id IN (%s, %s)", (STUDENT_A, STUDENT_B))
    for row in original_rows:
        execute_dml(
            "INSERT INTO STUDENT_TOPIC_COMPLETIONS (user_id, topic_id, completed_at) VALUES (%s, %s, %s)",
            (row["user_id"], row["topic_id"], row["completed_at"])
        )

def get_test_topics():
    topics = execute_query("SELECT topic_id, subject_id, topic_name FROM TOPICS ORDER BY topic_id LIMIT 3")
    assert len(topics) >= 2, "Need at least 2 topics in database for testing"
    return topics[0], topics[1]

def test_mark_topic_complete_success():
    t1, _ = get_test_topics()
    t1_id = t1["topic_id"]

    # Initially not completed
    status_res = client.get(f"/api/curriculum/topics/{t1_id}/status/{STUDENT_A}")
    assert status_res.status_code == 200
    assert status_res.json()["is_completed"] is False

    # Mark as completed
    res = client.post(f"/api/curriculum/topics/{t1_id}/complete", json={"user_id": STUDENT_A})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["is_completed"] is True
    assert data["topic_id"] == t1_id
    assert data["user_id"] == STUDENT_A
    assert data["completed_at"] is not None

    # Check status endpoint confirms completed
    status_res2 = client.get(f"/api/curriculum/topics/{t1_id}/status/{STUDENT_A}")
    assert status_res2.status_code == 200
    assert status_res2.json()["is_completed"] is True

def test_get_user_completed_topics():
    t1, t2 = get_test_topics()
    t1_id = t1["topic_id"]
    t2_id = t2["topic_id"]

    # Mark t1
    client.post(f"/api/curriculum/topics/{t1_id}/complete", json={"user_id": STUDENT_A})

    res = client.get(f"/api/curriculum/completed/{STUDENT_A}")
    assert res.status_code == 200
    body = res.json()
    assert body["user_id"] == STUDENT_A
    assert t1_id in body["completed_topic_ids"]
    assert t2_id not in body["completed_topic_ids"]
    assert body["total_completed"] == 1

    # Mark t2
    client.post(f"/api/curriculum/topics/{t2_id}/complete", json={"user_id": STUDENT_A})
    res2 = client.get(f"/api/curriculum/completed/{STUDENT_A}")
    assert res2.status_code == 200
    body2 = res2.json()
    assert t1_id in body2["completed_topic_ids"]
    assert t2_id in body2["completed_topic_ids"]
    assert body2["total_completed"] == 2

def test_duplicate_completion_prevention():
    t1, _ = get_test_topics()
    t1_id = t1["topic_id"]

    # First attempt
    res1 = client.post(f"/api/curriculum/topics/{t1_id}/complete", json={"user_id": STUDENT_A})
    assert res1.status_code == 200
    assert res1.json()["message"] == "Topic marked as completed!"

    # Second attempt (duplicate)
    res2 = client.post(f"/api/curriculum/topics/{t1_id}/complete", json={"user_id": STUDENT_A})
    assert res2.status_code == 200
    assert res2.json()["status"] == "success"
    assert "already marked as completed" in res2.json()["message"]

    # Verify database has exactly 1 row for this user and topic
    count_row = execute_one(
        "SELECT COUNT(*) AS cnt FROM STUDENT_TOPIC_COMPLETIONS WHERE user_id = %s AND topic_id = %s",
        (STUDENT_A, t1_id)
    )
    assert count_row["cnt"] == 1

def test_student_isolation():
    t1, _ = get_test_topics()
    t1_id = t1["topic_id"]

    # Student A marks t1 completed
    client.post(f"/api/curriculum/topics/{t1_id}/complete", json={"user_id": STUDENT_A})

    # Student A should see it completed
    status_a = client.get(f"/api/curriculum/topics/{t1_id}/status/{STUDENT_A}").json()
    assert status_a["is_completed"] is True

    # Student B should NOT see it completed (must remain False)
    status_b = client.get(f"/api/curriculum/topics/{t1_id}/status/{STUDENT_B}").json()
    assert status_b["is_completed"] is False

    completed_b = client.get(f"/api/curriculum/completed/{STUDENT_B}").json()
    assert t1_id not in completed_b["completed_topic_ids"]
    assert completed_b["total_completed"] == 0

def test_unmark_topic_complete():
    t1, _ = get_test_topics()
    t1_id = t1["topic_id"]

    # Mark complete
    client.post(f"/api/curriculum/topics/{t1_id}/complete", json={"user_id": STUDENT_A})
    assert client.get(f"/api/curriculum/topics/{t1_id}/status/{STUDENT_A}").json()["is_completed"] is True

    # Delete / unmark
    del_res = client.delete(f"/api/curriculum/topics/{t1_id}/complete?user_id={STUDENT_A}")
    assert del_res.status_code == 200
    assert del_res.json()["is_completed"] is False

    # Check status
    assert client.get(f"/api/curriculum/topics/{t1_id}/status/{STUDENT_A}").json()["is_completed"] is False

def test_invalid_user_or_topic_error():
    t1, _ = get_test_topics()
    t1_id = t1["topic_id"]

    # Invalid user ID
    err_user = client.post(f"/api/curriculum/topics/{t1_id}/complete", json={"user_id": NON_EXISTENT_USER})
    assert err_user.status_code == 404
    assert "User with ID" in err_user.json()["detail"]

    # Invalid topic ID
    err_topic = client.post(f"/api/curriculum/topics/{NON_EXISTENT_TOPIC}/complete", json={"user_id": STUDENT_A})
    assert err_topic.status_code == 404
    assert "Topic with ID" in err_topic.json()["detail"]

def test_end_to_end_student_completion_workflow():
    """
    Verifies Section 6 Expected User Workflow:
    Step 1: Student opens Skill Tree graph.
    Step 2: Student selects a topic.
    Step 3: Student chats with Socratic AI.
    Step 4: Student clicks Mark as Done.
    Step 5: Backend persists completion in database.
    Step 6: Success response received with completed_at timestamp.
    Step 7 & 8: Skill Tree completion list includes the topic.
    Step 9 & 10: Topic remains completed on simulated re-login / re-query.
    """
    t1, _ = get_test_topics()
    t_id = t1["topic_id"]
    sub_id = t1["subject_id"]

    # Step 1: Fetch Skill Tree graph
    graph_res = client.get(f"/api/curriculum/graph/{sub_id}")
    assert graph_res.status_code == 200
    node_ids = [n["id"] for n in graph_res.json()["nodes"]]
    assert t_id in node_ids

    # Step 2: Student checks initial completion (must be false)
    init_status = client.get(f"/api/curriculum/topics/{t_id}/status/{STUDENT_A}").json()
    assert init_status["is_completed"] is False

    # Step 3: Socratic inquiry
    chat_res = client.post("/api/tutor/query", json={
        "query": "Explain foundational invariants of this concept",
        "subject_id": sub_id,
        "topic_id": t_id,
        "user_id": STUDENT_A
    })
    assert chat_res.status_code == 200

    # Step 4 & 5: Student clicks Mark as Done
    done_res = client.post(f"/api/curriculum/topics/{t_id}/complete", json={"user_id": STUDENT_A})
    assert done_res.status_code == 200
    done_data = done_res.json()
    assert done_data["status"] == "success"
    assert done_data["is_completed"] is True
    assert done_data["completed_at"] is not None

    # Step 7 & 8: Skill Tree fetches completed topics for student
    completed_res = client.get(f"/api/curriculum/completed/{STUDENT_A}?subject_id={sub_id}")
    assert completed_res.status_code == 200
    assert t_id in completed_res.json()["completed_topic_ids"]

    # Step 9 & 10: Refresh / Re-login check
    relogin_check = client.get(f"/api/curriculum/topics/{t_id}/status/{STUDENT_A}")
    assert relogin_check.status_code == 200
    assert relogin_check.json()["is_completed"] is True
