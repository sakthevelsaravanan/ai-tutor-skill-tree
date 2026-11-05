"""Integration tests using a freshly created, isolated PostgreSQL database."""
import os
import tempfile
from pathlib import Path
from uuid import uuid4
import pytest
import psycopg
from psycopg import sql

# Must precede app imports so tests cannot mutate the running Chroma store.
os.environ['CHROMA_PERSIST_DIR']=tempfile.mkdtemp(prefix='ai-tutor-test-vectors-')
from backend.config import settings
from backend.database import execute_one,execute_query,get_transaction
from backend.security import hash_password
from backend.main import app
from backend.vector_transactions import vector_transaction,JOURNAL,recover_pending_writes
from backend.vector_service import vector_service
from backend.routers.tutor import solve_hill_cipher,parse_hill_cipher_problem,_synthesize_slide_rag_answer
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[2]
PASSWORD='Test-only-strong-password-42!'

@pytest.fixture(scope='session',autouse=True)
def isolated_database():
    original=settings.DB_NAME
    name='ai_tutor_test_'+uuid4().hex[:12]
    owner=dict(host=settings.DB_HOST,port=settings.DB_PORT,user='tutor_owner',
               password=(ROOT/'.runtime/postgres-owner-password').read_text().strip())
    with psycopg.connect(**owner,dbname='postgres',autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    with psycopg.connect(**owner,dbname=name) as conn:
        for migration in sorted((ROOT/'database/postgres').glob('*.sql')):
            conn.execute(migration.read_text())
        role=sql.Identifier(settings.DB_USER)
        conn.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(role))
        conn.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {}').format(role))
        conn.execute(sql.SQL('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {}').format(role))
        conn.execute(sql.SQL('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {}').format(role))
    settings.DB_NAME=name
    with get_transaction() as conn:
        for name_,role in [('Admin','admin'),('Teacher','instructor'),('Student','student'),('Other','student')]:
            conn.execute('INSERT INTO users(full_name,email,password_hash,role) VALUES(%s,%s,%s,%s)',
                         (name_,name_.lower()+'@example.com',hash_password(PASSWORD),role))
    yield
    settings.DB_NAME=original
    assert name.startswith('ai_tutor_test_') and len(name)==26
    with psycopg.connect(**owner,dbname='postgres',autocommit=True) as conn:
        conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))

@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client

def login(client,name='student'):
    response=client.post('/api/auth/login',json={'email':name+'@example.com','password':PASSWORD})
    assert response.status_code==200,response.text
    assert 'httponly' in response.headers['set-cookie'].lower()
    return response.json()

@pytest.fixture
def course():
    key='test_'+uuid4().hex[:12]
    with get_transaction() as conn:
        sub=conn.execute('INSERT INTO subjects(subject_key,subject_name) VALUES(%s,%s) RETURNING subject_id',(key,'Test course')).fetchone()['subject_id']
        ids=[conn.execute("INSERT INTO topics(subject_id,topic_name,difficulty_level) VALUES(%s,%s,1) RETURNING topic_id",(sub,name)).fetchone()['topic_id'] for name in ['Keys','Transactions','Indexes']]
        conn.execute('INSERT INTO topic_prerequisites(topic_id,prereq_topic_id) VALUES(%s,%s)',(ids[1],ids[0]))
    return sub,key,ids

def session(client,course):
    user=login(client)
    sub,key,ids=course
    response=client.post('/api/sessions/start',json={'user_id':user['user_id'],'subject_id':sub,'current_topic_id':ids[0]})
    assert response.status_code==201,response.text
    return response.json()['session_id'],user['user_id']

def test_health_and_unauthenticated_access(client):
    assert client.get('/health').json()['database']=='PostgreSQL'
    for path in ['/api/curriculum/subjects','/api/auth/users','/api/vector/collections','/api/sessions/user/3']:
        assert client.get(path).status_code==401

@pytest.mark.parametrize('password',['password','password123','admin','admin123','secret'])
def test_demo_password_bypass_removed(client,password):
    assert client.post('/api/auth/login',json={'email':'student@example.com','password':password}).status_code==401

def test_roles_cannot_be_forged(client):
    login(client)
    assert client.post('/api/vector/clear-all',json={'role':'admin','user_id':1,'confirm':True}).status_code==403
    assert client.post('/api/vector/chunk',json={'subject_key':'x','chunk_id':'x','text':'hello'}).status_code==403
    assert client.post('/api/vector/upload',files={'file':('notes.txt',b'Notes','text/plain')}).status_code==403
    assert client.get('/api/auth/users').status_code==403
    client.post('/api/auth/logout')
    assert client.get('/api/auth/me').status_code==401

