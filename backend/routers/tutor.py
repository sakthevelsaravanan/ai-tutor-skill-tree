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
    Extracts valid slide/chapter titles, clean body lines, page numbers, and similarity.
    """
    parsed_slides = []
    seen_titles = set()

    def is_valid_slide_title(c: str) -> bool:
        c = c.strip()
        if not c or len(c) < 3 or len(c) > 65:
            return False
        # Formulas, equations, and font artifacts (/H) are not titles
        if any(sym in c for sym in ['=', '+', '->', '⊕', '≡', '≈', '≠', '/H', 'λ']):
            return False
        if not re.match(r'^[A-Z0-9"\']', c):
            return False
        if re.search(r'[,:;\-–—]$|\b(of|and|or|in|to|for|with|a|an|the|is|are)\s*$', c, re.I):
            return False
        if re.search(r'\b(is called|is defined as|we have|we see|which means|can be written)\b', c, re.I):
            return False
        return True

    for ch in chunks:
        doc = ch.get("document", "")
        meta = ch.get("metadata", {})
        sim = ch.get("similarity", 0)
        page = meta.get("page_number", "N/A")
        src_file = meta.get("file_name", "Course Slides")

        # Skip administrative acknowledgment slides
        doc_lower = doc.lower()
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
            cleaned = line.lstrip("-* 	☞●•").strip()
            if cleaned and len(cleaned) > 1:
                cleaned_lines.append(cleaned)

        if not cleaned_lines:
            continue

        title = None
        body = []
        for line in cleaned_lines:
            if title is None and is_valid_slide_title(line):
                title = line
            else:
                body.append(line)

        if not title:
            title = meta.get('chapter') or meta.get('topic_name') or 'Course Material'

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
    parsed_slides: list,
    subject_name: str,
    clean_topic: str
) -> str:
    """
    Synthesize a clean, plain, academically grounded response from retrieved course slides/notes.
    - Plain, complete sentences and formulas without cutoffs or sentence fragments.
    - Includes plain similarity score and page number for verifiable attribution.
    - Excludes meta-commentary, introductory filler ('our interest here is...'), and reflective questions.
    """
    if not parsed_slides:
        return (
            f"No direct matching topics were found in the uploaded course material for **{subject_name}** "
            f"matching *'{query}'*. Please check your query or verify the document in the Vectors tab."
        )

    q_lower = query.lower()
    stop_words = {
        "what", "is", "a", "an", "the", "are", "explain", "tell", "me", "about",
        "how", "why", "in", "to", "for", "of", "and", "or", "does", "do", "can",
        "define", "concept", "give", "show", "detail", "details"
    }
    query_words = set(w for w in re.findall(r'\b[a-z0-9_-]+\b', q_lower) if w not in stop_words and len(w) > 1)

    output_blocks = []
    # Process top 2 most relevant parsed slide chunks
    for p in parsed_slides[:2]:
        sim_pct = f"{round(float(p.get('similarity', 0)) * 100, 1)}%"
        page_val = p.get('page', 'N/A')
        page_ref = f"Page {page_val}" if page_val != "N/A" else p.get('file', 'Notes')
        raw_title = p.get('title', clean_topic or 'Course Material').strip()

        # Clean title: strip trailing numbers or "Section X.X"
        clean_title = re.sub(r'^(Section|Chapter)\s+\d+(?:\.\d+)?\s*', '', raw_title, flags=re.I).strip()
        clean_title = re.sub(r'\s+\d+$', '', clean_title).strip()
        clean_title = re.sub(r'^\d+\.\s*', '', clean_title).strip()
        if not clean_title or len(clean_title) < 3:
            clean_title = clean_topic or 'Course Material'

        doc = p.get('chunk', {}).get('document', '')
        if not doc and p.get('body'):
            doc = "\n".join(p['body'])

        # 1. De-hyphenate words broken across newlines (e.g. representa-\ntion -> representation)
        doc = re.sub(r'(\b[a-zA-Z]+)[-\u2010\u2013\u2014]\s*\n?\s*([a-zA-Z]+\b)', r'\1\2', doc)

        # 2. Split lines and unwrap continuous sentences
        raw_lines = [l.strip() for l in doc.splitlines() if l.strip()]
        unwrapped = []
        buf = []
        for l in raw_lines:
            if re.search(r'(?i)\b(copyright|all rights reserved|page \d+|table \d+\.\d+)\b', l):
                continue
            is_bullet = l.startswith(('-', '•', '*', '–')) or bool(re.match(r'^\d+[\.\)]\s+', l))
            is_formula = any(sym in l for sym in ['=', '->', '⊕', '≡', '≈', '≠']) and ('(' in l or len(l) < 70)
            is_sec_heading = bool(re.match(r'^(Section|Chapter|Table|Figure)\s+\d+', l, re.I))

            if is_bullet or is_formula or is_sec_heading:
                if buf:
                    unwrapped.append(' '.join(buf))
                    buf = []
                unwrapped.append(l)
            else:
                buf.append(l)
        if buf:
            unwrapped.append(' '.join(buf))

        # 3. Extract and score complete grammatical sentences and formulas
        sentences = []
        for item in unwrapped:
            if bool(re.match(r'^(Section|Chapter|Table|Figure)\s+\d+', item, re.I)):
                continue
            if any(sym in item for sym in ['=', '->', '⊕']) and len(item) < 80:
                clean_f = item.strip()
                if len(clean_f) > 5:
                    sentences.append(f"`{clean_f}`")
                continue

            sents = re.split(r'(?<=[.!?])\s+', item)
            for s in sents:
                s_clean = s.strip()
                s_clean = re.sub(r'^(?:[0-9A-Fa-f]{1,4}\s+){2,}', '', s_clean)
                if len(s_clean) < 22:
                    continue
                # If starts with broken closing bracket/punct like `tack), is called...`, clean or reject
                if re.match(r'^[a-z0-9]+\)\s*[,;]?\s*', s_clean):
                    s_clean = re.sub(r'^[a-z0-9]+\)\s*[,;]?\s*', '', s_clean)
                    if s_clean:
                        s_clean = s_clean[0].upper() + s_clean[1:]
                if not re.match(r'^[A-Z0-9"(\[]', s_clean):
                    continue
                if not re.search(r'[\.\?\!]$', s_clean) and not s_clean.startswith('`'):
                    continue
                if re.search(r'[-–—:,]$', s_clean):
                    continue
                # Filter dangling prepositions / conjunctions / verbs at end of sentence
                if re.search(r'\b(to|is|are|of|and|or|in|for|with|a|an|the|that|as)\s*[\.\?\!]?$', s_clean, re.I):
                    continue
                # Filter out self-referential introductory filler ("Our interest here is...", etc.)
                if re.search(r'(?i)^(our interest here is|in this chapter|in this section|as noted before|as mentioned earlier|as we have seen|we shall now)\b', s_clean):
                    continue
                sentences.append(s_clean)

        seen_s = set()
        deduped = []
        for s in sentences:
            s_low = s.lower().strip()
            if s_low not in seen_s:
                seen_s.add(s_low)
                deduped.append(s)

        if not deduped:
            continue

        scored = []
        for idx, s in enumerate(deduped):
            score = 0
            s_low = s.lower()
            for qw in query_words:
                if qw in s_low:
                    score += 2
            if idx == 0:
                score += 1
            scored.append((score, idx, s))

        scored.sort(key=lambda x: (-x[0], x[1]))
        chosen_indices = sorted([x[1] for x in scored[:4]])
        chosen_sents = [deduped[i] for i in chosen_indices]

        paragraphs = []
        prose_sents = [s for s in chosen_sents if not s.startswith('`')]
        code_sents = [s for s in chosen_sents if s.startswith('`')]

        if prose_sents:
            paragraphs.append(" ".join(prose_sents))
        if code_sents:
            for c in code_sents:
                paragraphs.append(f"> {c}")

        if paragraphs:
            block_content = "\n\n".join(paragraphs)
            output_blocks.append(f"#### **{clean_title}** `(Match: {sim_pct} · {page_ref})`\n\n{block_content}")

    if not output_blocks:
        return (
            f"Sufficient supporting information was not found in the selected course material for "
            f"**{subject_name}** matching *'{query}'*. Please check your query or verify the course material."
        )

    return "\n\n---\n\n".join(output_blocks)


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
