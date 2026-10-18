USE ai_tutor_db;

-- ------------------------------------------------------------
-- Tables
-- ------------------------------------------------------------

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
        CHECK (confused_count >= 0),

    INDEX idx_session_user_stage (user_id, current_stage),
    INDEX idx_session_topic (current_topic_id)
) ENGINE=InnoDB;

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
        ON DELETE SET NULL,

    INDEX idx_log_session_time (session_id, created_at)
) ENGINE=InnoDB;

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
        CHECK (check_score BETWEEN 1 AND 5),

    INDEX idx_attempt_user_topic (user_id, topic_id),
    INDEX idx_attempt_verdict (verdict)
) ENGINE=InnoDB;

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
        CHECK (total_attempts >= 0),

    INDEX idx_mastery_status (user_id, mastery_status)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Triggers
-- ------------------------------------------------------------

DROP TRIGGER IF EXISTS trg_after_quiz_attempt_mastery;
DROP TRIGGER IF EXISTS trg_after_session_confused_threshold;

DELIMITER //

CREATE TRIGGER trg_after_quiz_attempt_mastery
AFTER INSERT ON QUIZ_ATTEMPTS
FOR EACH ROW
BEGIN
    DECLARE calculated_status VARCHAR(30);

    IF NEW.verdict = 'CONFUSED' OR (COALESCE(NEW.mcq_score, 0) <= 1 AND COALESCE(NEW.check_score, 1) <= 2) THEN
        SET calculated_status = 'NEEDS_PREREQ_REVIEW';
    ELSEIF NEW.verdict = 'UNDERSTOOD' AND COALESCE(NEW.mcq_score, 0) = 3 AND COALESCE(NEW.check_score, 5) >= 4 THEN
        SET calculated_status = 'MASTERED';
    ELSE
        SET calculated_status = 'IN_PROGRESS';
    END IF;

    INSERT INTO STUDENT_TOPIC_MASTERY (
        user_id,
        topic_id,
        mastery_status,
        best_mcq_score,
        latest_check_score,
        total_attempts,
        last_updated
    )
    VALUES (
        NEW.user_id,
        NEW.topic_id,
        calculated_status,
        NEW.mcq_score,
        NEW.check_score,
        1,
        CURRENT_TIMESTAMP
    )
    ON DUPLICATE KEY UPDATE
        mastery_status = calculated_status,
        best_mcq_score = GREATEST(COALESCE(best_mcq_score, 0), COALESCE(NEW.mcq_score, 0)),
        latest_check_score = COALESCE(NEW.check_score, latest_check_score),
        total_attempts = total_attempts + 1,
        last_updated = CURRENT_TIMESTAMP;
END //

CREATE TRIGGER trg_after_session_confused_threshold
AFTER UPDATE ON LEARNING_SESSIONS
FOR EACH ROW
BEGIN
    IF NEW.confused_count >= 3 AND OLD.confused_count < 3 AND NEW.current_topic_id IS NOT NULL THEN
        INSERT INTO STUDENT_TOPIC_MASTERY (
            user_id,
            topic_id,
            mastery_status,
            total_attempts,
            last_updated
        )
        VALUES (
            NEW.user_id,
            NEW.current_topic_id,
            'NEEDS_PREREQ_REVIEW',
            1,
            CURRENT_TIMESTAMP
        )
        ON DUPLICATE KEY UPDATE
            mastery_status = 'NEEDS_PREREQ_REVIEW',
            last_updated = CURRENT_TIMESTAMP;
    END IF;
END //

DELIMITER ;

-- ------------------------------------------------------------
-- Functions & Stored Procedures
-- ------------------------------------------------------------

DROP FUNCTION IF EXISTS fn_calculate_subject_mastery;
DROP PROCEDURE IF EXISTS sp_recommend_next_topic;
DROP PROCEDURE IF EXISTS sp_record_quiz_and_advance_stage;

DELIMITER //

CREATE FUNCTION fn_calculate_subject_mastery(
    p_user_id INT,
    p_subject_id INT
)
RETURNS DECIMAL(5,2)
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE v_total_topics INT DEFAULT 0;
    DECLARE v_mastered_topics INT DEFAULT 0;
    DECLARE v_percentage DECIMAL(5,2) DEFAULT 0.00;

    SELECT COUNT(*)
    INTO v_total_topics
    FROM TOPICS
    WHERE subject_id = p_subject_id;

    IF v_total_topics = 0 THEN
        RETURN 0.00;
    END IF;

    SELECT COUNT(*)
    INTO v_mastered_topics
    FROM STUDENT_TOPIC_MASTERY stm
    INNER JOIN TOPICS t ON stm.topic_id = t.topic_id
    WHERE stm.user_id = p_user_id
      AND t.subject_id = p_subject_id
      AND stm.mastery_status = 'MASTERED';

    SET v_percentage = (v_mastered_topics / v_total_topics) * 100.00;
    RETURN v_percentage;
