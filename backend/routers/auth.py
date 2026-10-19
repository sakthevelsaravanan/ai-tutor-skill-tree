from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from backend.database import execute_one, execute_query

router = APIRouter(prefix="/api/auth", tags=["Authentication & RBAC"])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    user_id: int
    full_name: str
    email: str
    role: str

@router.post("/login", response_model=UserResponse)
def login(req: LoginRequest):
    user = execute_one(
        "SELECT user_id, full_name, email, role, password_hash FROM USERS WHERE email = %s",
        (req.email,)
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return UserResponse(
        user_id=user["user_id"],
        full_name=user["full_name"],
        email=user["email"],
        role=user["role"]
    )

@router.get("/users")
def get_all_users():
    return execute_query("SELECT user_id, full_name, email, role, created_at FROM USERS ORDER BY role, user_id")

@router.get("/roles")
def get_roles():
    return {
        "roles": ["student", "instructor"],
        "permissions": {
            "student": ["read_curriculum", "view_prerequisites", "run_quizzes", "view_mastery"],
            "instructor": ["read_curriculum", "create_subject", "upload_textbook", "vector_rud", "edit_topics"]
        }
    }
