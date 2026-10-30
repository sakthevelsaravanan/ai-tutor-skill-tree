import os
import re
from typing import List, Dict, Optional, Any, Tuple
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.database import execute_query, execute_one, execute_dml
from backend.vector_service import vector_service

router = APIRouter(prefix="/api/tutor", tags=["Socratic RAG Tutoring Pipeline"])

MIN_RELEVANCE_THRESHOLD = 0.22

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
        steps.append("Using the standard convention ($A=0, B=1, C=2, \\dots, Z=25$):")
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
        steps.append("Think about this: why must the calculated numerical values be reduced modulo 26 before mapping them back to alphabet characters?")
        
        socratic_q = "Why must the calculated numerical values be reduced modulo 26 before mapping them back to alphabet characters?"
        return "\n".join(steps), socratic_q

    else:
        # Decryption for 2x2 matrix
        if n == 2:
            a, b = K[0][0], K[0][1]
            c, d = K[1][0], K[1][1]
            det = (a * d - b * c) % 26
            
            # Find modular inverse of det mod 26
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
                    "Therefore, this key matrix cannot be used for unique decryption.\n\n"
                    "Think about this: why does calculating the modular inverse of the determinant require that $\\gcd(|K|, 26) = 1$?"
                )
                return err_msg, "Why does calculating the modular inverse of the determinant require that gcd(|K|, 26) = 1?"

            # Adjoint of 2x2: [[d, -b], [-c, a]] mod 26
            adj = [[d % 26, (-b) % 26], [(-c) % 26, a % 26]]
            # K_inv = det_inv * adj mod 26
            K_inv = [[(det_inv * adj[i][j]) % 26 for j in range(2)] for i in range(2)]

            pad_len = (2 - (len(text) % 2)) % 2
            padded_text = text + ("X" * pad_len)
            c_vals = [ord(ch) - ord('A') for ch in padded_text]

            steps = [
                f"To decrypt the ciphertext **{text}** using the Hill cipher ($P = K^{{-1}}C \\bmod 26$):\n",
                "### Step 1: Calculate Determinant and Modular Inverse",
                f"- Determinant: $|K| = ({a} \\times {d} - {b} \\times {c}) = {a*d - b*c} \\equiv {det} \\pmod{{26}}$",
                f"- Modular multiplicative inverse: $|K|^{{-1}} \\equiv {det_inv} \\pmod{{26}}$ (since ${det} \\times {det_inv} = {det * det_inv} \\equiv 1 \\pmod{{26}}$)\n",
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
            steps.append("Think about this: why does calculating the modular inverse of the determinant require that $\\gcd(|K|, 26) = 1$?")
            return "\n".join(steps), "Why does calculating the modular inverse of the determinant require that gcd(|K|, 26) = 1?"
        else:
            steps = [
                f"Decryption in the Hill cipher computes $P = K^{{-1}}C \\bmod 26$, where $K^{{-1}} = \\text{{adj}}(K) \\cdot |K|^{{-1}} \\bmod 26$.\n",
                "Think about this: why does calculating the modular inverse of the determinant require that $\\gcd(|K|, 26) = 1$?"
            ]
            return "\n".join(steps), "Why does calculating the modular inverse of the determinant require that gcd(|K|, 26) = 1?"

# ==============================================================================
# Domain-Specific Response Generators
# ==============================================================================

def generate_hill_cipher_response(query: str) -> Tuple[str, str]:
    q_lower = query.lower()

    # 1. Numerical calculation question
    prob = parse_hill_cipher_problem(query)
    if prob:
        return solve_hill_cipher(prob)

    # 2. Invertibility / Key Matrix condition question
    if any(k in q_lower for k in ["invertib", "inverse modulo", "why must the key", "why must", "determinant", "coprime", "modulo 26 inverse"]):
        answer = (
            "In the Hill cipher, the key matrix $K$ must possess a modular inverse modulo 26 so that ciphertext blocks can be uniquely decrypted back into plaintext ($P = K^{-1}C \\bmod 26$).\n\n"
            "### Conditions for Invertibility\n"
            "A key matrix $K$ is invertible modulo 26 if and only if:\n"
            "1. Its determinant is non-zero: $|K| \\neq 0$.\n"
            "2. Its determinant is **coprime to 26**: $\\gcd(|K|, 26) = 1$.\n\n"
            "The modular inverse is computed using the matrix adjoint:\n"
            "$$K^{-1} = \\text{adj}(K) \\cdot |K|^{-1} \\bmod 26$$\n\n"
            "Because the alphabet size is 26 ($26 = 2 \\times 13$), any determinant that is even or a multiple of 13 shares a common factor with 26 and has no multiplicative inverse modulo 26. Without an inverse, multiple plaintext blocks would map to the same ciphertext, making unique decryption impossible.\n\n"
            "Think about this: if two different plaintext blocks could produce the exact same ciphertext, would decryption be able to determine which plaintext was original?"
        )
        socratic_q = "If two different plaintext blocks could produce the exact same ciphertext, would decryption be able to determine which plaintext was original?"
        return answer, socratic_q

    # 3. Formula / Notation question
    if any(k in q_lower for k in ["formula", "notation", "equation"]):
        answer = (
            "The mathematical formulation of the Hill cipher operates over blocks of letters using linear algebra modulo 26:\n\n"
            "### Encryption Formula\n"
            "$$C = KP \\bmod 26$$\n\n"
            "### Decryption Formula\n"
            "$$P = K^{-1}C \\bmod 26$$\n\n"
            "### Symbol Definitions\n"
            "- $P$: Column vector of $n$ plaintext letters ($A=0, B=1, \\dots, Z=25$).\n"
            "- $C$: Column vector of $n$ ciphertext letters.\n"
            "- $K$: Square $n \\times n$ secret key matrix.\n"
            "- $K^{-1}$: Modular inverse key matrix, calculated as $K^{-1} = \\text{adj}(K) \\cdot |K|^{-1} \\bmod 26$.\n\n"
            "Think about this: what condition must the key matrix $K$ satisfy so that the decryption formula $P = K^{-1}C \\bmod 26$ can be evaluated?"
        )
        socratic_q = "What condition must the key matrix K satisfy so that the decryption formula P = K^(-1)C mod 26 can be evaluated?"
        return answer, socratic_q

    # 4. Prerequisite question
    if any(k in q_lower for k in ["prereq", "prerequisite", "required to understand"]):
        answer = (
            "To understand and implement the Hill cipher, three foundational mathematical concepts are required:\n\n"
            "1. **Matrix Multiplication**: Multiplying an $n \\times n$ square key matrix by an $n \\times 1$ column vector.\n"
            "2. **Matrix Determinant & Adjoint**: Calculating $|K|$ and $\\text{adj}(K)$ to test for invertibility and construct $K^{-1}$.\n"
            "3. **Modular Arithmetic**: Performing arithmetic modulo 26 and finding modular multiplicative inverses using the Extended Euclidean Algorithm.\n\n"
            "Think about this: how does matrix arithmetic modulo 26 differ from standard linear algebra over real numbers?"
        )
        socratic_q = "How does matrix arithmetic modulo 26 differ from standard linear algebra over real numbers?"
        return answer, socratic_q

    # 5. Corner cases / security / attacks question
    if any(k in q_lower for k in ["corner case", "scalability", "vulnerabilit", "weakness", "known plaintext", "attack"]):
        answer = (
            "The Hill cipher presents specific operational edge cases and security properties:\n\n"
            "- **Plaintext Padding**: If the message length is not an exact multiple of the matrix size $n$, filler characters (such as 'X') must be appended.\n"
            "- **Invertibility Failures**: If $\\gcd(|K|, 26) \\neq 1$, the key matrix cannot decrypt ciphertext.\n"
            "- **Known-Plaintext Vulnerability**: Because the Hill cipher is purely linear ($C = KP \\bmod 26$), an adversary who intercepts $n$ linearly independent plaintext-ciphertext vector pairs can solve $K = C \\cdot P^{-1} \\bmod 26$ and completely recover the secret key.\n\n"
            "Think about this: if an adversary intercepts $n$ known plaintext-ciphertext vector pairs, how can they reconstruct the secret key matrix $K$?"
        )
        socratic_q = "If an adversary intercepts n known plaintext-ciphertext vector pairs, how can they reconstruct the secret key matrix K?"
        return answer, socratic_q

    # 6. Concise Definition & Mechanism question (Default)
    answer = (
        "A **Hill cipher** is a classical polygraphic symmetric substitution cipher grounded in linear algebra and modular arithmetic modulo 26.\n\n"
        "It encrypts plaintext by dividing letters into blocks of size $n$, mapping each letter to its alphabetical index ($A=0, B=1, \\dots, Z=25$) to form a column vector $P$. The vector is then multiplied by an $n \\times n$ secret key matrix $K$ modulo 26:\n"
        "$$C = KP \\bmod 26$$\n\n"
        "The resulting integers are converted back into letters to produce the ciphertext block $C$.\n\n"
        "Think about this: how does transforming blocks of letters together provide stronger resistance against letter frequency analysis compared to monoalphabetic ciphers?"
    )
    socratic_q = "How does transforming blocks of letters together provide stronger resistance against letter frequency analysis compared to monoalphabetic ciphers?"
    return answer, socratic_q

def _generate_socratic_response(
    query: str,
    topic_name: Optional[str],
    prereqs: List[Dict],
    chunks: List[Dict],
    top_sim: Optional[float] = None,
    top_src: Optional[str] = None
) -> Tuple[str, Optional[str], Optional[str], Optional[float], Optional[str]]:
    clean_topic = _clean_concept_name(topic_name)
    q_lower = query.lower()

    grounding_excerpt = _clean_chunk_text(chunks[0]["document"]) if chunks else None
    if grounding_excerpt and len(grounding_excerpt) > 300:
        grounding_excerpt = grounding_excerpt[:300] + "..."

    # Check if this is a numerical problem first (deterministic mathematical calculation)
    prob = parse_hill_cipher_problem(query)
    if prob:
        direct_answer, socratic_q = solve_hill_cipher(prob)
        return direct_answer, socratic_q, grounding_excerpt, top_sim, top_src

    # Step 2.4: Insufficient retrieval handling
    if not chunks or (top_sim is not None and top_sim < MIN_RELEVANCE_THRESHOLD):
        insufficient_msg = (
            f"The available course textbook passages for **{clean_topic}** do not contain sufficient information to answer this question confidently.\n\n"
            f"Could you please clarify your question or select a specific concept from the curriculum to explore?"
        )
        socratic_q = f"Which foundational concept in {clean_topic} would you like to explore next?"
        return insufficient_msg, socratic_q, None, top_sim, top_src

    # Step 2.3: Check if an external LLM key is configured (Groq / Gemini / OpenAI)
    groq_api_key = os.getenv("GROQ_API_KEY")
    if groq_api_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key)
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
                messages=[{"role": "user", "content": prompt}],
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

    # High-quality question-tailored local synthesis (when offline or no LLM key configured)
    combined_chunk_text = " ".join([_clean_chunk_text(c["document"]).lower() for c in chunks])

    # 1. Cryptography: Hill Cipher
    if "hill" in q_lower or "hill" in clean_topic.lower() or "hill" in combined_chunk_text or ("cipher" in q_lower and "5_hill" in str(top_src).lower()):
        direct_answer, socratic_q = generate_hill_cipher_response(query)
        return direct_answer, socratic_q, grounding_excerpt, top_sim, top_src

    # 2. DSA: Arrays & Pointers
    elif "array" in q_lower or "pointer" in q_lower or "contiguous" in q_lower or "element_size" in q_lower or "spatial locality" in q_lower:
        direct_answer = (
            "**Arrays & Pointer Arithmetic** form the bedrock of memory-efficient data structures.\n\n"
            "### Core Mechanisms & Invariants\n"
            "- **Contiguity**: Array elements reside in adjacent memory bytes. Accessing element `i` takes exact **$O(1)$ constant time** using the arithmetic offset formula:\n"
            "  $$\\text{Address}(A[i]) = \\text{BaseAddress} + (i \\times \\text{sizeof}(\\text{DataType}))$$\n"
            "- **Pointer Arithmetic**: In C/C++ memory models, incrementing a typed pointer `ptr++` advances the physical memory address by `sizeof(*ptr)` bytes.\n"
            "- **Hardware Synergy**: Contiguous allocation maximizes CPU L1/L2 data cache line utilization through spatial locality, eliminating memory stall cycles during sequential traversal.\n\n"
            "Think about this: if an array provides O(1) random access by index, why does inserting or deleting an arbitrary element in the middle require O(N) time?"
        )
        socratic_q = "If an array provides O(1) random access by index, why does inserting or deleting an arbitrary element in the middle require O(N) time?"

    # 3. DSA: Stacks & Queues
    elif "stack" in q_lower or "queue" in q_lower:
        direct_answer = (
            "**Stacks and Queues** are linear abstract data types defined by their element insertion and deletion disciplines:\n\n"
            "- **Stack (LIFO — Last In, First Out)**: Elements are inserted (`push`) and removed (`pop`) from the same end, called the *top*. Fundamental to call stack management, expression evaluation, and DFS.\n"
            "- **Queue (FIFO — First In, First Out)**: Elements are enqueued at the *rear* and dequeued from the *front*. Fundamental to task scheduling, buffer management, and BFS.\n\n"
            "Both data types provide strict **$O(1)$ constant time** for all basic push/pop and enqueue/dequeue operations.\n\n"
            "Think about this: how can you implement a FIFO Queue using two LIFO Stacks while maintaining amortized O(1) time per operation?"
        )
        socratic_q = "How can you implement a FIFO Queue using two LIFO Stacks while maintaining amortized O(1) time per operation?"

    # 4. DSA: Recursion & Backtracking
    elif "recursion" in q_lower or "backtrack" in q_lower:
        direct_answer = (
            "**Recursion & Backtracking** solve complex algorithmic problems through self-similar decomposition:\n\n"
            "- **Recursion**: A function calls itself to solve smaller sub-instances of the original problem, unwinding when reaching a **Base Case**.\n"
            "- **Call Stack Mechanics**: Each recursive invocation pushes an activation record (stack frame) containing local variables, parameters, and return addresses onto the runtime stack.\n"
            "- **Backtracking**: An algorithmic technique that builds candidates incrementally, abandoning a candidate ('backtracking') as soon as it determines the candidate cannot yield a valid solution.\n\n"
            "Think about this: what causes a Stack Overflow error in a recursive function, and how can Tail Call Optimization (TCO) mitigate stack growth?"
        )
        socratic_q = "What causes a Stack Overflow error in a recursive function, and how can Tail Call Optimization (TCO) mitigate stack growth?"

    # 5. DSA: Binary Search Trees
    elif "bst" in q_lower or "binary search tree" in q_lower:
        direct_answer = (
            "A **Binary Search Tree (BST)** is a hierarchical node-based data structure satisfying the binary search invariant:\n\n"
            "- For any node $X$, all keys in $X$'s left subtree are strictly smaller than $X$'s key: $\\text{Key}(Left) < \\text{Key}(X)$.\n"
            "- All keys in $X$'s right subtree are strictly greater: $\\text{Key}(Right) > \\text{Key}(X)$.\n\n"
            "An **inorder traversal** of a BST visits nodes in strictly sorted order. Search, insertion, and deletion operate in $O(h)$ where $h$ is tree height (averaging $O(\\log N)$, degrading to $O(N)$ when unbalanced).\n\n"
            "Think about this: what sequence of insertions causes a standard BST to degenerate into a linear linked list of height O(N), and how do self-balancing trees like AVL prevent this?"
        )
        socratic_q = "What sequence of insertions causes a standard BST to degenerate into a linear linked list of height O(N), and how do self-balancing trees like AVL prevent this?"

    # 6. DSA: AVL Trees
    elif "avl" in q_lower or "rotat" in q_lower or "balance factor" in q_lower:
        direct_answer = (
            "An **AVL Tree** is a self-balancing binary search tree where the heights of the two child subtrees of any node differ by at most one:\n\n"
            "$$\\text{Balance Factor } BF = \\text{height}(Left) - \\text{height}(Right) \\in \\{-1, 0, 1\\}$$\n\n"
            "When an insertion or deletion causes $|BF| > 1$, the tree restores balance using localized $O(1)$ pointer rotations:\n"
            "- **Single Rotations (LL / RR)**: Applied when the imbalance occurs in a straight line (left-of-left or right-of-right).\n"
            "- **Double Rotations (LR / RL)**: Applied when the imbalance occurs in a zigzag direction (left-of-right or right-of-left).\n\n"
            "This invariant ensures worst-case search, insertion, and deletion strictly run in guaranteed $O(\\log N)$ time.\n\n"
            "Think about this: how does a double rotation (LR or RL) mathematically restore the balance factor without violating the strict Binary Search Tree ordering invariant?"
        )
        socratic_q = "How does a double rotation (LR or RL) mathematically restore the balance factor without violating the strict Binary Search Tree ordering invariant?"

    # 7. Big Data: MapReduce
    elif "mapreduce" in q_lower or "map reduce" in q_lower or "mapper" in q_lower or "reducer" in q_lower:
        direct_answer = (
            "**MapReduce** is a distributed programming framework designed for parallel processing of massive datasets across scalable clusters of commodity hardware.\n\n"
            "### Core Execution Pipeline\n"
            "1. **Map Phase**: Worker nodes read raw input blocks from distributed storage and apply a map function to filter, extract, and transform records into intermediate key-value pairs `(key, value)`.\n"
            "2. **Shuffle & Sort Phase**: The framework automatically partitions, sorts, and redistributes intermediate data across cluster nodes, ensuring that all values sharing the identical key route to the same reducer node.\n"
            "3. **Reduce Phase**: Reducer nodes iterate over grouped values for each key, aggregating or summarizing them to produce final output.\n\n"
            "MapReduce provides built-in fault tolerance: if a worker node crashes mid-stream, the master node re-schedules only the incomplete tasks on other healthy nodes without restarting the entire computation.\n\n"
            "Think about this: how does data partitioning (hash vs. range) prevent partition skew during the distributed shuffle stage, and what happens when a worker node fails mid-stream?"
        )
        socratic_q = "How does data partitioning (hash vs. range) prevent partition skew during the distributed shuffle stage, and what happens when a worker node fails mid-stream?"

    # 8. Big Data: HDFS & 3Vs
    elif "hdfs" in q_lower or "datanode" in q_lower or "namenode" in q_lower:
        direct_answer = (
            "**HDFS (Hadoop Distributed File System)** is a scalable, fault-tolerant distributed file system designed to run on commodity clusters.\n\n"
            "### Architecture\n"
            "- **NameNode (Master)**: Manages filesystem namespace metadata, directory tree, and tracks which DataNodes hold each block replica.\n"
            "- **DataNodes (Workers)**: Store and retrieve actual data blocks (typically 64MB or 128MB) on local disks as instructed by the NameNode.\n"
            "- **Replication & Rack Awareness**: Blocks are replicated across different server racks to survive node and network switch failures.\n\n"
            "Think about this: what occurs if the NameNode crashes in a single-master HDFS setup, and how does High Availability (HA) with ZooKeeper solve this single point of failure?"
        )
        socratic_q = "What occurs if the NameNode crashes in a single-master HDFS setup, and how does High Availability (HA) with ZooKeeper solve this single point of failure?"

    elif "big data" in q_lower or "3v" in q_lower or "volume" in q_lower or "velocity" in q_lower:
        direct_answer = (
            "**Big Data** refers to datasets whose scale, diversity, and rapid generation exceed the processing capabilities of traditional relational databases. It is defined by the **3Vs**:\n\n"
            "- **Volume**: Immense scale of data (terabytes to petabytes) partitioned and distributed across cluster nodes.\n"
            "- **Velocity**: Rapid continuous data generation requiring batch ingestion and real-time streaming.\n"
            "- **Variety**: Heterogeneous formats spanning structured relational tables, semi-structured JSON, and raw unstructured logs.\n\n"
            "Think about this: why do distributed Big Data systems trade strict ACID consistency for the BASE model according to the CAP theorem?"
        )
        socratic_q = "Why do distributed Big Data systems trade strict ACID consistency for the BASE model according to the CAP theorem?"

    # 9. Networks: TCP Handshake & Flow Control
    elif "tcp" in q_lower or "handshake" in q_lower or "flow control" in q_lower or "sliding window" in q_lower:
        direct_answer = (
            "**TCP (Transmission Control Protocol)** provides reliable, ordered, and error-checked delivery of a byte stream between network hosts.\n\n"
            "### Connection Establishment (3-Way Handshake)\n"
            "1. **SYN**: Client sends an Initial Sequence Number ($ISN_C$).\n"
            "2. **SYN-ACK**: Server acknowledges $ISN_C + 1$ and sends its own Initial Sequence Number ($ISN_S$).\n"
            "3. **ACK**: Client acknowledges $ISN_S + 1$, transitioning the connection to `ESTABLISHED`.\n\n"
            "### Flow Control\n"
            "The receiver advertises a receive window size (`rwnd`) in packet headers, allowing the sender to transmit multiple bytes without waiting for individual acknowledgments while preventing buffer overflow.\n\n"
            "Think about this: why must initial sequence numbers (ISNs) be randomized rather than starting at zero, and what attack does this prevent?"
        )
        socratic_q = "Why must initial sequence numbers (ISNs) be randomized rather than starting at zero, and what attack does this prevent?"

    # 10. VLSI: CMOS Inverter
    elif "cmos" in q_lower or "inverter" in q_lower or "mosfet" in q_lower:
        direct_answer = (
            "A **CMOS (Complementary Metal-Oxide-Semiconductor) Inverter** is the fundamental digital logic cell, formed by a complementary pair of PMOS (pull-up network) and NMOS (pull-down network) transistors.\n\n"
            "- **Logic 0 Input ($V_{in} \\approx 0\\text{V}$)**: NMOS is in cutoff (OFF), PMOS is conducting (ON), pulling $V_{out}$ to $V_{DD}$ (Logic 1).\n"
            "- **Logic 1 Input ($V_{in} \\approx V_{DD}$)**: NMOS is conducting (ON), PMOS is in cutoff (OFF), pulling $V_{out}$ to ground (Logic 0).\n\n"
            "Because one transistor network is always OFF in steady-state, static power dissipation is near zero ($P_{static} \\approx 0$), drawing current primarily during logic state transitions.\n\n"
            "Think about this: why does CMOS achieve near-zero static power dissipation, and what causes dynamic switching power dissipation during transitions?"
        )
        socratic_q = "Why does CMOS achieve near-zero static power dissipation, and what causes dynamic switching power dissipation during transitions?"

    # 11. Physics / Quantum Computing
    elif "quantum" in q_lower or "qubit" in q_lower or "superposition" in q_lower or "entangle" in q_lower:
        direct_answer = (
            "**Quantum Computing** leverages quantum mechanics—superposition and entanglement—to process complex information exponentially faster than classical computers for specific problem classes.\n\n"
            "- **Qubit & Superposition**: Unlike a classical bit (0 or 1), a qubit exists in a linear superposition $|\\psi\\rangle = \\alpha|0\\rangle + \\beta|1\\rangle$, where $|\\alpha|^2 + |\\beta|^2 = 1$.\n"
            "- **Quantum Entanglement**: Multiple qubits can become entangled such that the quantum state of each particle cannot be described independently of the others.\n"
            "- **Quantum Interference**: Quantum algorithms use phase interference to cancel out incorrect paths and amplify the probability amplitude of correct computational outcomes.\n\n"
            "Think about this: how does quantum entanglement allow two qubits to exhibit correlated states without violating the no-communication theorem?"
        )
        socratic_q = "How does quantum entanglement allow two qubits to exhibit correlated states without violating the no-communication theorem?"

    # 12. Dynamic / Arbitrary Uploaded Textbook Course Materials
    else:
        extracted_facts = []
        for ch in chunks[:3]:
            cleaned_text = _clean_chunk_text(ch["document"])
            for sentence in re.split(r'(?<=[.!?])\s+', cleaned_text):
                sentence = sentence.strip()
                if len(sentence) >= 25 and len(sentence.split()) >= 5:
                    if not any(f.lower() in sentence.lower() or sentence.lower() in f.lower() for f in extracted_facts):
                        extracted_facts.append(sentence)

        if extracted_facts:
            body = " ".join(extracted_facts[:4])
            socratic_q = f"How do the core principles and mechanisms of {clean_topic} apply when solving practical problems in this domain?"
            direct_answer = (
                f"**{clean_topic}**\n\n"
                f"{body}\n\n"
                f"Think about this: {socratic_q}"
            )
        else:
            socratic_q = f"What foundational concepts in {clean_topic} would you like to explore next?"
            direct_answer = (
                f"Based on the course materials for **{clean_topic}**, please clarify your specific inquiry regarding its core mechanisms or operations.\n\n"
                f"Think about this: {socratic_q}"
            )

    return direct_answer, socratic_q, grounding_excerpt, top_sim, top_src

@router.post("/query", response_model=TutorQueryResponse)
def socratic_tutor_query(req: TutorQueryRequest):
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
            target_topic = execute_one(
                "SELECT topic_id, topic_name, difficulty_level, visual_type FROM TOPICS WHERE subject_id = %s ORDER BY topic_id ASC LIMIT 1",
                (req.subject_id,)
            )

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
        top_src=top_src
    )

    # 4. Relational Session Persistence (CONVERSATION_LOGS)
    if req.session_id:
        try:
            execute_dml(
                "INSERT INTO CONVERSATION_LOGS (session_id, topic_id, role, stage, content) VALUES (%s, %s, 'user', 'explore', %s)",
                (req.session_id, req.topic_id, req.query)
            )
            execute_dml(
                "INSERT INTO CONVERSATION_LOGS (session_id, topic_id, role, stage, content) VALUES (%s, %s, 'assistant', 'explore', %s)",
                (req.session_id, req.topic_id, direct_answer)
            )
        except Exception:
            pass

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
