"""Authenticated learning sessions backed by PostgreSQL transactions and triggers."""
from uuid import UUID, uuid4
from typing import Optional, List, Dict, Any, Literal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from backend.database import get_transaction, execute_query, execute_one
from backend.security import current_user, require_owner

router = APIRouter(prefix='/api/sessions', tags=['Learning sessions'])

class StartSessionRequest(BaseModel):
    user_id: int = Field(..., description="ID of the student user initiating the session")
    subject_id: int = Field(..., description="ID of the subject domain")
    current_topic_id: Optional[int] = Field(None, description="Initial concept topic ID if pre-selected")
    quiz_difficulty: Optional[int] = Field(1, ge=1, le=3, description="Quiz difficulty tier (1=Intro, 2=Intermediate, 3=Advanced)")

class SessionResponse(BaseModel):
    session_id: UUID
    user_id: int
    subject_id: int
    current_topic_id: Optional[int] = None
    current_stage: str = "topic"
    quiz_difficulty: int = 1
    confused_count: int = 0
    started_at: Optional[str] = None
    updated_at: Optional[str] = None

class SaveMessageRequest(BaseModel):
    session_id: UUID = Field(..., description="UUID of the parent learning session")
    content: str = Field(..., min_length=1, description="Message text content")
    role: Literal["user", "assistant", "system"] = Field("user", description="Sender role in dialogue")
    stage: Optional[Literal["topic", "explore", "quiz", "check", "clarify"]] = Field(
        None, description="Stage at message generation (defaults to session's current stage)"
    )
    topic_id: Optional[int] = Field(None, description="Topic ID (defaults to session's current topic)")

class MessageResponse(BaseModel):
    log_id: int
    session_id: UUID
    topic_id: Optional[int] = None
    role: str
    stage: str
    content: str
    created_at: Optional[str] = None

class QuizAttemptRequest(BaseModel):
    session_id: UUID = Field(..., description="UUID of the learning session")
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
    session_id: UUID
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


def owned_session(session_id, user, conn=None):
    query = 'SELECT * FROM learning_sessions WHERE session_id=%s'
    session = conn.execute(query + ' FOR UPDATE', (session_id,)).fetchone() if conn else execute_one(query, (session_id,))
    if not session:
        raise HTTPException(404, 'Learning session not found.')
    require_owner(user, session['user_id'])
    return session


def validate_topic(topic_id, subject_id, conn=None):
    query = 'SELECT topic_id,subject_id FROM topics WHERE topic_id=%s'
    topic = conn.execute(query, (topic_id,)).fetchone() if conn else execute_one(query, (topic_id,))
    if not topic:
        raise HTTPException(404, 'Topic not found.')
    if topic['subject_id'] != subject_id:
        raise HTTPException(400, 'Topic does not belong to the session subject.')


@router.post('/start', status_code=201)
def start_learning_session(req: StartSessionRequest, user=Depends(current_user)):
    require_owner(user, req.user_id)
    if not execute_one('SELECT user_id FROM users WHERE user_id=%s', (req.user_id,)):
        raise HTTPException(404, 'User not found.')
    if not execute_one('SELECT subject_id FROM subjects WHERE subject_id=%s', (req.subject_id,)):
        raise HTTPException(404, 'Subject not found.')
    if req.current_topic_id is not None:
        validate_topic(req.current_topic_id, req.subject_id)
    with get_transaction() as conn:
        return conn.execute("""INSERT INTO learning_sessions(session_id,user_id,subject_id,current_topic_id,quiz_difficulty)
            VALUES(%s,%s,%s,%s,%s) RETURNING *""",
            (uuid4(),req.user_id,req.subject_id,req.current_topic_id,req.quiz_difficulty or 1)).fetchone()


@router.post('/message', status_code=201)
def save_conversation_message(req: SaveMessageRequest, user=Depends(current_user)):
    if req.role != 'user':
        raise HTTPException(403, 'Assistant and system messages are generated by the server.')
    content = req.content.strip()
    if not content:
        raise HTTPException(400, 'Message content cannot be blank.')
    with get_transaction() as conn:
        session = owned_session(req.session_id,user,conn)
        topic_id = req.topic_id if req.topic_id is not None else session['current_topic_id']
        if topic_id is not None:
            validate_topic(topic_id,session['subject_id'],conn)
        return conn.execute("""INSERT INTO conversation_logs(session_id,topic_id,role,stage,content)
            VALUES(%s,%s,'user',%s,%s) RETURNING *""",
            (req.session_id,topic_id,session['current_stage'],content)).fetchone()


