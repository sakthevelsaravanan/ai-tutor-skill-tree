# Chapter1: Relational STEM Skill Tree & Vector Knowledge Base

---

## 1. System Overview & Problem Statement

Modern STEM curriculums (such as Computer Science, Digital Electronics, and Data Structures) are inherently hierarchical and non-linear. Students struggling with advanced topics (e.g., *Gate-Level Minimization* or *Synchronous Sequential Logic*) often fail not because the concept is inherently incomprehensible, but due to unaddressed prerequisite gaps in foundational modules (e.g., *Binary Numbers* or *Boolean Algebra*).

Traditional Learning Management Systems (LMS) record flat progress percentages and lack relational DAG graph awareness. They cannot traverse concept dependency chains, enforce strict sequential prerequisite ordering, or ground tutoring answers strictly in verifiable course textbooks.

**Chapter1** solves this by unifying:
1. **A Normalized Relational Directed Acyclic Graph (DAG)** in **PostgreSQL 18** (with MySQL 8.0 compatibility scripts) modeling multi-hop prerequisite dependencies via Recursive Common Table Expressions (CTEs), referential integrity constraints, and idempotent completion tracking.
2. **Dense Vector Knowledge Retrieval (ChromaDB)** using 384-dimensional dense semantic embeddings and cosine distance indexing (HNSW) to ground tutoring responses strictly in uploaded textbook passages and slide materials.
3. **Strict Role-Based Sequential Learning**: Enforces prerequisite gating for `student` accounts (locking downstream chapters until prerequisites are mastered and marked done) while providing unlocked inspection access for `instructor` and `admin` roles.
4. **An Interactive Full-Stack Application** built with **FastAPI** and **Next.js 14**, featuring an interactive Skill Tree DAG, slide-grounded Socratic tutoring with live streaming, and a dedicated Vector Store Manager for real-time ChromaDB collection inspection.

---

## 2. 50-Mark DBMS Evaluation Rubric & Team Split

The project is engineered to strictly satisfy every component of the 50-mark DBMS evaluation rubric across two team members:

| Rubric Component | Marks | Member 1 Responsibilities | Member 2 Responsibilities |
| :--- | :---: | :--- | :--- |
| **1. Database Design (ER & 3NF Schema)** | **5** | Normalized 3NF Entities: `USERS`, `SUBJECTS`, `TOPICS`, `TOPIC_PREREQUISITES`. Conceptual ER modeling & relational mapping. | Normalized 3NF Entities: `STUDENT_TOPIC_COMPLETIONS`, `LEARNING_SESSIONS`, `CONVERSATION_LOGS`. State machine & constraint design. |
| **2. DB Creation & Tech Justification** | **9** | Curriculum DDL, ChromaDB collection setup, polyglot storage justification matrix (Relational vs. Vector). | Session & completion DDL, referential integrity cascades, composite primary keys, B-Tree indexing strategy. |
| **3. SQL Operations & Graph Queries** | **8** | Recursive CTEs (Ancestor prerequisite traversal, Descendant unlocked pathways), multi-table curriculum joins. | Correlated subqueries comparing student progress to cohort averages, nested `NOT EXISTS` unlocked topic queries. |
| **4. Advanced Database Concepts** | **13** | ChromaDB Vector RUD (Create, Read, Update, Delete) + Recursive CTE DAG walks (7 Marks). | Database Triggers (`trg_after_quiz_attempt_mastery`), Stored Procedure (`sp_recommend_next_topic`), Stored Function (`fn_calculate_subject_mastery`) (6 Marks). |
| **5. Web App & Database Integration** | **5** | Document Ingestion pipeline, Vector Store Manager UI, FastAPI core REST backend, and ChromaDB search. | Interactive Next.js Skill Tree DAG viewer, Socratic Tutor Chat with live token streaming, and sequential unlock engine. |
| **6. Authentication & Security (RBAC)** | **4** | Role-Based Access Control (`student`, `instructor`, `admin`), password hashing, secure curriculum projections. | Session ownership validation, user identity verification, prerequisite lock enforcement guardrails. |
| **7. Documentation, Git & Viva Defense** | **6** | Git repository architecture, Chapters 1–3 documentation, vector benchmarks, viva demo runbook. | Git commit history, Chapters 4–6 documentation, automated test suites, viva code defense guide. |

---

## 3. System Architecture

