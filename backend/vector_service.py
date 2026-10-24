import chromadb
from typing import List, Dict, Optional, Any
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
        ids: List[str],
        batch_size: int = 100
    ) -> int:
        col = self.get_or_create_collection(subject_key)
        total = len(ids)
        for i in range(0, total, batch_size):
            end = min(i + batch_size, total)
            col.upsert(
                documents=documents[i:end],
                metadatas=metadatas[i:end],
                ids=ids[i:end]
            )
        return total

    # 2. Read (Semantic Top-K Search)
    def search(
        self,
        subject_key: str,
        query_text: str,
        n_results: int = 4,
        where_filter: Optional[Dict] = None
    ) -> List[Dict]:
        col_name = self._get_collection_name(subject_key)
        try:
            col = self.client.get_collection(col_name)
        except Exception:
            return []

        if col.count() == 0:
            return []

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

    # 4. Delete (Remove Chunks by IDs or Filter)
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

    def clear_collection(self, subject_key: str) -> int:
        col_name = self._get_collection_name(subject_key)
        try:
            col = self.client.get_collection(col_name)
            count = col.count()
            self.client.delete_collection(col_name)
            # Recreate clean empty collection with same metadata
            self.client.get_or_create_collection(
                name=col_name,
                metadata={"hnsw:space": "cosine", "subject": subject_key}
            )
            return count
        except Exception:
            return 0

    def clear_all_vectors(self) -> Dict[str, Any]:
        cols = self.client.list_collections()
        total_chunks = 0
        cleared_names = []
        for col in cols:
            try:
                count = col.count()
                total_chunks += count
                cleared_names.append(col.name)
                self.client.delete_collection(col.name)
            except Exception:
                pass
        return {
            "total_chunks_deleted": total_chunks,
            "collections_cleared": cleared_names,
            "total_collections": len(cleared_names)
        }

    def get_stats(self, subject_key: str) -> Dict:
        col_name = self._get_collection_name(subject_key)
        try:
            col = self.client.get_collection(col_name)
            return {
                "collection_name": col.name,
                "total_chunks": col.count(),
                "metadata": col.metadata
            }
        except Exception:
            return {
                "collection_name": col_name,
                "total_chunks": 0,
                "metadata": {}
            }

    def list_collections(self) -> List[Dict]:
        cols = self.client.list_collections()
        return [{"name": c.name, "count": c.count()} for c in cols]

    def get_chunks(self, subject_key: str, limit: int = 50) -> List[Dict]:
        col_name = self._get_collection_name(subject_key)
        try:
            col = self.client.get_collection(col_name)
        except Exception:
            return []
        res = col.get(limit=limit)
        items = []
        if res and res.get("documents"):
            docs = res["documents"]
            metas = res.get("metadatas") or [{}] * len(docs)
            ids = res.get("ids") or [""] * len(docs)
            for i in range(len(docs)):
                items.append({
                    "id": ids[i],
                    "document": docs[i],
                    "metadata": metas[i] if i < len(metas) and metas[i] else {}
                })
        return items

vector_service = VectorStoreService()
