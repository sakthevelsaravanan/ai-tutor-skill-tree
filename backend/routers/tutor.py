import os
import re
from typing import List, Dict, Optional, Any, Tuple
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from uuid import UUID
from backend.config import settings
from backend.security import current_user
from backend.routers.sessions import owned_session
from backend.database import get_transaction
from backend.database import execute_query, execute_one, execute_dml
from backend.vector_service import vector_service

router = APIRouter(prefix="/api/tutor", tags=["Socratic RAG Tutoring Pipeline"])

MIN_RELEVANCE_THRESHOLD = 0.22

class TutorQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    subject_id: int
    topic_id: Optional[int] = None
    session_id: Optional[UUID] = None
    user_id: Optional[int] = None
    include_prereqs: bool = True

class TutorQueryResponse(BaseModel):
    answer: str
    target_topic: Optional[Dict[str, Any]] = None
    prerequisites: List[Dict[str, Any]] = []
    retrieved_chunks: List[Dict[str, Any]] = []
    session_id: Optional[UUID] = None
    relational_filter_applied: bool = False
    reflection_question: Optional[str] = None
    grounding_excerpt: Optional[str] = None
    top_similarity: Optional[float] = None
    top_source: Optional[str] = None

def _fetch_prerequisite_chain(topic_id: int) -> List[Dict]:
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
            prereq_topic_id,
            prereq_topic_name,
            prereq_difficulty,
            MAX(importance_weight) AS importance_weight,
            MIN(traversal_depth) AS traversal_depth,
            MIN(learning_order_path) AS learning_order_path
        FROM PrerequisiteChain
        GROUP BY prereq_topic_id, prereq_topic_name, prereq_difficulty
        ORDER BY traversal_depth ASC, importance_weight DESC;
    """
    return execute_query(cte_query, (topic_id,))

def _clean_concept_name(name: Optional[str]) -> str:
    if not name:
        return "STEM Curriculum"
    clean = re.sub(r'^\d+[\s_-]*', '', name)
    clean = re.sub(
        r':\s*(Fundamental Concepts|Structural Models|Dynamic Processes|Advanced Synthesis).*$',
        '',
        clean,
        flags=re.IGNORECASE
    )
    clean = re.sub(r'[_\-]+', ' ', clean).strip()
    return clean.title() if clean else name

def _clean_chunk_text(raw_text: str) -> str:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    cleaned_lines = []
    for line in lines:
        upper = line.upper()
        if any(h in upper for h in [
            "UE22CS", "UE24CS", "APPLIED CRYPTOGRAPHY", "PES UNIVERSITY", 
            "EMERGENCY EXIT", "NO CHATTING", "ASSEMBLY POINT", "PHONES ON SILENT", 
            "WASHROOM", "NO SLEEPING", "THANK YOU", "ISFCR", "ISFCR.PESU", 
            "PAGE ", "A NOTE ON SECURITY", "DEPARTMENT OF", "RING ROAD CAMPUS",
            "ANY QUESTIONS", "THANKS FOR YOUR ATTENTION"
        ]):
            continue
        if any(ex in upper for ex in ["EXAMPLE 1", "EXAMPLE 2", "EXAMPLE 3", "EXAMPLE 4", "EXAMPLE 5", "EXAMPLE 6"]):
            if len(line.split()) < 6:
                continue
        clean = line.lstrip("-* \t\u261e\u25cf\u2022").strip()
        if clean:
            cleaned_lines.append(clean)
    return " ".join(cleaned_lines)

def _is_substantive_chunk(raw_text: str) -> bool:
    cleaned = _clean_chunk_text(raw_text)
    return len(cleaned) >= 35 and len(cleaned.split()) >= 6

# ==============================================================================
# Numerical Solver for Hill Cipher
# ==============================================================================

def parse_hill_cipher_problem(query: str) -> Optional[Dict[str, Any]]:
    q_lower = query.lower()
    
    # Must involve hill cipher or encryption/matrix calculation
    is_calc = any(k in q_lower for k in [
        "encrypt", "decrypt", "calculation", "step by step", "calculate", 
        "find the ciphertext", "compute", "show the calculation"
    ])
    if not is_calc:
        return None

    is_decrypt = "decrypt" in q_lower

    # Match matrix like [[2,3],[3,4]] or [[3, 3], [2, 5]] or [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    matrix_match = re.search(
        r'\[\s*\[\s*([\d\s,\-]+)\s*\]\s*,\s*\[\s*([\d\s,\-]+)\s*\](?:\s*,\s*\[\s*([\d\s,\-]+)\s*\])?\s*\]',
        query
    )
    if not matrix_match:
        return None

    rows_raw = [matrix_match.group(1), matrix_match.group(2)]
    if matrix_match.group(3):
        rows_raw.append(matrix_match.group(3))

    matrix = []
    for r_str in rows_raw:
        nums = [int(n.strip()) for n in re.split(r'[,\s]+', r_str.strip()) if n.strip()]
        matrix.append(nums)

    n = len(matrix)
    for r in matrix:
        if len(r) != n:
            return None

    # Find target text: e.g. "plaintext CD", "plaintext 'CD'", "encrypt AB"
    target_text = None
    text_match = re.search(r'(?:plaintext|ciphertext|text|message)\s*[:=]?\s*[\'"]?([A-Za-z]{2,12})[\'"]?', query, re.IGNORECASE)
    if text_match:
        target_text = text_match.group(1).upper()
    else:
        # Search for standalone uppercase words not in keywords
        exclude = {
            "USING", "THE", "HILL", "CIPHER", "ENCRYPT", "DECRYPT", "WITH", "KEY", 
            "MATRIX", "SHOW", "CALCULATION", "STEP", "BY", "FIND", "AND", "PLAIN", 
            "TEXT", "CIPHERTEXT", "CODE"
        }
        words = re.findall(r'\b[A-Za-z]{2,12}\b', query)
        for w in words:
            if w.upper() not in exclude and len(w) <= 8:
                target_text = w.upper()
                break

    if not target_text:
        return None

    return {
        "operation": "decrypt" if is_decrypt else "encrypt",
        "matrix": matrix,
        "n": n,
        "text": target_text
    }

def solve_hill_cipher(problem: Dict[str, Any]) -> Tuple[str, str]:
    from math import gcd
    matrix=problem['matrix']; n=problem['n']; text=problem['text']; op=problem['operation']
    def determinant(m):
        if len(m)==1: return m[0][0]
        return sum((-1)**j*m[0][j]*determinant([row[:j]+row[j+1:] for row in m[1:]]) for j in range(len(m)))
    det=determinant(matrix)
    question='Why must the determinant be relatively prime to 26 for unique decryption?'
    if gcd(det,26)!=1:
        return f'The determinant is {det}. Since gcd({det}, 26) is not 1, this key does not permit unique decryption.\n\n'+question,question
    working=matrix
    if op=='decrypt':
        inverse=pow(det,-1,26)
        working=[[(inverse*(-1)**(i+j)*determinant([row[:i]+row[i+1:] for k,row in enumerate(matrix) if k!=j]))%26
                  for j in range(n)] for i in range(n)]
        if len(text)%n:
            return f'Ciphertext length must be a multiple of {n}; please supply the complete ciphertext.',question
    padded=text+'X'*((-len(text))%n) if op=='encrypt' else text
    result=[]; steps=[]
    for i in range(0,len(padded),n):
        block=padded[i:i+n]; values=[ord(c)-65 for c in block]
        output=[sum(working[r][c]*values[c] for c in range(n))%26 for r in range(n)]
        letters=''.join(chr(v+65) for v in output);result.append(letters)
        steps.append(f'- **{block}**: {values} → {output} → **{letters}**')
    title='Ciphertext' if op=='encrypt' else 'Decrypted plaintext'
    answer=f'Using A=0 through Z=25 and column vectors modulo 26. Key determinant: {det}.\n\n'
    if padded!=text: answer+=f'Pad with X to obtain **{padded}**.\n\n'
    if op=='decrypt': answer+=f'Inverse key modulo 26: `{working}`.\n\n'
    answer+='\n'.join(steps)+f'\n\n**{title}: {"".join(result)}**\n\n'+question
    return answer,question

# ==============================================================================
# Domain-Specific Response Generators
# ==============================================================================

def _generate_socratic_response(
    query: str,
    topic_name: Optional[str],
    prereqs: List[Dict],
    chunks: List[Dict],
    top_sim: Optional[float] = None,
    top_src: Optional[str] = None,
    history: Optional[List[Dict]] = None
) -> Tuple[str, Optional[str], Optional[str], Optional[float], Optional[str]]:
    clean_topic = _clean_concept_name(topic_name)
    q_lower = query.lower()

    # Check if this is a numerical Hill cipher problem first (deterministic mathematical calculation)
    if ("hill" in q_lower or "hill" in clean_topic.lower() or "cipher" in q_lower):
        prob = parse_hill_cipher_problem(query)
        if prob:
            direct_answer, socratic_q = solve_hill_cipher(prob)
            return direct_answer, socratic_q, None, top_sim, top_src


    # Step 2.4: Insufficient retrieval handling
    if not chunks or (top_sim is not None and top_sim < MIN_RELEVANCE_THRESHOLD):
        insufficient_msg = (
            f"The available course textbook passages for **{clean_topic}** do not contain sufficient information to answer this question confidently.\n\n"
            f"Could you please clarify your question or select a specific concept from the curriculum to explore?"
        )
        socratic_q = f"Which foundational concept in {clean_topic} would you like to explore next?"
        return insufficient_msg, socratic_q, None, top_sim, top_src

    grounding_excerpt = _clean_chunk_text(chunks[0]["document"]) if chunks else None
    if grounding_excerpt and len(grounding_excerpt) > 300:
        grounding_excerpt = grounding_excerpt[:300] + "..."

    # Step 2.3: Check if an external LLM key is configured (Groq / Gemini / OpenAI)
    groq_api_key = settings.GROQ_API_KEY
    if groq_api_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key, timeout=30, max_retries=1)
            context_text = "\n\n".join([
                f"[{c.get('metadata', {}).get('file_name', 'Textbook')}]: {_clean_chunk_text(c['document'])}"
                for c in chunks
            ])
            prereq_text = ", ".join([p["prereq_topic_name"] for p in prereqs]) if prereqs else "None"

            prompt = f"""You are a dedicated, encouraging, and academically rigorous Socratic STEM Tutor.