```
                  +-------------------------------------------------------+
                  |               Next.js 14 Web Frontend                 |
                  |     (TypeScript, Tailwind CSS, Skill Tree, Chat UI)   |
                  +---------------------------+---------------------------+
                                              | HTTP / REST (JSON)
                                              v
                  +-------------------------------------------------------+
                  |                 FastAPI Backend Server                |
                  |   - /api/auth           - /api/curriculum             |
                  |   - /api/vectors        - /api/tutor                  |
                  |   - /api/sessions       - /health                     |
                  +-------------+---------------------------+-------------+
                                |                           |
                  Relational Queries & CRUD        Dense Semantic Embeddings
                                |                           |
                                v                           v
+--------------------------------------------------+  +-----------------------------------+
|            PostgreSQL 18 / MySQL 8.0 Core        |  |         ChromaDB Vector Store     |
| - 3NF Normalized Relational Schema               |  | - Persistent Embeddings           |
| - Self-Referencing Prerequisite Adjacency Table  |  | - HNSW Cosine Distance Indexing   |
| - Recursive CTEs for Multi-Hop Graph Traversal   |  | - Collections per Subject Domain  |
| - Idempotent Completion Tracking (UNIQUE Keys)   |  | - Full Vector RUD Operations      |
| - ACID Multi-Table Transactions                  |  | - Textbook Passage Chunking       |
| - RBAC: student, instructor, admin               |  +-----------------------------------+
+--------------------------------------------------+
```

---

## 4. Polyglot Persistence Architecture Justification

A central architectural decision in Chapter1 is **polyglot persistence**: combining a relational DBMS (PostgreSQL 18 / MySQL 8.0) with a specialized vector database (ChromaDB).

| Evaluation Parameter | Relational Core (PostgreSQL 18 / MySQL) | ChromaDB Vector Store |
| :--- | :--- | :--- |
| **Data Nature** | Highly structured tabular data, strict data types, entity relationships, and foreign keys. | High-dimensional unstructured text embeddings (384-d floating-point arrays). |
| **Primary Indexing** | B-Tree and Hash indexes on primary/foreign keys (`idx_comp_user`, `idx_comp_topic`). | Hierarchical Navigable Small World (HNSW) graph for Approximate Nearest Neighbor (ANN) search. |
| **Query Engine** | Relational algebra, multi-table `JOIN`s, Recursive Common Table Expressions (`WITH RECURSIVE`). | Cosine distance similarity metric: $\text{Cosine}(u, v) = \frac{u \cdot v}{\|u\| \|v\|}$. |
| **System Responsibilities**| User authentication, RBAC, curriculum DAG hierarchy, student completion state, session history. | Semantic vector search matching student questions to exact textbook sections with match scores. |
| **Integrity & Guarantees** | Strict ACID compliance, foreign key cascades (`ON DELETE CASCADE`), `UNIQUE` composite constraints. | Eventually consistent vector persistence with Vector RUD operational endpoints. |

---

## 5. Relational Database Schema (Third Normal Form - 3NF)

The database schema is strictly normalized to Third Normal Form (3NF). Discrete entities are isolated into independent tables to eliminate insertion, update, and deletion anomalies.

### Core Tables (`database/postgres/001_schema.sql`)

