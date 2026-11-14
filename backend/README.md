# AI Tutor & Skill Tree - Backend Documentation

This service provides the **FastAPI** REST backend for the **Chapter1** platform, unifying relational curriculum DAG graph traversal in **PostgreSQL 18** with dense semantic vector search in **ChromaDB**.

---

## 1. Architecture Overview

- **Framework**: FastAPI (Python 3.10+) with Uvicorn ASGI server
- **Relational DBMS**: PostgreSQL 18 (`ai_tutor_db`) via `psycopg` (v3) using `dict_row` factory, context-managed ACID transactions, and explicit error handling
- **Vector Knowledge Base**: ChromaDB persistent vector store (`chroma_data/chroma.sqlite3`) with 384-dimensional embeddings (`all-MiniLM-L6-v2`)
- **Curriculum & DAG Engine**:
  - `topics` & `topic_prerequisites`: Self-referencing adjacency graph traversed via Recursive Common Table Expressions (CTEs).
  - `student_topic_completions`: Idempotent completion tracking (`UNIQUE(user_id, topic_id)`) driving the sequential unlock engine.
- **Socratic RAG Tutor Pipeline**:
  - Hybrid lexical & semantic re-ranking (combines dense cosine similarity with exact keyword and topic title boosts).
  - Noise and boilerplate purging (strips copyright, page headers, dangling fragments).
  - Topic-isolated dialogue history (past chapter chats do not leak across topics).
- **Authentication & RBAC**:
  - Secure bcrypt password hashing with JWT HTTP-only cookies and Bearer tokens.
  - Role-Based Access Control: `student` (strictly prerequisite-gated), `instructor` (unrestricted preview), `admin` (full management).

---

## 2. Environment Configuration

The backend is configured via `backend/config.py` and `.env` in the project root:

```ini
# Database Configuration (PostgreSQL 18)
DB_HOST=127.0.0.1
DB_PORT=5433
DB_USER=ai_tutor_app
DB_PASSWORD=
DB_NAME=ai_tutor_db

# ChromaDB Vector Store
CHROMA_PERSIST_DIR=./chroma_data

# Authentication & Security
JWT_SECRET=your-secure-random-jwt-secret
COOKIE_SECURE=false
```

PostgreSQL initialization and role provisioning are handled automatically by:
```bash
python scripts/bootstrap_postgres.py
```

---

## 3. Running the Backend Server

### Automated Startup (Recommended)
From the project root:
```powershell
.\scripts\start.ps1
```

### Manual Startup
1. Ensure PostgreSQL is running on port 5433:
   ```powershell
   & "C:\Program Files\PostgreSQL\18\bin\postgres.exe" -D ".runtime\postgres" -p 5433 -h 127.0.0.1
   ```
2. Launch FastAPI with live reload:
   ```bash
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
   ```

- **Interactive Swagger UI**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`
- **Health Check Endpoint**: `http://localhost:8000/health`

---

## 4. Core API Endpoints Reference

### A. Authentication & RBAC (`backend/routers/auth.py`)
- `POST /api/auth/login`: Authenticates `student`, `instructor`, or `admin` credentials (e.g. `password123`) and sets secure session cookies.
- `GET /api/auth/me`: Returns current authenticated user profile, permissions, and active role.
- `POST /api/auth/logout`: Clears authentication cookies and invalidates session.

### B. Curriculum & Skill Tree (`backend/routers/curriculum.py`)
- `GET /api/curriculum/subjects`: Lists indexed course domains with topic counts.
- `GET /api/curriculum/topics/{subject_id}`: Retrieves all curriculum topics sorted by difficulty level and book order.
- `GET /api/curriculum/graph/{subject_id}`: Returns DAG nodes and prerequisite edges for interactive React Flow rendering.
- `GET /api/curriculum/prerequisites/{topic_id}`: Executes **Recursive CTE** (Ancestor Walk) resolving transitive prerequisites.
- `GET /api/curriculum/unlocked/{topic_id}`: Executes **Recursive CTE** (Descendant Walk) finding downstream unlocked pathways.
- `POST /api/curriculum/complete-topic`: Atomically records topic completion in `student_topic_completions`.
- `GET /api/curriculum/completions/{subject_id}`: Returns completed topic IDs for the active user.

### C. Socratic RAG Tutor (`backend/routers/tutor.py`)
- `POST /api/tutor/query`:
  - Enforces prerequisite lock validation for student role.
  - Queries ChromaDB collection with cosine distance metric.
  - Applies hybrid lexical and topic title boosts to ensure precise concept matching (e.g. exact technical terms like "HTTP").
  - Formats grounded textbook citations with match percentages (e.g. `(Match: 83.8% · Page 9)`).
  - Logs user questions and assistant answers into `conversation_logs` categorized by `topic_id`.

### D. ChromaDB Vector Store & Ingestion (`backend/routers/vector_rud.py`)
- `POST /api/vector/upload`: Ingests textbook PDFs, chunks text into semantic segments, computes 384-d embeddings, and registers course metadata in PostgreSQL.
- `GET /api/vector/chunks/{subject_key}`: Paginated inspection of stored vectors and metadata.
- `POST /api/vector/chunk`: **Create** a new vector chunk with metadata.
- `PUT /api/vector/chunk`: **Update** chunk text and re-embed in-place.
- `DELETE /api/vector/chunk`: **Delete** chunk from ChromaDB and update relational counters.
- `DELETE /api/vector/course/{subject_id}`: Deletes course from PostgreSQL (`ON DELETE CASCADE`) and drops ChromaDB collection.

### E. Sessions (`backend/routers/sessions.py`)
- `POST /api/sessions/start`: Creates or resumes a study session in `learning_sessions`.
- `GET /api/sessions/{session_id}`: Returns session metadata and topic-isolated conversation logs.