Answer the student's specific question directly, using the provided course textbook excerpts as factual grounding.

Rules:
1. Focus directly on the specific question asked. If a definition is requested, provide a concise definition. If a formula is requested, explain the formula. If a numerical problem is presented, calculate the steps and state the final answer.
2. Do NOT append unnecessary generic boilerplate or fixed theoretical paragraphs.
3. Ground all factual assertions, formulas, and mechanisms in the textbook excerpts below.
4. Do NOT include course codes (e.g., UE22CS...), slide numbers, file names, or administrative boilerplate.
5. Conclude your explanation with exactly ONE thoughtful Socratic follow-up question directly related to the current inquiry.
6. Never generate unrelated questions about networking, packet drops, or latency unless the topic is specifically computer networks.

Textbook Excerpts:
{context_text}

Active Concept: {clean_topic}
Prerequisite Knowledge: {prereq_text}
Student Question: {query}"""

            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "system", "content": prompt}] + (history or []) + [{"role": "user", "content": query}],
                temperature=0.3,
                max_tokens=600
            )
            raw_answer = completion.choices[0].message.content.strip()

            lines = raw_answer.splitlines()
            socratic_q = None
            for l in reversed(lines):
                if l.strip().endswith("?") and len(l.strip()) > 15:
                    socratic_q = l.strip().lstrip("*-# \t")
                    break

            if not socratic_q:
                socratic_q = f"How do the underlying principles of {clean_topic} apply in this context?"
                raw_answer += f"\n\nThink about this: {socratic_q}"

            return raw_answer, socratic_q, grounding_excerpt, top_sim, top_src
        except Exception:
            pass

    excerpts=[]
    for chunk in chunks[:3]:
        text=_clean_chunk_text(chunk['document'])
        source=chunk.get('metadata',{}).get('file_name','Uploaded material')
        page=chunk.get('metadata',{}).get('page_number')
        excerpts.append(f"**{source}" + (f", page {page}" if page else '') + f"**\n\n{text}")
    answer="Here are the relevant passages from your uploaded material:\n\n" + "\n\n".join(excerpts)
    question="How would you explain the main idea in these passages in your own words?"
    return answer+'\n\n'+question, question, grounding_excerpt, top_sim, top_src

@router.post("/query", response_model=TutorQueryResponse)
def socratic_tutor_query(req: TutorQueryRequest, user=Depends(current_user)):
    if not req.query.strip():
        raise HTTPException(422,'Enter a question.')
    if req.user_id is not None and req.user_id != user['user_id']:
        raise HTTPException(403,'User identity must match the signed-in account.')
    history=[]
    if req.session_id:
        session=owned_session(req.session_id,user)
        if session['subject_id'] != req.subject_id:
            raise HTTPException(400,'Session does not belong to this subject.')
        rows=execute_query('SELECT role,content FROM conversation_logs WHERE session_id=%s ORDER BY log_id DESC LIMIT 8',(req.session_id,))
        history=list(reversed(rows))

    subject = execute_one(
        "SELECT subject_id, subject_key, subject_name FROM SUBJECTS WHERE subject_id = %s",
        (req.subject_id,)
    )
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    subject_key = subject["subject_key"]

    # 1. Relational Graph Lookup (Topic & Recursive Prerequisites)
    target_topic = None
    prereqs = []
    allowed_topic_ids = []

    if req.topic_id:
        target_topic = execute_one(
            "SELECT topic_id, topic_name, difficulty_level, visual_type FROM TOPICS WHERE topic_id = %s AND subject_id = %s",
            (req.topic_id, req.subject_id)
        )
        if not target_topic:
            raise HTTPException(400,'Topic does not belong to this subject.')

        if target_topic:
            prereqs = _fetch_prerequisite_chain(target_topic["topic_id"])
            allowed_topic_ids = [target_topic["topic_id"]] + [p["prereq_topic_id"] for p in prereqs]

    active_concept_name = target_topic["topic_name"] if target_topic else subject["subject_name"]
    clean_concept = _clean_concept_name(active_concept_name)

    # 2. Dense Vector Retrieval (ChromaDB)
    stats = vector_service.get_stats(subject_key)
    total_col_chunks = stats.get("total_chunks", 0)
    candidate_limit = min(20, max(8, total_col_chunks)) if total_col_chunks > 0 else 8

    relational_filter_applied = False
    raw_chunks: List[Dict] = []

    # Try relational prerequisite-guided search first
    if allowed_topic_ids and req.include_prereqs:
        try:
            where_filter = {"topic_id": {"$in": allowed_topic_ids}}
            candidate_chunks = vector_service.search(
                subject_key=subject_key,
                query_text=req.query,
                n_results=candidate_limit,
                where_filter=where_filter
            )
            substantive_matches = [c for c in candidate_chunks if _is_substantive_chunk(c["document"])]
            if substantive_matches and substantive_matches[0].get("similarity", 0) >= MIN_RELEVANCE_THRESHOLD:
                raw_chunks = candidate_chunks
                relational_filter_applied = True
        except Exception:
            raw_chunks = []

    # If relational filter returned no substantive matches, search subject-wide collection
    if not raw_chunks:
        raw_chunks = vector_service.search(
            subject_key=subject_key,
            query_text=req.query,
            n_results=candidate_limit
        )

    # If the user query is short or template-based, augment with clean concept
    substantive_chunks = [c for c in raw_chunks if _is_substantive_chunk(c["document"])]
    if not substantive_chunks and clean_concept and clean_concept.lower() not in req.query.lower():
        augmented_query = f"{clean_concept} {req.query}"
        augmented_chunks = vector_service.search(
            subject_key=subject_key,
            query_text=augmented_query,
            n_results=candidate_limit
        )
        aug_substantive = [c for c in augmented_chunks if _is_substantive_chunk(c["document"])]
        if aug_substantive:
            seen_ids = set()
            merged = []
            for c in raw_chunks + augmented_chunks:
                if c["id"] not in seen_ids:
                    seen_ids.add(c["id"])
                    merged.append(c)
            merged.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            raw_chunks = merged
            substantive_chunks = [c for c in raw_chunks if _is_substantive_chunk(c["document"])]

    # Prioritize substantive chunks over slide titles and empty fragments
    grounding_chunks = substantive_chunks[:4] if substantive_chunks else raw_chunks[:4]

    top_sim = round(float(grounding_chunks[0]["similarity"]), 4) if grounding_chunks else None
    top_src = grounding_chunks[0].get("metadata", {}).get("file_name", "Course Textbook") if grounding_chunks else None
    grounding_excerpt = _clean_chunk_text(grounding_chunks[0]["document"])[:300] if grounding_chunks else None

    # 3. Generate Socratic Tutor Answer Tailored to Question Type
    direct_answer, reflection_q, grounding_excerpt, top_sim, top_source = _generate_socratic_response(
        query=req.query,
        topic_name=active_concept_name,
        prereqs=prereqs,
        chunks=grounding_chunks,
        top_sim=top_sim,
        top_src=top_src,
        history=history
    )

    # Persist the whole turn atomically, with ownership checked under a row lock.
    if req.session_id:
        with get_transaction() as conn:
            session=owned_session(req.session_id,user,conn)
            topic_id=target_topic['topic_id'] if target_topic else session['current_topic_id']
            conn.execute("UPDATE learning_sessions SET current_stage='explore', current_topic_id=%s WHERE session_id=%s",(topic_id,req.session_id))
            with conn.cursor() as cursor:
                cursor.executemany("INSERT INTO conversation_logs(session_id,topic_id,role,stage,content) VALUES(%s,%s,%s,'explore',%s)",
                    [(req.session_id,topic_id,'user',req.query),(req.session_id,topic_id,'assistant',direct_answer)])

    return TutorQueryResponse(
        answer=direct_answer,
        target_topic=target_topic,
        prerequisites=prereqs,
        retrieved_chunks=grounding_chunks,
        session_id=req.session_id,
        relational_filter_applied=relational_filter_applied,
        reflection_question=reflection_q,
        grounding_excerpt=grounding_excerpt,
        top_similarity=top_sim,
        top_source=top_source
    )
