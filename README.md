# AI Tutor & Skill Tree

Map STEM prerequisites and provide interactive, LLM-driven tutoring customized to a student's real-time knowledge gaps.

---

## Architecture & Team Contributions

- **Member 1 (Curriculum & Vector Store)**:
  - MySQL Relational Core: `USERS`, `SUBJECTS`, `TEXTBOOKS`, `TOPICS`, `TOPIC_PREREQUISITES`
  - Recursive CTEs for DAG prerequisite path traversal and ancestor/descendant exploration
  - ChromaDB Vector Store: Semantic PDF chunking and Vector RUD operations (`/api/vector`)
  - Socratic RAG Tutoring Pipeline (`/api/tutor`): Prerequisite-guided context retrieval and reasoning
- **Member 2 (Session Management, Quizzes & Adaptive Mastery)**:
  - Session & Mastery Schema: `LEARNING_SESSIONS`, `CONVERSATION_LOGS`, `QUIZ_ATTEMPTS`, `STUDENT_TOPIC_MASTERY`
  - MySQL Triggers: `trg_after_quiz_attempt_mastery` and `trg_after_session_confused_threshold`
  - MySQL Stored Procedures & Functions: `sp_recommend_next_topic` and `fn_calculate_subject_mastery`
  - FastAPI Session & Quiz Endpoints (`/api/sessions`):
    - `POST /api/sessions/start` - Start learning session
    - `POST /api/sessions/message` - Log conversation turn
    - `POST /api/sessions/quiz-attempt` - Record quiz attempt & trigger automated mastery update
    - `GET /api/sessions/recommend/{user_id}/{subject_id}` - Adaptive topic recommendation
    - `GET /api/sessions/mastery/{user_id}/{subject_id}` - Subject mastery percentage calculation
    - `GET /api/sessions/{session_id}` - Session details with complete chat log & quiz history
    - `GET /api/sessions/user/{user_id}` - Student session history

---

## Quick Start

### 1. Database Initialization
Execute the SQL scripts in order:
```powershell
# 1. Member 1: Curriculum & RBAC
Get-Content database/01_curriculum_rbac_recursive.sql | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p

# 2. Member 2: Sessions, Triggers, Routines & Seed Data
Get-Content database/02_sessions_triggers_procedures.sql | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p
```

### 2. Backend Server
```powershell
# Install dependencies
pip install -r backend/requirements.txt

# Start backend server
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive API docs available at `http://localhost:8000/docs`.

### 3. Run Automated Tests
```powershell
# Run Member 2 session & mastery unit tests
python -m pytest backend/test_sessions.py -v

# Run Member 1 vector RUD tests
python backend/test_vector_rud.py

# Run comprehensive 39-endpoint API test suite
python -m backend.verify_all_apis

# Optional: Run live database integration test
python backend/test_sessions_live.py
```

### 4. Frontend Client (Next.js, TypeScript & Tailwind CSS)
```powershell
cd frontend
npm install
npm run dev
# Open http://localhost:3000 in your browser
```
