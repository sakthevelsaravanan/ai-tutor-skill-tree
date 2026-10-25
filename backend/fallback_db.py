import os
import sqlite3

FALLBACK_DB_PATH = os.path.join(os.path.dirname(__file__), "ai_tutor_fallback.db")

class SQLiteCursorProxy:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        if params is not None:
            sql = sql.replace("%s", "?")
            return self._cursor.execute(sql, params)
        return self._cursor.execute(sql)

    def executemany(self, sql, seq_of_params):
        sql = sql.replace("%s", "?")
        return self._cursor.executemany(sql, seq_of_params)

    def executescript(self, sql):
        return self._cursor.executescript(sql)

    def fetchone(self):
        row = self._cursor.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self._cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cursor.close()

    def __getattr__(self, name):
        return getattr(self._cursor, name)

class SQLiteConnProxy:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return SQLiteCursorProxy(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def begin(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)

def init_fallback_db():
    conn = sqlite3.connect(FALLBACK_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.create_function("concat", -1, lambda *a: "".join(str(x) if x is not None else "" for x in a))
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS USERS (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS SUBJECTS (
        subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_key TEXT UNIQUE NOT NULL,
        subject_name TEXT NOT NULL,
        description TEXT,
        is_indexed INTEGER DEFAULT 0,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS TEXTBOOKS (
        textbook_id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        uploaded_by INTEGER,
        file_name TEXT NOT NULL,
        chroma_collection_name TEXT NOT NULL,
        chunk_count INTEGER DEFAULT 0,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS TOPICS (
        topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        topic_name TEXT NOT NULL,
        difficulty_level INTEGER NOT NULL,
        visual_type TEXT NOT NULL,
        embed_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS TOPIC_PREREQUISITES (
        topic_id INTEGER NOT NULL,
        prereq_topic_id INTEGER NOT NULL,
        importance_weight INTEGER DEFAULT 3,
        PRIMARY KEY (topic_id, prereq_topic_id)
    );

    CREATE TABLE IF NOT EXISTS LEARNING_SESSIONS (
        session_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        current_topic_id INTEGER,
        current_stage TEXT NOT NULL DEFAULT 'topic',
        quiz_difficulty INTEGER NOT NULL DEFAULT 1,
        confused_count INTEGER NOT NULL DEFAULT 0,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS CONVERSATION_LOGS (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        topic_id INTEGER,
        role TEXT NOT NULL,
        stage TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS QUIZ_ATTEMPTS (
        attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        topic_id INTEGER NOT NULL,
        difficulty_level INTEGER NOT NULL,
        mcq_score INTEGER,
        check_score INTEGER,
        verdict TEXT,
        attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS STUDENT_TOPIC_MASTERY (
        user_id INTEGER NOT NULL,
        topic_id INTEGER NOT NULL,
        mastery_status TEXT NOT NULL DEFAULT 'UNTOUCHED',
        best_mcq_score INTEGER DEFAULT 0,
        latest_check_score INTEGER DEFAULT 0,
        total_attempts INTEGER DEFAULT 0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, topic_id)
    );

    CREATE TABLE IF NOT EXISTS MASTERY_AUDIT_LOG (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        topic_id INTEGER NOT NULL,
        old_mastery REAL,
        new_mastery REAL,
        reason TEXT,
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("SELECT COUNT(*) FROM USERS")
    if cur.fetchone()[0] == 0:
        users = [
            (1, 'Dr. Alan Turing', 'turing@aitutor.edu', '$2b$12$e80yvV8gWp5l01N0Pz71ceQ2u8c5TzB6sR4c7E9h1K0q9Z8y7w6x1', 'instructor'),
            (2, 'Dr. Grace Hopper', 'hopper@aitutor.edu', '$2b$12$e80yvV8gWp5l01N0Pz71ceQ2u8c5TzB6sR4c7E9h1K0q9Z8y7w6x2', 'instructor'),
            (3, 'Roshan Kumar', 'roshan@student.edu', '$2b$12$e80yvV8gWp5l01N0Pz71ceQ2u8c5TzB6sR4c7E9h1K0q9Z8y7w6x3', 'student'),
            (4, 'Sakthevel Saravanan', 'sakthi@student.edu', '$2b$12$e80yvV8gWp5l01N0Pz71ceQ2u8c5TzB6sR4c7E9h1K0q9Z8y7w6x4', 'student'),
            (5, 'Charlie Davis', 'charlie@student.edu', '$2b$12$e80yvV8gWp5l01N0Pz71ceQ2u8c5TzB6sR4c7E9h1K0q9Z8y7w6x5', 'student'),
            (6, 'Ada Lovelace', 'admin@aitutor.edu', '$2b$12$e80yvV8gWp5l01N0Pz71ceQ2u8c5TzB6sR4c7E9h1K0q9Z8y7w6x6', 'admin')
        ]
        cur.executemany("INSERT INTO USERS (user_id, full_name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)", users)
        conn.commit()

    cur.execute("SELECT COUNT(*) FROM SUBJECTS")
    if cur.fetchone()[0] == 0:
        subjects = [
            (1, 'dsa', 'Data Structures & Algorithms', 'Fundamental algorithmic problem-solving and data representations.', 1, 1),
            (2, 'dvlsi', 'Digital VLSI Design', 'CMOS logic gates, semiconductor physics, and static timing analysis.', 1, 2),
            (3, 'cs', 'Computer Systems & Architecture', 'Instruction set architectures, processor pipelining, and memory hierarchies.', 1, 1),
            (4, 'networks', 'Computer Networks & Protocols', 'Layered networking models, TCP/IP, and routing protocols.', 1, 2)
        ]
        cur.executemany("INSERT INTO SUBJECTS (subject_id, subject_key, subject_name, description, is_indexed, created_by) VALUES (?, ?, ?, ?, ?, ?)", subjects)

        textbooks = [
            (1, 1, 1, 'Introduction_to_Algorithms_CLRS.pdf', 'chroma_dsa', 5),
            (2, 2, 2, 'CMOS_VLSI_Design_Weste_Harris.pdf', 'chroma_dvlsi', 3),
            (3, 3, 1, 'Computer_Organization_Design_Patterson.pdf', 'chroma_cs', 2),
            (4, 4, 2, 'Computer_Networking_Top_Down_Kurose.pdf', 'chroma_networks', 5)
        ]
        cur.executemany("INSERT INTO TEXTBOOKS (textbook_id, subject_id, uploaded_by, file_name, chroma_collection_name, chunk_count) VALUES (?, ?, ?, ?, ?, ?)", textbooks)

        topics = [
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
        ]
        cur.executemany("INSERT INTO TOPICS (topic_id, subject_id, topic_name, difficulty_level, visual_type, embed_url) VALUES (?, ?, ?, ?, ?, ?)", topics)

        prereqs = [
            (102, 101, 5), (103, 101, 4), (103, 102, 4), (105, 101, 4), (105, 104, 5),
            (106, 105, 5), (107, 101, 4), (107, 102, 4), (108, 103, 4), (108, 107, 5),
            (109, 104, 5), (110, 108, 5), (110, 103, 4),
            (202, 201, 5), (203, 202, 5), (204, 201, 4), (205, 203, 5), (206, 205, 5), (207, 205, 4),
            (302, 301, 5), (303, 302, 4), (304, 303, 5), (305, 301, 3), (306, 305, 5)
        ]
        cur.executemany("INSERT INTO TOPIC_PREREQUISITES (topic_id, prereq_topic_id, importance_weight) VALUES (?, ?, ?)", prereqs)
        conn.commit()

    conn.close()

def get_fallback_connection():
    init_fallback_db()
    conn = sqlite3.connect(FALLBACK_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.create_function("concat", -1, lambda *a: "".join(str(x) if x is not None else "" for x in a))
    return SQLiteConnProxy(conn)
