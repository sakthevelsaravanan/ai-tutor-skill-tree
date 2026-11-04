"""Text extraction and deterministic, document-based topic indexing."""
import io
import re
import hashlib
from pathlib import Path
from pypdf import PdfReader
from fastapi import HTTPException
from backend.vector_service import vector_service
from backend.vector_transactions import vector_transaction

class DocumentIndexer:
    def __init__(self, chunk_size=1000, chunk_overlap=150):
        self.chunk_size=chunk_size
        self.chunk_overlap=chunk_overlap

    def _split_text(self,text):
        return [text[i:i+self.chunk_size].strip() for i in range(0,len(text),self.chunk_size-self.chunk_overlap) if text[i:i+self.chunk_size].strip()]

    def extract(self,file_bytes,file_name):
        if file_name.lower().endswith('.pdf'):
            try:
                reader=PdfReader(io.BytesIO(file_bytes))
                pages=[(i+1,page.extract_text() or '') for i,page in enumerate(reader.pages)]
            except Exception:
                raise HTTPException(400,'The PDF could not be read. Upload an unencrypted, text-based PDF.')
        else:
            try:
                pages=[(1,file_bytes.decode('utf-8-sig'))]
            except UnicodeDecodeError:
                raise HTTPException(400,'Text documents must use UTF-8 encoding.')
        pages=[(n,t.strip()) for n,t in pages if len(t.strip())>=35]
        if not pages:
            raise HTTPException(422,'No usable text found. Scanned PDFs need OCR before uploading.')
        return pages

    def process_and_index_document(self,file_bytes,file_name,subject_id,subject_key,uploaded_by=1,
                                   explicit_topic_id=None,subject_name=None,classification=None):
        pages=self.extract(file_bytes,file_name)
        file_name=Path(file_name).name[:255]
        with vector_transaction([subject_key]) as conn:
            if subject_id is not None:
                subject=conn.execute('SELECT * FROM subjects WHERE subject_id=%s',(subject_id,)).fetchone()
                if not subject: raise HTTPException(404,'Subject not found.')
            else:
                subject=conn.execute("""INSERT INTO subjects(subject_key,subject_name,description,created_by)
                    VALUES(%s,%s,%s,%s) ON CONFLICT(subject_key) DO UPDATE SET subject_key=EXCLUDED.subject_key RETURNING *""",
                    (subject_key,subject_name,classification or 'Uploaded course material',uploaded_by)).fetchone()
                subject_id=subject['subject_id']
            topics=conn.execute('SELECT * FROM topics WHERE subject_id=%s ORDER BY topic_id',(subject_id,)).fetchall()
            if not topics:
                headings=[]
                for _,text in pages:
                    for line in text.splitlines():
                        match=re.match(r'^(?:#{1,3} +|(?:Chapter|Unit|Module) +[0-9]+[ :.-]+)(.{4,95})$',line.strip(),re.I)
                        if match and match.group(1).strip() not in headings:
                            headings.append(match.group(1).strip())
                # Headings provide topics; prerequisite edges require curated evidence.
                for title in (headings[:24] or [subject['subject_name']]):
                    conn.execute("INSERT INTO topics(subject_id,topic_name,difficulty_level,visual_type) VALUES(%s,%s,1,'p5js')",
                                 (subject_id,title[:100]))
                topics=conn.execute('SELECT * FROM topics WHERE subject_id=%s ORDER BY topic_id',(subject_id,)).fetchall()
            if explicit_topic_id is not None and explicit_topic_id not in {t['topic_id'] for t in topics}:
                raise HTTPException(400,'Selected topic does not belong to this course.')
            docs=[]; metas=[]; ids=[]
            file_hash=hashlib.sha256(file_name.encode()).hexdigest()[:24]
            for page,text in pages:
                for idx,chunk in enumerate(self._split_text(text)):
                    words=set(re.findall(r'[a-z]{3,}',chunk.lower()))
                    topic=max(topics,key=lambda t:len(words & set(re.findall(r'[a-z]{3,}',t['topic_name'].lower()))))
                    topic_id=explicit_topic_id or topic['topic_id']
                    docs.append(chunk)
                    ids.append(f'{subject_key}_{file_hash}_p{page}_c{idx}')
                    metas.append({'subject':subject_key,'subject_id':subject_id,'topic_id':topic_id,'concept_id':topic_id,
                                  'file_name':file_name,'page_number':page,'chunk_index':idx})
            col=vector_service.get_or_create_collection(subject_key)
            col.delete(where={'file_name':file_name})
            vector_service.add_chunks(subject_key,docs,metas,ids)
            conn.execute("""INSERT INTO textbooks(subject_id,uploaded_by,file_name,chroma_collection_name,chunk_count)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT(subject_id,file_name) DO UPDATE
                SET chunk_count=EXCLUDED.chunk_count,uploaded_at=now(),uploaded_by=EXCLUDED.uploaded_by""",
                (subject_id,uploaded_by,file_name,f'chroma_{subject_key}',len(docs)))
        return {'subject_id':subject_id,'subject_key':subject_key,'subject_name':subject['subject_name'],
                'file_name':file_name,'pages_parsed':len(pages),'chunks_indexed':len(docs),'collection':f'chroma_{subject_key}'}

pdf_indexer=DocumentIndexer()
document_indexer=pdf_indexer
