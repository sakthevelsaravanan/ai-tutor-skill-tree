
-- ============================================================
-- Project: AI Tutor & Skill Tree
-- Member 2: Adaptive Tutoring Engine & Mastery Tracking
-- File: 02_sessions_triggers_procedures.sql
-- Database: MySQL 8.0+
-- ============================================================

-- IMPORTANT:
-- Create/select the project database before running this file.
-- The USERS, SUBJECTS and TOPICS tables must exist first.
-- Those parent tables are defined in Member 1's SQL file.

-- ============================================================
-- 1. LEARNING_SESSIONS
-- Stores each student's active tutoring session and stage.
-- ============================================================

CREATE TABLE IF NOT EXISTS LEARNING_SESSIONS (
    session_id CHAR(36) PRIMARY KEY,
    user_id INT NOT NULL,
    subject_id INT NOT NULL,
    current_topic_id INT NULL,

    current_stage ENUM(
        'topic',
        'explore',
        'quiz',
        'check',
        'clarify'
    ) NOT NULL DEFAULT 'topic',

    quiz_difficulty TINYINT NOT NULL DEFAULT 1,
    confused_count INT NOT NULL DEFAULT 0,

    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_session_user
        FOREIGN KEY (user_id)
        REFERENCES USERS(user_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_session_subject
        FOREIGN KEY (subject_id)
        REFERENCES SUBJECTS(subject_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_session_topic
        FOREIGN KEY (current_topic_id)
        REFERENCES TOPICS(topic_id)
        ON DELETE SET NULL,

    CONSTRAINT chk_session_difficulty
        CHECK (quiz_difficulty BETWEEN 1 AND 3),

    CONSTRAINT chk_session_confused_count
        CHECK (confused_count >= 0)
);

-- ============================================================
-- 2. CONVERSATION_LOGS
-- Stores user messages and tutor responses for each session.
-- ============================================================

CREATE TABLE IF NOT EXISTS CONVERSATION_LOGS (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    session_id CHAR(36) NOT NULL,
    topic_id INT NULL,

    role ENUM('user', 'assistant', 'system') NOT NULL,
    stage ENUM(
        'topic',
        'explore',
        'quiz',
        'check',
        'clarify'
    ) NOT NULL,

    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_log_session
        FOREIGN KEY (session_id)
        REFERENCES LEARNING_SESSIONS(session_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_log_topic
        FOREIGN KEY (topic_id)
        REFERENCES TOPICS(topic_id)
        ON DELETE SET NULL
);

-- ============================================================
-- 3. QUIZ_ATTEMPTS
-- Records quiz scores and comprehension-check verdicts.
-- ============================================================

CREATE TABLE IF NOT EXISTS QUIZ_ATTEMPTS (
    attempt_id INT AUTO_INCREMENT PRIMARY KEY,
    session_id CHAR(36) NOT NULL,
    user_id INT NOT NULL,
    topic_id INT NOT NULL,

    difficulty_level TINYINT NOT NULL,
    mcq_score TINYINT NULL,
    check_score TINYINT NULL,

    verdict ENUM(
        'UNDERSTOOD',
        'PARTIAL',
        'CONFUSED'
    ) NULL,

    attempted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_attempt_session
        FOREIGN KEY (session_id)
        REFERENCES LEARNING_SESSIONS(session_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_attempt_user
        FOREIGN KEY (user_id)
        REFERENCES USERS(user_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_attempt_topic
        FOREIGN KEY (topic_id)
        REFERENCES TOPICS(topic_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_attempt_difficulty
        CHECK (difficulty_level BETWEEN 1 AND 3),

    CONSTRAINT chk_attempt_mcq_score
        CHECK (mcq_score BETWEEN 0 AND 3),

    CONSTRAINT chk_attempt_check_score
        CHECK (check_score BETWEEN 1 AND 5)
);

-- ============================================================
-- 4. STUDENT_TOPIC_MASTERY
-- Tracks each student's progress on each topic.
-- ============================================================

CREATE TABLE IF NOT EXISTS STUDENT_TOPIC_MASTERY (
    user_id INT NOT NULL,
    topic_id INT NOT NULL,

    mastery_status ENUM(
        'UNTOUCHED',
        'IN_PROGRESS',
        'NEEDS_PREREQ_REVIEW',
        'MASTERED'
    ) NOT NULL DEFAULT 'UNTOUCHED',

    best_mcq_score TINYINT NULL,
    latest_check_score TINYINT NULL,
    total_attempts INT NOT NULL DEFAULT 0,

    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (user_id, topic_id),

    CONSTRAINT fk_mastery_user
        FOREIGN KEY (user_id)
        REFERENCES USERS(user_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_mastery_topic
        FOREIGN KEY (topic_id)
        REFERENCES TOPICS(topic_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_mastery_mcq_score
        CHECK (best_mcq_score BETWEEN 0 AND 3),

    CONSTRAINT chk_mastery_check_score
        CHECK (latest_check_score BETWEEN 1 AND 5),

    CONSTRAINT chk_mastery_total_attempts
        CHECK (total_attempts >= 0)
);

-- ============================================================
-- End of initial Member 2 table definitions.
-- DML, analytical queries, triggers, procedures and functions
-- will be added in subsequent sections.
-- ============================================================