END //

CREATE PROCEDURE sp_recommend_next_topic(
    IN p_user_id INT,
    IN p_subject_id INT,
    OUT p_recommended_topic_id INT,
    OUT p_recommendation_reason VARCHAR(255)
)
BEGIN
    DECLARE v_candidate_topic_id INT DEFAULT NULL;

    -- Check prerequisite review needs first
    SELECT tp.prereq_topic_id
    INTO v_candidate_topic_id
    FROM STUDENT_TOPIC_MASTERY stm
    INNER JOIN TOPICS t ON stm.topic_id = t.topic_id
    INNER JOIN TOPIC_PREREQUISITES tp ON t.topic_id = tp.topic_id
    LEFT JOIN STUDENT_TOPIC_MASTERY stm_prereq 
        ON tp.prereq_topic_id = stm_prereq.topic_id AND stm_prereq.user_id = p_user_id
    WHERE stm.user_id = p_user_id
      AND t.subject_id = p_subject_id
      AND stm.mastery_status = 'NEEDS_PREREQ_REVIEW'
      AND (stm_prereq.mastery_status IS NULL OR stm_prereq.mastery_status <> 'MASTERED')
    ORDER BY tp.importance_weight DESC
    LIMIT 1;

    IF v_candidate_topic_id IS NOT NULL THEN
        SET p_recommended_topic_id = v_candidate_topic_id;
        SET p_recommendation_reason = 'Remediation: Foundational prerequisite review.';
    ELSE
        -- Resume in-progress topic
        SELECT stm.topic_id
        INTO v_candidate_topic_id
        FROM STUDENT_TOPIC_MASTERY stm
        INNER JOIN TOPICS t ON stm.topic_id = t.topic_id
        WHERE stm.user_id = p_user_id
          AND t.subject_id = p_subject_id
          AND stm.mastery_status = 'IN_PROGRESS'
        ORDER BY stm.last_updated DESC
        LIMIT 1;

        IF v_candidate_topic_id IS NOT NULL THEN
            SET p_recommended_topic_id = v_candidate_topic_id;
            SET p_recommendation_reason = 'Continuity: Resuming in-progress topic.';
        ELSE
            -- Next untouched topic with fulfilled prerequisites
            SELECT t.topic_id
            INTO v_candidate_topic_id
            FROM TOPICS t
            LEFT JOIN STUDENT_TOPIC_MASTERY stm 
                ON t.topic_id = stm.topic_id AND stm.user_id = p_user_id
            WHERE t.subject_id = p_subject_id
              AND (stm.mastery_status IS NULL OR stm.mastery_status = 'UNTOUCHED')
              AND NOT EXISTS (
                  SELECT 1
                  FROM TOPIC_PREREQUISITES tp
                  LEFT JOIN STUDENT_TOPIC_MASTERY prereq_stm 
                      ON tp.prereq_topic_id = prereq_stm.topic_id AND prereq_stm.user_id = p_user_id
                  WHERE tp.topic_id = t.topic_id
                    AND (prereq_stm.mastery_status IS NULL OR prereq_stm.mastery_status <> 'MASTERED')
              )
            ORDER BY t.difficulty_level ASC, t.topic_id ASC
            LIMIT 1;

            IF v_candidate_topic_id IS NOT NULL THEN
                SET p_recommended_topic_id = v_candidate_topic_id;
                SET p_recommendation_reason = 'Progression: Prerequisites fulfilled.';
            ELSE
                SET p_recommended_topic_id = NULL;
                SET p_recommendation_reason = 'Complete: All topics mastered.';
            END IF;
        END IF;
    END IF;
END //

