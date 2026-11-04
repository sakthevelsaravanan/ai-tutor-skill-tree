"""Index clearly labeled original demo notes; does not reset existing courses."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.database import execute_one,get_transaction
from backend.pdf_indexer import pdf_indexer

admin=execute_one("SELECT user_id FROM users WHERE role='admin' ORDER BY user_id LIMIT 1")
existing=execute_one("SELECT subject_id FROM subjects WHERE subject_key='database_foundations'")
result=pdf_indexer.process_and_index_document((ROOT/'docs/demo_course.md').read_bytes(),'demo_course.md',
    existing['subject_id'] if existing else None,'database_foundations',admin['user_id'],
    subject_name='Database Foundations (demo)',classification='Original demonstration notes')
with get_transaction() as conn:
    topics={r['topic_name']:r['topic_id'] for r in conn.execute('SELECT topic_id,topic_name FROM topics WHERE subject_id=%s',(result['subject_id'],)).fetchall()}
    conn.execute('INSERT INTO topic_prerequisites(topic_id,prereq_topic_id,importance_weight) VALUES(%s,%s,5) ON CONFLICT DO NOTHING',
                 (topics['Normalization'],topics['Keys and relationships']))
    conn.execute('UPDATE topics SET difficulty_level=2 WHERE topic_id=%s',(topics['Normalization'],))
print(f"Demo course ready: {result['chunks_indexed']} passages, {len(topics)} topics.")
