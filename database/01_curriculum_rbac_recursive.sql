CREATE DATABASE IF NOT EXISTS ai_tutor_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE ai_tutor_db;

-- ------------------------------------------------------------
-- Tables
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS USERS (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student', 'instructor') NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_role (role),
    INDEX idx_user_email (email)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS SUBJECTS (
    subject_id INT AUTO_INCREMENT PRIMARY KEY,
    subject_key VARCHAR(50) NOT NULL UNIQUE,
    subject_name VARCHAR(100) NOT NULL,
    description TEXT NULL,
    is_indexed BOOLEAN NOT NULL DEFAULT FALSE,
    created_by INT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_subject_created_by
        FOREIGN KEY (created_by)
        REFERENCES USERS(user_id)
        ON DELETE SET NULL,
    INDEX idx_subject_key (subject_key)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS TEXTBOOKS (
    textbook_id INT AUTO_INCREMENT PRIMARY KEY,
    subject_id INT NOT NULL,
    uploaded_by INT NULL,
    file_name VARCHAR(255) NOT NULL,
    chroma_collection_name VARCHAR(100) NOT NULL,
    chunk_count INT NOT NULL DEFAULT 0,
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_textbook_subject
        FOREIGN KEY (subject_id)
        REFERENCES SUBJECTS(subject_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_textbook_user
        FOREIGN KEY (uploaded_by)
        REFERENCES USERS(user_id)
        ON DELETE SET NULL,
    CONSTRAINT chk_textbook_chunk_count
        CHECK (chunk_count >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS TOPICS (
    topic_id INT AUTO_INCREMENT PRIMARY KEY,
    subject_id INT NOT NULL,
    topic_name VARCHAR(100) NOT NULL,
    difficulty_level TINYINT NOT NULL,
    visual_type ENUM('iframe', 'p5js') NOT NULL,
    embed_url TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_topic_subject
        FOREIGN KEY (subject_id)
        REFERENCES SUBJECTS(subject_id)
        ON DELETE CASCADE,
    CONSTRAINT uq_subject_topic
        UNIQUE (subject_id, topic_name),
    CONSTRAINT chk_topic_difficulty
        CHECK (difficulty_level BETWEEN 1 AND 3),
    INDEX idx_topic_subject (subject_id),
    INDEX idx_topic_difficulty (difficulty_level)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS TOPIC_PREREQUISITES (
    topic_id INT NOT NULL,
    prereq_topic_id INT NOT NULL,
    importance_weight TINYINT NOT NULL DEFAULT 3,
    PRIMARY KEY (topic_id, prereq_topic_id),
    CONSTRAINT fk_prereq_topic
        FOREIGN KEY (topic_id)
        REFERENCES TOPICS(topic_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_prereq_parent
        FOREIGN KEY (prereq_topic_id)
        REFERENCES TOPICS(topic_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_no_self_prereq
        CHECK (topic_id <> prereq_topic_id),
    CONSTRAINT chk_importance_weight
        CHECK (importance_weight BETWEEN 1 AND 5),
    INDEX idx_prereq_parent (prereq_topic_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- RBAC & Views
-- ------------------------------------------------------------

CREATE ROLE IF NOT EXISTS student_role;
CREATE ROLE IF NOT EXISTS instructor_role;

CREATE OR REPLACE VIEW vw_student_curriculum AS
SELECT 
    s.subject_id,
    s.subject_key,
    s.subject_name,
    s.description AS subject_description,
    t.topic_id,
    t.topic_name,
    t.difficulty_level,
    t.visual_type,
    t.embed_url
FROM SUBJECTS s
INNER JOIN TOPICS t ON s.subject_id = t.subject_id
WHERE s.is_indexed = TRUE;

CREATE OR REPLACE VIEW vw_available_subjects AS
SELECT 
    s.subject_id,
    s.subject_key,
    s.subject_name,
    s.description,
    COUNT(DISTINCT t.topic_id) AS total_topics,
    COUNT(DISTINCT tb.textbook_id) AS total_textbooks,
    COALESCE(SUM(tb.chunk_count), 0) AS total_indexed_chunks
FROM SUBJECTS s
LEFT JOIN TOPICS t ON s.subject_id = t.subject_id
LEFT JOIN TEXTBOOKS tb ON s.subject_id = tb.subject_id
WHERE s.is_indexed = TRUE
GROUP BY s.subject_id, s.subject_key, s.subject_name, s.description;

CREATE OR REPLACE VIEW vw_topic_prerequisite_graph AS
SELECT 
    s.subject_name,
    t.topic_id,
    t.topic_name,
    t.difficulty_level AS topic_difficulty,
    pt.topic_id AS prereq_id,
    pt.topic_name AS prereq_name,
    pt.difficulty_level AS prereq_difficulty,
    tp.importance_weight
FROM TOPIC_PREREQUISITES tp
INNER JOIN TOPICS t ON tp.topic_id = t.topic_id
INNER JOIN TOPICS pt ON tp.prereq_topic_id = pt.topic_id
INNER JOIN SUBJECTS s ON t.subject_id = s.subject_id;

GRANT SELECT ON ai_tutor_db.SUBJECTS TO student_role;
GRANT SELECT ON ai_tutor_db.TOPICS TO student_role;
GRANT SELECT ON ai_tutor_db.TOPIC_PREREQUISITES TO student_role;
GRANT SELECT ON ai_tutor_db.TEXTBOOKS TO student_role;
GRANT SELECT ON ai_tutor_db.vw_student_curriculum TO student_role;
GRANT SELECT ON ai_tutor_db.vw_available_subjects TO student_role;
GRANT SELECT ON ai_tutor_db.vw_topic_prerequisite_graph TO student_role;

REVOKE INSERT, UPDATE, DELETE ON ai_tutor_db.SUBJECTS FROM student_role;
REVOKE INSERT, UPDATE, DELETE ON ai_tutor_db.TOPICS FROM student_role;
REVOKE INSERT, UPDATE, DELETE ON ai_tutor_db.TOPIC_PREREQUISITES FROM student_role;
REVOKE INSERT, UPDATE, DELETE ON ai_tutor_db.TEXTBOOKS FROM student_role;
REVOKE INSERT, UPDATE, DELETE ON ai_tutor_db.USERS FROM student_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON ai_tutor_db.SUBJECTS TO instructor_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ai_tutor_db.TOPICS TO instructor_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ai_tutor_db.TOPIC_PREREQUISITES TO instructor_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ai_tutor_db.TEXTBOOKS TO instructor_role;
GRANT SELECT ON ai_tutor_db.USERS TO instructor_role;
GRANT SELECT ON ai_tutor_db.vw_student_curriculum TO instructor_role;
GRANT SELECT ON ai_tutor_db.vw_available_subjects TO instructor_role;
GRANT SELECT ON ai_tutor_db.vw_topic_prerequisite_graph TO instructor_role;

-- ------------------------------------------------------------
-- Seed Data
-- ------------------------------------------------------------

INSERT INTO USERS (user_id, full_name, email, password_hash, role)
VALUES 
(1, 'Dr. Alan Turing', 'turing@aitutor.edu', '$2b$12$e80yvV8gWp5l01N0Pz71ceQ2u8c5TzB6sR4c7E9h1K0q9Z8y7w6x1', 'instructor'),
(2, 'Dr. Grace Hopper', 'hopper@aitutor.edu', '$2b$12$e80yvV8gWp5l01N0Pz71ceQ2u8c5TzB6sR4c7E9h1K0q9Z8y7w6x2', 'instructor'),
(3, 'Roshan Kumar', 'roshan@student.edu', '$2b$12$e80yvV8gWp5l01N0Pz71ceQ2u8c5TzB6sR4c7E9h1K0q9Z8y7w6x3', 'student'),
(4, 'Sakthevel Saravanan', 'sakthi@student.edu', '$2b$12$e80yvV8gWp5l01N0Pz71ceQ2u8c5TzB6sR4c7E9h1K0q9Z8y7w6x4', 'student'),
(5, 'Charlie Davis', 'charlie@student.edu', '$2b$12$e80yvV8gWp5l01N0Pz71ceQ2u8c5TzB6sR4c7E9h1K0q9Z8y7w6x5', 'student')
ON DUPLICATE KEY UPDATE full_name = VALUES(full_name);

INSERT INTO SUBJECTS (subject_id, subject_key, subject_name, description, is_indexed, created_by)
VALUES 
(1, 'dsa', 'Data Structures & Algorithms', 'Fundamental algorithmic problem-solving and data representations.', TRUE, 1),
(2, 'dvlsi', 'Digital VLSI Design', 'CMOS logic gates, semiconductor physics, and static timing analysis.', TRUE, 2),
(3, 'cs', 'Computer Systems & Architecture', 'Instruction set architectures, processor pipelining, and memory hierarchies.', TRUE, 1),
(4, 'networks', 'Computer Networks & Protocols', 'Layered networking models, TCP/IP, and routing protocols.', FALSE, 2)
ON DUPLICATE KEY UPDATE subject_name = VALUES(subject_name);

INSERT INTO TEXTBOOKS (textbook_id, subject_id, uploaded_by, file_name, chroma_collection_name, chunk_count)
VALUES
(1, 1, 1, 'Introduction_to_Algorithms_CLRS.pdf', 'chroma_dsa_clrs', 450),
(2, 2, 2, 'CMOS_VLSI_Design_Weste_Harris.pdf', 'chroma_dvlsi_weste', 380),
(3, 3, 1, 'Computer_Organization_Design_Patterson.pdf', 'chroma_cs_patterson', 410),
(4, 4, 2, 'Computer_Networking_Top_Down_Kurose.pdf', 'chroma_networks_kurose', 0)
ON DUPLICATE KEY UPDATE chunk_count = VALUES(chunk_count);

INSERT INTO TOPICS (topic_id, subject_id, topic_name, difficulty_level, visual_type, embed_url)
VALUES
(101, 1, 'Arrays & Pointer Arithmetic', 1, 'iframe', 'https://visualgo.net/en/array'),
(102, 1, 'Singly & Doubly Linked Lists', 1, 'iframe', 'https://visualgo.net/en/list'),
(103, 1, 'Stacks & Queues', 1, 'iframe', 'https://visualgo.net/en/stackqueue'),
(104, 1, 'Recursion & Backtracking', 2, 'p5js', '/visuals/p5/recursion_tree.js'),
(105, 1, 'Binary Search Trees (BST)', 2, 'iframe', 'https://visualgo.net/en/bst'),
(106, 1, 'AVL & Balanced Search Trees', 2, 'iframe', 'https://visualgo.net/en/avl'),
(107, 1, 'Graph Representations (Adjacency List & Matrix)', 2, 'p5js', '/visuals/p5/graph_traversal.js'),
(108, 1, 'Breadth-First & Depth-First Search', 2, 'iframe', 'https://visualgo.net/en/dfsbfs'),
(109, 1, 'Dynamic Programming & Memoization', 3, 'p5js', '/visuals/p5/dp_grid.js'),
(110, 1, 'Shortest Path & Dijkstra Algorithm', 3, 'iframe', 'https://visualgo.net/en/sssp'),

(201, 2, 'MOSFET Physics & Operation Regions', 1, 'iframe', 'https://falstad.com/circuit/circuitjs.html?ctz=mosfet'),
(202, 2, 'CMOS Inverter DC Characteristics & VTC', 1, 'p5js', '/visuals/p5/cmos_vtc_curve.js'),
(203, 2, 'Static CMOS Combinational Logic Gates', 2, 'iframe', 'https://falstad.com/circuit/circuitjs.html?ctz=nand_nor'),
(204, 2, 'Transmission Gates & Pass-Transistor Logic', 2, 'p5js', '/visuals/p5/pass_transistor.js'),
(205, 2, 'Latches, Flip-Flops & Clocking Strategies', 2, 'iframe', 'https://falstad.com/circuit/circuitjs.html?ctz=d_flipflop'),
(206, 2, 'Setup, Hold & Clock Skew Timing Analysis', 3, 'p5js', '/visuals/p5/timing_diagram.js'),
(207, 2, 'Finite State Machine (FSM) Synthesis', 3, 'p5js', '/visuals/p5/fsm_state_diagram.js'),

(301, 3, 'Binary Representation & Two’s Complement', 1, 'iframe', 'https://academo.org/demos/twos-complement/'),
(302, 3, 'Combinational ALU Design', 1, 'iframe', 'https://circuitverse.org/simulator/embed/alu_4bit'),
(303, 3, 'Instruction Cycle & Single-Cycle Datapath', 2, 'p5js', '/visuals/p5/mips_datapath.js'),
(304, 3, 'Processor Pipelining & Data Hazards', 2, 'p5js', '/visuals/p5/pipeline_hazard.js'),
(305, 3, 'Cache Memory Organization & Hit/Miss Latency', 2, 'p5js', '/visuals/p5/cache_direct_mapped.js'),
(306, 3, 'Virtual Memory & Multi-Level Page Tables', 3, 'p5js', '/visuals/p5/paging_tlb.js')
ON DUPLICATE KEY UPDATE topic_name = VALUES(topic_name);

INSERT INTO TOPIC_PREREQUISITES (topic_id, prereq_topic_id, importance_weight)
VALUES
(102, 101, 5),
(103, 101, 4),
(103, 102, 4),
(105, 101, 4),
(105, 104, 5),
(106, 105, 5),
(107, 101, 4),
(107, 102, 4),
(108, 103, 4),
(108, 107, 5),
(109, 104, 5),
(109, 101, 3),
(110, 108, 5),
(110, 103, 4),

(202, 201, 5),
(203, 202, 5),
(204, 201, 4),
(205, 203, 5),
(206, 205, 5),
(207, 205, 4),

(302, 301, 5),
(303, 302, 4),
(304, 303, 5),
(305, 301, 3),
(306, 305, 5)
ON DUPLICATE KEY UPDATE importance_weight = VALUES(importance_weight);

-- Runtime operations demo
UPDATE TEXTBOOKS 
SET file_name = 'Introduction_to_Algorithms_CLRS_4th_Ed.pdf',
    chunk_count = 512,
    uploaded_at = CURRENT_TIMESTAMP
WHERE textbook_id = 1;

UPDATE TOPICS
SET difficulty_level = 3,
    visual_type = 'p5js',
    embed_url = '/visuals/p5/avl_rotations_interactive.js'
WHERE topic_id = 106;

DELETE FROM TOPIC_PREREQUISITES
WHERE topic_id = 109 AND prereq_topic_id = 101;

-- ------------------------------------------------------------
-- Recursive CTEs & Joins
-- ------------------------------------------------------------

-- Prerequisite path lookup (ancestor traversal)
WITH RECURSIVE PrerequisiteChain AS (
    SELECT 
        tp.topic_id AS target_topic_id,
        tp.prereq_topic_id,
        t_pre.topic_name AS prereq_topic_name,
        t_pre.difficulty_level AS prereq_difficulty,
        tp.importance_weight,
        1 AS traversal_depth,
        CAST(t_pre.topic_name AS CHAR(1000)) AS learning_order_path
    FROM TOPIC_PREREQUISITES tp
    INNER JOIN TOPICS t_pre ON tp.prereq_topic_id = t_pre.topic_id
    WHERE tp.topic_id = 106

    UNION ALL

    SELECT 
        pc.target_topic_id,
        tp_parent.prereq_topic_id,
        t_ancestor.topic_name,
        t_ancestor.difficulty_level,
        tp_parent.importance_weight,
        pc.traversal_depth + 1,
        CONCAT(t_ancestor.topic_name, ' -> ', pc.learning_order_path)
    FROM PrerequisiteChain pc
    INNER JOIN TOPIC_PREREQUISITES tp_parent ON pc.prereq_topic_id = tp_parent.topic_id
    INNER JOIN TOPICS t_ancestor ON tp_parent.prereq_topic_id = t_ancestor.topic_id
)
SELECT 
    target_topic_id,
    prereq_topic_id,
    prereq_topic_name,
    prereq_difficulty,
    importance_weight,
    traversal_depth,
    learning_order_path
FROM PrerequisiteChain
ORDER BY traversal_depth DESC, importance_weight DESC;

-- Unlocked topics lookup (descendant traversal)
WITH RECURSIVE UnlockedTopicsChain AS (
    SELECT 
        tp.topic_id AS unlocked_topic_id,
        t.topic_name AS unlocked_topic_name,
        t.difficulty_level,
        tp.prereq_topic_id AS root_mastered_id,
        1 AS unlock_tier
    FROM TOPIC_PREREQUISITES tp
    INNER JOIN TOPICS t ON tp.topic_id = t.topic_id
    WHERE tp.prereq_topic_id = 201

    UNION ALL

    SELECT 
        tp_child.topic_id,
        t_child.topic_name,
        t_child.difficulty_level,
        utc.root_mastered_id,
        utc.unlock_tier + 1
    FROM UnlockedTopicsChain utc
    INNER JOIN TOPIC_PREREQUISITES tp_child ON utc.unlocked_topic_id = tp_child.prereq_topic_id
    INNER JOIN TOPICS t_child ON tp_child.topic_id = t_child.topic_id
)
SELECT DISTINCT
    unlocked_topic_id,
    unlocked_topic_name,
    difficulty_level,
    unlock_tier
FROM UnlockedTopicsChain
ORDER BY unlock_tier ASC, difficulty_level ASC;

-- Curriculum join with prerequisite summary
SELECT 
    s.subject_key,
    s.subject_name,
    COALESCE(tb.file_name, 'No Textbook Attached') AS textbook_file,
    t.topic_id,
    t.topic_name,
    t.difficulty_level,
    t.visual_type,
    COUNT(tp.prereq_topic_id) AS total_prerequisites_required,
    GROUP_CONCAT(p_top.topic_name ORDER BY tp.importance_weight DESC SEPARATOR '; ') AS prerequisite_list
FROM SUBJECTS s
INNER JOIN TOPICS t ON s.subject_id = t.subject_id
LEFT JOIN TEXTBOOKS tb ON s.subject_id = tb.subject_id
LEFT JOIN TOPIC_PREREQUISITES tp ON t.topic_id = tp.topic_id
LEFT JOIN TOPICS p_top ON tp.prereq_topic_id = p_top.topic_id
GROUP BY 
    s.subject_key,
    s.subject_name,
    tb.file_name,
    t.topic_id,
    t.topic_name,
    t.difficulty_level,
    t.visual_type
ORDER BY s.subject_id, t.difficulty_level ASC, t.topic_id;

-- Prerequisite depth analysis
WITH RECURSIVE PathDepthCTE AS (
    SELECT 
        tp.topic_id,
        tp.prereq_topic_id,
        1 AS chain_depth
    FROM TOPIC_PREREQUISITES tp

    UNION ALL

    SELECT 
        child.topic_id,
        parent.prereq_topic_id,
        child.chain_depth + 1
    FROM PathDepthCTE child
    INNER JOIN TOPIC_PREREQUISITES parent ON child.prereq_topic_id = parent.topic_id
    WHERE child.chain_depth < 10
)
SELECT 
    s.subject_name,
    t.topic_name AS target_topic,
    MAX(pd.chain_depth) AS max_prerequisite_depth
FROM PathDepthCTE pd
INNER JOIN TOPICS t ON pd.topic_id = t.topic_id
INNER JOIN SUBJECTS s ON t.subject_id = s.subject_id
GROUP BY s.subject_name, t.topic_name
HAVING MAX(pd.chain_depth) >= 2
ORDER BY max_prerequisite_depth DESC, s.subject_name;