CREATE PROCEDURE sp_record_quiz_and_advance_stage(
    IN p_session_id CHAR(36),
    IN p_mcq_score TINYINT,
    IN p_check_score TINYINT,
    IN p_verdict VARCHAR(20),
    OUT p_next_stage VARCHAR(20)
)
BEGIN
    DECLARE v_user_id INT;
    DECLARE v_topic_id INT;
    DECLARE v_diff TINYINT;

    SELECT user_id, current_topic_id, quiz_difficulty
    INTO v_user_id, v_topic_id, v_diff
    FROM LEARNING_SESSIONS
    WHERE session_id = p_session_id;

    IF v_user_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Session not found.';
    END IF;

    INSERT INTO QUIZ_ATTEMPTS (
        session_id,
        user_id,
        topic_id,
        difficulty_level,
        mcq_score,
        check_score,
        verdict
    )
    VALUES (
        p_session_id,
        v_user_id,
        v_topic_id,
        v_diff,
        p_mcq_score,
        p_check_score,
        p_verdict
    );

    IF p_verdict = 'CONFUSED' THEN
        SET p_next_stage = 'clarify';
        UPDATE LEARNING_SESSIONS
        SET current_stage = 'clarify',
            confused_count = confused_count + 1
        WHERE session_id = p_session_id;
    ELSEIF p_verdict = 'UNDERSTOOD' THEN
        SET p_next_stage = 'explore';
        UPDATE LEARNING_SESSIONS
        SET current_stage = 'explore',
            confused_count = 0
        WHERE session_id = p_session_id;
    ELSE
        SET p_next_stage = 'check';
        UPDATE LEARNING_SESSIONS
        SET current_stage = 'check'
        WHERE session_id = p_session_id;
    END IF;
END //

DELIMITER ;

-- ------------------------------------------------------------
-- Seed Data
-- ------------------------------------------------------------

INSERT INTO LEARNING_SESSIONS (session_id, user_id, subject_id, current_topic_id, current_stage, quiz_difficulty, confused_count)
VALUES
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 3, 1, 105, 'quiz', 2, 0),
('b2c3d4e5-f6a7-8901-bcde-fa2345678901', 4, 2, 206, 'clarify', 3, 2),
('c3d4e5f6-a7b8-9012-cdef-ab3456789012', 5, 3, 303, 'explore', 2, 0)
ON DUPLICATE KEY UPDATE current_stage = VALUES(current_stage);

INSERT INTO CONVERSATION_LOGS (session_id, topic_id, role, stage, content)
VALUES
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 105, 'assistant', 'topic', 'BST maintains invariant where left < root < right.'),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 105, 'user', 'explore', 'How does deletion work for two children?'),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 105, 'assistant', 'explore', 'Replace node with in-order successor or predecessor.'),
('b2c3d4e5-f6a7-8901-bcde-fa2345678901', 206, 'user', 'clarify', 'Why does clock skew cause hold violations regardless of clock frequency?')
ON DUPLICATE KEY UPDATE content = VALUES(content);

INSERT INTO QUIZ_ATTEMPTS (session_id, user_id, topic_id, difficulty_level, mcq_score, check_score, verdict)
VALUES
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 3, 101, 1, 3, 5, 'UNDERSTOOD'),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 3, 102, 1, 3, 4, 'UNDERSTOOD'),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 3, 104, 2, 1, 2, 'CONFUSED'),
('b2c3d4e5-f6a7-8901-bcde-fa2345678901', 4, 201, 1, 3, 5, 'UNDERSTOOD'),
('b2c3d4e5-f6a7-8901-bcde-fa2345678901', 4, 202, 1, 3, 4, 'UNDERSTOOD'),
('b2c3d4e5-f6a7-8901-bcde-fa2345678901', 4, 206, 3, 0, 1, 'CONFUSED');

INSERT INTO STUDENT_TOPIC_MASTERY (user_id, topic_id, mastery_status, best_mcq_score, latest_check_score, total_attempts)
VALUES
(3, 101, 'MASTERED', 3, 5, 1),
(3, 102, 'MASTERED', 3, 4, 1),
(3, 104, 'NEEDS_PREREQ_REVIEW', 1, 2, 1),
(4, 201, 'MASTERED', 3, 5, 1),
(4, 202, 'MASTERED', 3, 4, 1),
(4, 206, 'NEEDS_PREREQ_REVIEW', 0, 1, 1)
ON DUPLICATE KEY UPDATE mastery_status = VALUES(mastery_status);

-- ------------------------------------------------------------
-- Nested & Correlated Queries
-- ------------------------------------------------------------

-- Below-average performance lookup
SELECT 
    u.full_name,
    s.subject_name,
    t.topic_name,
    qa.mcq_score AS student_score,
    (
        SELECT ROUND(AVG(sub_qa.mcq_score), 2)
        FROM QUIZ_ATTEMPTS sub_qa
        WHERE sub_qa.topic_id = qa.topic_id
    ) AS cohort_topic_average
