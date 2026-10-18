import io
from typing import List, Dict, Tuple
from pypdf import PdfReader
from backend.vector_service import vector_service
from backend.database import execute_dml, execute_one

class PDFIndexer:
    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _split_text(self, text: str) -> List[str]:
        chunks = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= text_len:
                break
            start += self.chunk_size - self.chunk_overlap
        return chunks

    def process_and_index_pdf(
        self,
        file_bytes: bytes,
        file_name: str,
        subject_id: int,
        subject_key: str,
        uploaded_by: int
    ) -> Tuple[int, int]:
        reader = PdfReader(io.BytesIO(file_bytes))
        total_pages = len(reader.pages)

        all_docs = []
        all_metas = []
        all_ids = []

        chunk_counter = 0
        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            if not page_text.strip():
                continue

            page_chunks = self._split_text(page_text)
            for idx, chunk in enumerate(page_chunks):
                chunk_id = f"{subject_key}_tb_{file_name[:8]}_p{page_idx + 1}_c{idx}"
                all_docs.append(chunk)
                all_ids.append(chunk_id)
                all_metas.append({
                    "subject": subject_key,
                    "subject_id": subject_id,
                    "file_name": file_name,
                    "page_number": page_idx + 1,
                    "chunk_index": idx
                })
                chunk_counter += 1

        if all_docs:
            vector_service.add_chunks(
                subject_key=subject_key,
                documents=all_docs,
                metadatas=all_metas,
                ids=all_ids
            )

        # Update or insert MySQL TEXTBOOKS record
        col_name = f"chroma_{subject_key}"
        existing = execute_one(
            "SELECT textbook_id FROM TEXTBOOKS WHERE subject_id = %s AND file_name = %s",
            (subject_id, file_name)
        )
        if existing:
            execute_dml(
                "UPDATE TEXTBOOKS SET chunk_count = %s, uploaded_at = CURRENT_TIMESTAMP WHERE textbook_id = %s",
                (len(all_docs), existing["textbook_id"])
            )
        else:
            execute_dml(
                "INSERT INTO TEXTBOOKS (subject_id, uploaded_by, file_name, chroma_collection_name, chunk_count) VALUES (%s, %s, %s, %s, %s)",
                (subject_id, uploaded_by, file_name, col_name, len(all_docs))
            )

        # Mark subject as indexed
        execute_dml("UPDATE SUBJECTS SET is_indexed = TRUE WHERE subject_id = %s", (subject_id,))

        return total_pages, len(all_docs)

pdf_indexer = PDFIndexer()
