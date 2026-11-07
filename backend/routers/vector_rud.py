from typing import Optional, Dict, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from pydantic import BaseModel, Field
import hashlib
import re
from backend.database import execute_one, execute_query
from backend.security import current_user, require_admin, require_instructor
from backend.vector_service import vector_service
from backend.vector_transactions import vector_transaction
from backend.pdf_indexer import pdf_indexer

router=APIRouter(prefix='/api/vector',tags=['Textbook vectors'],dependencies=[Depends(current_user)])

class SearchRequest(BaseModel):
    subject_key:str
    query:str=Field(min_length=1,max_length=4000)
    top_k:int=Field(4,ge=1,le=50)
    where_filter:Optional[Dict]=None
class AddChunkRequest(BaseModel):
    subject_key:str
    chunk_id:str=Field(min_length=1,max_length=200)
    text:str=Field(min_length=1,max_length=20000)
    metadata:Optional[Dict]=None
class UpdateChunkRequest(BaseModel):
    subject_key:str
    chunk_id:str
    new_text:str=Field(min_length=1,max_length=20000)
    new_metadata:Optional[Dict]=None
class DeleteChunksRequest(BaseModel):
    subject_key:str
    chunk_ids:List[str]=Field(min_length=1,max_length=1000)
class ClearCollectionRequest(BaseModel):
    subject_key:str
class ClearAllVectorsRequest(BaseModel):
    confirm:bool=False

def subject_for(key):
    subject=execute_one('SELECT * FROM subjects WHERE subject_key=%s',(key,))
    if not subject: raise HTTPException(404,'Course not found.')
    return subject

def metadata_for(subject,metadata):
    meta=dict(metadata or {})
    topic_id=meta.get('topic_id')
    if topic_id is not None:
        topic=execute_one('SELECT topic_id FROM topics WHERE topic_id=%s AND subject_id=%s',(topic_id,subject['subject_id']))
        if not topic: raise HTTPException(400,'Chunk topic must belong to its course.')
        meta['topic_id']=int(topic_id)
        meta['concept_id']=int(topic_id)
    meta.update(subject=subject['subject_key'],subject_id=subject['subject_id'])
    if any(not isinstance(v,(str,int,float,bool)) for v in meta.values()):
        raise HTTPException(422,'Metadata values must be strings, numbers, or booleans.')
    return meta

@router.post('/chunk')
def add_vector_chunk(req:AddChunkRequest,user=Depends(require_admin)):
    subject=subject_for(req.subject_key)
    metadata=metadata_for(subject,req.metadata)
    with vector_transaction([req.subject_key]):
        col=vector_service.get_or_create_collection(req.subject_key)
        if col.get(ids=[req.chunk_id])['ids']: raise HTTPException(409,'Chunk ID already exists; use edit.')
        vector_service.add_chunks(req.subject_key,[req.text],[metadata],[req.chunk_id])
    return {'status':'success','chunk_id':req.chunk_id,'message':'Chunk added.'}

@router.get('/chunks/{subject_key}')
def list_subject_chunks(subject_key:str,limit:int=Query(200,ge=1,le=1000),offset:int=Query(0,ge=0),user=Depends(require_admin)):
    subject_for(subject_key)
    return vector_service.get_chunks(subject_key,limit,offset)

@router.post('/search')
def search_vectors(req:SearchRequest):
    subject_for(req.subject_key)
    results=vector_service.search(req.subject_key,req.query,req.top_k,req.where_filter)
    return {'subject':req.subject_key,'query':req.query,'total_results':len(results),'results':results}

@router.put('/update')
def update_vector_chunk(req:UpdateChunkRequest,user=Depends(require_admin)):
    subject=subject_for(req.subject_key)
    with vector_transaction([req.subject_key]):
        col=vector_service.get_or_create_collection(req.subject_key)
        old=col.get(ids=[req.chunk_id])
        if not old['ids']: raise HTTPException(404,'Chunk not found.')
        meta=metadata_for(subject,{**(old['metadatas'][0] or {}),**(req.new_metadata or {})})
        vector_service.update_chunk(req.subject_key,req.chunk_id,req.new_text,meta)
    return {'status':'success','message':'Chunk updated and re-embedded.'}

