import time
import sys
import httpx
from fastapi.testclient import TestClient
from backend.main import app

# Check if live server is running on port 8000
USE_LIVE_SERVER = False
LIVE_BASE_URL = "http://127.0.0.1:8000"

try:
    with httpx.Client(timeout=1.0) as check_client:
        r = check_client.get(f"{LIVE_BASE_URL}/health")
        if r.status_code == 200:
            USE_LIVE_SERVER = True
except Exception:
    USE_LIVE_SERVER = False

if USE_LIVE_SERVER:
    print(f"[*] Detected live backend running at {LIVE_BASE_URL}. Running full end-to-end HTTP tests.")
    http = httpx.Client(base_url=LIVE_BASE_URL, timeout=10.0)
else:
    print("[*] Running tests via in-process FastAPI TestClient.")
    http = TestClient(app)

results = []

def run_test(category: str, name: str, test_fn):
    start = time.time()
    try:
        test_fn()
        elapsed_ms = round((time.time() - start) * 1000, 2)
        results.append({"category": category, "name": name, "status": "PASS", "time_ms": elapsed_ms, "error": None})
        print(f"  [PASS] {name} ({elapsed_ms}ms)")
    except Exception as e:
        elapsed_ms = round((time.time() - start) * 1000, 2)
        results.append({"category": category, "name": name, "status": "FAIL", "time_ms": elapsed_ms, "error": str(e)})
        print(f"  [FAIL] {name} ({elapsed_ms}ms) -> {e}")

def verify_system_endpoints():
    print("\n=== 1. SYSTEM & HEALTH ENDPOINTS ===")
    
    def test_root():
        res = http.get("/")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.json()
        assert data.get("status") == "online"
        assert "endpoints" in data
    run_test("System", "GET / (Root API discovery)", test_root)

    def test_health():
        res = http.get("/health")
        assert res.status_code == 200
        assert res.json().get("status") == "healthy"
    run_test("System", "GET /health (Liveness check)", test_health)

def verify_auth_rbac():
    print("\n=== 2. AUTHENTICATION & RBAC ENDPOINTS ===")

    def test_student_login():
        res = http.post("/api/auth/login", json={"email": "roshan@student.edu", "password": "password123"})
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "student"
        assert data["email"] == "roshan@student.edu"
    run_test("Auth", "POST /api/auth/login (Student role)", test_student_login)

    def test_instructor_login():
        res = http.post("/api/auth/login", json={"email": "turing@aitutor.edu", "password": "password123"})
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "instructor"
        assert data["user_id"] == 1
    run_test("Auth", "POST /api/auth/login (Instructor role)", test_instructor_login)

    def test_admin_login():
        res = http.post("/api/auth/login", json={"email": "admin@aitutor.edu", "password": "admin123"})
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "admin"
        assert data["user_id"] == 6
    run_test("Auth", "POST /api/auth/login (Admin role - Ada Lovelace)", test_admin_login)

    def test_invalid_login():
        res = http.post("/api/auth/login", json={"email": "nonexistent@user.edu", "password": "wrong"})
        assert res.status_code == 401
    run_test("Auth", "POST /api/auth/login (Invalid credentials -> 401)", test_invalid_login)

    def test_wrong_password():
        res = http.post("/api/auth/login", json={"email": "roshan@student.edu", "password": "wrong_password"})
        assert res.status_code == 401
    run_test("Auth", "POST /api/auth/login (Wrong password for existing user -> 401)", test_wrong_password)

    def test_get_users():
        res = http.get("/api/auth/users")
        assert res.status_code == 200
        users = res.json()
        assert len(users) >= 6
        roles = {u["role"] for u in users}
        assert "student" in roles and "instructor" in roles and "admin" in roles
    run_test("Auth", "GET /api/auth/users (User list & roles)", test_get_users)

    def test_get_roles():
        res = http.get("/api/auth/roles")
        assert res.status_code == 200
        data = res.json()
        assert "student" in data["roles"]
        assert "instructor" in data["roles"]
        assert "admin" in data["roles"]
        assert "vector_rud" in data["permissions"]["admin"]
        assert "manage_chromadb" in data["permissions"]["admin"]
        assert "vector_rud" not in data["permissions"]["instructor"]
    run_test("Auth", "GET /api/auth/roles (RBAC permissions matrix)", test_get_roles)

