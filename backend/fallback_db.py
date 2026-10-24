import os
import sqlite3

FALLBACK_DB_PATH = os.path.join(os.path.dirname(__file__), "ai_tutor_fallback.db")

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
    conn.close()

def get_fallback_connection():
    init_fallback_db()
    conn = sqlite3.connect(FALLBACK_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.create_function("concat", -1, lambda *a: "".join(str(x) if x is not None else "" for x in a))
    return conn
