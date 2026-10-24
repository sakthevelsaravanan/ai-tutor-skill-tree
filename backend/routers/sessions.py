"""
Member 2: Learning Session, Conversation Logs, and Quiz Mastery API Endpoints.
Implements M2-APP1 requirements:
- POST /api/sessions/start (create LEARNING_SESSIONS row with UUID)
- POST /api/sessions/message (append turn to CONVERSATION_LOGS)
- POST /api/sessions/quiz-attempt (insert QUIZ_ATTEMPTS and trigger trg_after_quiz_attempt_mastery)
- GET  /api/sessions/recommend/{user_id}/{subject_id} (call sp_recommend_next_topic)
- GET  /api/sessions/mastery/{user_id}/{subject_id} (call fn_calculate_subject_mastery)
- GET  /api/sessions/{session_id} (fetch session details and history)
- GET  /api/sessions/user/{user_id} (list user's learning sessions)
"""

import uuid
from decimal import Decimal
from typing import Optional, List, Dict, Any, Literal
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import pymysql

from backend.database import get_connection, get_transaction, execute_query, execute_one

router = APIRouter(prefix="/api/sessions", tags=["Learning Sessions & Mastery (M2)"])

# ============================================================
# Pydantic Schemas
# ============================================================

class StartSessionRequest(BaseModel):
    user_id: int = Field(..., description="ID of the student user initiating the session")
    subject_id: int = Field(..., description="ID of the subject domain")
    current_topic_id: Optional[int] = Field(None, description="Initial concept topic ID if pre-selected")
    quiz_difficulty: Optional[int] = Field(1, ge=1, le=3, description="Quiz difficulty tier (1=Intro, 2=Intermediate, 3=Advanced)")

class SessionResponse(BaseModel):
    session_id: str
    user_id: int
    subject_id: int
    current_topic_id: Optional[int] = None
    current_stage: str = "topic"
    quiz_difficulty: int = 1
    confused_count: int = 0
    started_at: Optional[str] = None
    updated_at: Optional[str] = None

class SaveMessageRequest(BaseModel):
    session_id: str = Field(..., description="UUID of the parent learning session")
    content: str = Field(..., min_length=1, description="Message text content")
    role: Literal["user", "assistant", "system"] = Field("user", description="Sender role in dialogue")
    stage: Optional[Literal["topic", "explore", "quiz", "check", "clarify"]] = Field(
        None, description="Stage at message generation (defaults to session's current stage)"
    )
    topic_id: Optional[int] = Field(None, description="Topic ID (defaults to session's current topic)")

class MessageResponse(BaseModel):
    log_id: int
    session_id: str
    topic_id: Optional[int] = None
    role: str
    stage: str
    content: str
    created_at: Optional[str] = None

class QuizAttemptRequest(BaseModel):
    session_id: str = Field(..., description="UUID of the learning session")
    user_id: Optional[int] = Field(None, description="Student user ID (inferred from session if omitted)")
    topic_id: Optional[int] = Field(None, description="Topic ID (inferred from session current topic if omitted)")
    difficulty_level: Optional[int] = Field(None, ge=1, le=3, description="Quiz difficulty (1-3, defaults to session difficulty)")
    mcq_score: Optional[int] = Field(None, ge=0, le=3, description="MCQ score from 0 to 3")
    check_score: Optional[int] = Field(None, ge=1, le=5, description="Understanding self-check score from 1 to 5")
    verdict: Optional[Literal["UNDERSTOOD", "PARTIAL", "CONFUSED"]] = Field(
        None, description="Qualitative evaluation verdict"
    )

class QuizAttemptResponse(BaseModel):
    attempt_id: int
    session_id: str
    user_id: int
    topic_id: int
    difficulty_level: int
    mcq_score: Optional[int] = None
    check_score: Optional[int] = None
    verdict: Optional[str] = None
    next_stage: Optional[str] = None
    mastery_status: Optional[str] = None
    attempted_at: Optional[str] = None

class TopicDetail(BaseModel):
    topic_id: int
    topic_name: str
    difficulty_level: int
    visual_type: str
    embed_url: Optional[str] = None

class RecommendationResponse(BaseModel):
    user_id: int
    subject_id: int
    recommended_topic_id: Optional[int] = None
    recommendation_reason: Optional[str] = None
    topic: Optional[TopicDetail] = None

class SubjectMasteryResponse(BaseModel):
    user_id: int
    subject_id: int
    subject_name: Optional[str] = None
    mastery_percentage: float

# ============================================================
# Helper Functions
# ============================================================