def get_active_test_subject():
    try:
        res = http.get("/api/curriculum/subjects").json()
        if res and len(res) > 0:
            return res[0]
    except Exception:
        pass
    return {"subject_id": 1, "subject_key": "dsa", "subject_name": "Data Structures & Algorithms"}

def verify_curriculum():
    print("\n=== 3. CURRICULUM & SKILL TREE ENDPOINTS ===")

    def test_subjects():
        res = http.get("/api/curriculum/subjects")
        assert res.status_code == 200
        subjects = res.json()
        assert len(subjects) >= 1
    run_test("Curriculum", "GET /api/curriculum/subjects (Course Subjects)", test_subjects)

    sub = get_active_test_subject()
    sub_id = sub["subject_id"]

    def test_topics_by_subject():
        res = http.get(f"/api/curriculum/topics/{sub_id}")
        assert res.status_code == 200
        topics = res.json()
        assert len(topics) >= 1
        assert topics[0]["difficulty_level"] <= topics[-1]["difficulty_level"]
    run_test("Curriculum", f"GET /api/curriculum/topics/{sub_id} (Topics difficulty sort)", test_topics_by_subject)

    def test_graph_dag():
        res = http.get(f"/api/curriculum/graph/{sub_id}")
        assert res.status_code == 200
        data = res.json()
        assert "nodes" in data and "edges" in data
        assert len(data["nodes"]) >= 1
    run_test("Curriculum", f"GET /api/curriculum/graph/{sub_id} (Skill tree DAG nodes & edges)", test_graph_dag)

    def test_visual_config():
        topics_res = http.get(f"/api/curriculum/topics/{sub_id}").json()
        first_topic_id = topics_res[0]["topic_id"] if topics_res else 412
        res = http.get(f"/api/curriculum/visual/{first_topic_id}")
        assert res.status_code == 200
        topic = res.json()
        assert "visual_type" in topic
    run_test("Curriculum", "GET /api/curriculum/visual/106 (Visualizer config)", test_visual_config)

    def test_visual_404():
        res = http.get("/api/curriculum/visual/99999")
        assert res.status_code == 404
    run_test("Curriculum", "GET /api/curriculum/visual/99999 (Missing topic -> 404)", test_visual_404)

def verify_recursive_ctes():
    print("\n=== 4. RECURSIVE CTE DATABASE QUERIES ===")

    sub = get_active_test_subject()
    sub_id = sub["subject_id"]
    topics = http.get(f"/api/curriculum/topics/{sub_id}").json()
    first_id = topics[0]["topic_id"] if topics else 412
    last_id = topics[-1]["topic_id"] if len(topics) > 1 else first_id

    def test_ancestor_prerequisites():
        res = http.get(f"/api/curriculum/prerequisites/{last_id}")
        assert res.status_code == 200
        prereqs = res.json()
        if prereqs:
            assert any("learning_order_path" in p for p in prereqs)
    run_test("Recursive CTE", f"GET /api/curriculum/prerequisites/{last_id} (Ancestor Walk)", test_ancestor_prerequisites)

    def test_descendant_unlocked():
        res = http.get(f"/api/curriculum/unlocked/{first_id}")
        assert res.status_code == 200
        unlocked = res.json()
        if unlocked:
            assert "unlock_tier" in unlocked[0]
    run_test("Recursive CTE", f"GET /api/curriculum/unlocked/{first_id} (Descendant Walk)", test_descendant_unlocked)

