import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.routers.tutor import (
    parse_hill_cipher_problem,
    solve_hill_cipher,
    _clean_concept_name,
    _clean_chunk_text,
    _is_substantive_chunk,
)

client = TestClient(app)

def get_test_subject_id() -> int:
    res = client.get("/api/curriculum/subjects")
    if res.status_code == 200 and len(res.json()) > 0:
        return res.json()[0]["subject_id"]
    return 10

# ==============================================================================
# 1. Hill Cipher Parser & Numerical Solver Tests
# ==============================================================================

def test_parse_hill_cipher_encryption():
    query = "Encrypt the plaintext 'CD' using Hill cipher with key matrix [[2, 3], [3, 4]]. Show step by step calculation."
    problem = parse_hill_cipher_problem(query)
    assert problem is not None
    assert problem["operation"] == "encrypt"
    assert problem["matrix"] == [[2, 3], [3, 4]]
    assert problem["n"] == 2
    assert problem["text"] == "CD"

def test_solve_hill_cipher_encryption_exact():
    # Plaintext CD: C=2, D=3
    # K = [[2, 3], [3, 4]]
    # Row 1: 2*2 + 3*3 = 4 + 9 = 13 (N)
    # Row 2: 3*2 + 4*3 = 6 + 12 = 18 (S)
    # Ciphertext should be NS
    problem = {
        "operation": "encrypt",
        "matrix": [[2, 3], [3, 4]],
        "n": 2,
        "text": "CD"
    }
    steps, socratic_q = solve_hill_cipher(problem)
    assert "Final Ciphertext" in steps
    assert "NS" in steps
    assert "modulo 26" in socratic_q

def test_solve_hill_cipher_odd_length_padding():
    # Plaintext 'ACT' with 2x2 matrix -> pads with 'X' to 'ACTX'
    problem = {
        "operation": "encrypt",
        "matrix": [[2, 3], [3, 4]],
        "n": 2,
        "text": "ACT"
    }
    steps, socratic_q = solve_hill_cipher(problem)
    assert "ACT" in steps
    assert "Final Ciphertext" in steps

def test_solve_hill_cipher_decryption_exact():
    # Ciphertext NS with key [[2, 3], [3, 4]]
    # Det = (2*4 - 3*3) = -1 = 25 mod 26
    # gcd(25, 26) = 1, inverse of 25 mod 26 is 25 (since 25*25 = 625 = 24*26 + 1)
    # Decrypting NS should yield CD
    problem = {
        "operation": "decrypt",
        "matrix": [[2, 3], [3, 4]],
        "n": 2,
        "text": "NS"
    }
    steps, socratic_q = solve_hill_cipher(problem)
    assert "Decrypted Plaintext" in steps
    assert "CD" in steps
    assert "gcd" in socratic_q

def test_solve_hill_cipher_non_invertible_matrix():
    # Determinant mod 26 is not coprime to 26 (e.g. det = 2 or det = 0)
    # Matrix [[2, 4], [2, 4]] -> det = 0
    problem = {
        "operation": "decrypt",
        "matrix": [[2, 4], [2, 4]],
        "n": 2,
        "text": "NS"
    }
    steps, socratic_q = solve_hill_cipher(problem)
    assert "no modular inverse modulo 26" in steps
    assert "cannot be used for unique decryption" in steps

def test_parse_hill_cipher_non_cipher_query():
    query = "What is an AVL tree and how do single and double rotations work?"
    problem = parse_hill_cipher_problem(query)
    assert problem is None

# ==============================================================================
# 2. Text Normalization & Cleaning Tests
# ==============================================================================

def test_clean_concept_name():
    assert _clean_concept_name("1001 Solar Power") == "Solar Power"
    assert _clean_concept_name("DSA: Fundamental Concepts & Architecture") == "Dsa"
    assert _clean_concept_name("distributed_systems") == "Distributed Systems"
    assert _clean_concept_name(None) == "STEM Curriculum"

def test_clean_chunk_text():
    raw = (
        "PES UNIVERSITY\n"
        "EMERGENCY EXIT INSTRUCTIONS\n"
        "PAGE 12\n"
        "Hill cipher is a polygraphic substitution cipher.\n"
        "THANK YOU FOR ATTENDING"
    )
    cleaned = _clean_chunk_text(raw)
    assert "PES UNIVERSITY" not in cleaned
    assert "EMERGENCY EXIT" not in cleaned
    assert "THANK YOU" not in cleaned
    assert "Hill cipher is a polygraphic substitution cipher." in cleaned

def test_is_substantive_chunk():
    short_chunk = "Page 1 - Overview"
    substantive_chunk = "The Hill cipher operates on streams of data divided into multi-letter blocks using modular matrix arithmetic."
    assert not _is_substantive_chunk(short_chunk)
    assert _is_substantive_chunk(substantive_chunk)

# ==============================================================================
# 3. Socratic Tutor API Endpoint & Edge Cases
# ==============================================================================

def test_tutor_query_valid_subject():
    sid = get_test_subject_id()
    res = client.post("/api/tutor/query", json={
        "subject_id": sid,
        "query": "How does binary search achieve O(log n) time complexity?",
        "include_prereqs": True
    })
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert len(data["answer"]) > 20
    assert "reflection_question" in data

def test_tutor_query_hill_cipher_integration():
    sid = get_test_subject_id()
    res = client.post("/api/tutor/query", json={
        "subject_id": sid,
        "query": "Calculate the encryption of plaintext 'CD' using Hill cipher with key matrix [[2, 3], [3, 4]] step by step.",
        "include_prereqs": False
    })
    assert res.status_code == 200
    data = res.json()
    assert "NS" in data["answer"]
    assert "Step 1" in data["answer"]
    assert "pmatrix" in data["answer"]

def test_tutor_query_missing_subject_404():
    res = client.post("/api/tutor/query", json={
        "subject_id": 999999,
        "query": "Explain quantum superposition."
    })
    assert res.status_code == 404
    assert "Subject not found" in res.json()["detail"]

def test_tutor_query_invalid_topic_id_graceful_fallback():
    # Topic 88888 does not exist in subject -> falls back gracefully
    sid = get_test_subject_id()
    res = client.post("/api/tutor/query", json={
        "subject_id": sid,
        "topic_id": 88888,
        "query": "What are the core properties of a prime mover?"
    })
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data

def test_tutor_query_empty_query_string():
    sid = get_test_subject_id()
    res = client.post("/api/tutor/query", json={
        "subject_id": sid,
        "query": "   "
    })
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
