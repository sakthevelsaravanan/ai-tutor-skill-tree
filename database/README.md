# Database Architecture & Execution Guide

This directory contains the complete MySQL 8.0+ relational implementation for the **AI Tutor & Skill Tree** project, split cleanly across two member-owned SQL files to preserve Git blame integrity and rubric alignment.

---

## 1. Execution Order & Quick Start

> [!IMPORTANT]
> `01_curriculum_rbac_recursive.sql` (Member 1) **must** be executed before `02_sessions_triggers_procedures.sql` (Member 2). The session and mastery tables in script 2 depend on foreign keys (`USERS`, `SUBJECTS`, `TOPICS`) defined in script 1.

### Option A: Using MySQL Command Line Client / PowerShell

```powershell
# Step 1: Run Member 1's script (Creates database, 5 curriculum tables, RBAC, DML, CTEs)
Get-Content database/01_curriculum_rbac_recursive.sql | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p

# Step 2: Run Member 2's script (Creates 4 session/mastery tables, triggers, stored procedures, functions, correlated queries)
Get-Content database/02_sessions_triggers_procedures.sql | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p
```

### Option B: Using MySQL Workbench
1. Open MySQL Workbench and connect to your local MySQL instance.
2. Open `database/01_curriculum_rbac_recursive.sql` and execute the entire script (`Ctrl + Shift + Enter`).
3. Open `database/02_sessions_triggers_procedures.sql` and execute the entire script (`Ctrl + Shift + Enter`).

---

## 2. File Ownership & Rubric Mapping

### `01_curriculum_rbac_recursive.sql` — Authored by Member 1 (Roshan2607)
* **M1-DB1 (Core Relational DDL & Constraints)**:
  * `USERS` — Platform accounts with role `ENUM('student', 'instructor')` and unique email.
  * `SUBJECTS` — STEM domains (`dsa`, `dvlsi`, `cs`, `networks`) with vector indexing state.
  * `TEXTBOOKS` — Textbook metadata linked to ChromaDB collections with `CHECK (chunk_count >= 0)`.
  * `TOPICS` — Fine-grained concepts with `CHECK (difficulty_level BETWEEN 1 AND 3)`, `visual_type ENUM('iframe', 'p5js')`, and embed URLs.
  * `TOPIC_PREREQUISITES` — Composite PK `(topic_id, prereq_topic_id)` with `CHECK (topic_id <> prereq_topic_id)` and `CHECK (importance_weight BETWEEN 1 AND 5)`.
* **M1-DB2 (Database RBAC & Security)**:
  * `CREATE ROLE student_role` with read-only grants on curriculum tables and views.
  * `CREATE ROLE instructor_role` with full authoring and administrative privileges.
  * Secure views: `vw_student_curriculum`, `vw_available_subjects`, `vw_topic_prerequisite_graph`.
* **M1-DB3 (DML Seed Data & Runtime CRUD)**:
  * Seed data for instructors, students, 4 STEM subjects, textbooks, 23 topics, and 25+ directed prerequisite edges.
  * Runtime operational queries for updating textbooks, altering topic visualizers, and pruning prerequisite edges.
* **M1-DB4 (Recursive CTEs & Multi-Table Joins)**:
  * **Recursive CTE 1 (Ancestor Walk)**: Traversing prerequisite DAG upward to identify foundational gaps.
  * **Recursive CTE 2 (Descendant Walk)**: Traversing downstream unlocked topics.
  * **Query 3 (Multi-Table JOIN)**: Curriculum audit joining `SUBJECTS`, `TOPICS`, `TEXTBOOKS`, and prerequisites.
  * **Query 4 (Path Depth CTE)**: Critical learning path depth analysis per subject.

---

### `02_sessions_triggers_procedures.sql` — Authored by Member 2 (sakthevelsaravanan)
* **M2-DB1 (Session & Mastery DDL)**:
  * `LEARNING_SESSIONS` — UUID `session_id CHAR(36)`, 5-stage enum (`'topic'`, `'explore'`, `'quiz'`, `'check'`, `'clarify'`), `quiz_difficulty`, `confused_count`.
  * `CONVERSATION_LOGS` — Turn-by-turn chat history (`role`, `stage`, `content`).
  * `QUIZ_ATTEMPTS` — Quantitative assessment records (`mcq_score 0-3`, `check_score 1-5`, `verdict`).
  * `STUDENT_TOPIC_MASTERY` — Composite PK `(user_id, topic_id)` tracking mastery status.
* **M2-DB4 (MySQL Triggers — 13 Marks)**:
  * `trg_after_quiz_attempt_mastery`: Automatically recalculates mastery status (`MASTERED`, `IN_PROGRESS`, `NEEDS_PREREQ_REVIEW`) whenever a quiz attempt is inserted.
  * `trg_after_session_confused_threshold`: Automatically flips topic to `NEEDS_PREREQ_REVIEW` when `confused_count >= 3`.
* **M2-DB5 (Stored Procedures & Functions — 6 Marks)**:
  * `fn_calculate_subject_mastery(user_id, subject_id)`: Returns student mastery percentage (`DECIMAL(5,2)`).
  * `sp_recommend_next_topic(user_id, subject_id, OUT topic_id, OUT reason)`: Adaptive prioritization engine (Remediation $\rightarrow$ Continuity $\rightarrow$ Progression).
  * `sp_record_quiz_and_advance_stage(session_id, mcq_score, check_score, verdict, OUT next_stage)`: Atomic quiz submission and session stage transition.
* **M2-DB3 (Nested & Correlated Subqueries — 8 Marks)**:
  * Correlated subquery for below-average performance detection against topic cohort averages.
  * Correlated subquery identifying bottleneck topics with above-average confusion rates.
  * Nested subquery with `NOT EXISTS` finding ready-to-learn unlocked concepts.
  * Aggregated subquery finding students who completed all Level 1 topics.

---

## 3. Viva Demo Cheat Sheet

### Member 1 Live Demonstration
1. **RBAC Verification**:
   ```sql
   SHOW GRANTS FOR 'student_role';
   SHOW GRANTS FOR 'instructor_role';
   ```
2. **Recursive CTE Live Traversal**:
   Run the `PrerequisiteChain` CTE with `tp.topic_id = 106` (AVL Trees) or `tp.topic_id = 109` (Dynamic Programming) to show multi-hop prerequisite resolution.
3. **Curriculum View**:
   ```sql
   SELECT * FROM vw_student_curriculum WHERE subject_key = 'dsa';
   SELECT * FROM vw_topic_prerequisite_graph;
   ```

### Member 2 Live Demonstration
1. **Trigger Automated Mastery Recalculation**:
   Insert a confused quiz attempt and demonstrate the trigger automatically updating `STUDENT_TOPIC_MASTERY`:
   ```sql
   INSERT INTO QUIZ_ATTEMPTS (session_id, user_id, topic_id, difficulty_level, mcq_score, check_score, verdict)
   VALUES ('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 3, 105, 2, 0, 1, 'CONFUSED');

   -- Verify automatic trigger update:
   SELECT * FROM STUDENT_TOPIC_MASTERY WHERE user_id = 3 AND topic_id = 105;
   -- Output will show: mastery_status = 'NEEDS_PREREQ_REVIEW'
   ```
2. **Stored Function Execution**:
   ```sql
   SELECT fn_calculate_subject_mastery(3, 1) AS dsa_mastery_pct;
   ```
3. **Stored Procedure Adaptive Recommendation**:
   ```sql
   CALL sp_recommend_next_topic(3, 1, @rec_id, @reason);
   SELECT @rec_id AS recommended_topic_id, @reason AS recommendation_reason;
   ```