def verify_chromadb_vector_rud():
    print("\n=== 5. CHROMADB VECTOR RUD OPERATIONS ===")

    sub = get_active_test_subject()
    sub_key = sub["subject_key"]

    def test_list_collections():
        res = http.get("/api/vector/collections")
        assert res.status_code == 200
        cols = res.json()
        names = [c["name"] for c in cols]
        assert f"chroma_{sub_key}" in names
    run_test("Vector RUD", "GET /api/vector/collections (List all collections)", test_list_collections)

    def test_collection_stats():
        res = http.get(f"/api/vector/stats/{sub_key}")
        assert res.status_code == 200
        data = res.json()
        assert data["collection_name"] == f"chroma_{sub_key}"
        assert data["total_chunks"] >= 1
    run_test("Vector RUD", f"GET /api/vector/stats/{sub_key} (Collection chunk counts)", test_collection_stats)

    def test_semantic_search():
        res = http.post("/api/vector/search", json={
            "subject_key": sub_key,
            "query": f"principles and data structures in {sub['subject_name']}",
            "top_k": 2
        })
        assert res.status_code == 200
        data = res.json()
        assert data["total_results"] > 0
        top = data["results"][0]
        assert "similarity" in top
        assert 0.0 <= top["similarity"] <= 1.0
        assert "id" in top
    run_test("Vector RUD", "POST /api/vector/search (Semantic Top-K & Cosine Similarity)", test_semantic_search)

    test_chunk_id = f"test_e2e_chunk_{int(time.time())}"

    def test_create_chunk():
        res = http.post("/api/vector/chunk", json={
            "subject_key": sub_key,
            "chunk_id": test_chunk_id,
            "text": "Temporary verification chunk testing vector store additions and cosine indexing.",
            "metadata": {"subject": sub_key, "chapter": "Testing", "difficulty": 1}
        })
        assert res.status_code == 200
        assert res.json()["status"] == "success"
    run_test("Vector RUD", "POST /api/vector/chunk (Vector CREATE)", test_create_chunk)

    def test_read_chunk():
        res = http.get(f"/api/vector/chunks/{sub_key}?limit=50")
        assert res.status_code == 200
        chunks = res.json()
        ids = [c["id"] for c in chunks]
        assert test_chunk_id in ids
    run_test("Vector RUD", f"GET /api/vector/chunks/{sub_key} (Vector READ list)", test_read_chunk)

    def test_update_chunk():
        res = http.put("/api/vector/update", json={
            "subject_key": sub_key,
            "chunk_id": test_chunk_id,
            "new_text": "Updated: Temporary verification chunk testing vector updates and re-embedding.",
            "new_metadata": {"subject": sub_key, "chapter": "Testing v2", "updated": True}
        })
        assert res.status_code == 200
        search_res = http.post("/api/vector/search", json={
            "subject_key": sub_key,
            "query": "Temporary verification chunk testing vector updates",
            "top_k": 1
        })
        assert search_res.status_code == 200
        assert "re-embedding" in search_res.json()["results"][0]["document"]
    run_test("Vector RUD", "PUT /api/vector/update (Vector UPDATE & Re-embed)", test_update_chunk)

    def test_delete_chunk():
        res = http.request("DELETE", "/api/vector/delete", json={
            "subject_key": sub_key,
            "chunk_ids": [test_chunk_id]
        })
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        check_res = http.get(f"/api/vector/chunks/{sub_key}?limit=50")
        remaining_ids = [c["id"] for c in check_res.json()]
        assert test_chunk_id not in remaining_ids
    run_test("Vector RUD", "DELETE /api/vector/delete (Vector DELETE & Cleanup)", test_delete_chunk)

    def test_clear_collection_non_admin_forbidden():
        res = http.request("DELETE", "/api/vector/clear-collection", json={
            "subject_key": sub_key,
            "role": "student",
            "user_id": 3
        })
        assert res.status_code == 403, f"Expected 403 Forbidden for student, got {res.status_code}"
    run_test("Vector RUD", "DELETE /api/vector/clear-collection (Student -> 403 Forbidden)", test_clear_collection_non_admin_forbidden)

    def test_clear_all_non_admin_forbidden():
        res = http.request("DELETE", "/api/vector/clear-all", json={
            "role": "instructor",
            "user_id": 1
        })
        assert res.status_code == 403, f"Expected 403 Forbidden for instructor, got {res.status_code}"
    run_test("Vector RUD", "DELETE /api/vector/clear-all (Instructor -> 403 Forbidden)", test_clear_all_non_admin_forbidden)

    def test_clear_collection_admin_success():
        temp_key = f"tmp_admin_{int(time.time())}"
        http.post("/api/vector/chunk", json={
            "subject_key": temp_key,
            "chunk_id": "c1",
            "text": "Admin clear verification chunk",
            "metadata": {"subject": temp_key}
        })
        res = http.request("DELETE", "/api/vector/clear-collection", json={
            "subject_key": temp_key,
            "role": "admin",
            "user_id": 6
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["deleted_count"] >= 1
        stats = http.get(f"/api/vector/stats/{temp_key}").json()
        assert stats["total_chunks"] == 0
    run_test("Vector RUD", "DELETE /api/vector/clear-collection (Admin -> 200 Success & Wiped)", test_clear_collection_admin_success)

    def test_delete_course_non_admin_forbidden():
        res = http.delete("/api/vector/course/99999?role=student&user_id=3")
        assert res.status_code == 403, f"Expected 403 Forbidden for student, got {res.status_code}"
    run_test("Vector RUD", "DELETE /api/vector/course/{id} (Student -> 403 Forbidden)", test_delete_course_non_admin_forbidden)

def verify_tutor_rag_pipeline():
    print("\n=== 6. SOCRATIC RAG TUTOR PIPELINE & RELATIONAL CTE ===")

    sub = get_active_test_subject()
    sub_id = sub["subject_id"]
    topics = http.get(f"/api/curriculum/topics/{sub_id}").json()
    first_topic = topics[0] if topics else {"topic_id": 412, "topic_name": "Distributed Storage"}

    def test_tutor_query_with_prereqs():
        topic_title = first_topic.get("topic_name", "algorithms")
        res = http.post("/api/tutor/query", json={
            "query": f"Explain the core mechanisms, structure, and operations of {topic_title}",
            "subject_id": sub_id,
            "topic_id": first_topic["topic_id"],
            "include_prereqs": True
        })
        assert res.status_code == 200, f"Expected 200 got {res.status_code}: {res.text}"
        data = res.json()
        assert len(data["answer"]) > 10, f"Answer too short: {data['answer']}"
        assert len(data["retrieved_chunks"]) > 0, f"No chunks retrieved: {data.get('retrieved_chunks')}"
    run_test("Tutor RAG", "POST /api/tutor/query (Relational Prerequisite Guided RAG)", test_tutor_query_with_prereqs)

    def test_tutor_query_general():
        res = http.post("/api/tutor/query", json={
            "query": f"Explain fundamental principles and core structures in {sub['subject_name']}",
            "subject_id": sub_id
        })
        assert res.status_code == 200, f"Expected 200 got {res.status_code}: {res.text}"
        data = res.json()
        assert len(data["answer"]) > 10, f"Answer too short: {data['answer']}"
        assert len(data["retrieved_chunks"]) > 0, f"No chunks: {data.get('retrieved_chunks')}"
    run_test("Tutor RAG", "POST /api/tutor/query (Subject-wide Vector Search)", test_tutor_query_general)

    def test_document_ingestion_upload():
        sample_doc = "HDFS splits files into large blocks and distributes them across cluster data nodes with triple replication for high fault tolerance."
        files = {
            "file": ("temp_test_hdfs_chunk.txt", sample_doc.encode("utf-8"), "text/plain")
        }
        data = {
            "subject_id": str(sub_id),
            "subject_key": sub["subject_key"],
            "uploaded_by": "1",
            "topic_id": str(first_topic["topic_id"])
        }
        res = http.post("/api/vector/upload", data=data, files=files)
        assert res.status_code == 200
        res_json = res.json()
        assert res_json["status"] == "success"
        assert res_json["chunks_indexed"] >= 1
    run_test("Tutor RAG", "POST /api/vector/upload (Document Ingestion & Relational Tagging)", test_document_ingestion_upload)

def verify_edge_cases_and_dynamic_subjects():
    print("\n=== 7. DYNAMIC SUBJECT CREATION & EDGE CASE VERIFICATION ===")

    def test_unsupported_file_extension():
        files = {
            "file": ("malicious_payload.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/octet-stream")
        }
        res = http.post("/api/vector/upload", data={"subject_name": "Test Exploit"}, files=files)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}"
        assert "Supported formats: PDF, TXT, MD." in res.json().get("detail", "")
    run_test("Edge Cases", "POST /api/vector/upload (.exe file -> 400 rejection)", test_unsupported_file_extension)

    dynamic_subject_state = {}
    def test_dynamic_subject_creation():
        doc_content = (
            "Quantum superposition is a fundamental principle of quantum mechanics. "
            "It states that much like waves in classical physics, any two or more quantum states can be added together "
            "and the result will be another valid quantum state. "
            "Quantum entanglement is a phenomenon where quantum states of two or more objects have to be described "
            "with reference to each other, even though the individual objects may be spatially separated. "
            "Qubits are the fundamental unit of quantum information, utilizing both |0> and |1> states simultaneously."
        )
        files = {
            "file": ("quantum_computing_handbook.txt", doc_content.encode("utf-8"), "text/plain")
        }
        data = {
            "subject_name": "Quantum Computing & Qubits",
            "classification": "Physics & Applied Sciences",
            "uploaded_by": "1"
        }
        res = http.post("/api/vector/upload", data=data, files=files)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        body = res.json()
        assert body["status"] == "success"
        assert body["chunks_indexed"] >= 1
        assert "subject_id" in body and body["subject_id"] > 0
        assert body["subject_name"] == "Quantum Computing & Qubits"
        dynamic_subject_state["subject_id"] = body["subject_id"]
        dynamic_subject_state["subject_key"] = body["subject_key"]
    run_test("Edge Cases", "POST /api/vector/upload (Dynamic course creation & ChromaDB indexing)", test_dynamic_subject_creation)

    def test_dynamic_skill_tree_dag():
        sub_id = dynamic_subject_state.get("subject_id")
        assert sub_id is not None, "Previous test failed to save dynamic subject_id"
        res = http.get(f"/api/curriculum/graph/{sub_id}")
        assert res.status_code == 200
        graph = res.json()
        assert len(graph["nodes"]) >= 4, f"Expected >= 4 nodes, got {len(graph['nodes'])}"
        assert len(graph["edges"]) >= 3, f"Expected >= 3 edges, got {len(graph['edges'])}"
        assert graph["nodes"][0]["difficulty_level"] <= 2
    run_test("Edge Cases", "GET /api/curriculum/graph/{new_id} (Dynamic DAG node & edge synthesis)", test_dynamic_skill_tree_dag)

    def test_dynamic_socratic_tutor():
        sub_id = dynamic_subject_state.get("subject_id")
        assert sub_id is not None
        res = http.post("/api/tutor/query", json={
            "query": "What is quantum superposition and how do qubits differ from classical bits?",
            "subject_id": sub_id
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert len(data["answer"]) > 25
        assert len(data["retrieved_chunks"]) > 0
        assert data.get("reflection_question") or "quantum" in data["answer"].lower()
    run_test("Edge Cases", "POST /api/tutor/query (Socratic RAG on dynamic course materials)", test_dynamic_socratic_tutor)

    def test_tutor_invalid_subject():
        res = http.post("/api/tutor/query", json={
            "query": "What is quantum mechanics?",
            "subject_id": 99999
        })
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
    run_test("Edge Cases", "POST /api/tutor/query (Missing subject_id -> 404)", test_tutor_invalid_subject)

    sub = get_active_test_subject()
    sub_id = sub["subject_id"]
    sub_key = sub["subject_key"]

    def test_tutor_invalid_topic_fallback():
        res = http.post("/api/tutor/query", json={
            "query": "Explain binary search efficiency.",
            "subject_id": sub_id,
            "topic_id": 999999
        })
        assert res.status_code == 200, f"Expected 200 graceful fallback, got {res.status_code}"
        data = res.json()
        assert len(data["answer"]) > 10
    run_test("Edge Cases", "POST /api/tutor/query (Invalid topic_id -> Graceful fallback)", test_tutor_invalid_topic_fallback)

    def test_high_top_k_search():
        res = http.post("/api/vector/search", json={
            "subject_key": sub_key,
            "query": "distributed storage processing and clusters",
            "top_k": 30
        })
        assert res.status_code == 200
        data = res.json()
        assert data["total_results"] > 0
        for r in data["results"]:
            assert 0.0 <= r["similarity"] <= 1.0
    run_test("Edge Cases", "POST /api/vector/search (High Top-K bounded similarity)", test_high_top_k_search)

    def test_nonexistent_collection_stats():
        res = http.get("/api/vector/stats/unknown_collection_slug_12345")
        assert res.status_code == 200
        data = res.json()
        assert data["total_chunks"] == 0
    run_test("Edge Cases", "GET /api/vector/stats (Non-existent collection -> 0 chunks)", test_nonexistent_collection_stats)

    def test_delete_nonexistent_chunk():
        res = http.request("DELETE", "/api/vector/delete", json={
            "subject_key": sub_key,
            "chunk_ids": ["non_existent_chunk_id_xyz999"]
        })
        assert res.status_code == 200
        assert res.json()["status"] == "success"
    run_test("Edge Cases", "DELETE /api/vector/delete (Non-existent chunk_id -> safe 200)", test_delete_nonexistent_chunk)

    def test_cleanup_dynamic_subject():
        dyn_id = dynamic_subject_state.get("subject_id")
        dyn_key = dynamic_subject_state.get("subject_key")
        if dyn_key:
            from backend.vector_service import vector_service
            try:
                vector_service.delete_collection(dyn_key)
            except Exception:
                pass
        if dyn_id:
            from backend.database import execute_dml
            try:
                execute_dml("DELETE FROM TOPIC_PREREQUISITES WHERE topic_id IN (SELECT topic_id FROM TOPICS WHERE subject_id = %s) OR prereq_topic_id IN (SELECT topic_id FROM TOPICS WHERE subject_id = %s)", (dyn_id, dyn_id))
                execute_dml("DELETE FROM TOPICS WHERE subject_id = %s", (dyn_id,))
                execute_dml("DELETE FROM TEXTBOOKS WHERE subject_id = %s", (dyn_id,))
                execute_dml("DELETE FROM SUBJECTS WHERE subject_id = %s", (dyn_id,))
            except Exception:
                pass
    run_test("Edge Cases", "CLEANUP (Remove dynamic test subject & Chroma collection)", test_cleanup_dynamic_subject)

def main():
    print("=" * 65)
    print("AI TUTOR & SKILL TREE — FULL API & FEATURE VERIFICATION SUITE")
    print("=" * 65)

    verify_system_endpoints()
    verify_auth_rbac()
    verify_curriculum()
    verify_recursive_ctes()
    verify_chromadb_vector_rud()
    verify_tutor_rag_pipeline()
    verify_edge_cases_and_dynamic_subjects()

    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] == "FAIL"]
    total = len(results)

    print("\n" + "=" * 65)
    print(f"VERIFICATION SUMMARY: {len(passed)}/{total} PASSED ({(len(passed)/total)*100:.1f}%)")
    print("=" * 65)

    if failed:
        print("\nFAILED TESTS:")
        for f in failed:
            print(f"  - [{f['category']}] {f['name']}: {f['error']}")
        sys.exit(1)
    else:
        print("\nAll endpoints and database operations passed verification successfully!")
        sys.exit(0)

if __name__ == "__main__":
    main()