def _stringify_timestamps(record: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Convert timestamp and Decimal objects in database rows to serializable types."""
    if not record:
        return record
    clean = dict(record)
    for key, val in clean.items():
        if isinstance(val, Decimal):
            clean[key] = float(val)
        elif hasattr(val, "isoformat"):
            clean[key] = val.isoformat()
    return clean

# ============================================================
# Endpoint 1: Start a Learning Session (POST /api/sessions/start)
# ============================================================

@router.post("/start", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def start_learning_session(req: StartSessionRequest):
    """
    Creates a new learning session in LEARNING_SESSIONS with a generated UUID.
    Validates user, subject, and optional initial topic existence.
    """
    # 1. Verify user exists
    user = execute_one("SELECT user_id, role FROM USERS WHERE user_id = %s", (req.user_id,))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {req.user_id} does not exist."
        )

    # 2. Verify subject exists
    subject = execute_one("SELECT subject_id, subject_name FROM SUBJECTS WHERE subject_id = %s", (req.subject_id,))
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {req.subject_id} does not exist."
        )

    # 3. Verify topic belongs to subject if provided
    if req.current_topic_id is not None:
        topic = execute_one(
            "SELECT topic_id, subject_id, topic_name FROM TOPICS WHERE topic_id = %s",
            (req.current_topic_id,)
        )
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Topic with ID {req.current_topic_id} does not exist."
            )
        if topic["subject_id"] != req.subject_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Topic {req.current_topic_id} ('{topic['topic_name']}') does not belong to subject {req.subject_id}."
            )

    # 4. Generate UUID session_id conforming to CHAR(36)
    session_id = str(uuid.uuid4())
    diff = req.quiz_difficulty or 1

    try:
        with get_transaction() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO LEARNING_SESSIONS (
                        session_id, user_id, subject_id, current_topic_id,
                        current_stage, quiz_difficulty, confused_count
                    ) VALUES (%s, %s, %s, %s, 'topic', %s, 0)
                """, (session_id, req.user_id, req.subject_id, req.current_topic_id, diff))
                cursor.execute(
                    "SELECT * FROM LEARNING_SESSIONS WHERE session_id = %s",
                    (session_id,)
                )
                session_record = cursor.fetchone()
    except pymysql.Error as db_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while creating session: {db_err}"
        )

    return _stringify_timestamps(session_record)

# ============================================================
# Endpoint 2: Save a Conversation Message (POST /api/sessions/message)
# ============================================================

