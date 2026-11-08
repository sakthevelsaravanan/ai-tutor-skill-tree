"""Text extraction and deterministic, document-based topic indexing."""
import io
import hashlib
from pathlib import Path
from pypdf import PdfReader
from fastapi import HTTPException
from backend.vector_service import vector_service
from backend.vector_transactions import vector_transaction
from backend.course_structure import split_sections, section_for, create_topics

class DocumentIndexer:
    def __init__(self, chunk_size=1000, chunk_overlap=150):
        self.chunk_size=chunk_size
        self.chunk_overlap=chunk_overlap

    def _split_text(self,text):
        return [text[i:i+self.chunk_size].strip() for i in range(0,len(text),self.chunk_size-self.chunk_overlap) if text[i:i+self.chunk_size].strip()]

    def extract(self,file_bytes,file_name):
        # UploadFile spools large uploads to disk; avoid copying the whole PDF into RAM.
        stream = io.BytesIO(file_bytes) if isinstance(file_bytes, bytes) else file_bytes
        stream.seek(0)
        fname_lower = file_name.lower()
        if fname_lower.endswith('.pdf'):
            try:
                reader=PdfReader(stream)
                pages=[(i+1,page.extract_text() or '') for i,page in enumerate(reader.pages)]
            except Exception:
                raise HTTPException(400,'The PDF could not be read. Upload an unencrypted, text-based PDF.')
        elif fname_lower.endswith(('.pptx', '.ppt')):
            pages = []
            try:
                from pptx import Presentation
                prs = Presentation(stream)
                for i, slide in enumerate(prs.slides):
                    texts = []
                    for shape in slide.shapes:
                        if hasattr(shape, "text") and shape.text:
                            texts.append(shape.text.strip())
                    pages.append((i + 1, "\n".join(texts)))
            except Exception:
                # Fallback to direct XML parsing if needed
                try:
                    import zipfile
                    import xml.etree.ElementTree as ET
                    stream.seek(0)
                    pages = []
                    with zipfile.ZipFile(stream) as z:
                        slide_files = sorted([f for f in z.namelist() if f.startswith('ppt/slides/slide') and f.endswith('.xml')],
                                             key=lambda x: int(''.join(filter(str.isdigit, x)) or '0'))
                        for i, sf in enumerate(slide_files):
                            root = ET.fromstring(z.read(sf))
                            text_bits = [elem.text for elem in root.iter() if elem.text and elem.text.strip()]
                            pages.append((i + 1, " ".join(text_bits)))
                except Exception:
                    raise HTTPException(400, 'The presentation could not be read. Upload a valid, uncorrupted PPT or PPTX file.')
        else:
            try:
                pages=[(1,stream.read().decode('utf-8-sig'))]
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
            sections=split_sections(pages, markdown=file_name.lower().endswith((".md", ".txt")))
            topics=create_topics(conn,subject_id,file_name,sections)
            all_topic_ids={t['topic_id'] for t in conn.execute('SELECT topic_id FROM topics WHERE subject_id=%s',(subject_id,)).fetchall()}
            if explicit_topic_id is not None and explicit_topic_id not in all_topic_ids:
                raise HTTPException(400,'Selected topic does not belong to this course.')
            col=vector_service.get_or_create_collection(subject_key)
            col.delete(where={'file_name':file_name})
            docs=[]; metas=[]; ids=[]; chunk_count=0
            file_hash=hashlib.sha256(file_name.encode()).hexdigest()[:24]
            for page,text in pages:
                boundaries=[(0,section_for(sections,page,0))]+[(section.offset,i) for i,section in enumerate(sections) if section.start_page==page and section.offset>0]
                idx=0
                for pos,(start,section_idx) in enumerate(boundaries):
                    end=boundaries[pos+1][0] if pos+1<len(boundaries) else len(text)
                    topic=topics[section_idx]
                    for chunk in self._split_text(text[start:end]):
                        front_matter=page<sections[0].start_page
                        topic_id=explicit_topic_id or (0 if front_matter else topic['topic_id'])
                        docs.append(chunk)
                        ids.append(f'{subject_key}_{file_hash}_p{page}_c{idx}')
                        metas.append({'subject':subject_key,'subject_id':subject_id,'topic_id':topic_id,'concept_id':topic_id,
                                      'file_name':file_name,'page_number':page,'chunk_index':idx,'chapter':'Front matter' if front_matter else topic['topic_name']})
                        idx+=1
                        if len(docs)>=100:
                            vector_service.add_chunks(subject_key,docs,metas,ids)
                            chunk_count+=len(docs)
                            docs=[];metas=[];ids=[]
            if docs:
                vector_service.add_chunks(subject_key,docs,metas,ids)
                chunk_count += len(docs)
            conn.execute("""INSERT INTO textbooks(subject_id,uploaded_by,file_name,chroma_collection_name,chunk_count)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT(subject_id,file_name) DO UPDATE
                SET chunk_count=EXCLUDED.chunk_count,uploaded_at=now(),uploaded_by=EXCLUDED.uploaded_by""",
                (subject_id,uploaded_by,file_name,f'chroma_{subject_key}',chunk_count))
        return {'subject_id':subject_id,'subject_key':subject_key,'subject_name':subject['subject_name'],
                'file_name':file_name,'pages_parsed':len(pages),'chunks_indexed':chunk_count,'collection':f'chroma_{subject_key}'}

pdf_indexer=DocumentIndexer()
document_indexer=pdf_indexer