FROM QUIZ_ATTEMPTS qa
INNER JOIN USERS u ON qa.user_id = u.user_id
INNER JOIN TOPICS t ON qa.topic_id = t.topic_id
INNER JOIN SUBJECTS s ON t.subject_id = s.subject_id
WHERE qa.mcq_score < (
    SELECT AVG(inner_qa.mcq_score)
    FROM QUIZ_ATTEMPTS inner_qa
    WHERE inner_qa.topic_id = qa.topic_id
)
ORDER BY s.subject_name, t.topic_name;

-- Bottleneck topic detection
SELECT 
    s.subject_name,
    t.topic_id,
    t.topic_name,
    t.difficulty_level,
    COUNT(qa.attempt_id) AS total_topic_attempts,
    SUM(CASE WHEN qa.verdict = 'CONFUSED' THEN 1 ELSE 0 END) AS confused_attempts,
    ROUND(SUM(CASE WHEN qa.verdict = 'CONFUSED' THEN 1 ELSE 0 END) * 100.0 / COUNT(qa.attempt_id), 1) AS confusion_rate_pct
FROM QUIZ_ATTEMPTS qa
INNER JOIN TOPICS t ON qa.topic_id = t.topic_id
INNER JOIN SUBJECTS s ON t.subject_id = s.subject_id
GROUP BY s.subject_name, t.topic_id, t.topic_name, t.difficulty_level
HAVING confusion_rate_pct > (
    SELECT (SUM(CASE WHEN inner_qa.verdict = 'CONFUSED' THEN 1 ELSE 0 END) * 100.0) / COUNT(inner_qa.attempt_id)
    FROM QUIZ_ATTEMPTS inner_qa
    INNER JOIN TOPICS inner_t ON inner_qa.topic_id = inner_t.topic_id
    WHERE inner_t.subject_id = t.subject_id
)
ORDER BY confusion_rate_pct DESC;

-- Topics unlocked and ready to attempt
SELECT 
    t.topic_id,
    t.topic_name,
    t.difficulty_level,
    t.visual_type
FROM TOPICS t
WHERE t.subject_id = 1
  AND t.topic_id NOT IN (
      SELECT topic_id 
      FROM STUDENT_TOPIC_MASTERY 
      WHERE user_id = 3 AND mastery_status IN ('MASTERED', 'IN_PROGRESS')
  )
  AND NOT EXISTS (
      SELECT 1
      FROM TOPIC_PREREQUISITES tp
      WHERE tp.topic_id = t.topic_id
        AND tp.prereq_topic_id NOT IN (
            SELECT topic_id
            FROM STUDENT_TOPIC_MASTERY
            WHERE user_id = 3 AND mastery_status = 'MASTERED'
        )
  );

-- Students who completed foundational topics
SELECT 
    u.user_id,
    u.full_name,
    u.email
FROM USERS u
WHERE u.role = 'student'
  AND u.user_id IN (
      SELECT stm.user_id
      FROM STUDENT_TOPIC_MASTERY stm
      INNER JOIN TOPICS t ON stm.topic_id = t.topic_id
      WHERE t.subject_id = 2 AND t.difficulty_level = 1 AND stm.mastery_status = 'MASTERED'
      GROUP BY stm.user_id
      HAVING COUNT(DISTINCT t.topic_id) = (
          SELECT COUNT(*)
          FROM TOPICS
          WHERE subject_id = 2 AND difficulty_level = 1
      )
  );

-- ------------------------------------------------------------
-- RBAC Grants
-- ------------------------------------------------------------

GRANT SELECT, INSERT, UPDATE ON ai_tutor_db.LEARNING_SESSIONS TO student_role;
GRANT SELECT, INSERT ON ai_tutor_db.CONVERSATION_LOGS TO student_role;
GRANT SELECT, INSERT ON ai_tutor_db.QUIZ_ATTEMPTS TO student_role;
GRANT SELECT ON ai_tutor_db.STUDENT_TOPIC_MASTERY TO student_role;
GRANT EXECUTE ON FUNCTION ai_tutor_db.fn_calculate_subject_mastery TO student_role;
GRANT EXECUTE ON PROCEDURE ai_tutor_db.sp_recommend_next_topic TO student_role;
GRANT EXECUTE ON PROCEDURE ai_tutor_db.sp_record_quiz_and_advance_stage TO student_role;

GRANT ALL PRIVILEGES ON ai_tutor_db.* TO instructor_role;
