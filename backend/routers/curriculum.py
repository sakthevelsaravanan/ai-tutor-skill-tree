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
"""

from fastapi import APIRouter, HTTPException
from backend.database import execute_query, execute_one

router = APIRouter(prefix="/api/curriculum", tags=["Curriculum & Skill Tree"])

@router.get("/subjects")
def get_subjects():
    """
    Retrieve all course subjects with aggregated counts of associated topics and indexed textbooks.
    Performs SQL GROUP BY with LEFT JOIN across SUBJECTS, TOPICS, and TEXTBOOKS tables.
    """
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
            embed_url
        FROM TOPICS
        WHERE subject_id = %s
        ORDER BY difficulty_level ASC, topic_id ASC
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
