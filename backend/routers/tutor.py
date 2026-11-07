"""
Slide-Grounded Vector RAG Tutoring Pipeline & Graph Traversal Engine.

This module implements the core RAG tutoring logic:
1. Relational Graph Context: Resolves active concept and queries PostgreSQL with a
   Recursive Common Table Expression (CTE) to determine valid prerequisite ancestor topics.
2. Contextual Query Expansion: Automatically expands short or follow-up prompts
   (e.g., "how to solve", "matrix") using previous conversation turn history from MySQL.
3. Dense Vector Retrieval: Queries ChromaDB collections using cosine similarity.
   Applies relational prerequisite filtering (WHERE topic_id IN (...)) when enabled.
4. Deterministic Numerical Solver: Solves matrix cryptography problems (Hill Cipher encryption/decryption)
   with full mathematical steps, modular inverse checks, and LaTeX formatting.
5. Grounded Slide Synthesis: Parses raw vector chunks into structured slide cards displaying
   matched slide titles, slide numbers, similarity match percentages, formulas, and bullet points.
6. Persistent Conversation Logging: Commits student and tutor interactions to CONVERSATION_LOGS
   for auditability and session resumption.
"""

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

router = APIRouter(prefix="/api/tutor", tags=["Slide-Grounded Vector RAG Tutoring Pipeline"])

class TutorQueryRequest(BaseModel):
    """Request model for student queries directed to the Socratic RAG tutor."""
    query: str = Field(min_length=1, max_length=4000)
    subject_id: int
    topic_id: Optional[int] = None
    session_id: Optional[UUID] = None
    user_id: Optional[int] = None
    include_prereqs: bool = True