@router.post("/message", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def save_conversation_message(req: SaveMessageRequest):
    """
    Appends a dialogue turn to CONVERSATION_LOGS linked to an active session.
    Preserves stage, topic context, and ordering timestamps.
    """
    # 1. Verify parent session exists
    session = execute_one(
        "SELECT session_id, current_topic_id, current_stage FROM LEARNING_SESSIONS WHERE session_id = %s",
        (req.session_id,)
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Learning session '{req.session_id}' not found."
        )

    # 2. Resolve default stage and topic
    stage = req.stage if req.stage is not None else session["current_stage"]
    topic_id = req.topic_id if req.topic_id is not None else session["current_topic_id"]

    if topic_id is not None:
        topic_exists = execute_one("SELECT topic_id FROM TOPICS WHERE topic_id = %s", (topic_id,))
        if not topic_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Referenced topic ID {topic_id} does not exist."
            )

    content = req.content.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be blank."
        )

    try:
        with get_transaction() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO CONVERSATION_LOGS (session_id, topic_id, role, stage, content)
                    VALUES (%s, %s, %s, %s, %s)
                """, (req.session_id, topic_id, req.role, stage, content))
                log_id = cursor.lastrowid
                cursor.execute("SELECT * FROM CONVERSATION_LOGS WHERE log_id = %s", (log_id,))
                log_record = cursor.fetchone()
    except pymysql.Error as db_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving message: {db_err}"
        )

    return _stringify_timestamps(log_record)

# ============================================================
# Endpoint 3: Record Quiz Attempt (POST /api/sessions/quiz-attempt)
# ============================================================

@router.post("/quiz-attempt", response_model=QuizAttemptResponse, status_code=status.HTTP_201_CREATED)
def record_quiz_attempt(req: QuizAttemptRequest):
    """
    Inserts a quiz attempt into QUIZ_ATTEMPTS.
    Relies on MySQL trigger trg_after_quiz_attempt_mastery to update STUDENT_TOPIC_MASTERY automatically.
    Updates the session's stage and confused count atomically.
    """
    # 1. Verify parent session exists
    session = execute_one("""
        SELECT session_id, user_id, subject_id, current_topic_id,
               quiz_difficulty, confused_count, current_stage
        FROM LEARNING_SESSIONS WHERE session_id = %s
    """, (req.session_id,))
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Learning session '{req.session_id}' not found."
        )

    # 2. Resolve and validate user_id
    user_id = req.user_id if req.user_id is not None else session["user_id"]
    user = execute_one("SELECT user_id FROM USERS WHERE user_id = %s", (user_id,))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} does not exist."
        )

    # 3. Resolve and validate topic_id
    topic_id = req.topic_id if req.topic_id is not None else session["current_topic_id"]
    if topic_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session has no current topic and no topic_id was provided."
        )
    topic = execute_one("SELECT topic_id FROM TOPICS WHERE topic_id = %s", (topic_id,))
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic with ID {topic_id} does not exist."
        )

    # 4. Resolve difficulty level
    diff = req.difficulty_level if req.difficulty_level is not None else (session["quiz_difficulty"] or 1)
    if diff not in (1, 2, 3):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="difficulty_level must be between 1 and 3."
        )

    # 5. Determine stage transition and confused_count increment
    current_confused = session.get("confused_count") or 0
    if req.verdict == "CONFUSED":
        next_stage = "clarify"
        new_confused_count = current_confused + 1
    elif req.verdict == "UNDERSTOOD":
        next_stage = "explore"
        new_confused_count = 0
    elif req.verdict == "PARTIAL":
        next_stage = "check"
        new_confused_count = current_confused
    else:
        next_stage = session.get("current_stage") or "topic"
        new_confused_count = current_confused

    try:
        with get_transaction() as conn:
            with conn.cursor() as cursor:
                # Insert attempt - MySQL trigger trg_after_quiz_attempt_mastery executes automatically
                cursor.execute("""
                    INSERT INTO QUIZ_ATTEMPTS (
                        session_id, user_id, topic_id, difficulty_level,
                        mcq_score, check_score, verdict
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    req.session_id, user_id, topic_id, diff,
                    req.mcq_score, req.check_score, req.verdict
                ))
                attempt_id = cursor.lastrowid

                # Update session current_stage and confused_count
                # If confused_count >= 3, trg_after_session_confused_threshold automatically fires
                cursor.execute("""
                    UPDATE LEARNING_SESSIONS
                    SET current_stage = %s,
                        confused_count = %s,
                        current_topic_id = %s
                    WHERE session_id = %s
                """, (next_stage, new_confused_count, topic_id, req.session_id))

                # Read back mastery status recalculated by trigger
                cursor.execute("""
                    SELECT mastery_status FROM STUDENT_TOPIC_MASTERY
                    WHERE user_id = %s AND topic_id = %s
                """, (user_id, topic_id))
                mastery_row = cursor.fetchone()
                mastery_status = mastery_row["mastery_status"] if mastery_row else None

                cursor.execute("SELECT attempted_at FROM QUIZ_ATTEMPTS WHERE attempt_id = %s", (attempt_id,))
                attempt_row = cursor.fetchone()
                attempted_at = attempt_row["attempted_at"].isoformat() if attempt_row and attempt_row.get("attempted_at") else None

    except pymysql.Error as db_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while recording quiz attempt: {db_err}"
        )

    return QuizAttemptResponse(
        attempt_id=attempt_id,
        session_id=req.session_id,
        user_id=user_id,
        topic_id=topic_id,
        difficulty_level=diff,
        mcq_score=req.mcq_score,
        check_score=req.check_score,
        verdict=req.verdict,
        next_stage=next_stage,
        mastery_status=mastery_status,
        attempted_at=attempted_at
    )

# ============================================================
# Endpoint 4: Recommend Next Topic (GET /api/sessions/recommend/{user_id}/{subject_id})
# ============================================================

@router.get("/recommend/{user_id}/{subject_id}", response_model=RecommendationResponse)
def recommend_next_topic(user_id: int, subject_id: int):
    """
    Calls stored procedure sp_recommend_next_topic(user_id, subject_id, OUT topic_id, OUT reason).
    Prioritizes Remediation (unmet prerequisites) -> Continuity (in-progress) -> Progression (unlocked).
    """
    # 1. Verify user exists
    user = execute_one("SELECT user_id, full_name FROM USERS WHERE user_id = %s", (user_id,))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )

    # 2. Verify subject exists
    subject = execute_one("SELECT subject_id, subject_name FROM SUBJECTS WHERE subject_id = %s", (subject_id,))
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {subject_id} not found."
        )

    # 3. Call stored procedure sp_recommend_next_topic with OUT parameters
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "CALL sp_recommend_next_topic(%s, %s, @rec_id, @reason);",
                (user_id, subject_id)
            )
            cursor.execute(
                "SELECT @rec_id AS recommended_topic_id, @reason AS recommendation_reason;"
            )
            rec = cursor.fetchone() or {}
    except pymysql.Error as db_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error executing sp_recommend_next_topic: {db_err}"
        )
    finally:
        conn.close()

    rec_topic_id = rec.get("recommended_topic_id")
    reason = rec.get("recommendation_reason")

    # 4. Fetch topic details if a topic was recommended
    topic_detail = None
    if rec_topic_id is not None:
        t_row = execute_one("""
            SELECT topic_id, topic_name, difficulty_level, visual_type, embed_url
            FROM TOPICS WHERE topic_id = %s
        """, (rec_topic_id,))
        if t_row:
            topic_detail = TopicDetail(
                topic_id=t_row["topic_id"],
                topic_name=t_row["topic_name"],
                difficulty_level=t_row["difficulty_level"],
                visual_type=t_row["visual_type"],
                embed_url=t_row.get("embed_url")
            )

    return RecommendationResponse(
        user_id=user_id,
        subject_id=subject_id,
        recommended_topic_id=rec_topic_id,
        recommendation_reason=reason,
        topic=topic_detail
    )