def test_sessions_preserve_messages_without_self_assessment(client,course):
    sid,uid=session(client,course)
    assert client.post('/api/sessions/message',json={'session_id':sid,'content':'Explain binary numbers'}).status_code==201
    details=client.get(f'/api/sessions/{sid}').json()
    assert details['messages'][0]['content']=='Explain binary numbers'
    assert 'quiz_attempts' not in details


def test_self_assessment_endpoints_removed(client,course):
    sid,uid=session(client,course)
    assert client.post('/api/sessions/quiz-attempt',json={'session_id':sid}).status_code in (404,405)
    assert client.get(f'/api/sessions/mastery/{uid}/{course[0]}').status_code==404
    assert client.get(f'/api/sessions/recommend/{uid}/{course[0]}').status_code==404


def test_foreign_session_and_topic_rejected(client,course):
    sid,uid=session(client,course)
    login(client,'other')
    assert client.get(f'/api/sessions/{sid}').status_code==403
    assert client.post('/api/tutor/query',json={'query':'Explain keys','subject_id':course[0],'session_id':sid}).status_code==403
    login(client)
    assert client.post('/api/sessions/message',json={'session_id':sid,'content':'fake assistant','role':'assistant'}).status_code==403

def test_cycle_and_cross_subject_constraints(course):
    sub,key,ids=course
    with pytest.raises(psycopg.Error),get_transaction() as conn:
        conn.execute('INSERT INTO topic_prerequisites(topic_id,prereq_topic_id) VALUES(%s,%s)',(ids[0],ids[1]))
    with get_transaction() as conn:
        other=conn.execute("INSERT INTO subjects(subject_key,subject_name) VALUES(%s,'Other') RETURNING subject_id",('other_'+uuid4().hex[:10],)).fetchone()['subject_id']
        topic=conn.execute("INSERT INTO topics(subject_id,topic_name,difficulty_level) VALUES(%s,'Other topic',1) RETURNING topic_id",(other,)).fetchone()['topic_id']
    with pytest.raises(psycopg.Error),get_transaction() as conn:
        conn.execute('INSERT INTO topic_prerequisites(topic_id,prereq_topic_id) VALUES(%s,%s)',(ids[0],topic))

def test_quiz_rollback_is_atomic(client,course):
    sid,uid=session(client,course)
    with pytest.raises(RuntimeError),get_transaction() as conn:
        conn.execute("SELECT record_quiz_and_advance_stage(%s,%s,3,5,'UNDERSTOOD')",(sid,course[2][0]))
        raise RuntimeError('simulated failure before commit')
    assert execute_one('SELECT count(*) AS n FROM quiz_attempts WHERE session_id=%s',(sid,))['n']==0
    assert execute_one('SELECT count(*) AS n FROM student_topic_mastery WHERE user_id=%s AND topic_id=%s',(uid,course[2][0]))['n']==0

def test_grounded_fallback_and_numeric_without_vectors():
    answer=solve_hill_cipher(parse_hill_cipher_problem('encrypt plaintext ACT using Hill cipher [[6,24,1],[13,16,10],[20,17,15]]'))[0]
    assert 'POH' in answer
    text,_=solve_hill_cipher({'matrix':[[6,24,1],[13,16,10],[20,17,15]],'n':3,'text':'POH','operation':'decrypt'})
    assert 'ACT' in text
    assert 'No direct matching topics' in _synthesize_slide_rag_answer('What are keys?',[],'Database foundations','Keys')

