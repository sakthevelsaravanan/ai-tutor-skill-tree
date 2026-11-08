"""
Curriculum Hierarchy, Skill Tree DAG & Recursive Common Table Expression (CTE) Engine.

This module provides endpoints for course structures and prerequisite graph traversal:
1. Course Catalog: Lists enrolled/indexed courses with aggregate counts of topics and textbooks.
2. Ordered Topic Sequence: Fetches concept topics ordered by difficulty level and ID.
3. Recursive CTE Ancestor Walk (/prerequisites/{topic_id}):
   Traverses backwards from a target concept through direct and transitive prerequisite
   relationships in TOPIC_PREREQUISITES. Computes traversal depth and learning path string.
4. Recursive CTE Descendant Walk (/unlocked/{topic_id}):
   Traverses forwards from a mastered concept to determine all downstream concepts
   unlocked across subsequent tiers.
5. Skill Tree DAG Synthesis (/graph/{subject_id}):
   Supplies node attributes (difficulty, visual type) and weighted directed edges
   to drive the frontend Directed Acyclic Graph (DAG) interactive visualization.
6. Topic Completion Tracking (/topics/{topic_id}/complete, /completed/{user_id}):
   Allows authenticated students to manually mark topics as completed after learning them
   in the Socratic AI chatbox. Persists completion status with unique constraint.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from backend.database import execute_query, execute_one, execute_dml, get_transaction
from backend.security import current_user, require_owner

router = APIRouter(prefix="/api/curriculum", tags=["Curriculum & Skill Tree"], dependencies=[Depends(current_user)])

def check_topic_unlocked(topic_id: int, user_id: int):
    """
    Checks if all direct prerequisites for topic_id have been completed by user_id in PostgreSQL.
    Returns (is_unlocked, missing_prereq_name).
    """
    missing = execute_query("""
        SELECT p.prereq_topic_id, t.topic_name
        FROM topic_prerequisites p
        JOIN topics t ON p.prereq_topic_id = t.topic_id
        WHERE p.topic_id = %s
          AND p.prereq_topic_id NOT IN (
              SELECT topic_id FROM student_topic_completions WHERE user_id = %s
          )
        ORDER BY t.sort_order ASC, p.prereq_topic_id ASC
    """, (topic_id, user_id))
    if missing:
        return False, missing[0]["topic_name"]
    return True, None

@router.get("/topics/{topic_id}/access/{user_id}")
def get_topic_access(topic_id: int, user_id: int, actor=Depends(current_user)):
    require_owner(actor, user_id)
    if actor.get("role") in ("admin", "instructor"):
        return {
            "topic_id": topic_id,
            "user_id": user_id,
            "is_unlocked": True,
            "missing_prerequisite": None,
            "message": "All topics are unlocked for instructors and administrators."
        }
    is_unlocked, missing_name = check_topic_unlocked(topic_id, user_id)
    return {
        "topic_id": topic_id,
        "user_id": user_id,
        "is_unlocked": is_unlocked,
        "missing_prerequisite": missing_name,
        "message": f"Complete '{missing_name}' to unlock this topic." if missing_name else "Topic is unlocked."
    }

@router.get("/subjects")
def get_subjects(actor=Depends(current_user)):
    """
    Retrieve all course subjects with aggregated counts of associated topics and indexed textbooks.
    Enforces student course isolation: students see demo/instructor courses + their own uploaded courses.
    """
    role = actor.get("role", "student")
    user_id = actor["user_id"]
    if role in ("admin", "instructor"):
        where_clause = ""
        params = ()
    else:
        where_clause = """
            WHERE s.created_by IS NULL
               OR s.created_by = %s
               OR s.created_by IN (SELECT user_id FROM users WHERE role IN ('instructor', 'admin'))
        """
        params = (user_id,)

    return execute_query(f"""
        SELECT 
            s.subject_id,
            s.subject_key,
            s.subject_name,
            s.description,
            s.is_indexed,
            s.created_by,
            COUNT(DISTINCT t.topic_id) AS total_topics,
            COUNT(DISTINCT tb.textbook_id) AS total_textbooks
        FROM SUBJECTS s
        LEFT JOIN TOPICS t ON s.subject_id = t.subject_id
        LEFT JOIN TEXTBOOKS tb ON s.subject_id = tb.subject_id
        {where_clause}
        GROUP BY s.subject_id, s.subject_key, s.subject_name, s.description, s.is_indexed, s.created_by
        ORDER BY s.subject_id
    """, params)

@router.get("/topics/{subject_id}")
def get_topics_by_subject(subject_id: int):
    """
    Fetch all learning topics for a given subject ordered sequentially by difficulty level.
    """
    return execute_query("""
        SELECT 
            topic_id,
            subject_id,
            topic_name,
            difficulty_level,
            visual_type,
            embed_url, source_file, start_page, end_page, sort_order
        FROM TOPICS
        WHERE subject_id = %s
        ORDER BY sort_order ASC, topic_id ASC
    """, (subject_id,))

@router.get("/prerequisites/{topic_id}")
def get_topic_prerequisite_tree(topic_id: int):
    """
    Recursive Common Table Expression (CTE) - Ancestor Prerequisite Walk.

    SQL Execution Mechanics:
    - Anchor Member: Selects immediate parent prerequisites from TOPIC_PREREQUISITES
      where topic_id equals the requested topic_id, setting traversal_depth = 1.
    - Recursive Member: Joins PrerequisiteChain with TOPIC_PREREQUISITES on
      pc.prereq_topic_id = tp_parent.topic_id, incrementing traversal_depth and concatenating
      learning_order_path.
    - Outer Aggregation: Groups by prereq_topic_id to resolve diamond dependencies,
      taking MIN(traversal_depth) and MAX(importance_weight).
    """
    cte_query = """
        WITH RECURSIVE PrerequisiteChain AS (
            SELECT 
                tp.topic_id AS target_topic_id,
                tp.prereq_topic_id,
                t_pre.topic_name AS prereq_topic_name,
                t_pre.difficulty_level AS prereq_difficulty,
                tp.importance_weight,
                1 AS traversal_depth,
                CAST(t_pre.topic_name AS TEXT) AS learning_order_path
            FROM TOPIC_PREREQUISITES tp
            INNER JOIN TOPICS t_pre ON tp.prereq_topic_id = t_pre.topic_id
            WHERE tp.topic_id = %s

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
            MAX(importance_weight) AS importance_weight,
            MIN(traversal_depth) AS traversal_depth,
            MIN(learning_order_path) AS learning_order_path
        FROM PrerequisiteChain
        GROUP BY target_topic_id, prereq_topic_id, prereq_topic_name, prereq_difficulty
        ORDER BY traversal_depth ASC, importance_weight DESC;
    """
    return execute_query(cte_query, (topic_id,))

@router.get("/unlocked/{topic_id}")
def get_unlocked_topics(topic_id: int):
    """
    Recursive Common Table Expression (CTE) - Descendant Unlocked Topics Walk.

    SQL Execution Mechanics:
    - Anchor Member: Identifies topics immediately unlocked when the given topic_id is mastered
      (WHERE tp.prereq_topic_id = %s), setting unlock_tier = 1.
    - Recursive Member: Joins UnlockedTopicsChain with downstream topics in TOPIC_PREREQUISITES,
      incrementing unlock_tier at each level of progression.
    - Outer Aggregation: Groups by unlocked_topic_id and orders by unlock_tier ASC.
    """
    cte_query = """
        WITH RECURSIVE UnlockedTopicsChain AS (
            SELECT 
                tp.topic_id AS unlocked_topic_id,
                t.topic_name AS unlocked_topic_name,
                t.difficulty_level,
                tp.prereq_topic_id AS root_mastered_id,
                1 AS unlock_tier
            FROM TOPIC_PREREQUISITES tp
            INNER JOIN TOPICS t ON tp.topic_id = t.topic_id
            WHERE tp.prereq_topic_id = %s

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
        SELECT 
            unlocked_topic_id,
            unlocked_topic_name,
            difficulty_level,
            MIN(unlock_tier) AS unlock_tier
        FROM UnlockedTopicsChain
        GROUP BY unlocked_topic_id, unlocked_topic_name, difficulty_level
        ORDER BY unlock_tier ASC, difficulty_level ASC;
    """
    return execute_query(cte_query, (topic_id,))

@router.get("/graph/{subject_id}")
def get_subject_graph(subject_id: int):
    """
    Generate graph payload for frontend DAG visualization.
    Returns:
    - nodes: Array of topic vertices { id, label, difficulty_level, visual_type }.
    - edges: Array of directed dependencies { source: prereq_id, target: topic_id, weight }.
    """
    nodes = execute_query("""
        SELECT topic_id AS id, topic_name AS label, difficulty_level, visual_type, source_file, start_page, end_page, sort_order
        FROM TOPICS
        WHERE subject_id = %s ORDER BY sort_order, topic_id
    """, (subject_id,))

    edges = execute_query("""
        SELECT 
            tp.prereq_topic_id AS source,
            tp.topic_id AS target,
            tp.importance_weight AS weight, tp.basis
        FROM TOPIC_PREREQUISITES tp
        INNER JOIN TOPICS t ON tp.topic_id = t.topic_id
        WHERE t.subject_id = %s
    """, (subject_id,))

    return {"nodes": nodes, "edges": edges}

@router.get("/visual/{topic_id}")
def get_visual_config(topic_id: int):
    """
    Fetch interactive visualizer configuration and simulation embed URL for a topic.
    """
    topic = execute_one(
        "SELECT topic_id, topic_name, visual_type, embed_url FROM TOPICS WHERE topic_id = %s",
        (topic_id,)
    )
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found.")
    return topic


# ============================================================
# Manual Topic Completion Tracking
# ============================================================

class TopicCompletionRequest(BaseModel):
    user_id: int

class TopicCompletionResponse(BaseModel):
    status: str
    message: str
    topic_id: int
    user_id: int
    is_completed: bool
    completed_at: Optional[str] = None

class UserCompletedTopicsResponse(BaseModel):
    user_id: int
    completed_topic_ids: List[int]
    total_completed: int

class TopicStatusResponse(BaseModel):
    topic_id: int
    user_id: int
    is_completed: bool
    completed_at: Optional[str] = None

@router.post("/topics/{topic_id}/complete", response_model=TopicCompletionResponse)
def mark_topic_completed(topic_id: int, req: TopicCompletionRequest, actor=Depends(current_user)):
    require_owner(actor, req.user_id)
    """
    Manually marks a specific topic as completed for the authenticated student.
    Persists completion in PostgreSQL in STUDENT_TOPIC_COMPLETIONS.
    Prevents duplicate completion records and ensures user isolation.
    """
    # 1. Verify user exists
    user = execute_one("SELECT user_id, full_name, role FROM USERS WHERE user_id = %s", (req.user_id,))
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {req.user_id} not found.")
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Only students can mark topics as completed.")

    # 2. Verify topic exists
    topic = execute_one("SELECT topic_id, topic_name, subject_id FROM TOPICS WHERE topic_id = %s", (topic_id,))
    if not topic:
        raise HTTPException(status_code=404, detail=f"Topic with ID {topic_id} not found.")

    with get_transaction() as conn:
        inserted=conn.execute("INSERT INTO student_topic_completions(user_id,topic_id) VALUES(%s,%s) ON CONFLICT(user_id,topic_id) DO NOTHING RETURNING completed_at", (req.user_id,topic_id)).fetchone()
        created=inserted or conn.execute("SELECT completed_at FROM student_topic_completions WHERE user_id=%s AND topic_id=%s",(req.user_id,topic_id)).fetchone()
    return TopicCompletionResponse(status='success',message='Topic marked as completed!' if inserted else 'Topic is already marked as completed.',topic_id=topic_id,user_id=req.user_id,is_completed=True,completed_at=created['completed_at'].isoformat())

@router.delete("/topics/{topic_id}/complete", response_model=TopicCompletionResponse)
def unmark_topic_completed(topic_id: int, user_id: int = Query(...), actor=Depends(current_user)):
    require_owner(actor, user_id)
    """
    Optionally unmarks a completed topic for the authenticated student.
    """
    execute_dml(
        "DELETE FROM STUDENT_TOPIC_COMPLETIONS WHERE user_id = %s AND topic_id = %s",
        (user_id, topic_id)
    )
    return TopicCompletionResponse(
        status="success",
        message="Topic completion removed.",
        topic_id=topic_id,
        user_id=user_id,
        is_completed=False,
        completed_at=None
    )

@router.get("/completed/{user_id}", response_model=UserCompletedTopicsResponse)
def get_user_completed_topics(user_id: int, subject_id: Optional[int] = None, actor=Depends(current_user)):
    require_owner(actor, user_id)
    """
    Retrieves the list of completed topic IDs for a given student user.
    Optionally filtered by subject_id.
    """
    user = execute_one("SELECT user_id FROM USERS WHERE user_id = %s", (user_id,))
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found.")

    if subject_id is not None:
        rows = execute_query("""
            SELECT c.topic_id
            FROM STUDENT_TOPIC_COMPLETIONS c
            INNER JOIN TOPICS t ON c.topic_id = t.topic_id
            WHERE c.user_id = %s AND t.subject_id = %s
            ORDER BY c.completed_at DESC
        """, (user_id, subject_id))
    else:
        rows = execute_query("""
            SELECT topic_id
            FROM STUDENT_TOPIC_COMPLETIONS
            WHERE user_id = %s
            ORDER BY completed_at DESC
        """, (user_id,))

    completed_ids = [r["topic_id"] for r in rows]
    return UserCompletedTopicsResponse(
        user_id=user_id,
        completed_topic_ids=completed_ids,
        total_completed=len(completed_ids)
    )

@router.get("/topics/{topic_id}/status/{user_id}", response_model=TopicStatusResponse)
def get_topic_completion_status(topic_id: int, user_id: int, actor=Depends(current_user)):
    require_owner(actor, user_id)
    """
    Fetches the completion status of a single topic for a given student.
    """
    if not execute_one("SELECT user_id FROM USERS WHERE user_id = %s", (user_id,)):
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found.")
    if not execute_one("SELECT topic_id FROM TOPICS WHERE topic_id = %s", (topic_id,)):
        raise HTTPException(status_code=404, detail=f"Topic with ID {topic_id} not found.")

    row = execute_one(
        "SELECT completion_id, completed_at FROM STUDENT_TOPIC_COMPLETIONS WHERE user_id = %s AND topic_id = %s",
        (user_id, topic_id)
    )
    if not row:
        return TopicStatusResponse(
            topic_id=topic_id,
            user_id=user_id,
            is_completed=False,
            completed_at=None
        )

    raw_at = row.get("completed_at")
    completed_at_str = raw_at.isoformat() if hasattr(raw_at, "isoformat") else (str(raw_at) if raw_at else None)
    return TopicStatusResponse(
        topic_id=topic_id,
        user_id=user_id,
        is_completed=True,
        completed_at=completed_at_str
    )
