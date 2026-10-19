from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Dict, Optional
from backend.vector_service import vector_service
from backend.pdf_indexer import pdf_indexer

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

class DeleteChunksRequest(BaseModel):
    subject_key: str
    chunk_ids: Optional[List[str]] = None
    where_filter: Optional[Dict] = None

# 1. READ (Semantic Similarity Search)
@router.post("/search")
def search_vectors(req: SearchRequest):
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

# 4. CREATE / INDEX (PDF Upload and Chunking)
@router.post("/upload")
async def upload_and_index_pdf(
    file: UploadFile = File(...),
    subject_id: int = Form(...),
    subject_key: str = Form(...),
    uploaded_by: int = Form(...)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_bytes = await file.read()
    try:
        pages, chunks = pdf_indexer.process_and_index_pdf(
            file_bytes=file_bytes,
            file_name=file.filename,
            subject_id=subject_id,
            subject_key=subject_key,
            uploaded_by=uploaded_by
        )
        return {
            "status": "success",
            "file_name": file.filename,
            "pages_parsed": pages,
            "chunks_indexed": chunks,
            "collection": f"chroma_{subject_key}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")

@router.get("/stats/{subject_key}")
def get_collection_stats(subject_key: str):
    return vector_service.get_stats(subject_key)

@router.get("/collections")
def list_collections():
    return vector_service.list_collections()