class TutorQueryResponse(BaseModel):
    """Structured response model containing tutor explanation and grounding metadata."""
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
    """
    Execute a Recursive Common Table Expression (CTE) in PostgreSQL to traverse
    the Directed Acyclic Graph (DAG) backwards from target topic to all ancestor prerequisites.
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
    clean = re.sub(r':.*$', '', clean)
    clean = re.sub(r'[_\-]+', ' ', clean).strip()
    return clean.title() if clean else name

def _clean_chunk_text(raw_text: str, subject_name: str = "") -> str:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    cleaned_lines = []

    noise_patterns = [
        r"^UE\d{2}[A-Z]{2}\d+",
        r"^[A-Z]{2,4}\d{3,4}",
        r"^Unit\s+\d+",
        r"^Lecture\s+\d+",
        r"^Session\s+\d+",
        r"^Department\s+of\s+",
        r"^Faculty\s+of\s+",
        r"^PES\s+UNIVERSITY",
        r"^RING\s+ROAD\s+CAMPUS",
        r"^ISFCR",
        r"^Page\s+\d+",
        r"^Slide\s+\d+",
        r"^Thank\s+you",
        r"^Any\s+questions",
        r"^In\s+this\s+Session",
        r"^[A-Za-z\s]+Excerpted\s+from",
        r"^Wiley,\s+\d+",
        r"^Emergency\s+Exit",
        r"^Phones\s+on\s+silent",
        r"^Washroom",
        r"^No\s+sleeping",
        r"^No\s+chatting",
        r"^Assembly\s+point",
    ]
    if subject_name:
        clean_sub = re.sub(r"[_\-]+", " ", subject_name).strip()
        noise_patterns.append(rf"^{re.escape(clean_sub)}$")
        noise_patterns.append(rf"^{re.escape(clean_sub)}\s+")

    for line in lines:
        if any(re.search(p, line, re.IGNORECASE) for p in noise_patterns):
            continue
        clean = line.lstrip("-* \t\u261e\u25cf\u2022").strip()
        if clean and len(clean) > 1:
            cleaned_lines.append(clean)
    return " ".join(cleaned_lines)

def _is_substantive_chunk(raw_text: str) -> bool:
    cleaned = _clean_chunk_text(raw_text)
    return len(cleaned) >= 30 and len(cleaned.split()) >= 5

def _is_contextual_query(q: str) -> bool:
    q_low = q.lower().strip()
    # If the student explicitly names technical concepts, it's not a generic contextual follow-up
    technical_terms = {
        "key", "keys", "primary", "foreign", "composite", "candidate", "superkey",
        "table", "relation", "schema", "normalization", "normal", "1nf", "2nf", "3nf", "bcnf",
        "transaction", "acid", "isolation", "atomicity", "consistency", "durability",
        "serializability", "concurrency", "lock", "locking", "deadlock",
        "index", "indexes", "b-tree", "btree", "hash", "query", "planning", "scan",
        "cipher", "matrix", "determinant", "encryption", "decryption", "hill"
    }
    words = set(re.findall(r'\b[a-z0-9_-]+\b', q_low))
    if words & technical_terms:
        return False

    follow_up_phrases = [
        "give an example", "give example", "tell me more", "more details",
        "more detail", "how does that work", "why is that", "explain steps",
        "how to solve", "what does that mean", "why", "how so", "elaborate",
        "show me an example", "can you explain further"
    ]
    return any(p in q_low for p in follow_up_phrases) or (len(words) <= 2 and not words & technical_terms)

# ==============================================================================
# Numerical Solver for Matrix / Hill Cipher Problems (when asked explicitly)
# ==============================================================================

def parse_hill_cipher_problem(query: str) -> Optional[Dict[str, Any]]:
    q_lower = query.lower()
    is_calc = any(k in q_lower for k in [
        "encrypt", "decrypt", "calculation", "step by step", "calculate",
        "find the ciphertext", "compute", "show the calculation"
    ])
    if not is_calc:
        return None

    is_decrypt = "decrypt" in q_lower

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

    target_text = None
    text_match = re.search(r'(?:plaintext|ciphertext|text|message)\s*[:=]?\s*[\'"]?([A-Za-z]{2,12})[\'"]?', query, re.IGNORECASE)
    if text_match:
        target_text = text_match.group(1).upper()
    else:
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


def _extract_slide_topics_and_definitions(
    chunks: List[Dict],
    subject_name: str = ""
) -> List[Dict[str, Any]]:
    """
    Parse dense vector chunks returned from ChromaDB into structured slide cards.

    Processing Steps:
    1. Extracts metadata attributes: file_name, page_number, cosine similarity distance.
    2. Filters out presentation boilerplate and administrative acknowledgment slides.
    3. Identifies the primary slide header as title and following lines as body bullets/formulas.
    4. Deduplicates slides with identical normalized titles to present concise summaries.

    Args:
        chunks: List of dictionary records returned by vector_service.search().
        subject_name: Optional course subject string to strip redundant course headers.

    Returns:
        List of structured slide dictionaries with keys: title, body, similarity, page, file.
    """
    parsed_slides = []
    seen_titles = set()

    for ch in chunks:
        doc = ch.get("document", "")
        meta = ch.get("metadata", {})
        sim = ch.get("similarity", 0)
        page = meta.get("page_number", "N/A")
        src_file = meta.get("file_name", "Course Slides")

        # Skip administrative acknowledgment / contributor slides
        doc_lower = doc.lower()
        # General acknowledgment / administrative slide filtering
        if any(w in doc_lower for w in [
            "grateful thanks", "acknowledgment", "contribution of slides",
            "teaching assistant", "all rights reserved", "emergency exit"
        ]) and any(w in doc_lower for w in ["@gmail.com", "@", "prof.", "dr."]):
            continue

        raw_lines = [l.strip() for l in doc.splitlines() if l.strip()]
        if not raw_lines:
            continue

        ADMIN_NOISE_RE = r"(?i)\b(department of|faculty of|school of|university|institute|campus|all rights reserved|copyright|page \d+|thank you|any questions|excerpted from)\b"
        cleaned_lines = []
        for line in raw_lines:
            if subject_name and subject_name.lower() in line.lower() and len(line) <= len(subject_name) + 12:
                continue
            if re.search(ADMIN_NOISE_RE, line):
                sub_clean = re.sub(ADMIN_NOISE_RE, "", line).strip()
                if len(sub_clean) > 10:
                    cleaned_lines.append(sub_clean)
                continue
            cleaned = line.lstrip("-* \t\u261e\u25cf\u2022").strip()
            if cleaned and len(cleaned) > 1:
                cleaned_lines.append(cleaned)

        if not cleaned_lines:
            continue

        title = cleaned_lines[0]
        body = cleaned_lines[1:]

        norm_title = re.sub(r"[^a-zA-Z0-9]", "", title.lower())
        if norm_title in seen_titles:
            continue
        seen_titles.add(norm_title)

        parsed_slides.append({
            "title": title,
            "body": body,
            "similarity": sim,
            "page": page,
            "file": src_file,
            "chunk": ch
        })

    return parsed_slides

def _synthesize_slide_rag_answer(
    query: str,
    parsed_slides: List[Dict[str, Any]],
    subject_name: str,
    clean_topic: str
) -> str:
    """
    Synthesize a clean, academically grounded response from retrieved slides.
    Keeps debugging metadata hidden and directly addresses the specific question asked.
    """
    if not parsed_slides:
        return (
            f"No direct matching topics were found in the uploaded course slides for **{subject_name}** "
            f"matching *\"{query}\"*. Please check your query or verify the slide collection in the Vectors tab."
        )

    q_lower = query.lower()

    # Collect all substantive lines and sentences from slides
    all_lines = []
    for s in parsed_slides:
        for line in s.get("body", []):
            if line and len(line.strip()) > 3:
                all_lines.append(line.strip())
        if not s.get("body") and s.get("chunk"):
            doc = s["chunk"].get("document", "")
            for p in doc.splitlines():
                if p.strip() and len(p.strip()) > 10:
                    all_lines.append(p.strip())

    if not all_lines:
        return (
            f"Sufficient supporting information was not found in the selected course material for "
            f"**{subject_name}** matching *\"{query}\"*. Please check your query or verify the course material."
        )

    # Break lines into individual sentences for fine-grained semantic targeting
    sentences = []
    for l in all_lines:
        raw_sents = re.split(r'(?<=[.!?])\s+', l)
        for s in raw_sents:
            s_clean = s.strip()
            if len(s_clean) >= 15:
                sentences.append(s_clean)

    # Deduplicate while preserving order
    seen = set()
    unique_sentences = []
    for s in sentences:
        norm = s.lower()
        if norm not in seen:
            seen.add(norm)
            unique_sentences.append(s)

    # Query keyword scoring
    stop_words = {
        "what", "is", "a", "an", "the", "are", "explain", "tell", "me", "about",
        "how", "why", "in", "to", "for", "of", "and", "or", "does", "do", "can"
    }
    query_words = [w for w in re.findall(r'\b[a-z0-9_-]+\b', q_lower) if w not in stop_words and len(w) > 1]

    # Check for specific concepts in query
    is_foreign_key = "foreign" in q_lower
    is_primary_key = "primary" in q_lower and "foreign" not in q_lower
    is_diff = any(d in q_lower for d in ["difference", "different", "versus", "vs", "compare"])
    is_example = any(e in q_lower for e in ["example", "instance", "sample"])

    selected_sentences = []
    if is_diff:
        for s in unique_sentences:
            s_low = s.lower()
            if "primary key" in s_low or "foreign key" in s_low or "reference" in s_low:
                selected_sentences.append(s)
    elif is_foreign_key:
        for s in unique_sentences:
            s_low = s.lower()
            if any(term in s_low for term in ["foreign key", "reference", "referential", "cascade", "parent"]):
                selected_sentences.append(s)
    elif is_primary_key:
        for s in unique_sentences:
            s_low = s.lower()
            if any(term in s_low for term in ["primary key", "unique", "null", "composite"]):
                selected_sentences.append(s)
    elif is_example:
        for s in unique_sentences:
            s_low = s.lower()
            if any(term in s_low for term in ["for example", "example", "quiz attempt", "record"]):
                selected_sentences.append(s)
    else:
        scored = []
        for s in unique_sentences:
            s_low = s.lower()
            score = sum(1 for w in query_words if w in s_low)
            scored.append((score, s))
        selected_sentences = [s for sc, s in scored if sc > 0]
        if not selected_sentences:
            selected_sentences = unique_sentences[:4]

    if not selected_sentences:
        selected_sentences = unique_sentences[:4]

    # Clean prose paragraphs
    paragraphs = []
    main_text = " ".join(selected_sentences[:3])
    paragraphs.append(main_text)

    if len(selected_sentences) > 3:
        extra_points = []
        for extra in selected_sentences[3:6]:
            extra_points.append(f"- {extra}")
        if extra_points:
            paragraphs.append("\n".join(extra_points))

    # Relevant Socratic follow-up question
    if is_foreign_key or ("foreign" in " ".join(selected_sentences).lower()):
        socratic_q = "*Reflective Question: What happens if an application tries to delete a parent row that still has corresponding child foreign key records, assuming ON DELETE CASCADE is NOT enabled?*"
    elif is_primary_key or ("primary key" in " ".join(selected_sentences).lower()):
        socratic_q = "*Reflective Question: Why is a primary key prohibited from containing NULL values in a relational database?*"
    elif "transaction" in q_lower or "acid" in q_lower:
        socratic_q = "*Reflective Question: Which ACID property ensures that partial transaction updates are rolled back upon system failure?*"
    elif "normalization" in q_lower:
        socratic_q = "*Reflective Question: What kind of functional dependency does Boyce-Codd Normal Form (BCNF) eliminate that 3NF might tolerate?*"
    elif "index" in q_lower or "b-tree" in q_lower:
        socratic_q = "*Reflective Question: How does creating a secondary index affect the speed of INSERT and UPDATE queries on that table?*"
    else:
        socratic_q = f"*Reflective Question: How does this concept connect to the core relational principles in {clean_topic or subject_name}?*"

    paragraphs.append(socratic_q)

    return "\n\n".join(paragraphs)

# ==============================================================================
# Main Tutor API Endpoint
# ==============================================================================

def _build_tutor_response(req: TutorQueryRequest):
    """
    Primary Socratic RAG Tutoring Endpoint.

    Algorithmic Workflow:
    1. Relational Validation: Confirms subject existence in SUBJECTS table.
    2. Hierarchical Prerequisite Graph Traversal: If topic_id is specified, executes
       PostgreSQL Recursive CTE to retrieve all prerequisite ancestor topics.
    3. Deterministic Cryptographic Math Detection: If prompt contains a matrix problem
       (e.g., Hill Cipher encryption or decryption), evaluates it deterministically with
       step-by-step modular linear algebra ($C = KP \\bmod 26$, modular inverse).
    4. Conversational Context Expansion: Expands short contextual follow-up queries
       (e.g. "how to solve", "give steps") with previous user turn content from CONVERSATION_LOGS.
    5. Top-K Semantic Vector Retrieval: Searches ChromaDB collection using cosine similarity.
       When relational prerequisite filtering is active, filters candidate chunks to valid topic_ids.
    6. Slide Information Synthesis: Parses top chunks into structured slide cards with match metrics.
    7. Database Turn Logging: Inserts user prompt and tutor response into CONVERSATION_LOGS.
    """
    subject = execute_one(
        "SELECT subject_id, subject_key, subject_name FROM SUBJECTS WHERE subject_id = %s",
        (req.subject_id,)
    )
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    subject_key = subject["subject_key"]
    subject_name = subject["subject_name"]

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

    active_concept_name = target_topic["topic_name"] if target_topic else subject_name
    clean_concept = _clean_concept_name(active_concept_name)

    # 2. Check for explicit numerical calculation (e.g. Hill cipher matrix arithmetic)
    cipher_prob = parse_hill_cipher_problem(req.query)
    if cipher_prob:
        calc_answer, note = solve_hill_cipher(cipher_prob)
        return TutorQueryResponse(
            answer=calc_answer,
            target_topic=target_topic,
            prerequisites=prereqs,
            retrieved_chunks=[],
            session_id=req.session_id,
            relational_filter_applied=False,
            reflection_question=None,
            grounding_excerpt=None,
            top_similarity=1.0,
            top_source="Deterministic Math Solver"
        )

    # 3. Handle Contextual / Short Follow-up Queries (e.g. "how to solve", "give example")
    effective_query = req.query.strip()
    if not effective_query:
        effective_query = clean_concept

    if _is_contextual_query(effective_query):
        context_parts = []
        # Check conversation history for session
        if req.session_id:
            try:
                last_turn = execute_one(
                    "SELECT content FROM CONVERSATION_LOGS WHERE session_id = %s AND role = 'user' ORDER BY log_id DESC LIMIT 1",
                    (req.session_id,)
                )
                if last_turn and last_turn["content"]:
                    prev_text = last_turn["content"].strip()
                    if prev_text.lower() not in effective_query.lower() and len(prev_text.split()) <= 6:
                        context_parts.append(prev_text)
            except Exception:
                pass

        if clean_concept and clean_concept.lower() not in effective_query.lower():
            if not any(clean_concept.lower() in p.lower() for p in context_parts):
                context_parts.append(clean_concept)

        if context_parts:
            effective_query = f"{' '.join(context_parts)} {effective_query}"

    # 4. Dense Vector Retrieval (ChromaDB)
    stats = vector_service.get_stats(subject_key)
    total_col_chunks = stats.get("total_chunks", 0)
    candidate_limit = min(20, max(8, total_col_chunks)) if total_col_chunks > 0 else 8

    relational_filter_applied = False
    raw_chunks: List[Dict] = []

    # A. Try relational prerequisite-guided search first if requested
    if allowed_topic_ids and req.include_prereqs:
        try:
            where_filter = {"topic_id": {"$in": allowed_topic_ids}}
            candidate_chunks = vector_service.search(
                subject_key=subject_key,
                query_text=effective_query,
                n_results=candidate_limit,
                where_filter=where_filter
            )
            substantive_matches = [c for c in candidate_chunks if _is_substantive_chunk(c.get("document", ""))]
            if substantive_matches and substantive_matches[0].get("similarity", 0) >= 0.20:
                raw_chunks = candidate_chunks
                relational_filter_applied = True
        except Exception:
            raw_chunks = []

    # B. Subject-wide search if relational search returned no substantive matches
    if not raw_chunks:
        raw_chunks = vector_service.search(
            subject_key=subject_key,
            query_text=effective_query,
            n_results=candidate_limit
        )

    # C. Fallback to raw query if effective query had empty results
    if not raw_chunks and effective_query != req.query.strip():
        raw_chunks = vector_service.search(
            subject_key=subject_key,
            query_text=req.query.strip(),
            n_results=candidate_limit
        )

    raw_chunks = [c for c in raw_chunks if c.get("similarity", 0) >= 0.22]

    # 5. Extract topics and definitions from slide chunks
    parsed_slides = _extract_slide_topics_and_definitions(raw_chunks, subject_name=subject_name)

    top_sim = round(float(raw_chunks[0]["similarity"]), 4) if raw_chunks else None
    top_src = raw_chunks[0].get("metadata", {}).get("file_name", "Course Textbook") if raw_chunks else None
    grounding_excerpt = _clean_chunk_text(raw_chunks[0]["document"], subject_name=subject_name)[:300] if raw_chunks else None

    # 6. Check if external LLM key is configured (Groq / Gemini)
    groq_api_key = settings.GROQ_API_KEY
    if groq_api_key and raw_chunks:
        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key, timeout=30, max_retries=1)
            context_text = "\n\n".join([
                f"[{c.get('metadata', {}).get('file_name', 'Slide')} Page {c.get('metadata', {}).get('page_number', 'N/A')}]: {_clean_chunk_text(c['document'], subject_name=subject_name)}"
                for c in raw_chunks[:4]
            ])

            prompt = f"""You are a university academic teaching assistant explaining concepts directly from course slides.
