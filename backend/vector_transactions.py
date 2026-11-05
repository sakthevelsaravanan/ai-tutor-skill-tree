"""Recoverable PostgreSQL/Chroma writes for this single-host deployment.

A durable before-image plus a PostgreSQL commit marker distinguishes a committed
operation from an interrupted one. Every writer takes the same advisory lock.
"""
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
import json
import os
from backend.database import get_transaction
from backend.config import settings
from backend.vector_service import vector_service

JOURNAL = Path(settings.CHROMA_PERSIST_DIR) / 'write-journal.json'


def snapshot(key):
    name = vector_service._get_collection_name(key)
    if name not in {c['name'] for c in vector_service.list_collections()}:
        return None
    col = vector_service.client.get_collection(name)
    data = col.get(include=['documents', 'metadatas', 'embeddings'])
    return {'ids':data['ids'], 'documents':data['documents'], 'metadatas':data['metadatas'],
            'embeddings':data['embeddings'].tolist() if data['embeddings'] is not None else [],
            'metadata':col.metadata}


def restore(snapshots):
    for key, data in snapshots.items():
        name = vector_service._get_collection_name(key)
        if name in {c['name'] for c in vector_service.list_collections()}:
            vector_service.client.delete_collection(name)
        if data is not None:
            col = vector_service.client.create_collection(name, metadata=data['metadata'])
            for start in range(0,len(data['ids']),100):
                end=start+100
                col.upsert(ids=data['ids'][start:end],documents=data['documents'][start:end],
                           metadatas=data['metadatas'][start:end],embeddings=data['embeddings'][start:end])


def recover(conn):
    if JOURNAL.exists():
        journal=json.loads(JOURNAL.read_text(encoding='utf-8'))
        committed=conn.execute('SELECT 1 FROM vector_operation_commits WHERE operation_id=%s', (journal['id'],)).fetchone()
        if not committed:
            restore(journal['before'])
        JOURNAL.unlink()


def recover_pending_writes():
    with get_transaction() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(91002)')
        recover(conn)


def sync_counts(conn,key):
    subject=conn.execute('SELECT subject_id FROM subjects WHERE subject_key=%s',(key,)).fetchone()
    if not subject:
        return
    count=vector_service.get_stats(key)['total_chunks']
    conn.execute('UPDATE subjects SET is_indexed=%s WHERE subject_id=%s',(count>0,subject['subject_id']))
    files={}
    name=vector_service._get_collection_name(key)
    if count:
        for meta in vector_service.client.get_collection(name).get(include=['metadatas'])['metadatas']:
            file_name=(meta or {}).get('file_name')
            files[file_name]=files.get(file_name,0)+1
    for book in conn.execute('SELECT textbook_id,file_name FROM textbooks WHERE subject_id=%s',(subject['subject_id'],)).fetchall():
        conn.execute('UPDATE textbooks SET chunk_count=%s WHERE textbook_id=%s',(files.get(book['file_name'],0),book['textbook_id']))


@contextmanager
def vector_transaction(keys):
    # PostgreSQL lock serializes ingestion, RUD, and purge across workers.
    with get_transaction() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(91002)')
        recover(conn)
        if keys is None:
            keys=[c['name'].removeprefix('chroma_') for c in vector_service.list_collections()]
        before={key:snapshot(key) for key in keys}
        op_id=str(uuid4())
        JOURNAL.parent.mkdir(parents=True,exist_ok=True)
        tmp=JOURNAL.with_suffix('.tmp')
        with tmp.open('w',encoding='utf-8') as f:
            json.dump({'id':op_id,'before':before},f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,JOURNAL)
        try:
            yield conn
            for key in keys:
                sync_counts(conn,key)
            conn.execute('INSERT INTO vector_operation_commits(operation_id) VALUES(%s)',(op_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            # Leave the journal for recovery, reacquiring the lock first.
            raise
        finally:
            # Commit releases the advisory lock: recovery must reacquire it.
            conn.execute('SELECT pg_advisory_xact_lock(91002)')
            recover(conn)
