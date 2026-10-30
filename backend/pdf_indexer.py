import io
import re
from typing import List, Tuple, Optional
from pypdf import PdfReader
from backend.vector_service import vector_service
from backend.database import execute_dml, execute_one, execute_query

class DocumentIndexer:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150):
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

    def _extract_quarter_topic_title(self, quarter_pages: List[Tuple[int, str]], quarter_num: int, subject_name: str) -> str:
        TECH_BOOST = r"(?i)\b(analysis|analytics|algorithm|architecture|arima|autoregress|component|chain|circuit|data|distribution|dynamics|equation|estimation|filter|forecast|markov|matrix|model|network|operation|optimization|order|probability|process|protocol|random|signal|state|stationar|stochastic|structure|system|technique|time|transition|vector)\b"
        NOISE = r"(?i)\b(data analytics|ue\w+|dept\w*|department|prof\w*|dr\.|gowri|srinivasa|pes university|s\.no|page|table|figure|agenda|recap|outline|session|in this session|example|test your|solution|continued|purchased|customer|store|brand|ooty|coonoor|nilgiri|chennai|bangalore|retail|tea|coffee|supermarket|sales|review|lecture \d+|unit \d+|module \d+|chapter \d+)\b"

        candidates = {}

        for _, text in quarter_pages:
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            for l in lines[:4]:
                cleaned = re.sub(r"^[0-9\.\-:\s]+", "", l).strip()
                cleaned = re.sub(r"[^\x00-\x7F]+", "", cleaned).strip()
                cleaned = re.sub(r"(?i)^(what is |intro to |introduction to |a )", "", cleaned).strip()
                cleaned = re.sub(r"[?!:;\*\"']+$", "", cleaned).strip()
                words = cleaned.split()
                if 2 <= len(words) <= 6 and 6 <= len(cleaned) <= 50:
                    if not re.search(NOISE, cleaned) and not re.search(r"[@\\/_\{\}\$\=]", cleaned):
                        tech_matches = len(re.findall(TECH_BOOST, cleaned))
                        if tech_matches > 0:
                            score = 10 * tech_matches + (5 if any(w[0].isupper() for w in words) else 0)
                            cand_title = cleaned.title()
                            candidates[cand_title] = candidates.get(cand_title, 0) + score

        sorted_cands = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
        if sorted_cands:
            return sorted_cands[0][0]

        clean_name = subject_name.replace("_", " ").title()
        fallbacks = [
            f"Foundations of {clean_name}",
            f"Analytical Methods in {clean_name}",
            f"Modeling & Dynamics in {clean_name}",
            f"Advanced Systems & Applications"
        ]
        return fallbacks[quarter_num - 1]

    def ensure_subject_topics(
        self,
        subject_id: int,
        subject_name: str,
        document_sample: str = "",
        pages_content: Optional[List[Tuple[int, str]]] = None,
        force_refresh: bool = False
    ) -> List[int]:
        if not force_refresh:
            existing = execute_query(
                "SELECT topic_id, topic_name FROM TOPICS WHERE subject_id = %s ORDER BY difficulty_level ASC, topic_id ASC",
                (subject_id,)
            )
            if existing and len(existing) >= 4:
                return [t["topic_id"] for t in existing]

        if not pages_content:
            if document_sample:
                lines = [l for l in document_sample.splitlines() if l.strip()]
                n = max(1, len(lines) // 4)
                pages_content = [
                    (1, "\n".join(lines[:n])),
                    (2, "\n".join(lines[n:2*n])),
                    (3, "\n".join(lines[2*n:3*n])),
                    (4, "\n".join(lines[3*n:]))
                ]
            else:
                pages_content = [(1, subject_name)] * 4

        total_p = len(pages_content)
        q_size = max(1, total_p // 4)
        quarters = [
            pages_content[: q_size],
            pages_content[q_size : 2 * q_size],
            pages_content[2 * q_size : 3 * q_size],
            pages_content[3 * q_size :],
        ]

        base_topics = []
        for q_idx in range(4):
            q_pages = quarters[q_idx] if quarters[q_idx] else pages_content
            raw_title = self._extract_quarter_topic_title(q_pages, q_idx + 1, subject_name)
            topic_label = f"Part {q_idx + 1}: {raw_title}"
            diff_level = q_idx + 1
            base_topics.append((topic_label, diff_level, "p5js", ""))

        execute_dml(
            """DELETE FROM TOPIC_PREREQUISITES 
               WHERE topic_id IN (SELECT topic_id FROM TOPICS WHERE subject_id = %s) 
                  OR prereq_topic_id IN (SELECT topic_id FROM TOPICS WHERE subject_id = %s)""",
            (subject_id, subject_id)
        )
        execute_dml("DELETE FROM TOPICS WHERE subject_id = %s", (subject_id,))

        topic_ids = []
        for name, diff, vtype, embed in base_topics:
            execute_dml(
                "INSERT INTO TOPICS (subject_id, topic_name, difficulty_level, visual_type, embed_url) VALUES (%s, %s, %s, %s, %s)",
                (subject_id, name, diff, vtype, embed)
            )
            t_row = execute_one(
                "SELECT topic_id FROM TOPICS WHERE subject_id = %s AND topic_name = %s",
                (subject_id, name)
            )
            if t_row:
                topic_ids.append(t_row["topic_id"])

        # Strictly link Part 1 -> Part 2 -> Part 3 -> Part 4
        linear_prereqs = [(1, 0, 5), (2, 1, 5), (3, 2, 5)]
        for child_idx, parent_idx, weight in linear_prereqs:
            if child_idx < len(topic_ids) and parent_idx < len(topic_ids):
                execute_dml(
                    "INSERT INTO TOPIC_PREREQUISITES (topic_id, prereq_topic_id, importance_weight) VALUES (%s, %s, %s)",
                    (topic_ids[child_idx], topic_ids[parent_idx], weight)
                )

        return topic_ids

    def process_and_index_document(
        self,
        file_bytes: bytes,
        file_name: str,
        subject_id: int,
        subject_key: str,
        uploaded_by: int = 1,
        explicit_topic_id: Optional[int] = None
    ) -> Tuple[int, int]:
        is_pdf = file_name.lower().endswith(".pdf")
        pages_content = []

        if is_pdf:
            reader = PdfReader(io.BytesIO(file_bytes))
            for page_idx, page in enumerate(reader.pages):
                try:
                    text = page.extract_text() or ""
                    if text.strip():
                        pages_content.append((page_idx + 1, text))
                except Exception:
                    continue
        else:
            text = file_bytes.decode("utf-8", errors="ignore")
            raw_lines = [l for l in text.splitlines() if l.strip()]
            step = max(1, len(raw_lines) // 4)
            for p_idx in range(4):
                chunk_slice = raw_lines[p_idx * step : (p_idx + 1) * step]
                if chunk_slice:
                    pages_content.append((p_idx + 1, "\n".join(chunk_slice)))

        if not pages_content:
            pages_content = [(1, "General Document Content")]

        sub_row = execute_one("SELECT subject_name FROM SUBJECTS WHERE subject_id = %s", (subject_id,))
        subject_title = sub_row["subject_name"] if sub_row else subject_key.replace("_", " ").title()

        existing_topics = execute_query("SELECT topic_id FROM TOPICS WHERE subject_id = %s", (subject_id,))
        needs_topics = len(existing_topics) < 4

        topic_ids = self.ensure_subject_topics(
            subject_id=subject_id,
            subject_name=subject_title,
            pages_content=pages_content,
            force_refresh=needs_topics
        )

        total_pages = len(pages_content)
        q_size = max(1, total_pages // 4)
        all_docs = []
        all_metas = []
        all_ids = []

        clean_file_id = "".join(c for c in file_name[:12] if c.isalnum() or c in "-_")
        if not clean_file_id:
            clean_file_id = "doc"

        for page_num, content in pages_content:
            clean_content = content.replace("\u25cf", "-").replace("\u2022", "-").strip()
            chunks = [clean_content] if len(clean_content) <= 1200 else self._split_text(clean_content)

            q_idx = min(3, max(0, (page_num - 1) // q_size))
            assigned_topic = explicit_topic_id or (topic_ids[q_idx] if q_idx < len(topic_ids) else topic_ids[0])

            for idx, chunk in enumerate(chunks):
                clean_chunk = chunk.strip()
                chunk_upper = clean_chunk.upper()
                is_noise = (
                    len(clean_chunk) < 35 or
                    "THANK YOU" in chunk_upper or
                    "ANY QUESTIONS" in chunk_upper or
                    "THANKS FOR YOUR ATTENTION" in chunk_upper or
                    chunk_upper.startswith("QUESTIONS?") or
                    (len(clean_chunk.split()) < 6 and "@" in clean_chunk)
                )
                if is_noise and len(chunks) > 1:
                    continue

                chunk_id = f"{subject_key}_{clean_file_id}_p{page_num}_c{idx}"

                all_docs.append(clean_chunk)
                all_ids.append(chunk_id)
                all_metas.append({
                    "subject": subject_key,
                    "subject_id": int(subject_id),
                    "topic_id": int(assigned_topic),
                    "concept_id": int(assigned_topic),
                    "part_index": int(q_idx + 1),
                    "file_name": file_name,
                    "page_number": int(page_num),
                    "chunk_index": int(idx)
                })

        if all_docs:
            vector_service.add_chunks(
                subject_key=subject_key,
                documents=all_docs,
                metadatas=all_metas,
                ids=all_ids
            )

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

        execute_dml("UPDATE SUBJECTS SET is_indexed = TRUE WHERE subject_id = %s", (subject_id,))

        return total_pages, len(all_docs)

pdf_indexer = DocumentIndexer()
document_indexer = pdf_indexer
