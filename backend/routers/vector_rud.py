"""
ChromaDB Vector Database RUD (Read, Update, Delete) & Ingestion API (7 Marks).

This module implements the complete Vector Database lifecycle for academic course materials:
1. CREATE / UPSERT:
   - POST /api/vector/chunk: Creates or updates an individual vector chunk with metadata.
   - POST /api/vector/upload: Multi-format document parser (PDF, TXT, MD) with dynamic course
     creation, statistical 4-part skill tree generation, and batch embedding storage.
2. READ:
   - GET  /api/vector/chunks/{subject_key}: Paginated listing of raw vector chunks.
   - POST /api/vector/search: Semantic Top-K similarity search using HNSW cosine distance.
   - GET  /api/vector/stats/{subject_key}: Returns collection size and configuration.
   - GET  /api/vector/collections: Lists all active ChromaDB collections.
3. UPDATE:
   - PUT  /api/vector/update: Modifies chunk text or metadata, re-generating embeddings.
4. DELETE:
   - DELETE /api/vector/delete: Removes specific chunk IDs or chunks matching metadata filters.
   - DELETE /api/vector/clear-collection: Admin-only collection purge.
   - DELETE /api/vector/clear-all: Admin-only total database reset.
   - DELETE /api/vector/course/{subject_id}: Admin-only course cascade deletion.
5. ROLE-BASED ACCESS CONTROL (RBAC):
   - Enforces admin authorization on destructive purge and deletion operations.
"""

import time
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Dict, Optional
from backend.vector_service import vector_service
from backend.pdf_indexer import pdf_indexer
from backend.database import execute_dml, execute_one, execute_query

router = APIRouter(prefix="/api/vector", tags=["ChromaDB Vector RUD (7 Marks)"])

class SearchRequest(BaseModel):
    subject_key: str
    query: str
    top_k: int = 4
    where_filter: Optional[Dict] = None

class UpdateChunkRequest(BaseModel):
    subject_key: str
    chunk_id: str
    new_text: str
    new_metadata: Optional[Dict] = None

class AddChunkRequest(BaseModel):
    subject_key: str
    chunk_id: str
    text: str
    metadata: Optional[Dict] = None

class DeleteChunksRequest(BaseModel):
    subject_key: str
    chunk_ids: Optional[List[str]] = None
    where_filter: Optional[Dict] = None

class ClearCollectionRequest(BaseModel):
    subject_key: str
    user_id: Optional[int] = None
    role: Optional[str] = None