```sql
-- 1. Users Table (RBAC & Authentication)
CREATE TABLE users (
    user_id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    full_name varchar(100) NOT NULL,
    email varchar(255) NOT NULL UNIQUE,
    password_hash varchar(255) NOT NULL,
    role varchar(20) NOT NULL CHECK (role IN ('student', 'instructor', 'admin')),
    created_at timestamptz NOT NULL DEFAULT now()
);

-- 2. Subjects Table (Course Domains)
CREATE TABLE subjects (
    subject_id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    subject_key varchar(50) NOT NULL UNIQUE,
    subject_name varchar(100) NOT NULL,
    description text,
    is_indexed boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- 3. Topics Table (Curriculum Concepts)
CREATE TABLE topics (
    topic_id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    subject_id integer NOT NULL REFERENCES subjects ON DELETE CASCADE,
    topic_name varchar(100) NOT NULL,
    difficulty_level smallint NOT NULL CHECK (difficulty_level BETWEEN 1 AND 3),
    source_file text,
    start_page integer,
    end_page integer,
    sort_order integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(subject_id, topic_name)
);

-- 4. Topic Prerequisites Table (Self-Referencing Adjacency Table)
CREATE TABLE topic_prerequisites (
    topic_id integer NOT NULL REFERENCES topics ON DELETE CASCADE,
    prereq_topic_id integer NOT NULL REFERENCES topics ON DELETE CASCADE,
    importance_weight smallint NOT NULL DEFAULT 3 CHECK (importance_weight BETWEEN 1 AND 5),
    basis text NOT NULL DEFAULT 'curated' CHECK (basis IN ('curated', 'book_order')),
    PRIMARY KEY(topic_id, prereq_topic_id),
    CHECK(topic_id <> prereq_topic_id)
);

-- 5. Student Topic Completions Table (Progress & Unlock Tracking)
CREATE TABLE student_topic_completions (
    completion_id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id integer NOT NULL REFERENCES users ON DELETE CASCADE,
    topic_id integer NOT NULL REFERENCES topics ON DELETE CASCADE,
    completed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(user_id, topic_id)
);
CREATE INDEX idx_comp_user ON student_topic_completions(user_id);
CREATE INDEX idx_comp_topic ON student_topic_completions(topic_id);
```

### Relational Integrity Highlights
- **Referential Integrity (`ON DELETE CASCADE`)**: Deleting a subject or topic cascades automatically, removing dependent prerequisite edges, completions, and session logs without orphaned rows.
- **Cycle Prevention (`CHECK (topic_id <> prereq_topic_id)`)**: Prohibits self-loop dependencies at the database constraint level.
- **Idempotent Progress (`UNIQUE(user_id, topic_id)`)**: Guarantees that multiple clicks on "Mark as Done" never produce duplicate completion records.
- **B-Tree Indexing**: Dedicated indexes on `(user_id)` and `(topic_id)` ensure $O(\log N)$ lookup performance when computing live lock states.

---

## 6. Advanced SQL & Graph Queries

### A. Recursive CTE: Upward Prerequisite Ancestor Traversal
When a student attempts a concept, Chapter1 executes a Recursive Common Table Expression to resolve the complete transitive ancestor chain:

```sql
WITH RECURSIVE PrerequisiteAncestors AS (
    -- Anchor member: immediate prerequisites of the target topic
    SELECT 
        tp.topic_id,
        tp.prereq_topic_id,
        1 AS depth
    FROM topic_prerequisites tp
    WHERE tp.topic_id = :target_topic_id

    UNION ALL

    -- Recursive member: follow prerequisite edges upward
    SELECT 
        parent.topic_id,
        parent.prereq_topic_id,
        pa.depth + 1
    FROM topic_prerequisites parent
    INNER JOIN PrerequisiteAncestors pa 
        ON parent.topic_id = pa.prereq_topic_id
)
SELECT 
    t.topic_name AS target_concept,
    pt.topic_name AS required_ancestor,
    pa.depth
FROM PrerequisiteAncestors pa
INNER JOIN topics t ON pa.topic_id = t.topic_id
INNER JOIN topics pt ON pa.prereq_topic_id = pt.topic_id
ORDER BY pa.depth DESC;
```

### B. Nested & Correlated Subqueries
1. **Ready-to-Learn Unlocked Concepts (`NOT EXISTS`)**:
   ```sql
   SELECT t.topic_id, t.topic_name
   FROM topics t
   WHERE t.subject_id = :subject_id
     AND t.topic_id NOT IN (
         SELECT topic_id FROM student_topic_completions WHERE user_id = :user_id
     )
     AND NOT EXISTS (
         -- Must not have any uncompleted prerequisites
         SELECT 1 
         FROM topic_prerequisites tp
         WHERE tp.topic_id = t.topic_id
           AND tp.prereq_topic_id NOT IN (
               SELECT topic_id FROM student_topic_completions WHERE user_id = :user_id
           )
     );
   ```

2. **Cohort Bottleneck Detection**:
   Identifies topics where confusion rates exceed the global course average using a correlated subquery in the `HAVING` clause (`database/02_sessions_triggers_procedures.sql`).

---

## 7. Vector RUD & Slide-Grounded Socratic RAG Pipeline