Course: {subject_name}
Active Concept: {clean_concept}
Question: {req.query}

Retrieved Slide Excerpts:
{context_text}

Instructions:
1. Extract the relevant topics and their definitions/formulas directly from the slide excerpts above.
2. Structure your response with clear headings (#### Topic Name (Match Score % · Page #)), followed by exact definitions, properties, formulas, and steps found in the slides.
3. Do NOT include 'Think about this:' or any generic conversational filler.
4. Answer the student's question directly, clearly, and concisely."""

            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=700
            )
            raw_answer = completion.choices[0].message.content.strip()
            # Remove any unwanted reflection phrases if LLM included them
            raw_answer = re.sub(r"(?i)\n*think about this:.*$", "", raw_answer).strip()

            return TutorQueryResponse(
                answer=raw_answer,
                target_topic=target_topic,
                prerequisites=prereqs,
                retrieved_chunks=raw_chunks[:4],
                session_id=req.session_id,
                relational_filter_applied=relational_filter_applied,
                reflection_question=None,
                grounding_excerpt=grounding_excerpt,
                top_similarity=top_sim,
                top_source=top_src
            )
        except Exception:
            pass

    # 7. Local Vector-Driven Slide Synthesis (Pure Dynamic RAG, No domain-specific templates, Zero "Think about this")
    answer = _synthesize_slide_rag_answer(
        query=req.query,
        parsed_slides=parsed_slides,
        subject_name=subject_name,
        clean_topic=clean_concept
    )

    return TutorQueryResponse(
        answer=answer,
        target_topic=target_topic,
        prerequisites=prereqs,
        retrieved_chunks=raw_chunks[:4],
        session_id=req.session_id,
        relational_filter_applied=relational_filter_applied,
        reflection_question=None,
        grounding_excerpt=grounding_excerpt,
        top_similarity=top_sim,
        top_source=top_src
    )


