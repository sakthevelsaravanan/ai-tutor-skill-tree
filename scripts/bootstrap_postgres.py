"""Initialize the isolated local cluster. Never drops databases or resets accounts."""
from pathlib import Path
import secrets
import sys
import bcrypt
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
env_path = ROOT / '.env'
if not env_path.exists():
    env_path.write_text(f'DB_HOST=127.0.0.1\nDB_PORT=5433\nDB_USER=ai_tutor_app\n'
                        f'DB_PASSWORD={secrets.token_urlsafe(32)}\nDB_NAME=ai_tutor_db\n'
                        f'JWT_SECRET={secrets.token_urlsafe(48)}\nCOOKIE_SECURE=false\n')
from backend.config import settings

owner_password = (ROOT / '.runtime/postgres-owner-password').read_text().strip()
args = dict(host='127.0.0.1', port=5433, user='tutor_owner', password=owner_password)
with psycopg.connect(**args, dbname='postgres', autocommit=True) as conn:
    if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (settings.DB_USER,)).fetchone():
        conn.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(settings.DB_USER), sql.Literal(settings.DB_PASSWORD)))
    if not conn.execute('SELECT 1 FROM pg_database WHERE datname=%s', (settings.DB_NAME,)).fetchone():
        conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(settings.DB_NAME)))

credentials = []
with psycopg.connect(**args, dbname=settings.DB_NAME) as conn:
    conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version text PRIMARY KEY, applied_at timestamptz DEFAULT now())')
    for migration in sorted((ROOT / 'database/postgres').glob('*.sql')):
        version = migration.name.split('_')[0]
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=%s', (version,)).fetchone():
            conn.execute(migration.read_text())
            conn.execute('INSERT INTO schema_migrations(version) VALUES(%s)', (version,))
    for name, email, role in [('Administrator','admin@aitutor.edu','admin'),('Instructor','instructor@aitutor.edu','instructor'),('Student','student@aitutor.edu','student')]:
        if not conn.execute('SELECT 1 FROM users WHERE email=%s',(email,)).fetchone():
            password = secrets.token_urlsafe(15)
            hashed = bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()
            conn.execute('INSERT INTO users(full_name,email,role,password_hash) VALUES(%s,%s,%s,%s)',(name,email,role,hashed))
            credentials.append(f'| {role} | {email} | `{password}` |')
    conn.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
    conn.execute('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC')
    role = sql.Identifier(settings.DB_USER)
    conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(settings.DB_NAME),role))
    conn.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(role))
    conn.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {}').format(role))
    conn.execute(sql.SQL('REVOKE ALL ON schema_migrations FROM {}').format(role))
    conn.execute(sql.SQL('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {}').format(role))
    conn.execute(sql.SQL('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {}').format(role))

if credentials:
    access = ROOT / 'LOCAL_ACCESS.md'
    prefix = '# Local application access\n\nURL: http://localhost:3000\n\n| Role | Email | Password |\n|---|---|---|\n'
    with access.open('a',encoding='utf-8') as f:
        f.write((prefix if access.stat().st_size == 0 else '\n') + '\n'.join(credentials)+'\n')
print('PostgreSQL schema and application role ready. Account credentials are in LOCAL_ACCESS.md (gitignored).')
