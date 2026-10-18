import chromadb
from typing import List, Dict, Optional
from backend.config import settings

class VectorStoreService:
    def __init__(self, persist_directory: str = settings.CHROMA_PERSIST_DIR):
        self.client = chromadb.PersistentClient(path=persist_directory)

    def _get_collection_name(self, subject_key: str) -> str:
        clean_key = subject_key.strip().lower().replace("-", "_")
        return f"chroma_{clean_key}"

    def get_or_create_collection(self, subject_key: str):
        col_name = self._get_collection_name(subject_key)
        return self.client.get_or_create_collection(
            name=col_name,
            metadata={"hnsw:space": "cosine", "subject": subject_key}
        )

    # 1. Create (Add Chunks)
    def add_chunks(
        self,
        subject_key: str,
        documents: List[str],
        metadatas: List[Dict],
        ids: List[str]
    ) -> int:
        col = self.get_or_create_collection(subject_key)
        col.add(documents=documents, metadatas=metadatas, ids=ids)
        return len(ids)

    # 2. Read (Semantic Top-K Search)
    def search(
        self,
        subject_key: str,
        query_text: str,
        n_results: int = 4,
        where_filter: Optional[Dict] = None
    ) -> List[Dict]:
        col = self.get_or_create_collection(subject_key)
        kwargs = {
            "query_texts": [query_text],
            "n_results": min(n_results, max(1, col.count()))
        }
        if where_filter:
            kwargs["where"] = where_filter

        results = col.query(**kwargs)
        formatted = []
        if results and results.get("documents"):
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            ids = results["ids"][0] if results.get("ids") else [""] * len(docs)
            dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)

            for i in range(len(docs)):
                formatted.append({
                    "id": ids[i],
                    "document": docs[i],
                    "metadata": metas[i],
                    "distance": dists[i],
                    "similarity": round(1.0 - dists[i], 4)
                })
        return formatted

    # 3. Update (Modify Chunk Content & Metadata)
    def update_chunk(
        self,
        subject_key: str,
        chunk_id: str,
        new_text: str,
        new_metadata: Optional[Dict] = None
    ) -> bool:
        col = self.get_or_create_collection(subject_key)
        kwargs = {
            "ids": [chunk_id],
            "documents": [new_text]
        }
        if new_metadata:
            kwargs["metadatas"] = [new_metadata]
        col.update(**kwargs)
        return True

    # 4. Delete (Remove Chunks by IDs or Metadata Filter)
    def delete_chunks(
        self,
        subject_key: str,
        ids: Optional[List[str]] = None,
        where_filter: Optional[Dict] = None
    ) -> int:
        col = self.get_or_create_collection(subject_key)
        count_before = col.count()

        if ids:
            col.delete(ids=ids)
        elif where_filter:
            col.delete(where=where_filter)
        else:
            raise ValueError("Specify ids or where_filter for deletion.")

        count_after = col.count()
        return count_before - count_after

    def delete_collection(self, subject_key: str) -> bool:
        col_name = self._get_collection_name(subject_key)
        try:
            self.client.delete_collection(col_name)
            return True
        except Exception:
            return False

    # Stats & Diagnostics
    def get_stats(self, subject_key: str) -> Dict:
        col = self.get_or_create_collection(subject_key)
        return {
            "collection_name": col.name,
            "total_chunks": col.count(),
            "metadata": col.metadata
        }

    def list_collections(self) -> List[Dict]:
        cols = self.client.list_collections()
        return [{"name": c.name, "count": c.count()} for c in cols]

vector_service = VectorStoreService()