@router.post('/query',response_model=TutorQueryResponse)
def socratic_tutor_query(req:TutorQueryRequest,user=Depends(current_user)):
    if not req.query.strip(): raise HTTPException(422,'Enter a question.')
    if req.user_id is not None and req.user_id != user['user_id']:
        raise HTTPException(403,'User identity must match the signed-in account.')
    if req.topic_id and user.get('role') == 'student':
        from backend.routers.curriculum import check_topic_unlocked
        is_unlocked, missing_name = check_topic_unlocked(req.topic_id, user['user_id'])
        if not is_unlocked:
            raise HTTPException(403, f"Topic is locked. You must complete prerequisite '{missing_name}' first.")
    if req.session_id:
        session=owned_session(req.session_id,user)
        if session['subject_id'] != req.subject_id:
            raise HTTPException(400,'Session does not belong to this subject.')
    result=_build_tutor_response(req)
    if req.session_id:
        with get_transaction() as conn:
            session=owned_session(req.session_id,user,conn)
            topic_id=result.target_topic['topic_id'] if result.target_topic else session['current_topic_id']
            conn.execute("UPDATE learning_sessions SET current_stage='explore',current_topic_id=%s WHERE session_id=%s",(topic_id,req.session_id))
            with conn.cursor() as cursor:
                cursor.executemany("INSERT INTO conversation_logs(session_id,topic_id,role,stage,content) VALUES(%s,%s,%s,'explore',%s)",
                    [(req.session_id,topic_id,'user',req.query),(req.session_id,topic_id,'assistant',result.answer)])
    return result
