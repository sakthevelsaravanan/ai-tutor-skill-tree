# Database Architecture & DDL Guide

This directory houses the relational database schemas for the **Chapter1** platform, featuring:
1. **Primary Engine (PostgreSQL 18)**: Production migration scripts in `database/postgres/` powering the live full-stack application.
2. **Cross-Engine Rubric Scripts (MySQL 8.0)**: Cleaned standalone scripts (`01_*.sql`, `02_*.sql`, `03_*.sql`) demonstrating stored procedures, triggers, and correlated queries for the 50-mark evaluation rubric.

---

## 1. Primary Engine: PostgreSQL 18 (`database/postgres/`)

The live application runs on **PostgreSQL 18** (port `5433`, database `ai_tutor_db`). Migrations are applied in transactionally isolated batches by `scripts/bootstrap_postgres.py`.

### Migration Structure:
- **`001_schema.sql`**: Core 3NF entities: `users`, `subjects`, `topics`, `topic_prerequisites`, `learning_sessions`, `conversation_logs`, `quiz_attempts`, `student_topic_mastery`.
  - Enforces `CHECK (topic_id <> prereq_topic_id)` cycle prevention.
  - Implements PL/pgSQL triggers (`prerequisite_integrity`, `session_integrity`, `trg_after_quiz_attempt_mastery`).
- **`002_vector_journal.sql`**: `vector_operation_commits` table for two-phase transactional synchronization with ChromaDB.
- **`003_topic_completion.sql`**: `student_topic_completions` table with `UNIQUE(user_id, topic_id)` for idempotent completion tracking.
- **`004_document_structure.sql`**: Adds textbook pagination and sorting attributes (`start_page`, `end_page`, `sort_order`, `basis`).

### Bootstrapping PostgreSQL:
```powershell
# Automatically provisions roles, executes migrations, and generates credentials
python scripts/bootstrap_postgres.py
```

---

## 2. Evaluation & Demonstration Scripts: MySQL 8.0 (`database/`)

For viva defense and cross-engine evaluation, standalone MySQL scripts are preserved and cleaned of mock data:

```
database/
├── 01_curriculum_rbac_recursive.sql       # Member 1: DDL, RBAC Roles, Views, Recursive CTEs
├── 02_sessions_triggers_procedures.sql    # Member 2: Sessions, Triggers, Stored Procedures, Correlated Queries
└── 03_topic_completion_tracking.sql       # Independent Manual Completion Table
```

### Execution Order:
> [!IMPORTANT]
> `01_curriculum_rbac_recursive.sql` must be executed before `02_sessions_triggers_procedures.sql`. Script 2 foreign keys reference entities created in Script 1.

```powershell
# 1. Run Member 1's script (DDL, RBAC, Views, Recursive CTEs)
Get-Content database/01_curriculum_rbac_recursive.sql | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p

# 2. Run Member 2's script (Triggers, Procedures, Functions, Correlated Queries)
Get-Content database/02_sessions_triggers_procedures.sql | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p

# 3. Run completion tracking script
Get-Content database/03_topic_completion_tracking.sql | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p
```

---

## 3. 50-Mark Rubric Mapping

### Member 1: Curriculum DAG, Recursive CTEs & RBAC
- **Schema DDL (5 Marks)**: `USERS`, `SUBJECTS`, `TOPICS`, `TOPIC_PREREQUISITES` in 3NF.
- **Recursive CTEs (8 Marks)**:
  - *Ancestor Walk*: Resolves transitive prerequisite dependencies upwards.
  - *Descendant Walk*: Resolves downstream unlocked concepts downwards.
  - *Path Depth CTE*: Analyzes maximum curriculum depth.
- **RBAC & Security (4 Marks)**: `student_role` (read-only curriculum access) and `instructor_role` (authoring).

### Member 2: Sessions, Triggers, Stored Procedures & Analytics
- **Schema DDL (5 Marks)**: `STUDENT_TOPIC_COMPLETIONS`, `LEARNING_SESSIONS`, `CONVERSATION_LOGS`.
- **Database Triggers (6 Marks)**:
  - `trg_after_quiz_attempt_mastery`: Automatically recalculates competence upon attempt insertion.
  - `trg_after_session_confused_threshold`: Flips topic to `NEEDS_PREREQ_REVIEW` when confusion count $\ge 3$.
- **Stored Procedures & Functions (6 Marks)**:
  - `fn_calculate_subject_mastery(user_id, subject_id)`: Calculates mastery percentage.
  - `sp_recommend_next_topic(user_id, subject_id, OUT topic_id, OUT reason)`: Adaptive prioritization engine.
- **Nested & Correlated Subqueries (8 Marks)**:
  - Correlated subquery detecting performance below cohort topic averages.
  - Correlated `HAVING` subquery identifying bottleneck topics with above-average confusion rates.
  - Nested `NOT EXISTS` query identifying ready-to-learn unlocked topics.

---

## 4. Visual Diagrams & Schema Documentation

The repository includes standalone Python scripts to generate high-resolution diagrams:

```powershell
# Generate Conceptual ER Diagram (Chen / Crow's Foot Notation)
python docs/generate_conceptual_er_diagram.py
# Output: docs/conceptual_er_diagram.png

# Generate Physical Relational Schema Diagram (Table Mapping with PK/FK Connectors)
python docs/generate_relational_schema_diagram.py
# Output: docs/relational_schema_diagram.png
```
