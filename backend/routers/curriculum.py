from fastapi import APIRouter, HTTPException
from backend.database import execute_query, execute_one

router = APIRouter(prefix="/api/curriculum", tags=["Curriculum & Skill Tree"])

@router.get("/subjects")
def get_subjects():
    return execute_query("""
        SELECT 
            s.subject_id,
            s.subject_key,
            s.subject_name,
            s.description,
            s.is_indexed,
            COUNT(DISTINCT t.topic_id) AS total_topics,
            COUNT(DISTINCT tb.textbook_id) AS total_textbooks
        FROM SUBJECTS s
        LEFT JOIN TOPICS t ON s.subject_id = t.subject_id
        LEFT JOIN TEXTBOOKS tb ON s.subject_id = tb.subject_id
        GROUP BY s.subject_id, s.subject_key, s.subject_name, s.description, s.is_indexed
        ORDER BY s.subject_id
    """)

@router.get("/topics/{subject_id}")
def get_topics_by_subject(subject_id: int):
    return execute_query("""
        SELECT 
            topic_id,
            subject_id,
            topic_name,
            difficulty_level,
            visual_type,
            embed_url
        FROM TOPICS
        WHERE subject_id = %s
        ORDER BY difficulty_level ASC, topic_id ASC
    """, (subject_id,))

@router.get("/prerequisites/{topic_id}")
def get_topic_prerequisite_tree(topic_id: int):
    # Executes Member 1 Recursive CTE (Ancestor Walk)
    cte_query = """
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
    # Executes Member 1 Recursive CTE (Descendant Walk)
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
    nodes = execute_query("""
        SELECT topic_id AS id, topic_name AS label, difficulty_level, visual_type
        FROM TOPICS
        WHERE subject_id = %s
    """, (subject_id,))

    edges = execute_query("""
        SELECT 
            tp.prereq_topic_id AS `source`,
            tp.topic_id AS `target`,
            tp.importance_weight AS `weight`
        FROM TOPIC_PREREQUISITES tp
        INNER JOIN TOPICS t ON tp.topic_id = t.topic_id
        WHERE t.subject_id = %s
    """, (subject_id,))

    return {"nodes": nodes, "edges": edges}

@router.get("/visual/{topic_id}")
def get_visual_config(topic_id: int):
    topic = execute_one(
        "SELECT topic_id, topic_name, visual_type, embed_url FROM TOPICS WHERE topic_id = %s",
        (topic_id,)
    )
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found.")
    return topic
