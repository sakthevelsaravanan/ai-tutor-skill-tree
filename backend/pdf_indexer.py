"""Text extraction and deterministic, document-based topic indexing."""
import io
import re
import hashlib
from typing import List, Tuple, Optional, Dict, Set
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

    def _extract_quarter_topics_pure(
        self,
        quarters: List[List[Tuple[int, str]]],
        subject_name: str
    ) -> List[str]:
        """
        Extract representative topic titles across the 4 quarters of a document
        using pure statistical recurrence analysis.

        Algorithm:
        1. Scan the top 4 lines of all pages in each quarter to capture candidate titles.
        2. Count how many quarters each candidate appears in. Any candidate appearing in
           2 or more quarters is identified as a repeating template header/footer/author
           banner and filtered out automatically.
        3. Filter out administrative noise (such as agenda, summary, copyright, dr/prof).
        4. Exclude lines composed solely of tokens from the course title to avoid redundancy.
        5. Rank valid topic candidate lines by frequency within each quarter.
        6. Select the top candidate as the quarter's title, falling back to a structured
           academic label if no distinct candidate is found.

        Args:
            quarters: 4-element list containing page lists [(page_number, text), ...] for each quarter.
            subject_name: Name of the course subject to avoid trivial duplicate titles.

        Returns:
            List of 4 extracted topic titles corresponding to Quarters 1, 2, 3, and 4.
        """
        ADMIN_NOISE = r"(?i)\b(department|faculty|school|university|institute|college|all rights reserved|copyright|agenda|objectives|outline|table of contents|summary|recap|references|textbooks|page \d+|s\.no|slide \d+|session \d+|lecture \d+|unit \d+|module \d+|chapter \d+|thank you|questions\?|example|solution|continued|prof|dr\.|author|instructor|lecturer)\b"
        DANGLING_TAILS = {'for', 'to', 'in', 'of', 'by', 'with', 'and', 'or', 'the', 'a', 'an', 'at', 'from', 'as', 'on'}

        # Statistical detection of repeating headers/footers across quarters
        line_quarter_presence = {}
        for q_pages in quarters:
            seen_in_q = set()
            for _, text in q_pages:
                for l in [line.strip() for line in text.split("\n")[:4] if line.strip()]:
                    cleaned = re.sub(r"^[0-9\.\-:\s]+", "", l).strip()
                    cleaned = re.sub(r"[^\x00-\x7F]+", "", cleaned).strip()
                    cleaned = re.sub(r"(?i)^(what is |intro to |introduction to |overview of |a )", "", cleaned).strip()
                    cleaned = re.sub(r"[?!:;\*\"']+$", "", cleaned).strip()
                    norm = cleaned.lower()
                    if 2 <= len(cleaned.split()) <= 6 and 6 <= len(cleaned) <= 50:
                        seen_in_q.add(norm)
            for norm in seen_in_q:
                line_quarter_presence[norm] = line_quarter_presence.get(norm, 0) + 1

        # Any line appearing across 2 or more quarters is a global template header/footer
        template_lines = {norm for norm, count in line_quarter_presence.items() if count >= 2}

        # Subject tokens to prevent repeating the global subject title
        sub_tokens = set(re.findall(r"[A-Za-z]{3,}", subject_name.lower()))

        extracted_titles = []
        for q_idx, q_pages in enumerate(quarters):
            candidates = {}
            for _, text in q_pages:
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                for l in lines[:4]:
                    if "@" in l or "http" in l or l.endswith(".") or l.endswith(","):
                        continue
                    cleaned = re.sub(r"^[0-9\.\-:\s]+", "", l).strip()
                    cleaned = re.sub(r"[^\x00-\x7F]+", "", cleaned).strip()
                    cleaned = re.sub(r"(?i)^(what is |intro to |introduction to |overview of |a )", "", cleaned).strip()
                    cleaned = re.sub(r"[?!:;\*\"']+$", "", cleaned).strip()

                    words = cleaned.split()
                    if 2 <= len(words) <= 6 and 6 <= len(cleaned) <= 50:
                        norm = cleaned.lower()
                        if norm in template_lines:
                            continue
                        if words[-1].lower() in DANGLING_TAILS:
                            continue
                        cand_tokens = set(re.findall(r"[A-Za-z]{3,}", norm))
                        if cand_tokens and cand_tokens.issubset(sub_tokens):
                            continue
                        if not re.search(ADMIN_NOISE, cleaned) and not re.search(r"[@\\/_\{\}\$\=]", cleaned):
                            if not re.search(r"\b(we|you|they|assume|consider|suppose|let|is|are|was|were|can|will|should)\b", norm):
                                cap_words = sum(1 for w in words if w[0].isupper())
                                if cap_words >= len(words) // 2:
                                    cand_title = cleaned.title()
                                    candidates[cand_title] = candidates.get(cand_title, 0) + 1

            sorted_cands = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
            if sorted_cands:
                extracted_titles.append(sorted_cands[0][0])
            else:
                fallbacks = [
                    "Core Foundations",
                    "Key Methodologies",
                    "Applied Modeling",
                    "Advanced Systems"
                ]
                extracted_titles.append(fallbacks[q_idx])

        return extracted_titles

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
                if not headings and file_name.lower().endswith('.pdf') and len(pages)>=4:
                    # Upstream slide-title discovery, with duplicate titles collapsed.
                    quarters=[pages[i*len(pages)//4:(i+1)*len(pages)//4] for i in range(4)]
                    headings=list(dict.fromkeys(self._extract_quarter_topics_pure(quarters,subject['subject_name'])))
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