### Vector Store RUD Operations (ChromaDB)
Chapter1 implements complete Create, Read, Update, and Delete operations for dense vectors:
1. **Create (`POST /api/vectors/chunk` / PDF Ingestion)**: Ingests documents, splits passages into semantic chunks, computes 384-dimensional embeddings, and stores vectors with metadata (`page_number`, `file_name`, `topic_name`).
2. **Read (`GET /api/vectors/chunks/{subject_key}` / Search)**: Inspects stored passages with pagination, cosine distance metrics, and keyword filtering.
3. **Update (`PUT /api/vectors/chunk`)**: Edits passage text and recomputes the dense embedding vector in-place.
4. **Delete (`DELETE /api/vectors/chunk`)**: Atomically deletes the chunk from ChromaDB and updates subject passage counters.

### Slide-Grounded Response Synthesis
The tutor pipeline generates academically grounded explanations without hallucinations:
- **Noise & Boilerplate Purging**: Strips administrative slides, table headers, copyright notices, and practice problems (`1.7 * Convert...`).
- **Complete Grammatical Sentences**: Automatically de-hyphenates words split across newlines (e.g. `representa-\ntion` $\rightarrow$ `representation`) and filters out sentence fragments or dangling verbs.
- **Attribution & Transparency**: Every synthesized section includes verifiable citation tags:
  ```markdown
  #### **Octal and Hexadecimal Numbers** `(Match: 81.9% · Page 27)`
  ```
- **Zero Conversational Fluff**: No extraneous introductory phrases ("Our interest here is...") and zero unsolicited reflective questions.

---

## 8. Role-Based Access Control (RBAC) & Sequential Learning

Chapter1 enforces three distinct security roles:

| Role | Default User | Permissions & UI Behavior |
| :--- | :--- | :--- |
| **`student`** | `student` (`password123`) | **Sequential Prerequisite Enforced**: Chapters are locked (`🔒`) until prerequisites are completed. Selecting locked chapters in Tutor dropdown triggers an amber warning banner. Clicking "Mark as Done" unlocks subsequent chapters immediately. |
| **`instructor`**| `instructor` (`password123`) | **Fully Unlocked**: Unrestricted access to all chapters. Can inspect curriculum DAG, view all passages, and upload course materials. |
| **`admin`** | `admin` (`password123`) | **Root Administrative Access**: Full CRUD across users, subjects, vector collections, and database tables. |

---

## 9. Quick Start Guide (1-Click Launch)

### Prerequisites
- **Python 3.10+** (Python 3.11 recommended)
- **Node.js 18+** & **npm**
- **PostgreSQL 18** installed locally

### Option 1: 1-Click Automated Startup (Recommended)
Open PowerShell in the project root and run:

```powershell
.\start.ps1
```

The script automatically:
1. Validates and starts the PostgreSQL daemon on port `5433` (data directory: `.runtime/postgres`).
2. Verifies ChromaDB vector persistence in `.runtime/chroma_db`.
3. Launches the FastAPI backend server on **`http://localhost:8000`**.
4. Launches the Next.js frontend client on **`http://localhost:3000`**.

### Option 2: Manual Step-by-Step Launch

1. **Start PostgreSQL**:
   ```powershell
   & "C:\Program Files\PostgreSQL\18\bin\postgres.exe" -D ".runtime\postgres" -p 5433 -h 127.0.0.1
   ```

2. **Start FastAPI Backend**:
   ```powershell
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```
   *Swagger API Documentation: `http://localhost:8000/docs`*

3. **Start Next.js Frontend**:
   ```powershell
   cd frontend
   npm run dev
   ```
   *Web Application: `http://localhost:3000`*

---

## 10. Viva Defense & Live Demo Walkthrough

When presenting Chapter1 for the 50-mark evaluation, follow this structured runbook:

### Step 1: Authentication & RBAC Demonstration
1. Open `http://localhost:3000`. Click the **Student** 1-click demo button.
2. Navigate to the **Skill Tree**: show that Chapter 1 is unlocked, while Chapters 2 through 10 are locked (`🔒 Locked`).
3. Switch to the **Tutor** tab: demonstrate that selecting Chapter 3 in the dropdown is blocked with an amber lock notification.
4. Sign out and click **Instructor**: show that all chapters are immediately unlocked for teaching staff.

### Step 2: Sequential Learning & Completion Demonstration
1. Sign back in as **Student**. Navigate to Chapter 1 in the Tutor.
2. Ask a concept question: *"Explain binary to hexadecimal conversion."*
3. Highlight the synthesized response:
   - Notice the verifiable attribution header: `#### **Octal and Hexadecimal Numbers** (Match: 81.9% · Page 27)`.
   - Notice the clean, complete sentences without cutoffs or conversational fluff.
