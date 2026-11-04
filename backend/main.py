"""PostgreSQL-backed tutor service; frontend proxies /api to this local API."""
from contextlib import asynccontextmanager
import logging
import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from backend.database import execute_one
from backend.vector_service import vector_service
from backend.vector_transactions import recover_pending_writes
from backend.routers import auth, curriculum, vector_rud, tutor, sessions

@asynccontextmanager
async def lifespan(app):
    await run_in_threadpool(recover_pending_writes)
    yield

app=FastAPI(title='AI Tutor - PostgreSQL & ChromaDB',version='2.0.0',lifespan=lifespan)
for router in (auth.router,curriculum.router,vector_rud.router,tutor.router,sessions.router):
    app.include_router(router)

@app.exception_handler(psycopg.Error)
async def database_error(request:Request,exc:psycopg.Error):
    logging.getLogger(__name__).error('Database operation failed: %s',type(exc).__name__)
    return JSONResponse(status_code=503,content={'detail':'Database operation failed. Please retry or contact the administrator.'})

@app.get('/')
def root():
    return {'status':'online','service':'AI Tutor','database':'PostgreSQL','docs':'/docs'}

@app.get('/health')
@app.get('/api/health')
def health_check():
    try:
        db=execute_one('SELECT current_database() AS name,version() AS version')
        vector_service.client.heartbeat()
        return {'status':'healthy','database':'PostgreSQL','database_name':db['name'],'vectors':'ChromaDB'}
    except Exception:
        raise HTTPException(503,'PostgreSQL or ChromaDB is unavailable.')
