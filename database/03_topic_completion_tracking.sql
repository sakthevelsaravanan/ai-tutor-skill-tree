USE ai_tutor_db;

-- ============================================================
-- FEATURE: MANUAL TOPIC COMPLETION TRACKING
-- ============================================================
-- Allows students to manually mark topics as completed once they
-- finish studying them in the Socratic AI chatbox.
--
-- Design Properties:
-- 1. Third Normal Form (3NF) relational table with UUID/INT keys.
-- 2. Enforces foreign key referential integrity with CASCADE on user/topic deletion.
-- 3. Unique composite constraint (user_id, topic_id) preventing duplicate completion records.
-- 4. B-Tree indexes on user_id and topic_id for sub-millisecond status lookups.
-- 5. Independent of automated quiz attempt mastery and stored procedures.
-- ============================================================

CREATE TABLE IF NOT EXISTS STUDENT_TOPIC_COMPLETIONS (
    completion_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    topic_id INT NOT NULL,
    completed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comp_user FOREIGN KEY (user_id)
        REFERENCES USERS(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_comp_topic FOREIGN KEY (topic_id)
        REFERENCES TOPICS(topic_id) ON DELETE CASCADE,
    CONSTRAINT uq_user_topic_completion UNIQUE (user_id, topic_id),
    INDEX idx_comp_user (user_id),
    INDEX idx_comp_topic (topic_id)
) ENGINE=InnoDB;
