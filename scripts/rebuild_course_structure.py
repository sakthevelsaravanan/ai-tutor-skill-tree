"""Rebuild generated topics from retained passages. Preview first; --apply backs up both stores."""
import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.database import execute_query
from backend.vector_service import vector_service
from backend.vector_transactions import vector_transaction, snapshot
from backend.course_structure import split_sections, section_for, create_topics
from backend.config import settings


def reconstruct(data):
    files=defaultdict(lambda:defaultdict(list))
    for id_,doc,meta in zip(data['ids'],data['documents'],data['metadatas']):
        if meta and meta.get('file_name'):
            files[meta['file_name']][int(meta.get('page_number',1))].append((int(meta.get('chunk_index',0)),id_,doc,meta))
    result={}
    for name, grouped in files.items():
        pages=[]
        for page, rows in sorted(grouped.items()):
            rows.sort()
            text=rows[0][2]
            for _,_,tail,_ in rows[1:]:
                overlap=next((n for n in range(min(180,len(tail),len(text)),0,-1) if text.endswith(tail[:n])),0)
                text+=tail[overlap:]
            pages.append((page,text))
        result[name]=(split_sections(pages,markdown=name.lower().endswith(('.md','.txt'))),grouped)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');parser.add_argument('--remove-demo',action='store_true');args=parser.parse_args()
    subjects=execute_query('SELECT * FROM subjects ORDER BY subject_id')
    plans=[]
    for subject in subjects:
        if subject['subject_key']=='database_foundations':
            continue
        data=vector_service.get_or_create_collection(subject['subject_key']).get(include=['documents','metadatas'])
        plan=reconstruct(data)
        if plan:
            plans.append((subject,plan))
            print(subject['subject_name'],json.dumps({name:[vars(s) for s in sections] for name,(sections,_) in plan.items()},ensure_ascii=True))
    if not args.apply:
        return
    backup=ROOT/'.runtime'/'backups'/datetime.now().strftime('structure-%Y%m%d-%H%M%S');backup.mkdir(parents=True)
    env=os.environ.copy();env['PGPASSWORD']=(ROOT/'.runtime/postgres-owner-password').read_text().strip()
    subprocess.run([r'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe','-h',settings.DB_HOST,'-p',str(settings.DB_PORT),'-U','tutor_owner','-d',settings.DB_NAME,'-Fc','-f',str(backup/'database.dump')],env=env,check=True)
    for subject,plan in plans:
        key=subject['subject_key']
        with vector_transaction([key]) as conn:
            (backup/f'{key}.json').write_text(json.dumps(snapshot(key)),encoding='utf-8')
            # Generated topics are being replaced; conversations themselves are retained.
            conn.execute('DELETE FROM topics WHERE subject_id=%s',(subject['subject_id'],))
            col=vector_service.get_or_create_collection(key)
            for name,(sections,pages) in plan.items():
                topics=create_topics(conn,subject['subject_id'],name,sections)
                ids=[];metas=[]
                for page,rows in sorted(pages.items()):
                    for idx,id_,_,meta in rows:
                        topic=topics[section_for(sections,page,idx*850)]
                        front=page<sections[0].start_page
                        topic_id=0 if front else topic['topic_id']
                        ids.append(id_);metas.append({**meta,'topic_id':topic_id,'concept_id':topic_id,'chapter':'Front matter' if front else topic['topic_name']})
                        if len(ids)==100:
                            col.update(ids=ids,metadatas=metas);ids=[];metas=[]
                if ids:col.update(ids=ids,metadatas=metas)
    if args.remove_demo:
        for subject in subjects:
            if subject['subject_key']=='database_foundations' and subject['subject_name']=='Database Foundations (demo)':
                key=subject['subject_key']
                with vector_transaction([key]) as conn:
                    (backup/f'{key}.json').write_text(json.dumps(snapshot(key)),encoding='utf-8')
                    vector_service.delete_collection(key)
                    conn.execute('DELETE FROM subjects WHERE subject_id=%s',(subject['subject_id'],))
    print('Applied. Backup:',backup)

if __name__=='__main__':main()
