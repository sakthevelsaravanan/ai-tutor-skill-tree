import os
import re
from typing import List, Dict, Optional, Any, Tuple
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.database import execute_query, execute_one, execute_dml
from backend.vector_service import vector_service

router = APIRouter(prefix="/api/tutor", tags=["Slide-Grounded Vector RAG Tutoring Pipeline"])

class TutorQueryRequest(BaseModel):
    query: str
    subject_id: int
    topic_id: Optional[int] = None
    session_id: Optional[str] = None
    user_id: Optional[int] = 3
    include_prereqs: bool = True

class TutorQueryResponse(BaseModel):
    answer: str
    target_topic: Optional[Dict[str, Any]] = None
    prerequisites: List[Dict[str, Any]] = []
    retrieved_chunks: List[Dict[str, Any]] = []
    session_id: Optional[str] = None
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
    words = q_low.split()
    if len(words) <= 4:
        context_triggers = {
            "how", "solve", "why", "what", "steps", "calculate", "example",
            "formula", "more", "detail", "definition", "state", "states",
            "method", "procedure", "explain", "matrix"
        }
        return any(w in context_triggers for w in words)
    return False

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

def solve_hill_cipher(problem: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    op = problem["operation"]
    K = problem["matrix"]
    n = problem["n"]
    text = problem["text"]

    if op == "encrypt":
        pad_len = (n - (len(text) % n)) % n
        padded_text = text + ("X" * pad_len)
        letter_vals = [ord(c) - ord('A') for c in padded_text]
        
        steps = []
        steps.append(f"To encrypt the plaintext **{text}** using the Hill cipher ($C = KP \\bmod 26$), follow these steps:\n")
        steps.append("### Step 1: Convert Plaintext Letters to Numerical Values")
        steps.append("Using the standard alphabet index ($A=0, B=1, C=2, \\dots, Z=25$):")
        char_mappings = [f"**{c}** $\\to {ord(c) - ord('A')}$" for c in padded_text]
        steps.append("- " + ", ".join(char_mappings) + "\n")
        
        ciphertext_chars = []
        
        for b_idx in range(0, len(padded_text), n):
            block_chars = padded_text[b_idx:b_idx+n]
            P = letter_vals[b_idx:b_idx+n]
            
            p_vec_str = "\\begin{pmatrix} " + " \\\\ ".join(str(p) for p in P) + " \\end{pmatrix}"
            k_mat_str = "\\begin{pmatrix} " + " \\\\ ".join(" & ".join(str(v) for v in row) for row in K) + " \\end{pmatrix}"
            
            steps.append(f"### Step 2: Form Plaintext Vector and Key Matrix")
            steps.append(f"Plaintext block **{block_chars}** represented as column vector $P$:\n")
            steps.append(f"$$P = {p_vec_str}, \\quad K = {k_mat_str}$$\n")
            
            steps.append("### Step 3: Perform Matrix Multiplication ($KP$)")
            kp_calc_lines = []
            KP = []
            for i in range(n):
                mult_terms = [f"{K[i][j]} \\times {P[j]}" for j in range(n)]
                row_sum = sum(K[i][j] * P[j] for j in range(n))
                KP.append(row_sum)
                kp_calc_lines.append(f"\\text{{Row {i+1}}}: " + " + ".join(mult_terms) + f" = {row_sum}")
            
            steps.append("Multiply each row of key matrix $K$ by column vector $P$:\n")
            for line in kp_calc_lines:
                steps.append(f"- $${line}$$")
            
            kp_vec_str = "\\begin{pmatrix} " + " \\\\ ".join(str(val) for val in KP) + " \\end{pmatrix}"
            steps.append(f"\n$$KP = {kp_vec_str}$$\n")
            
            steps.append("### Step 4: Reduce Modulo 26 ($C = KP \\bmod 26$)")
            C = [val % 26 for val in KP]
            c_calc_lines = [f"{val} \\bmod 26 = {val % 26}" for val in KP]
            for line in c_calc_lines:
                steps.append(f"- $${line}$$")
                
            c_vec_str = "\\begin{pmatrix} " + " \\\\ ".join(str(val) for val in C) + " \\end{pmatrix}"
            steps.append(f"\n$$C = {c_vec_str}$$\n")
            
            steps.append("### Step 5: Convert Numbers Back to Ciphertext Letters")
            block_cipher = "".join(chr(val + ord('A')) for val in C)
            for val, c_char in zip(C, block_cipher):
                steps.append(f"- ${val} \\to$ **{c_char}**")
                
            ciphertext_chars.append(block_cipher)
            
        final_cipher = "".join(ciphertext_chars)
        steps.append(f"\n**Final Ciphertext**: **{final_cipher}**\n")
        return "\n".join(steps), "Note: Numerical values are reduced modulo 26 before mapping back to alphabet letters."

    else:
        if n == 2:
            a, b = K[0][0], K[0][1]
            c, d = K[1][0], K[1][1]
            det = (a * d - b * c) % 26
            
            det_inv = None
            for x in range(1, 26):
                if (det * x) % 26 == 1:
                    det_inv = x
                    break
                    
            if det_inv is None:
                err_msg = (
                    f"The key matrix $K = \\begin{{pmatrix}} {a} & {b} \\\\ {c} & {d} \\end{{pmatrix}}$ has determinant "
                    f"$|K| = ({a}\\times{d} - {b}\\times{c}) \\bmod 26 = {det}$.\n\n"
                    f"Because $\\gcd({det}, 26) \\neq 1$, $|K|$ has no modular inverse modulo 26. "
                    "Therefore, this key matrix cannot be used for unique decryption."
                )
                return err_msg, "Decryption requires gcd(|K|, 26) = 1."

            adj = [[d % 26, (-b) % 26], [(-c) % 26, a % 26]]
            K_inv = [[(det_inv * adj[i][j]) % 26 for j in range(2)] for i in range(2)]

            pad_len = (2 - (len(text) % 2)) % 2
            padded_text = text + ("X" * pad_len)
            c_vals = [ord(ch) - ord('A') for ch in padded_text]

            steps = [
                f"To decrypt the ciphertext **{text}** using the Hill cipher ($P = K^{{-1}}C \\bmod 26$):\n",
                "### Step 1: Calculate Determinant and Modular Inverse",
                f"- Determinant: $|K| = ({a} \\times {d} - {b} \\times {c}) = {a*d - b*c} \\equiv {det} \\pmod{{26}}$",
                f"- Modular multiplicative inverse: $|K|^{{-1}} \\equiv {det_inv} \\pmod{{26}}$ (since ${det} \\times {det_inv} \\equiv 1 \\pmod{{26}}$)\n",
                "### Step 2: Compute Inverse Key Matrix ($K^{-1}$)",
                f"$$K^{{-1}} = {det_inv} \\times \\begin{{pmatrix}} {adj[0][0]} & {adj[0][1]} \\\\ {adj[1][0]} & {adj[1][1]} \\end{{pmatrix}} \\equiv \\begin{{pmatrix}} {K_inv[0][0]} & {K_inv[0][1]} \\\\ {K_inv[1][0]} & {K_inv[1][1]} \\end{{pmatrix}} \\pmod{{26}}$$\n",
                "### Step 3: Decrypt Ciphertext Vector ($P = K^{-1}C \\bmod 26$)"
            ]

            plaintext_chars = []
            for b_idx in range(0, len(padded_text), 2):
                C_vec = c_vals[b_idx:b_idx+2]
                P_vals = [
                    (K_inv[0][0] * C_vec[0] + K_inv[0][1] * C_vec[1]) % 26,
                    (K_inv[1][0] * C_vec[0] + K_inv[1][1] * C_vec[1]) % 26
                ]
                block_plain = "".join(chr(val + ord('A')) for val in P_vals)
                plaintext_chars.append(block_plain)
                steps.append(f"- Block **{padded_text[b_idx:b_idx+2]}** (${C_vec[0]}, {C_vec[1]}$) $\\to$ (${P_vals[0]}, {P_vals[1]}$) $\\to$ **{block_plain}**")

            final_plain = "".join(plaintext_chars)
            steps.append(f"\n**Decrypted Plaintext**: **{final_plain}**\n")
            return "\n".join(steps), "Decryption requires gcd(|K|, 26) = 1."
        else:
            steps = [
                f"Decryption in the Hill cipher computes $P = K^{{-1}}C \\bmod 26$, where $K^{{-1}} = \\text{{adj}}(K) \\cdot |K|^{{-1}} \\bmod 26$.\n"
            ]
            return "\n".join(steps), "Decryption requires gcd(|K|, 26) = 1."

# ==============================================================================
# Slide-Grounded Vector Extraction & Synthesis
# ==============================================================================

def _extract_slide_topics_and_definitions(
    chunks: List[Dict],
    subject_name: str = ""
) -> List[Dict[str, Any]]:
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
        if any(w in doc_lower for w in [
            "with grateful thanks", "contribution of slides", "slides collated by",
            "teaching assistant", "vii sem", "viii sem", "v sem", "vi sem"
        ]) and any(w in doc_lower for w in ["@gmail.com", "@pes.edu", "prof.", "dr."]):
            continue

        raw_lines = [l.strip() for l in doc.splitlines() if l.strip()]
        if not raw_lines:
            continue

        # Filter noise from slide lines
        cleaned_lines = []
        noise_words = [
            "DATA ANALYTICS", "PES UNIVERSITY", "DEPARTMENT OF", "UNIT ",
            "LECTURE ", "EXCERPTED FROM", "WILEY", "PAGE ", "EMERGENCY EXIT",
            "THANK YOU", "ANY QUESTIONS", "RING ROAD CAMPUS", "ISFCR"
        ]
        if subject_name:
            noise_words.append(subject_name.upper())

        for line in raw_lines:
            line_up = line.upper()
            if any(nw in line_up for nw in noise_words):
                # Check if it has real content after noise
                sub_clean = line
                for nw in noise_words:
                    sub_clean = re.sub(rf"(?i)\b{re.escape(nw)}\b", "", sub_clean).strip()
                if len(sub_clean) > 10 and not any(nw in sub_clean.upper() for nw in noise_words):
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
    if not parsed_slides:
        return (
            f"No direct matching topics were found in the uploaded course slides for **{subject_name}** "
            f"matching *\"{query}\"*. Please check your query or verify the slide collection in the Vectors tab."
        )

    # Separate substantive slides (slides with explanation/bullets) from title divider slides
    content_slides = [s for s in parsed_slides if len(s["body"]) > 0]
    selected_slides = content_slides[:4] if content_slides else parsed_slides[:4]

    output_blocks = []
    
    q_lower = query.lower()
    is_solve_or_calc = any(k in q_lower for k in [
        "how to solve", "calculate", "solve", "step", "formula", "example",
        "procedure", "matrix", "compute"
    ])

    if is_solve_or_calc:
        output_blocks.append(f"### **Problem Solving & Methods from Course Slides**\n")
    else:
        output_blocks.append(f"### **Topics & Definitions from Course Slides**\n")

    for item in selected_slides:
        sim_pct = f"{round(item['similarity'] * 100, 1)}%"
        page_ref = f"Slide Page {item['page']}" if item['page'] != "N/A" else item['file']
        
        block_lines = []
        block_lines.append(f"#### **{item['title']}** `(Match: {sim_pct} · {page_ref})`")

        body_lines = item["body"]
        if not body_lines:
            block_lines.append(f"*(Title section in slide deck — refer to {page_ref} for visual diagrams)*\n")
        else:
            bullets = []
            narrative = []
            for line in body_lines:
                # Highlight mathematical formulas, transitions, or matrix equations
                if any(sym in line for sym in [
                    "PI =", "Pij", "P =", "Xn", "S = {", "lambda", "sum", "alpha",
                    "beta", "->", "x Pn", "det", "gcd", "bmod"
                ]):
                    narrative.append(f"> `{line}`")
                elif line.startswith("-") or line.startswith("•") or line.startswith("*") or (len(line) > 1 and line[0].isdigit() and line[1] in ".)"):
                    bullets.append(line)
                elif ":" in line and len(line.split(":")[0].split()) <= 4:
                    k, v = line.split(":", 1)
                    bullets.append(f"- **{k.strip()}:** {v.strip()}")
                else:
                    narrative.append(line)

            if narrative:
                block_lines.append("\n".join(narrative))
            if bullets:
                block_lines.append("\n".join(bullets))

        output_blocks.append("\n".join(block_lines))

    return "\n\n".join(output_blocks)

# ==============================================================================
# Main Tutor API Endpoint
# ==============================================================================

@router.post("/query", response_model=TutorQueryResponse)
def socratic_tutor_query(req: TutorQueryRequest):
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
            target_topic = execute_one(
                "SELECT topic_id, topic_name, difficulty_level, visual_type FROM TOPICS WHERE subject_id = %s ORDER BY topic_id ASC LIMIT 1",
                (req.subject_id,)
            )

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

    # 5. Extract topics and definitions from slide chunks
    parsed_slides = _extract_slide_topics_and_definitions(raw_chunks, subject_name=subject_name)

    top_sim = round(float(raw_chunks[0]["similarity"]), 4) if raw_chunks else None
    top_src = raw_chunks[0].get("metadata", {}).get("file_name", "Course Textbook") if raw_chunks else None
    grounding_excerpt = _clean_chunk_text(raw_chunks[0]["document"], subject_name=subject_name)[:300] if raw_chunks else None

    # 6. Check if external LLM key is configured (Groq / Gemini)
    groq_api_key = os.getenv("GROQ_API_KEY")
    if groq_api_key and raw_chunks:
        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key)
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

    # 7. Local Vector-Driven Slide Synthesis (Pure Dynamic RAG, Zero Hardcoded Crap, Zero "Think about this")
    answer = _synthesize_slide_rag_answer(
        query=req.query,
        parsed_slides=parsed_slides,
        subject_name=subject_name,
        clean_topic=clean_concept
    )

    # 8. Relational Session Persistence (CONVERSATION_LOGS)
    if req.session_id:
        try:
            execute_dml(
                "INSERT INTO CONVERSATION_LOGS (session_id, topic_id, role, stage, content) VALUES (%s, %s, 'user', 'explore', %s)",
                (req.session_id, req.topic_id, req.query)
            )
            execute_dml(
                "INSERT INTO CONVERSATION_LOGS (session_id, topic_id, role, stage, content) VALUES (%s, %s, 'assistant', 'explore', %s)",
                (req.session_id, req.topic_id, answer)
            )
        except Exception:
            pass

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
