# AI Tutor & Skill Tree - Backend Documentation

This service provides the FastAPI REST backend for the **AI Tutor & Skill Tree** platform, unifying Member 1's relational curriculum graph and ChromaDB vector store with Member 2's session tracking, quiz attempt evaluations, automated triggers, and adaptive mastery analytics.

---

## 1. Architecture Overview

- **Framework**: FastAPI (Python 3.10+) with Uvicorn ASGI server
- **Database Core**: MySQL 8.0+ relational schema (`ai_tutor_db`) via PyMySQL
- **Vector Store**: ChromaDB semantic search collection (`chroma_{subject_key}`)
- **Session & Mastery Engine (Member 2 - M2-APP1)**:
  - `LEARNING_SESSIONS`: Multi-stage interactive learning sessions identified by UUID (`CHAR(36)`).
  - `CONVERSATION_LOGS`: Turn-by-turn dialogue history preserving agent roles and workflow stages.
  - `QUIZ_ATTEMPTS`: Quantitative test submissions linked to sessions.
  - `STUDENT_TOPIC_MASTERY`: Automatically maintained by MySQL trigger `trg_after_quiz_attempt_mastery`.
  - `sp_recommend_next_topic`: Adaptive stored procedure prioritizing Remediation $\rightarrow$ Continuity $\rightarrow$ Progression.
  - `fn_calculate_subject_mastery`: MySQL stored function calculating student's subject mastery percentage.

---

## 2. Environment Configuration

Copy the example environment configuration:

```bash
cp backend/.env.example backend/.env
```

Configure your local MySQL credentials and ChromaDB settings in `backend/.env`:

```ini
# Database Configuration
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=ai_tutor_db

# ChromaDB Vector Store
CHROMA_PERSIST_DIR=./chroma_data

# Authentication / Security
JWT_SECRET=aitutor-jwt-secret-2026
JWT_ALGORITHM=HS256
```

---

## 3. Running the Backend Server

Install dependencies:

```bash
pip install -r backend/requirements.txt
```

Launch the server with live reload:

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

The interactive Swagger UI documentation is available at:
**`http://localhost:8000/docs`**

ReDoc documentation is available at:
**`http://localhost:8000/redoc`**

---

## 4. Member 2 API Endpoints Reference

### Endpoint 1: Start a Learning Session
- **Path**: `/api/sessions/start`
- **Method**: `POST`
- **Purpose**: Creates a new session row in `LEARNING_SESSIONS` with a generated UUID4, validates user and subject existence, and sets the initial workflow stage to `'topic'`.

**Request Body**:
```json
{
  "user_id": 3,
  "subject_id": 1,
  "current_topic_id": 105,
  "quiz_difficulty": 2
}
```

**Success Response (`201 Created`)**:
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": 3,
  "subject_id": 1,
  "current_topic_id": 105,
  "current_stage": "topic",
  "quiz_difficulty": 2,
  "confused_count": 0,
  "started_at": "2026-10-24T10:00:00",
  "updated_at": "2026-10-24T10:00:00"
}
```

---

### Endpoint 2: Save a Conversation Message
- **Path**: `/api/sessions/message`
- **Method**: `POST`
- **Purpose**: Appends a conversation turn to `CONVERSATION_LOGS` linked to an active session, preserving role, stage, topic, and timestamp.

**Request Body**:
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "content": "How does deletion work in a Binary Search Tree with two children?",
  "role": "user",
  "stage": "explore",
  "topic_id": 105
}
```

**Success Response (`201 Created`)**:
```json
{
  "log_id": 5,
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "topic_id": 105,
  "role": "user",
  "stage": "explore",
  "content": "How does deletion work in a Binary Search Tree with two children?",
  "created_at": "2026-10-24T10:05:00"
}
```

---

### Endpoint 3: Record a Quiz Attempt
- **Path**: `/api/sessions/quiz-attempt`
- **Method**: `POST`
- **Purpose**: Records a quantitative quiz attempt in `QUIZ_ATTEMPTS`. The MySQL trigger `trg_after_quiz_attempt_mastery` automatically recalculates student mastery (`MASTERED`, `IN_PROGRESS`, `NEEDS_PREREQ_REVIEW`) in `STUDENT_TOPIC_MASTERY`. Session stages and confusion counters are updated atomically in the same transaction.

**Request Body**:
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": 3,
  "topic_id": 105,
  "difficulty_level": 2,
  "mcq_score": 3,
  "check_score": 5,
  "verdict": "UNDERSTOOD"
}
```

**Success Response (`201 Created`)**:
```json
{
  "attempt_id": 7,
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": 3,
  "topic_id": 105,
  "difficulty_level": 2,
  "mcq_score": 3,
  "check_score": 5,
  "verdict": "UNDERSTOOD",
  "next_stage": "explore",
  "mastery_status": "MASTERED",
  "attempted_at": "2026-10-24T10:10:00"
}
```

---

### Endpoint 4: Recommend Next Topic
- **Path**: `/api/sessions/recommend/{user_id}/{subject_id}`
- **Method**: `GET`
- **Purpose**: Executes MySQL stored procedure `sp_recommend_next_topic` using OUT variables. Applies rule-based adaptive sequencing:
  1. **Remediation**: Recommends unmet prerequisites for topics flagged as `NEEDS_PREREQ_REVIEW`.
  2. **Continuity**: Resumes in-progress topics (`IN_PROGRESS`).
  3. **Progression**: Finds lowest difficulty topic whose prerequisites are fulfilled.

**Success Response (`200 OK`)**:
```json
{
  "user_id": 3,
  "subject_id": 1,
  "recommended_topic_id": 105,
  "recommendation_reason": "Continuity: Resuming in-progress topic.",
  "topic": {
    "topic_id": 105,
    "topic_name": "Binary Search Trees",
    "difficulty_level": 2,
    "visual_type": "iframe",
    "embed_url": "https://visualgo.net/en/bst"
  }
}
```

---

### Endpoint 5: Calculate Subject Mastery
- **Path**: `/api/sessions/mastery/{user_id}/{subject_id}`
- **Method**: `GET`
- **Purpose**: Calls MySQL stored function `fn_calculate_subject_mastery(user_id, subject_id)` and returns student's mastery percentage as a floating-point number.

**Success Response (`200 OK`)**:
```json
{
  "user_id": 3,
  "subject_id": 1,
  "subject_name": "Data Structures & Algorithms",
  "mastery_percentage": 66.67
}
```

---

### Supplementary Endpoints
- **`GET /api/sessions/{session_id}`**: Retrieves complete session metadata, ordered chat messages, and quiz attempt history.
- **`GET /api/sessions/user/{user_id}`**: Lists all active and completed sessions for a specific student.

---

## 5. Testing Guide

### Automated Unit Tests (Mocked DB dependencies)
Execute the complete 18-test suite testing all endpoints, constraint validations, error handling, and rollbacks:

```bash
python -m pytest backend/test_sessions.py -v
```

### Vector Store RUD Tests
Verify ChromaDB semantic search, chunk updates, and deletes:

```bash
python backend/test_vector_rud.py
```

### Live MySQL Integration Test Runner
Connects to your local MySQL 8.0 instance to verify stored routines and triggers:

```bash
python backend/test_sessions_live.py
```