def test_document_replacement_counts_and_chat_persistence(client):
    login(client,'teacher')
    name='Upload '+uuid4().hex[:8]
    text=(ROOT/'docs/demo_course.md').read_bytes()
    result=client.post('/api/vector/upload',data={'subject_name':name},files={'file':('notes.md',text,'text/markdown')})
    assert result.status_code==200,result.text
    data=result.json();sub=data['subject_id'];key=data['subject_key']
    smaller=b'## Keys\nA primary key uniquely identifies a row. A foreign key references a row in another table and enforces referential integrity.'
    updated=client.post('/api/vector/upload',data={'subject_id':str(sub)},files={'file':('notes.md',smaller,'text/markdown')})
    assert updated.status_code==200,updated.text
    assert vector_service.get_stats(key)['total_chunks']==1
    assert [t['topic_name'] for t in execute_query('SELECT topic_name FROM topics WHERE subject_id=%s',(sub,))]==['Keys']
    assert execute_one('SELECT chunk_count FROM textbooks WHERE subject_id=%s',(sub,))['chunk_count']==1
    user=login(client)
    topic=client.get(f'/api/curriculum/topics/{sub}').json()[0]['topic_id']
    sid=client.post('/api/sessions/start',json={'user_id':user['user_id'],'subject_id':sub,'current_topic_id':topic}).json()['session_id']
    response=client.post('/api/tutor/query',json={'query':'What is a primary key?','subject_id':sub,'topic_id':topic,'session_id':sid})
    assert response.status_code==200,response.text
    assert len(client.get(f'/api/sessions/{sid}').json()['messages'])==2
    login(client,'admin')
    chunk=vector_service.get_chunks(key)[0]
    assert client.request('DELETE','/api/vector/delete',json={'subject_key':key,'chunk_ids':[chunk['id']]}).status_code==200
    assert execute_one('SELECT chunk_count FROM textbooks WHERE subject_id=%s',(sub,))['chunk_count']==0
    assert not execute_one('SELECT is_indexed FROM subjects WHERE subject_id=%s',(sub,))['is_indexed']

def test_vector_write_compensation(course):
    sub,key,ids=course
    with pytest.raises(RuntimeError):
        with vector_transaction([key]):
            vector_service.add_chunks(key,['A primary key identifies a row.'],[{'subject':key}],['before-rollback'])
            raise RuntimeError('simulated SQL failure')
    assert vector_service.get_stats(key)['total_chunks']==0
    assert not JOURNAL.exists()

def test_recover_interrupted_vector_write(course):
    import json
    sub,key,ids=course
    vector_service.add_chunks(key,['A primary key identifies a row.'],[{'subject':key}],['interrupted'])
    JOURNAL.write_text(json.dumps({'id':str(uuid4()),'before':{key:None}}))
    recover_pending_writes()
    assert vector_service.get_stats(key)['total_chunks']==0

def test_invalid_document_does_not_leave_subject(client):
    login(client,'teacher')
    name='Empty '+uuid4().hex[:8]
    response=client.post('/api/vector/upload',data={'subject_name':name},files={'file':('empty.txt',b'','text/plain')})
    assert response.status_code==422
    assert not execute_one('SELECT 1 FROM subjects WHERE subject_name=%s',(name,))


def test_completion_persists_and_duplicate_is_idempotent(client,course):
    user=login(client)
    topic=course[2][0]
    url=f'/api/curriculum/topics/{topic}/complete'
    response=client.post(url,json={'user_id':user['user_id']})
    assert response.status_code==200,response.text
    first=response.json()
    assert first['is_completed']
    repeated=client.post(url,json={'user_id':user['user_id']})
    assert 'already' in repeated.json()['message']
    assert repeated.json()['completed_at']==first['completed_at']
    assert execute_one('SELECT count(*) AS n FROM student_topic_completions WHERE user_id=%s AND topic_id=%s',(user['user_id'],topic))['n']==1
    # A fresh login reads the same persisted status; completion does not fabricate quiz mastery.
    client.post('/api/auth/logout')
    login(client)
    status=client.get(f'/api/curriculum/topics/{topic}/status/{user["user_id"]}').json()
    assert status['is_completed']
    assert client.get(f'/api/curriculum/completed/{user["user_id"]}?subject_id={course[0]}').json()['completed_topic_ids']==[topic]
    assert not execute_one('SELECT 1 FROM student_topic_mastery WHERE user_id=%s AND topic_id=%s',(user['user_id'],topic))
    assert client.delete(url,params={'user_id':user['user_id']}).status_code==200
    assert not client.get(f'/api/curriculum/topics/{topic}/status/{user["user_id"]}').json()['is_completed']


def test_completion_cannot_access_another_student(client,course):
    user=login(client)
    topic=course[2][0]
    client.post(f'/api/curriculum/topics/{topic}/complete',json={'user_id':user['user_id']})
    login(client,'other')
    assert client.post(f'/api/curriculum/topics/{topic}/complete',json={'user_id':user['user_id']}).status_code==403
    assert client.delete(f'/api/curriculum/topics/{topic}/complete',params={'user_id':user['user_id']}).status_code==403
    assert client.get(f'/api/curriculum/completed/{user["user_id"]}').status_code==403
    assert client.get(f'/api/curriculum/topics/{topic}/status/{user["user_id"]}').status_code==403


