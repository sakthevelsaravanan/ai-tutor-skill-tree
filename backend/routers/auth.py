from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from backend.config import settings
from backend.database import execute_one, execute_query
from backend.security import current_user, require_admin, verify_password, create_token

router = APIRouter(prefix='/api/auth', tags=['Authentication'])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

@router.post('/login')
def login(req: LoginRequest, response: Response):
    user = execute_one('SELECT user_id, full_name, email, role, password_hash FROM USERS WHERE LOWER(email) = LOWER(%s)', (req.email,))
    if not user or not verify_password(req.password, user['password_hash']):
        raise HTTPException(401, 'Invalid email or password.')
    response.set_cookie('tutor_session', create_token(user['user_id']), httponly=True,
                        secure=settings.COOKIE_SECURE, samesite='strict', max_age=28800, path='/')
    return {k: v for k, v in user.items() if k != 'password_hash'}

@router.get('/me')
def me(user=Depends(current_user)):
    return user

@router.post('/logout')
def logout(response: Response):
    response.delete_cookie('tutor_session', path='/')
    return {'status': 'signed_out'}

@router.get('/users')
def users(user=Depends(require_admin)):
    return execute_query('SELECT user_id, full_name, email, role, created_at FROM USERS ORDER BY user_id')

@router.get('/roles')
def roles(user=Depends(current_user)):
    return {'roles': ['student', 'instructor', 'admin'], 'permissions': {
        'student': ['read_curriculum', 'socratic_chat', 'record_self_assessment', 'view_own_mastery'],
        'instructor': ['read_curriculum', 'upload_textbook', 'socratic_chat'],
        'admin': ['read_curriculum', 'upload_textbook', 'vector_rud', 'manage_users']}}