# ============================================================
# Endpoint 5: Calculate Subject Mastery (GET /api/sessions/mastery/{user_id}/{subject_id})
# ============================================================

@router.get("/mastery/{user_id}/{subject_id}", response_model=SubjectMasteryResponse)
def calculate_subject_mastery(user_id: int, subject_id: int):
    """
    Calls stored function fn_calculate_subject_mastery(user_id, subject_id).
    Returns student's mastery percentage (DECIMAL(5,2)) for the selected subject.
    """
    # 1. Verify user exists
    user = execute_one("SELECT user_id, full_name FROM USERS WHERE user_id = %s", (user_id,))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )

    # 2. Verify subject exists
    subject = execute_one("SELECT subject_id, subject_name FROM SUBJECTS WHERE subject_id = %s", (subject_id,))
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {subject_id} not found."
        )

    # 3. Call stored function fn_calculate_subject_mastery
    try:
        row = execute_one(
            "SELECT fn_calculate_subject_mastery(%s, %s) AS mastery_percentage;",
            (user_id, subject_id)
        )
    except pymysql.Error as db_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error executing fn_calculate_subject_mastery: {db_err}"
        )

    raw_val = row.get("mastery_percentage") if row else None
    mastery_pct = float(raw_val) if raw_val is not None else 0.0

    return SubjectMasteryResponse(
        user_id=user_id,
        subject_id=subject_id,
        subject_name=subject["subject_name"],
        mastery_percentage=mastery_pct
    )

# ============================================================
# Supplementary Endpoints: Session Lookup & History
# ============================================================

@router.get("/{session_id}")
def get_session_details(session_id: str):
    """Retrieve full details of a session, including current topic, stages, and recent messages."""
    session = execute_one("""
        SELECT 
            s.session_id, s.user_id, u.full_name AS student_name,
            s.subject_id, sub.subject_name,
            s.current_topic_id, t.topic_name AS current_topic_name,
            s.current_stage, s.quiz_difficulty, s.confused_count,
            s.started_at, s.updated_at
        FROM LEARNING_SESSIONS s
        INNER JOIN USERS u ON s.user_id = u.user_id
        INNER JOIN SUBJECTS sub ON s.subject_id = sub.subject_id
        LEFT JOIN TOPICS t ON s.current_topic_id = t.topic_id
        WHERE s.session_id = %s
    """, (session_id,))
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    messages = execute_query("""
        SELECT log_id, session_id, topic_id, role, stage, content, created_at
        FROM CONVERSATION_LOGS
        WHERE session_id = %s
        ORDER BY created_at ASC, log_id ASC
    """, (session_id,))

    attempts = execute_query("""
        SELECT attempt_id, session_id, user_id, topic_id, difficulty_level,
               mcq_score, check_score, verdict, attempted_at
        FROM QUIZ_ATTEMPTS
        WHERE session_id = %s
        ORDER BY attempted_at DESC
    """, (session_id,))

    clean_session = _stringify_timestamps(session)
    clean_session["messages"] = [_stringify_timestamps(m) for m in messages]
    clean_session["quiz_attempts"] = [_stringify_timestamps(a) for a in attempts]
    return clean_session

@router.get("/user/{user_id}")
def get_user_sessions(user_id: int):
    """Retrieve all active and past sessions for a student."""
    sessions = execute_query("""
        SELECT 
            s.session_id, s.subject_id, sub.subject_name,
            s.current_topic_id, t.topic_name,
            s.current_stage, s.quiz_difficulty, s.confused_count,
            s.started_at, s.updated_at
        FROM LEARNING_SESSIONS s
        INNER JOIN SUBJECTS sub ON s.subject_id = sub.subject_id
        LEFT JOIN TOPICS t ON s.current_topic_id = t.topic_id
        WHERE s.user_id = %s
        ORDER BY s.updated_at DESC
    """, (user_id,))
    return [_stringify_timestamps(s) for s in sessions]
