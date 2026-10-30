# AI Tutor & Skill Tree
### Adaptive Socratic Tutoring System Powered by Polyglot Relational DAGs and Dense Vector Retrieval

> **PES University — Department of Computer Science and Engineering**  
> **Course**: Database Management Systems (`UE23CS251AK`) — Level 3 Mini Project (50 Marks)  
> **Academic Year**: 2026–2027  
> **Repository**: [https://github.com/sakthevelsaravanan/ai-tutor-skill-tree](https://github.com/sakthevelsaravanan/ai-tutor-skill-tree)

---

## 1. System Overview & Problem Statement

Modern STEM education involves complex, non-linear dependency graphs. Students attempting advanced concepts (e.g., *Dynamic Programming* or *Setup/Hold Timing Analysis*) frequently struggle because of unaddressed gaps in foundational topics (e.g., *Recursion*, *CMOS Inverters*, or *Flip-Flop Clocking*). Traditional Learning Management Systems (LMS) store flat progress percentages and cannot identify the root-cause concept bottlenecks.

The **AI Tutor & Skill Tree** system solves this by unifying:
1. **A Relational Directed Acyclic Graph (DAG)** in **MySQL 8.0+** to model multi-hop prerequisite hierarchies, enforce relational integrity, and drive automated mastery recalculation.
2. **Dense Vector Knowledge Retrieval (ChromaDB)** to ground Socratic AI dialogue strictly in validated course textbook passages.
3. **Automated Database Triggers & Stored Routines** to dynamically adjust student mastery (`MASTERED`, `IN_PROGRESS`, `NEEDS_PREREQ_REVIEW`), flag bottlenecks, and adaptively recommend learning pathways.
4. **An Interactive Full-Stack Application** built with **FastAPI** (Python 3.10+) and **Next.js 14** (TypeScript & Tailwind CSS).

---

## 2. 50-Mark Rubric Mapping & Team Task Split

| Rubric Component | Marks | Member 1 Responsibilities | Member 2 Responsibilities |
| :--- | :---: | :--- | :--- |
| **1. Database Design** | **5** | Normalized 3NF Entities: `USERS`, `SUBJECTS`, `TEXTBOOKS`, `TOPICS`, `TOPIC_PREREQUISITES`. Conceptual ER modeling & relational mapping. | Normalized 3NF Entities: `LEARNING_SESSIONS`, `CONVERSATION_LOGS`, `QUIZ_ATTEMPTS`, `STUDENT_TOPIC_MASTERY`. Session lifecycle & state machine design. |
| **2. Database Creation & Justification** | **9** | DDL script `01_curriculum_rbac_recursive.sql`: PK/FK constraints, ChromaDB collections, polyglot storage justification. | DDL script `02_sessions_triggers_procedures.sql`: Foreign key cascades, check constraints, composite keys, indexing strategy. |
| **3. SQL Operations & Queries** | **8** | Recursive CTEs (Ancestor prerequisite traversal, Descendant unlocked pathways), multi-table curriculum joins. | Correlated subqueries comparing student performance to cohort averages, nested `NOT EXISTS` unlocked topic queries. |
| **4. Advanced DB Concepts** | **13** | ChromaDB Vector RUD (Create, Read, Update, Delete) + Recursive CTE DAG walks (7 Marks). | MySQL Triggers (`trg_after_quiz_attempt_mastery`, `trg_after_session_confused_threshold`), Stored Procedure (`sp_recommend_next_topic`), Stored Function (`fn_calculate_subject_mastery`) (6 Marks). |
| **5. Web App & Integration** | **5** | Interactive SVG/Canvas Skill Tree DAG Viewer, Document Ingestion, Vector Store Manager, FastAPI core backend. | Next.js 2-Column Quiz & Mastery Dashboard (`MasteryDashboard.tsx`), Session Tracking APIs, Socratic Chat Interface. |
| **6. Security & RBAC** | **4** | MySQL Role-Based Access Control (`student_role`, `instructor_role`), secure database views (`vw_student_curriculum`, `vw_topic_prerequisite_graph`). | Session ownership validation, user identity verification, state transition guardrails. |
| **7. Docs, Git & Viva** | **6** | Git repository architecture, Chapters 1–3 documentation, vector benchmarks. | Git commits, Chapters 4–6 documentation, automated test suites (`test_sessions.py`, `verify_all_apis.py`), viva demo runbook. |

---

## 3. System Architecture

```
                 +-------------------------------------------------------+
                 |              Next.js 14 Web Frontend                 |
                 |  (TypeScript, Tailwind CSS, SVG Skill Tree, Chat UI)  |
                 +---------------------------+---------------------------+
                                             | HTTP / JSON REST
                                             v
                 +-------------------------------------------------------+
                 |                 FastAPI Backend Server                |
                 |   - /api/curriculum     - /api/vector                 |
                 |   - /api/sessions       - /api/tutor                  |
                 +-------------+---------------------------+-------------+
                               |                           |
                 Relational Queries & CRUD        Semantic Embeddings (384-d)
                               |                           |
                               v                           v
+--------------------------------------------------+  +-----------------------------------+
|               MySQL 8.0+ Relational Core         |  |         ChromaDB Vector Store     |
| - 9 Normalized Tables (3NF)                      |  | - Persistent Embeddings           |
| - Recursive CTEs for DAG Path Resolution         |  | - Cosine Similarity Retrieval     |
| - Triggers: trg_after_quiz_attempt_mastery       |  | - Collections per Subject         |
| - Stored Proc: sp_recommend_next_topic           |  | - Vector RUD Operations           |
| - Stored Func: fn_calculate_subject_mastery      |  +-----------------------------------+
| - RBAC: student_role & instructor_role           |
+--------------------------------------------------+
```

---

## 4. Relational Database Schema (9 Tables in 3NF)

The database schema is cleanly partitioned into two owner scripts in `database/`:

### A. Curriculum & Prerequisite Core (`database/01_curriculum_rbac_recursive.sql`)
1. **`USERS`**: Stores user credentials, roles (`student`, `instructor`), institutional email addresses, and account metadata.
2. **`SUBJECTS`**: STEM knowledge disciplines (`dsa`, `dvlsi`, `cs`, `networks`) with vector indexing state.
3. **`TEXTBOOKS`**: Uploaded PDF courseware linked to corresponding ChromaDB collections with `CHECK (chunk_count >= 0)`.
4. **`TOPICS`**: Fine-grained curriculum concepts with difficulty ratings (`1` to `3`), visual types (`iframe`, `p5js`), and embed URLs.
5. **`TOPIC_PREREQUISITES`**: Directed edges representing prerequisite dependencies with composite PK `(topic_id, prereq_topic_id)` and `CHECK (topic_id <> prereq_topic_id)`.

### B. Session Tracking, Assessment & Mastery (`database/02_sessions_triggers_procedures.sql`)
6. **`LEARNING_SESSIONS`**: Student interactive sessions identified by UUID (`CHAR(36)`), tracking active topic, 5-stage workflow state (`topic`, `explore`, `quiz`, `check`, `clarify`), and confusion counters.
7. **`CONVERSATION_LOGS`**: Turn-by-turn chat history recording student inquiries, socratic AI responses, and active pedagogical stages.
8. **`QUIZ_ATTEMPTS`**: Quantitative assessment submissions tracking MCQ scores (`0-3`), check scores (`1-5`), and diagnostic verdicts (`UNDERSTOOD`, `CONFUSED`, `UNATTEMPTED`).
9. **`STUDENT_TOPIC_MASTERY`**: Composite PK `(user_id, topic_id)` tracking real-time status (`NOT_STARTED`, `IN_PROGRESS`, `MASTERED`, `NEEDS_PREREQ_REVIEW`), dynamically updated via triggers.

### C. Secure Database Views
- **`vw_student_curriculum`**: Student-safe projection joining subjects and topics for indexed domains.
- **`vw_available_subjects`**: Subject catalog aggregating topic counts, textbook uploads, and indexed chunks.
- **`vw_topic_prerequisite_graph`**: Graph edge projection detailing prerequisite difficulty levels and importance weights.

---

## 5. Advanced Database Features

### 1. MySQL Triggers
- **`trg_after_quiz_attempt_mastery`**: Fires `AFTER INSERT ON QUIZ_ATTEMPTS`. Evaluates quiz scores and verdict:
  - If `verdict = 'CONFUSED'` or `mcq_score = 0`: Flips topic status to `NEEDS_PREREQ_REVIEW`.
  - If `verdict = 'UNDERSTOOD'` and `mcq_score >= 2`: Promotes topic status to `MASTERED`.
  - Otherwise: Sets topic status to `IN_PROGRESS`.
- **`trg_after_session_confused_threshold`**: Fires `BEFORE UPDATE ON LEARNING_SESSIONS`. Automatically flags the topic for remediation if cumulative `confused_count >= 3`.

### 2. Stored Procedures & Functions
- **`sp_recommend_next_topic(IN user_id, IN subject_id, OUT topic_id, OUT reason)`**:
  - **Priority 1 (Remediation)**: Recommends missing prerequisites for topics in `NEEDS_PREREQ_REVIEW`.
  - **Priority 2 (Continuity)**: Resumes unfinished topics marked `IN_PROGRESS`.
  - **Priority 3 (Progression)**: Selects lowest-difficulty topic whose prerequisites are all `MASTERED`.
- **`sp_record_quiz_and_advance_stage(IN session_id, ... OUT next_stage)`**: Atomically inserts the quiz attempt and updates the session stage within an ACID transaction.
- **`fn_calculate_subject_mastery(user_id, subject_id)`**: Returns the student's mastery percentage (`DECIMAL(5,2)`) across all topics in the target subject.

### 3. Recursive Common Table Expressions (CTEs)
- **Ancestor Traversal (Upward DAG Walk)**: Finds all transitive prerequisites for a concept to diagnose missing foundational requirements.
- **Descendant Traversal (Downward DAG Walk)**: Identifies all downstream concepts unlocked once a given topic is mastered.
- **Prerequisite Depth Analysis**: Computes the maximum critical path length through the curriculum DAG.

### 4. Role-Based Access Control (RBAC)
- **`student_role`**: Granted read-only (`SELECT`) privileges on curriculum tables and views; granted `INSERT` and `UPDATE` on session logs and quiz attempts; granted `EXECUTE` on learning procedures.
- **`instructor_role`**: Granted administrative privileges (`ALL PRIVILEGES` / full CRUD) on curriculum, textbook ingestion, and curriculum modification.

---

## 6. Polyglot Vector Store Justification (MySQL vs. ChromaDB)

| Feature | MySQL 8.0+ Relational Core | ChromaDB Dense Vector Store |
| :--- | :--- | :--- |
| **Data Nature** | Highly structured tabular data, strict schemas, foreign key relationships. | Unstructured textbook PDF passages converted to dense 384-dimensional floating-point vectors. |
| **Query Mechanism** | Relational algebra, B-Tree indexes, Recursive CTEs, ACID transactions. | Approximate Nearest Neighbor (ANN) search via HNSW cosine distance indexing. |
| **System Role** | Identity, DAG prerequisite enforcement, session history, quantitative grading, mastery state. | Semantic similarity search matching student queries to exact textbook concepts for grounded Socratic answers. |
| **RUD Operations** | SQL `INSERT`, `SELECT`, `UPDATE`, `DELETE` with referential cascade rules. | Vector embeddings `add`, `query`, `update_metadata`, and `delete` via ChromaDB client. |

---

### 6.1 Dense Vector Knowledge Retrieval & Socratic AI Tutoring Workflow

The Socratic tutoring dialogue is grounded strictly in validated course textbook passages retrieved via dense vector similarity from ChromaDB:

```
[Student Inquiry]
       │
       ▼
[1. Backend Question Processing] (Extract natural query + resolve active concept & prerequisite chain)
       │
       ▼
[2. Dense Vector Embedding] (Generate 384-d dense embedding via ChromaDB all-MiniLM-L6-v2)
       │
       ▼
[3. ChromaDB Semantic Retrieval] (Query chroma_{subject_key} with optional relational DAG filter)
       │
       ▼
[4. Substantive Chunk Filtering] (Purge slide noise, course codes & headers; enforce relevance threshold >= 0.22)
       │
       ▼
[5. Socratic Prompt Construction] (Inject verified textbook excerpts into LLM / grounded synthesis engine)
       │
       ▼
[6. Direct Answer & Socratic Follow-Up] (Direct factual explanation + exactly ONE meaningful reasoning question)
       │
       ▼
[7. Clean Frontend Presentation] (Render only the student question and AI tutor answer; no raw metadata/badges)
```

#### Implementation Files & Component Architecture
- **`backend/routers/tutor.py`**: Core FastAPI router providing `POST /api/tutor/query`. Resolves active topics and recursive prerequisite chains from MySQL (`_fetch_prerequisite_chain`), executes dense vector search with candidate pool expansion, applies substantive chunk noise filtering (`_clean_chunk_text`, `_is_substantive_chunk`), enforces the relevance threshold (`MIN_RELEVANCE_THRESHOLD = 0.22`), and generates grounded explanations with focused Socratic follow-up questions (`_generate_socratic_response`).
- **`backend/vector_service.py`**: Persistent ChromaDB interface managing collections (`chroma_{subject_key}`) with cosine distance indexing (`hnsw:space: cosine`), batch ingestion, semantic search, and Vector RUD operations.
- **`backend/pdf_indexer.py`**: Textbook document parser and ingestion pipeline. Chunks PDF/text documents, extracts text, matches concepts, tags metadata (`subject_id`, `topic_id`, `file_name`, `page_number`), and populates ChromaDB collections.
- **`frontend/components/TutorChat.tsx`**: Clean Next.js interactive chat interface. Displays strictly the student's question and the AI tutor's grounded explanation in a distraction-free conversation stream, rendering Socratic reflection as a natural paragraph while preserving essential domain selection, active concept selection, and prerequisite filter controls.
- **`frontend/lib/api.ts` & `frontend/lib/types.ts`**: TypeScript API client and interface contracts (`TutorQueryRequest`, `TutorQueryResponse`).

#### API Contract: `POST /api/tutor/query`
- **Request Format (`TutorQueryRequest`)**:
  ```json
  {
    "query": "What is a Hill cipher, and why must the key matrix be invertible?",
    "subject_id": 12,
    "topic_id": 335,
    "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "user_id": 3,
    "include_prereqs": true
  }
  ```
- **Response Format (`TutorQueryResponse`)**:
  ```json
  {
    "answer": "A Hill cipher encrypts blocks of letters using matrix multiplication modulo 26...\n\nThink about this: if two different plaintext blocks could produce the same ciphertext, would decryption be able to determine which plaintext was original?",
    "target_topic": { "topic_id": 335, "topic_name": "5 Hill Ciphers: Fundamental Concepts & Core Principles", "difficulty_level": 1, "visual_type": "p5js" },
    "prerequisites": [],
    "retrieved_chunks": [ ... ],
    "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "relational_filter_applied": true,
    "reflection_question": "If two different plaintext blocks could produce the same ciphertext, would decryption be able to determine which plaintext was original?",
    "grounding_excerpt": "Hill cipher: Inverse of a Matrix Required for the decryption process...",
    "top_similarity": 0.6397,
    "top_source": "5_Hill ciphers.pdf"
  }
  ```
- **Insufficient Retrieval Handling**: If ChromaDB returns no matches or top similarity is below the relevance threshold (0.22), the tutor responds with an honest message stating that available textbook passages are insufficient, inviting the student to clarify or select a specific concept, without fabricating facts.

---

## 7. API Reference Catalog (FastAPI)

Interactive Swagger UI documentation is available at: `http://localhost:8000/docs`

### Session Management & Mastery Endpoints
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/sessions/start` | Creates a new session (`UUID4`), validates user and subject, sets initial stage to `'topic'`. |
| `POST` | `/api/sessions/message` | Appends a conversation turn to `CONVERSATION_LOGS` with active role, stage, and topic. |
| `POST` | `/api/sessions/quiz-attempt` | Records quiz submission in `QUIZ_ATTEMPTS`, firing `trg_after_quiz_attempt_mastery`. |
| `GET` | `/api/sessions/recommend/{user_id}/{subject_id}` | Invokes `sp_recommend_next_topic` and returns adaptive next concept. |
| `GET` | `/api/sessions/mastery/{user_id}/{subject_id}` | Calls `fn_calculate_subject_mastery` and returns completion percentage. |
| `GET` | `/api/sessions/{session_id}` | Fetches full session details, chat logs, and quiz attempt history. |
| `GET` | `/api/sessions/user/{user_id}` | Lists all learning sessions for a specific student. |

### Curriculum, Tutoring & Vector Endpoints
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/curriculum/subjects` | Lists all indexed subjects with topic and chunk counts. |
| `GET` | `/api/curriculum/tree/{subject_key}` | Returns complete DAG nodes, edges, difficulty levels, and visualizer types. |
| `POST` | `/api/curriculum/upload` | Ingests textbook PDF, chunks passages, and builds ChromaDB embeddings. |
| `POST` | `/api/tutor/query` | Prerequisite-aware Socratic dialogue generator grounded in vector context. |
| `GET` | `/api/vector/chunks/{subject_key}` | Vector Read: retrieves indexed chunks with metadata. |
| `PUT` | `/api/vector/chunk` | Vector Update: modifies chunk content and recalculates embeddings. |
| `DELETE`| `/api/vector/chunk` | Vector Delete: deletes chunk and synchronizes MySQL chunk count. |

---

## 8. Step-by-Step Execution Guide

### Prerequisites
- **MySQL Server 8.0+** running on `localhost:3306`
- **Python 3.10+**
- **Node.js 18+** and **npm**

---

### Step 1: Database Initialization
Run the database scripts in numerical order using PowerShell:

```powershell
# 1. Execute Member 1 Script (Creates database, 5 curriculum tables, RBAC, views, seed data, CTEs)
Get-Content database/01_curriculum_rbac_recursive.sql | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p

# 2. Execute Member 2 Script (Creates 4 session/mastery tables, triggers, routines, and seed attempts)
Get-Content database/02_sessions_triggers_procedures.sql | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p
```

---

### Step 2: Backend Setup & Server Start

1. Configure environment variables in `backend/.env`:
```ini
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=ai_tutor_db
CHROMA_PERSIST_DIR=./chroma_data
JWT_SECRET=aitutor-jwt-secret-2026
JWT_ALGORITHM=HS256
```

2. Install Python dependencies:
```powershell
# Use python -m pip to avoid Windows launcher wrapper issues
python -m pip install -r backend/requirements.txt
```

3. Start the FastAPI backend server:
```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
*API Swagger Documentation: `http://localhost:8000/docs`*

---

### Step 3: Frontend Client Setup & Start

1. Open a new terminal and navigate to `frontend`:
```powershell
cd frontend
npm install
npm run dev
```

2. Open **`http://localhost:3000`** in your browser.

---

### Step 4: Run Verification & Automated Test Suites

```powershell
# Run Member 2 session & mastery unit tests (18 automated tests)
python -m pytest backend/test_sessions.py -v

# Run Member 1 ChromaDB Vector RUD tests
python backend/test_vector_rud.py

# Run comprehensive 39-endpoint API test suite
python -m backend.verify_all_apis

# Run live database integration test runner
python backend/test_sessions_live.py
```

---

## 9. Viva Demonstration Runbook & Cheat Sheet

### Member 1 Live Demonstration
1. **Verify Role-Based Access Control**:
   ```sql
   SHOW GRANTS FOR 'student_role';
   SHOW GRANTS FOR 'instructor_role';
   ```
2. **Execute Recursive DAG Traversal**:
   Demonstrate multi-hop prerequisite resolution for `topic_id = 106` (*AVL Trees*) or `topic_id = 109` (*Dynamic Programming*):
   ```sql
   -- View Ancestor Prerequisite Chain:
   WITH RECURSIVE PrerequisiteChain AS (
       SELECT tp.topic_id, tp.prereq_topic_id, 1 AS depth
       FROM TOPIC_PREREQUISITES tp
       WHERE tp.topic_id = 106
       UNION ALL
       SELECT parent.topic_id, parent.prereq_topic_id, pc.depth + 1
       FROM TOPIC_PREREQUISITES parent
       INNER JOIN PrerequisiteChain pc ON parent.topic_id = pc.prereq_topic_id
   )
   SELECT t.topic_name AS target, pt.topic_name AS required_prereq, pc.depth
   FROM PrerequisiteChain pc
   INNER JOIN TOPICS t ON pc.topic_id = t.topic_id
   INNER JOIN TOPICS pt ON pc.prereq_topic_id = pt.topic_id;
   ```
3. **ChromaDB Vector RUD Verification**:
   Execute `python backend/test_vector_rud.py` to demonstrate document embedding creation, semantic retrieval, metadata updating, and chunk deletion.

---

### Member 2 Live Demonstration
1. **Demonstrate Automated Trigger Execution**:
   Insert a quiz attempt with verdict `'CONFUSED'` and observe the trigger automatically recalculating student mastery in `STUDENT_TOPIC_MASTERY`:
   ```sql
   -- Insert confused quiz attempt
   INSERT INTO QUIZ_ATTEMPTS (session_id, user_id, topic_id, difficulty_level, mcq_score, check_score, verdict)
   VALUES ('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 3, 105, 2, 0, 1, 'CONFUSED');

   -- Verify trigger immediately flipped topic to remediation status:
   SELECT user_id, topic_id, mastery_status, updated_at 
   FROM STUDENT_TOPIC_MASTERY 
   WHERE user_id = 3 AND topic_id = 105;
   -- Output shows: mastery_status = 'NEEDS_PREREQ_REVIEW'
   ```

2. **Execute Stored Function**:
   ```sql
   -- Calculate exact subject mastery percentage
   SELECT fn_calculate_subject_mastery(3, 1) AS dsa_mastery_pct;
   ```

3. **Execute Adaptive Stored Procedure**:
   ```sql
   -- Evaluates Remediation -> Continuity -> Progression
   CALL sp_recommend_next_topic(3, 1, @recommended_topic, @reason);
   SELECT @recommended_topic AS recommended_topic_id, @reason AS recommendation_reason;
   ```

4. **Correlated Subquery Analysis (Bottleneck Detection)**:
   ```sql
   -- Identifies topics where confusion rate exceeds the overall subject average
   SELECT 
       s.subject_name,
       t.topic_id,
       t.topic_name,
       t.difficulty_level,
       COUNT(qa.attempt_id) AS total_topic_attempts,
       SUM(CASE WHEN qa.verdict = 'CONFUSED' THEN 1 ELSE 0 END) AS confused_attempts,
       ROUND((SUM(CASE WHEN qa.verdict = 'CONFUSED' THEN 1 ELSE 0 END) / COUNT(qa.attempt_id)) * 100, 2) AS confusion_rate_pct
   FROM TOPICS t
   INNER JOIN SUBJECTS s ON t.subject_id = s.subject_id
   INNER JOIN QUIZ_ATTEMPTS qa ON t.topic_id = qa.topic_id
   GROUP BY s.subject_name, t.topic_id, t.topic_name, t.difficulty_level
   HAVING confusion_rate_pct > (
       SELECT (SUM(CASE WHEN sub_qa.verdict = 'CONFUSED' THEN 1 ELSE 0 END) / COUNT(sub_qa.attempt_id)) * 100
       FROM QUIZ_ATTEMPTS sub_qa
       INNER JOIN TOPICS sub_t ON sub_qa.topic_id = sub_t.topic_id
       WHERE sub_t.subject_id = s.subject_id
   );
   ```

---

## 10. Conclusion & Key Takeaways

The **AI Tutor & Skill Tree** project showcases that modern intelligent educational tools require deep database integration:
- Strict relational constraints and DAG graph modeling guarantee student mastery states remain consistent and sound.
- In-database triggers and stored routines eliminate application-level race conditions and enforce pedagogical guardrails directly at the data tier.
- Polyglot storage cleanly separates high-throughput ACID transactions in MySQL 8.0+ from dense semantic vector searches in ChromaDB.