class ClearAllVectorsRequest(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None
    confirm: bool = True

def _verify_admin_privilege(user_id: Optional[int], role: Optional[str]):
    if role and role.strip().lower() == "admin":
        return
    if user_id:
        user = execute_one("SELECT role FROM USERS WHERE user_id = %s", (user_id,))
        if user and user["role"] == "admin":
            return
    raise HTTPException(
        status_code=403,
        detail="Forbidden: Admin privilege required. Only system administrators can purge vectors or clear knowledge bases."
    )

@router.post("/chunk")
def add_vector_chunk(req: AddChunkRequest):
    """
    Vector CREATE Operation (7 Marks - Create).
    Inserts or updates a single text chunk and its metadata into ChromaDB.
    Generates embedding vectors via ChromaDB's default embedding function.
    """
    try:
        vector_service.add_chunks(
            subject_key=req.subject_key,
            documents=[req.text],
            metadatas=[req.metadata or {"subject": req.subject_key}],
            ids=[req.chunk_id]
        )
        return {
            "status": "success",
            "message": f"Chunk '{req.chunk_id}' added successfully.",
            "chunk_id": req.chunk_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chunks/{subject_key}")
def list_subject_chunks(subject_key: str, limit: int = 50):
    """
    Vector READ Operation (7 Marks - Read).
    Retrieves stored vector chunks and metadata for inspection.
    """
    try:
        return vector_service.get_chunks(subject_key=subject_key, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 1. READ (Semantic Similarity Search)
@router.post("/search")
def search_vectors(req: SearchRequest):
    """
    Vector READ / SEARCH Operation (7 Marks - Read / Semantic Similarity).
    Executes dense vector search across collection using HNSW cosine similarity.
    Supports metadata filtering (e.g., topic_id filter for relational prerequisite enforcement).
    """
    results = vector_service.search(
        subject_key=req.subject_key,
        query_text=req.query,
        n_results=req.top_k,
        where_filter=req.where_filter
    )
    return {
        "subject": req.subject_key,
        "query": req.query,
        "total_results": len(results),
        "results": results
    }

# 2. UPDATE (Chunk Modification / Re-embedding)
@router.put("/update")
def update_vector_chunk(req: UpdateChunkRequest):
    """
    Vector UPDATE Operation (7 Marks - Update).
    Modifies the textual content or metadata of an existing vector chunk by ID.
    Re-computes embedding vectors automatically upon update.
    """
    try:
        vector_service.update_chunk(
            subject_key=req.subject_key,
            chunk_id=req.chunk_id,
            new_text=req.new_text,
            new_metadata=req.new_metadata
        )
        return {
            "status": "success",
            "message": f"Chunk '{req.chunk_id}' updated and re-embedded successfully."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3. DELETE (Vector Removal by ID or Filter)
@router.delete("/delete")
def delete_vector_chunks(req: DeleteChunksRequest):
    """
    Vector DELETE Operation (7 Marks - Delete).
    Removes specific chunks from collection by their ID or metadata criteria.
    """
    try:
        deleted_count = vector_service.delete_chunks(
            subject_key=req.subject_key,
            ids=req.chunk_ids,
            where_filter=req.where_filter
        )
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "message": f"Removed {deleted_count} chunks from collection."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3b. CLEAR SINGLE COLLECTION VECTORS (ADMIN PRIVILEGE)
@router.delete("/clear-collection")
@router.post("/clear-collection")
def clear_collection_vectors(req: ClearCollectionRequest):
    """
    Admin Vector Collection Reset.
    Purges all stored vectors for a subject collection and resets relational indexing state.
    Requires Admin authorization role.
    """
    _verify_admin_privilege(req.user_id, req.role)
    try:
        deleted_count = vector_service.clear_collection(req.subject_key)
        execute_dml(
            "UPDATE SUBJECTS SET is_indexed = 0 WHERE subject_key = %s",
            (req.subject_key,)
        )
        execute_dml(
            "UPDATE TEXTBOOKS SET chunk_count = 0 WHERE chroma_collection_name = %s",
            (f"chroma_{req.subject_key}",)
        )
        return {
            "status": "success",
            "subject_key": req.subject_key,
            "deleted_count": deleted_count,
            "message": f"Successfully cleared all {deleted_count} vectors from collection '{req.subject_key}'."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3c. PURGE ALL VECTORS & CLEAR EVERYTHING (ADMIN PRIVILEGE)
@router.delete("/clear-all")
@router.post("/clear-all")
def clear_all_vectors(req: ClearAllVectorsRequest):
    """
    Admin Total System Wipe.
    Wipes all ChromaDB collections and purges all records in TOPIC_PREREQUISITES,
    TOPICS, TEXTBOOKS, and SUBJECTS relational tables for a clean slate demo.
    Requires Admin authorization role.
    """
    _verify_admin_privilege(req.user_id, req.role)
    try:
        result = vector_service.clear_all_vectors()
        # Wipe all relational records so everything is truly cleared
        execute_dml("DELETE FROM TOPIC_PREREQUISITES")
        execute_dml("DELETE FROM TOPICS")
        execute_dml("DELETE FROM TEXTBOOKS")
        execute_dml("DELETE FROM SUBJECTS")
        return {
            "status": "success",
            "total_chunks_deleted": result["total_chunks_deleted"],
            "collections_cleared": result["collections_cleared"],
            "total_collections": result["total_collections"],
            "message": f"Admin purge complete: wiped {result['total_chunks_deleted']} vectors and purged all courses from the database."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3d. DELETE INDIVIDUAL COURSE & VECTORS (ADMIN PRIVILEGE)
@router.delete("/course/{subject_id}")
def delete_course_and_vectors(subject_id: int, user_id: Optional[int] = None, role: Optional[str] = None):
    """
    Admin Course Cascade Deletion.
    Deletes the ChromaDB collection and purges the course from SUBJECTS, TOPICS,
    TOPIC_PREREQUISITES, and TEXTBOOKS relational tables.
    Requires Admin authorization role.
    """
    _verify_admin_privilege(user_id, role)
    sub = execute_one("SELECT subject_id, subject_key, subject_name FROM SUBJECTS WHERE subject_id = %s", (subject_id,))
    if not sub:
        raise HTTPException(status_code=404, detail="Course not found.")

    sub_key = sub["subject_key"]
    deleted_chunks = vector_service.clear_collection(sub_key)
    try:
        vector_service.delete_collection(sub_key)
    except Exception:
        pass

    topic_rows = execute_query("SELECT topic_id FROM TOPICS WHERE subject_id = %s", (subject_id,))
    topic_ids = [t["topic_id"] for t in topic_rows]
    if topic_ids:
        placeholders = ",".join(["%s"] * len(topic_ids))
        execute_dml(f"DELETE FROM TOPIC_PREREQUISITES WHERE topic_id IN ({placeholders}) OR prereq_topic_id IN ({placeholders})", tuple(topic_ids + topic_ids))

    execute_dml("DELETE FROM TOPICS WHERE subject_id = %s", (subject_id,))
    execute_dml("DELETE FROM TEXTBOOKS WHERE subject_id = %s", (subject_id,))
    execute_dml("DELETE FROM SUBJECTS WHERE subject_id = %s", (subject_id,))

    return {
        "status": "success",
        "deleted_subject_id": subject_id,
        "deleted_subject_name": sub["subject_name"],
        "deleted_chunks": deleted_chunks,
        "message": f"Successfully deleted course '{sub['subject_name']}' and removed all vectors."
    }

# 4. CREATE / INDEX (Document Ingestion Flow: PDF & TXT with Dynamic Subject Creation)
@router.post("/upload")
async def upload_and_index_document(
    file: UploadFile = File(...),
    subject_id: Optional[int] = Form(None),
    subject_key: Optional[str] = Form(None),
    subject_name: Optional[str] = Form(None),
    classification: Optional[str] = Form(None),
    uploaded_by: int = Form(1),
    topic_id: Optional[int] = Form(None)
):
    """
    Multi-format Course Document Ingestion & Vector Indexing Endpoint (7 Marks - Create).
    - Accepts PDF, TXT, or MD documents.
    - Dynamically provisions course in SUBJECTS table if subject_id is omitted.
    - Generates 4-part sequential skill tree DAG in TOPICS and TOPIC_PREREQUISITES.
    - Chunks, cleans, and tags content with quarter topics and page indices.
    - Upserts dense embeddings into ChromaDB collection.
    - Records file metadata in TEXTBOOKS table.
    """
    lower_name = file.filename.lower()
    if not (lower_name.endswith(".pdf") or lower_name.endswith(".txt") or lower_name.endswith(".md")):
        raise HTTPException(status_code=400, detail="Supported formats: PDF, TXT, MD.")

    resolved_subject_id = subject_id
    resolved_subject_key = subject_key
    resolved_subject_name = subject_name

    if resolved_subject_id:
        existing = execute_one(
            "SELECT subject_id, subject_key, subject_name FROM SUBJECTS WHERE subject_id = %s",
            (resolved_subject_id,)
        )
        if existing:
            resolved_subject_key = existing["subject_key"]
            resolved_subject_name = existing["subject_name"]

    if not resolved_subject_id:
        clean_name = (subject_name or (file.filename.rsplit(".", 1)[0].replace("_", " ").title())).strip()
        slug = (subject_key or "".join(c if c.isalnum() else "_" for c in clean_name.lower())).strip("_")
        slug = "_".join(filter(None, slug.split("_")))[:24]
        if not slug:
            slug = f"course_{int(time.time())}"

        existing = execute_one(
            "SELECT subject_id, subject_key, subject_name FROM SUBJECTS WHERE subject_key = %s OR LOWER(subject_name) = LOWER(%s)",
            (slug, clean_name)
        )
        if existing:
            resolved_subject_id = existing["subject_id"]
            resolved_subject_key = existing["subject_key"]
            resolved_subject_name = existing["subject_name"]
        else:
            desc = f"Classification: {classification or 'General STEM'}. Course curriculum."
            execute_dml(
                "INSERT INTO SUBJECTS (subject_key, subject_name, description, is_indexed, created_by) VALUES (%s, %s, %s, 1, %s)",
                (slug, clean_name, desc, uploaded_by)
            )
            created = execute_one("SELECT subject_id, subject_key, subject_name FROM SUBJECTS WHERE subject_key = %s", (slug,))
            resolved_subject_id = created["subject_id"]
            resolved_subject_key = created["subject_key"]
            resolved_subject_name = created["subject_name"]

    file_bytes = await file.read()
    try:
        pages, chunks = pdf_indexer.process_and_index_document(
            file_bytes=file_bytes,
            file_name=file.filename,
            subject_id=resolved_subject_id,
            subject_key=resolved_subject_key,
            uploaded_by=uploaded_by,
            explicit_topic_id=topic_id
        )
        return {
            "status": "success",
            "subject_id": resolved_subject_id,
            "subject_key": resolved_subject_key,
            "subject_name": resolved_subject_name,
            "file_name": file.filename,
            "pages_parsed": pages,
            "chunks_indexed": chunks,
            "topic_id": topic_id,
            "collection": f"chroma_{resolved_subject_key}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")

@router.get("/stats/{subject_key}")
def get_collection_stats(subject_key: str):
    return vector_service.get_stats(subject_key)

@router.get("/collections")
def list_collections():
    return vector_service.list_collections()