@router.delete('/delete')
def delete_vector_chunks(req:DeleteChunksRequest,user=Depends(require_admin)):
    subject_for(req.subject_key)
    with vector_transaction([req.subject_key]):
        count=vector_service.delete_chunks(req.subject_key,ids=req.chunk_ids)
    return {'status':'success','deleted_count':count,'message':'Chunks removed.'}

@router.post('/clear-collection')
def clear_collection_vectors(req:ClearCollectionRequest,user=Depends(require_admin)):
    subject_for(req.subject_key)
    with vector_transaction([req.subject_key]):
        count=vector_service.get_stats(req.subject_key)['total_chunks']
        col=vector_service.get_or_create_collection(req.subject_key)
        ids=col.get()['ids']
        if ids: col.delete(ids=ids)
    return {'status':'success','deleted_count':count,'message':'Collection cleared.'}

@router.post('/clear-all')
def clear_all_vectors(req:ClearAllVectorsRequest,user=Depends(require_admin)):
    if not req.confirm: raise HTTPException(400,'Explicit confirmation required.')
    with vector_transaction(None) as conn:
        keys=[c['name'].removeprefix('chroma_') for c in vector_service.list_collections()]
        count=sum(vector_service.get_stats(k)['total_chunks'] for k in keys)
        for key in keys: vector_service.client.delete_collection(f'chroma_{key}')
        conn.execute('DELETE FROM subjects')
    return {'status':'success','total_chunks_deleted':count,'collections_cleared':keys,'message':'Courses and vectors deleted.'}

@router.delete('/course/{subject_id}')
def delete_course_and_vectors(subject_id:int,user=Depends(require_admin)):
    subject=execute_one('SELECT * FROM subjects WHERE subject_id=%s',(subject_id,))
    if not subject: raise HTTPException(404,'Course not found.')
    key=subject['subject_key']
    with vector_transaction([key]) as conn:
        if f'chroma_{key}' in {c['name'] for c in vector_service.list_collections()}:
            vector_service.client.delete_collection(f'chroma_{key}')
        conn.execute('DELETE FROM subjects WHERE subject_id=%s',(subject_id,))
    return {'status':'success','deleted_subject_id':subject_id,'deleted_subject_name':subject['subject_name'],'message':'Course deleted.'}

@router.post('/upload')
async def upload_and_index_document(file:UploadFile=File(...),subject_id:Optional[int]=Form(None),
    subject_name:Optional[str]=Form(None),classification:Optional[str]=Form(None),topic_id:Optional[int]=Form(None),
    user=Depends(current_user)):
    name=file.filename or ''
    supported_exts = ('.pdf', '.ppt', '.pptx', '.txt', '.md')
    if not name.lower().endswith(supported_exts):
        raise HTTPException(400, 'Supported formats: PDF, PPT, PPTX, TXT, MD.')
    if subject_id is not None:
        subject=execute_one('SELECT * FROM subjects WHERE subject_id=%s',(subject_id,))
        if not subject: raise HTTPException(404,'Course not found.')
        key=subject['subject_key']; title=subject['subject_name']
    else:
        title=(subject_name or name.rsplit('.',1)[0]).strip()
        if not title or len(title)>100: raise HTTPException(422,'Course name must contain 1 to 100 characters.')
        existing=execute_one('SELECT * FROM subjects WHERE lower(subject_name)=lower(%s) AND (created_by=%s OR created_by IS NULL)',(title, user['user_id']))
        if existing:
            subject_id=existing['subject_id'];key=existing['subject_key']
        else:
            slug=re.sub(r'[^a-z0-9]+','_',title.lower()).strip('_')[:32] or 'course'
            key=slug+'_'+hashlib.sha256((title.casefold() + str(user['user_id'])).encode()).hexdigest()[:8]
    # Extraction/embedding is blocking work; keep it off the ASGI event loop.
    from starlette.concurrency import run_in_threadpool
    result=await run_in_threadpool(pdf_indexer.process_and_index_document,file.file,name,subject_id,key,
                                  user['user_id'],topic_id,title,classification)
    return {'status':'success',**result}

@router.get('/stats/{subject_key}')
def get_collection_stats(subject_key:str):
    subject_for(subject_key)
    return vector_service.get_stats(subject_key)

@router.get('/collections')
def list_collections(user=Depends(require_admin)):
    return vector_service.list_collections()