4. Click **Mark as Done** beside the composer:
   - Topic completes via PostgreSQL transaction in `student_topic_completions`.
   - Chapter 2 immediately unlocks on the Skill Tree with a green tick mark (`✓`).

### Step 3: Recursive CTE Live Traversal
Open PostgreSQL `psql` (port 5433) or DBeaver and execute the ancestor prerequisite CTE:
```sql
-- Target topic 86 (Combinational Logic)
WITH RECURSIVE PrereqWalk AS (
    SELECT topic_id, prereq_topic_id, 1 AS depth
    FROM topic_prerequisites
    WHERE topic_id = 86
    UNION ALL
    SELECT p.topic_id, p.prereq_topic_id, pw.depth + 1
    FROM topic_prerequisites p
    INNER JOIN PrereqWalk pw ON p.topic_id = pw.prereq_topic_id
)
SELECT t.topic_name, pt.topic_name AS prereq_name, pw.depth
FROM PrereqWalk pw
JOIN topics t ON pw.topic_id = t.topic_id
JOIN topics pt ON pw.prereq_topic_id = pt.topic_id;
```
Show how the engine traverses multi-hop ancestors (*Digital Systems* $\rightarrow$ *Boolean Algebra* $\rightarrow$ *Gate-Level Minimization* $\rightarrow$ *Combinational Logic*).

### Step 4: Vector Store Manager (ChromaDB Vector RUD)
1. Navigate to the **Knowledge Base** tab.
2. Demonstrate semantic vector search: search for `"NAND gate simplification"` and observe real-time cosine similarity match percentages.
3. Click **Read** on any row to expand full passage context, inspect page citations, or copy excerpts with 1 click.

---

## 11. Project Directory Structure

```
ai-tutor-skill-tree/
├── backend/                        # FastAPI REST Application
│   ├── routers/
│   │   ├── auth.py                 # JWT Authentication & RBAC Login
│   │   ├── curriculum.py           # Subject Graph, Topics, & Completion Endpoints
│   │   ├── tutor.py                # Socratic RAG Vector Tutoring Pipeline
│   │   ├── vector_rud.py           # ChromaDB Vector RUD Operations
│   │   └── sessions.py             # Session Lifecycle & Conversation Logging
│   ├── database.py                 # PostgreSQL Database Connection & Query Helpers
│   ├── vector_service.py           # ChromaDB Client & Semantic Search Engine
│   ├── pdf_indexer.py              # Textbook Parser & ChromaDB Vector Ingestion
│   └── main.py                     # FastAPI Application Initialization & Lifespan
├── database/                       # Relational DDL & Migration Scripts
│   ├── postgres/
│   │   └── 001_schema.sql          # 3NF PostgreSQL Schema & Constraints
│   ├── 01_curriculum_rbac_recursive.sql # Member 1 MySQL Schema, RBAC & CTEs
│   ├── 02_sessions_triggers_procedures.sql # Member 2 MySQL Triggers, Procs & Queries
│   └── 03_topic_completion_tracking.sql # Manual Completion Tracking Migration
├── docs/                           # Documentation & Viva Guides
│   ├── LOCAL_POSTGRES.md           # Local PostgreSQL Setup & Verification Guide
│   └── Chapter1_DBMS_Project_Code_Explanation_and_Viva_Guide.docx # Comprehensive Viva Guide
├── frontend/                       # Next.js 14 Web Application
│   ├── app/                        # Next.js App Router & Global Providers
│   ├── components/
│   │   ├── SkillTreeDag.tsx        # Interactive Skill Tree & Prerequisite DAG
│   │   ├── TutorChat.tsx           # Socratic Tutoring Interface with Live Reveal
│   │   ├── VectorStoreManager.tsx  # Knowledge Base Manager (Vector RUD UI)
│   │   ├── DocumentUpload.tsx      # Course Material Ingestion Interface
│   │   └── CustomDropdown.tsx      # Accessible Dropdown with Sequential Lock Icons
│   └── lib/                        # API Client, TypeScript Interfaces & Cookies
├── start.ps1                       # 1-Click Automated PowerShell Launcher
└── README.md                       # Comprehensive Project Documentation
```

---