@router.post('/quiz-attempt', status_code=201)
def record_quiz_attempt(req: QuizAttemptRequest, user=Depends(current_user)):
    if req.verdict is None or req.mcq_score is None or req.check_score is None:
        raise HTTPException(422, 'Provide all self-assessment scores and a verdict.')
    with get_transaction() as conn:
        session = owned_session(req.session_id,user,conn)
        if req.user_id is not None and req.user_id != session['user_id']:
            raise HTTPException(403, 'Quiz user must match session owner.')
        topic_id = req.topic_id if req.topic_id is not None else session['current_topic_id']
        if topic_id is None:
            raise HTTPException(400, 'Select a topic before recording an assessment.')
        validate_topic(topic_id,session['subject_id'],conn)
        if req.difficulty_level is not None:
            conn.execute('UPDATE learning_sessions SET quiz_difficulty=%s WHERE session_id=%s',
                         (req.difficulty_level,req.session_id))
        row = conn.execute('SELECT record_quiz_and_advance_stage(%s,%s,%s,%s,%s) AS id',
                           (req.session_id,topic_id,req.mcq_score,req.check_score,req.verdict)).fetchone()
        return conn.execute("""SELECT q.*,s.current_stage AS next_stage,m.mastery_status
            FROM quiz_attempts q JOIN learning_sessions s USING(session_id)
            JOIN student_topic_mastery m ON m.user_id=q.user_id AND m.topic_id=q.topic_id
            WHERE q.attempt_id=%s""", (row['id'],)).fetchone()


@router.get('/recommend/{user_id}/{subject_id}')
def recommend_next_topic(user_id:int,subject_id:int,user=Depends(current_user)):
    require_owner(user,user_id)
    rec = execute_one('SELECT * FROM recommend_next_topic(%s,%s)', (user_id,subject_id))
    topic = execute_one('SELECT * FROM topics WHERE topic_id=%s',(rec['recommended_topic_id'],)) if rec else None
    return {'user_id':user_id,'subject_id':subject_id,
            'recommended_topic_id':rec['recommended_topic_id'] if rec else None,
            'recommendation_reason':rec['recommendation_reason'] if rec else 'No eligible topics remain.', 'topic':topic}


@router.get('/mastery/{user_id}/{subject_id}')
def calculate_subject_mastery(user_id:int,subject_id:int,user=Depends(current_user)):
    require_owner(user,user_id)
    subject = execute_one('SELECT subject_name FROM subjects WHERE subject_id=%s',(subject_id,))
    if not subject:
        raise HTTPException(404,'Subject not found.')
    row = execute_one('SELECT fn_calculate_subject_mastery(%s,%s) AS mastery_percentage',(user_id,subject_id))
    topics = execute_query("""SELECT t.topic_id,t.topic_name,COALESCE(m.mastery_status,'UNTOUCHED') AS mastery_status,
        COALESCE(m.total_attempts,0) AS total_attempts FROM topics t LEFT JOIN student_topic_mastery m
        ON m.topic_id=t.topic_id AND m.user_id=%s WHERE t.subject_id=%s ORDER BY t.topic_id""",(user_id,subject_id))
    return {'user_id':user_id,'subject_id':subject_id,**subject,**row,'topics':topics}


@router.get('/user/{user_id}')
def get_user_sessions(user_id:int,subject_id:Optional[int]=None,user=Depends(current_user)):
    require_owner(user,user_id)
    return execute_query("""SELECT s.*,sub.subject_name,t.topic_name FROM learning_sessions s
        JOIN subjects sub USING(subject_id) LEFT JOIN topics t ON t.topic_id=s.current_topic_id
        WHERE s.user_id=%s AND (%s::integer IS NULL OR s.subject_id=%s)
        ORDER BY s.updated_at DESC LIMIT 100""",(user_id,subject_id,subject_id))


@router.get('/{session_id}')
def get_session_details(session_id:UUID,user=Depends(current_user)):
    session = owned_session(session_id,user)
    session['messages'] = execute_query('SELECT * FROM conversation_logs WHERE session_id=%s ORDER BY log_id',(session_id,))
    session['quiz_attempts'] = execute_query('SELECT * FROM quiz_attempts WHERE session_id=%s ORDER BY attempt_id DESC',(session_id,))
    return session
