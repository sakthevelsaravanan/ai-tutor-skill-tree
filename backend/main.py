import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import auth, curriculum, vector_rud, sessions

app = FastAPI(
    title="AI Tutor & Skill Tree API",
    description="Backend API combining MySQL 8.0+ relational core with ChromaDB vector store.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(curriculum.router)
app.include_router(vector_rud.router)
app.include_router(sessions.router)

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "AI Tutor & Skill Tree Backend",
        "endpoints": {
            "docs": "/docs",
            "auth": "/api/auth",
            "curriculum": "/api/curriculum",
            "vector_rud": "/api/vector",
            "sessions": "/api/sessions"
        }
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
