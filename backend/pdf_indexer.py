import io
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

    def _match_concept_id(self, chunk_text: str, subject_id_or_topics) -> Optional[int]:
        if isinstance(subject_id_or_topics, list):
            topics = subject_id_or_topics
        else:
            topics = execute_query(
                "SELECT topic_id, topic_name FROM TOPICS WHERE subject_id = %s",
                (subject_id_or_topics,)
            )
        text_lower = chunk_text.lower()
        for t in topics:
            if t["topic_name"].lower() in text_lower:
                return t["topic_id"]
        if topics:
            return topics[0]["topic_id"]
        return None

    def ensure_subject_topics(self, subject_id: int, subject_name: str, document_sample: str = "") -> List[int]:
        topics = execute_query(
            "SELECT topic_id, topic_name FROM TOPICS WHERE subject_id = %s",
            (subject_id,)
        )
        if topics:
            return [t["topic_id"] for t in topics]

        combined_lower = f"{subject_name} {document_sample}".lower()

        if any(k in combined_lower for k in ["mechanical", "prime mover", "energy resources", "turbine", "lathe", "machining", "robotics", "ic engine", "welding"]):
            base_topics = [
                ("Energy Resources & Renewable Solar/Wind Systems", 1, "p5js", ""),
                ("Engineering Materials, Alloys & Composites", 1, "p5js", ""),
                ("Prime Movers: Steam, Gas & Water Turbines", 2, "p5js", ""),
                ("Internal Combustion Engines: Petrol & Diesel Cycles", 2, "p5js", ""),
                ("Manufacturing Processes, Lathe Operations & Machining", 3, "p5js", ""),
                ("Joining Processes: Welding, Brazing & Fasteners", 3, "p5js", ""),
                ("Robotics Anatomy, Joint Configurations & Automation", 4, "p5js", "")
            ]
            prereq_pairs = [
                (2, 0, 5), # Prime Movers requires Energy Resources
                (3, 0, 5), # IC Engines requires Energy Resources
                (4, 1, 5), # Manufacturing requires Engineering Materials
                (5, 1, 4), # Joining Processes requires Engineering Materials
                (6, 4, 4), # Robotics requires Manufacturing & Machining
                (6, 2, 3)  # Robotics requires Prime Movers
            ]
        elif any(k in combined_lower for k in ["big data", "hadoop", "spark", "mapreduce", "hdfs"]):
            base_topics = [
                ("Big Data Ecosystem: The 3Vs & Ingestion Pipelines", 1, "p5js", ""),
                ("Distributed Storage Architecture: HDFS & Data Nodes", 2, "p5js", ""),
                ("Parallel Processing Engine: MapReduce & Shuffle Sort", 2, "p5js", ""),
                ("Distributed Analytical Engines: Apache Spark & Stream Analytics", 3, "p5js", ""),
                ("NoSQL Storage & CAP Theorem Fault Tolerance", 3, "p5js", "")
            ]
            prereq_pairs = [(1, 0, 5), (2, 1, 5), (3, 2, 4), (4, 1, 4)]
        elif any(k in combined_lower for k in ["quantum", "qubit", "superposition"]):
            base_topics = [
                ("Qubits & Quantum Superposition Principles", 1, "p5js", ""),
                ("Quantum Logic Gates & Entanglement Circuits", 2, "p5js", ""),
                ("Quantum Algorithms: Grover & Shor Speedup", 2, "p5js", ""),
                ("Fault-Tolerant Quantum Error Correction & Decoherence", 3, "p5js", "")
            ]
            prereq_pairs = [(1, 0, 5), (2, 1, 4), (3, 1, 5)]
        elif any(k in combined_lower for k in ["machine learning", "deep learning", "neural"]):
            base_topics = [
                ("Statistical Foundations & Linear Classifiers", 1, "p5js", ""),
                ("Neural Architectures & Backpropagation Dynamics", 2, "p5js", ""),
                ("Optimization, Loss Landscapes & Regularization", 2, "p5js", ""),
                ("Deep Representation Learning & Inference Engines", 3, "p5js", "")
            ]
            prereq_pairs = [(1, 0, 5), (2, 1, 4), (3, 2, 5)]
        else:
            import re
            found_units = re.findall(r'(?:Unit|Module|Chapter)\s*[-:]?\s*(\d+)?\s*[-:]?\s*([A-Za-z0-9 ,&/\-]{4,50})', document_sample)
            if len(found_units) >= 3:
                base_topics = []
                for idx, u in enumerate(found_units[:6]):
                    t_name = u[1].strip().title()
                    diff = min(4, 1 + idx // 2)
                    base_topics.append((t_name, diff, "p5js", ""))
                prereq_pairs = [(i + 1, i, 4) for i in range(len(base_topics) - 1)]
            else:
                clean_name = subject_name.replace("_", " ").strip().title()
                base_topics = [
                    (f"{clean_name}: Fundamental Concepts & Core Principles", 1, "p5js", ""),
                    (f"{clean_name}: Structural Models & Analytical Methods", 2, "p5js", ""),
                    (f"{clean_name}: Dynamic Processes & System Behavior", 2, "p5js", ""),
                    (f"{clean_name}: Advanced Synthesis & Optimization", 3, "p5js", "")
                ]
                prereq_pairs = [(1, 0, 5), (2, 1, 4), (3, 2, 4)]

        topic_ids = []
        for name, diff, vtype, embed in base_topics:
            execute_dml(
                "INSERT INTO TOPICS (subject_id, topic_name, difficulty_level, visual_type, embed_url) VALUES (%s, %s, %s, %s, %s)",
                (subject_id, name, diff, vtype, embed)
            )
            t_row = execute_one("SELECT topic_id FROM TOPICS WHERE subject_id = %s AND topic_name = %s", (subject_id, name))
            if t_row:
                topic_ids.append(t_row["topic_id"])

        for child_idx, parent_idx, weight in prereq_pairs:
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
            if text.strip():
                pages_content.append((1, text))

        sub_row = execute_one("SELECT subject_name FROM SUBJECTS WHERE subject_id = %s", (subject_id,))
        subject_title = sub_row["subject_name"] if sub_row else subject_key.replace("_", " ").title()
        doc_sample = " ".join([p[1] for p in pages_content[:15]])
        self.ensure_subject_topics(subject_id, subject_title, document_sample=doc_sample)

        total_pages = len(pages_content)
        all_docs = []
        all_metas = []
        all_ids = []

        cached_topics = execute_query(
            "SELECT topic_id, topic_name FROM TOPICS WHERE subject_id = %s",
            (subject_id,)
        )

        clean_file_id = "".join(c for c in file_name[:12] if c.isalnum() or c in "-_")
        if not clean_file_id:
            clean_file_id = "doc"

        for page_num, content in pages_content:
            clean_content = content.replace("\u25cf", "-").replace("\u2022", "-").strip()
            # If content is concise (standard slide format), keep as 1 chunk; otherwise split
            chunks = [clean_content] if len(clean_content) <= 1200 else self._split_text(clean_content)
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
                assigned_topic = explicit_topic_id or self._match_concept_id(clean_chunk, cached_topics) or 0

                all_docs.append(clean_chunk)
                all_ids.append(chunk_id)
                all_metas.append({
                    "subject": subject_key,
                    "subject_id": int(subject_id),
                    "topic_id": int(assigned_topic),
                    "concept_id": int(assigned_topic),
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

# Backward compatibility alias
pdf_indexer = DocumentIndexer()
document_indexer = pdf_indexer
