from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from backend.config import settings
from backend.database import execute_one

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except (ValueError, TypeError):
        return False

def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(user_id), 'iat': now, 'exp': now + timedelta(hours=8)},
                      settings.JWT_SECRET, algorithm='HS256')

def current_user(request: Request):
    token = request.cookies.get('tutor_session')
    try:
        claims = jwt.decode(token or '', settings.JWT_SECRET, algorithms=['HS256'],
                            options={'require': ['sub', 'iat', 'exp']})
        user_id = int(claims['sub'])
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(401, 'Please sign in.')
    user = execute_one('SELECT user_id, full_name, email, role FROM USERS WHERE user_id = %s', (user_id,))
    if not user:
        raise HTTPException(401, 'Account no longer exists.')
    return user

def require_admin(user=Depends(current_user)):
    if user['role'] != 'admin':
        raise HTTPException(403, 'Administrator access required.')
    return user

def require_instructor(user=Depends(current_user)):
    if user['role'] not in ('instructor', 'admin'):
        raise HTTPException(403, 'Instructor or administrator access required.')
    return user

def require_owner(user: dict, user_id: int):
    if user['user_id'] != user_id and user['role'] != 'admin':
        raise HTTPException(403, 'You cannot access another student learning record.')