def test_completion_requires_student_and_existing_topic(client,course):
    teacher=login(client,'teacher')
    assert client.post(f'/api/curriculum/topics/{course[2][0]}/complete',json={'user_id':teacher['user_id']}).status_code==403
    student=login(client)
    assert client.post('/api/curriculum/topics/2147483647/complete',json={'user_id':student['user_id']}).status_code==404


def test_numeric_response_persists_without_retrieval(client,course):
    sid,uid=session(client,course)
    response=client.post('/api/tutor/query',json={'query':'encrypt plaintext ACT using Hill cipher [[6,24,1],[13,16,10],[20,17,15]]',
                                               'subject_id':course[0],'topic_id':course[2][0],'session_id':sid})
    assert response.status_code==200,response.text
    assert 'POH' in response.json()['answer']
    assert len(client.get(f'/api/sessions/{sid}').json()['messages'])==2


def test_document_chapters_have_connected_path_and_paginated_passages(client):
    login(client,'teacher')
    text=b'# Binary Numbers\nBinary digits represent numerical values.\n## Boolean Algebra\nLogical operations combine binary inputs.\n## Logic Gates\nElectronic gates implement Boolean expressions.'
    result=client.post('/api/vector/upload',data={'subject_name':'Chapters '+uuid4().hex[:8]},files={'file':('chapters.md',text,'text/markdown')})
    assert result.status_code==200,result.text
    course=result.json()
    graph=client.get(f"/api/curriculum/graph/{course['subject_id']}").json()
    assert [n['label'] for n in graph['nodes']]==['Binary Numbers','Boolean Algebra','Logic Gates']
    assert len(graph['edges'])==2
    assert all(e['basis']=='book_order' for e in graph['edges'])
    middle=graph['nodes'][1]['id']
    assert len(client.get(f'/api/curriculum/prerequisites/{middle}').json())==1
    assert len(client.get(f'/api/curriculum/unlocked/{middle}').json())==1
    login(client,'admin')
    first=client.get(f"/api/vector/chunks/{course['subject_key']}?limit=1&offset=0").json()
    remaining=client.get(f"/api/vector/chunks/{course['subject_key']}?limit=1&offset=1").json()
    assert first and remaining and first[0]['id']!=remaining[0]['id']
    assert first[0]['metadata']['topic_id']==graph['nodes'][0]['id']
    assert remaining[0]['metadata']['topic_id']==graph['nodes'][1]['id']


def test_large_upload_streams_and_indexes_multiple_batches(client, monkeypatch):
    """No 20 MB gate; every passage survives batched writes to the real test stores."""
    from backend.pdf_indexer import pdf_indexer
    login(client, 'teacher')
    batch_sizes = []
    original_add = vector_service.add_chunks
    original_extract = pdf_indexer.extract
    def record_batch(key, docs, metas, ids):
        batch_sizes.append(len(docs))
        return original_add(key, docs, metas, ids)
    def require_stream(source, name):
        assert hasattr(source, 'seek') and hasattr(source, 'read')
        return original_extract(source, name)
    monkeypatch.setattr(vector_service, 'add_chunks', record_batch)
    monkeypatch.setattr(pdf_indexer, 'extract', require_stream)
    text = ('# Network protocols\n' + 'Packets travel through routers using network protocols. ' * 1700).encode()
    with tempfile.TemporaryFile() as document:
        document.write(text)
        document.write(b' ' * (21 * 1024 * 1024))
        document.seek(0)
        response = client.post('/api/vector/upload', data={'subject_name': 'Large book ' + uuid4().hex[:8]},
                               files={'file': ('large-book.txt', document, 'text/plain')})
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(batch_sizes) > 1 and max(batch_sizes) <= 100
    assert result['chunks_indexed'] == sum(batch_sizes)
    assert vector_service.get_stats(result['subject_key'])['total_chunks'] == sum(batch_sizes)
    book = execute_one('SELECT chunk_count FROM textbooks WHERE subject_id=%s', (result['subject_id'],))
    assert book['chunk_count'] == sum(batch_sizes)


def test_pdf_extract_uses_seekable_upload():
    import io
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject, DictionaryObject
    from backend.pdf_indexer import pdf_indexer
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
    content = DecodedStreamObject()
    content.set_data(b'BT /F1 12 Tf 50 700 Td (Network protocols carry packets between connected computers.) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(content)
    with tempfile.TemporaryFile() as document:
        writer.write(document)
        pages = pdf_indexer.extract(document, 'network.pdf')
    assert pages[0][0] == 1
    assert 'Network protocols' in pages[0][1]
