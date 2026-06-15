import os
import sys
import pickle
import numpy as np
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
COLLECTION_NAME = "maintenance_knowledge"

class VectorStore:
    """
    Lightweight numpy-backed vector store for maintenance knowledge documents.
    Uses SentenceTransformer embeddings for semantic search.
    (Replaces ChromaDB due to C++ build tool requirements on Windows)
    """

    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
            print(f"[VectorStore] Loading embedding model: {EMBEDDING_MODEL}")
            self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
            print(f"[VectorStore] Embedding model loaded successfully.")
        except ImportError:
            raise ImportError(
                "sentence_transformers is not installed. "
                "Run: pip install sentence-transformers"
            )

        os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
        self.db_path = os.path.join(CHROMA_PERSIST_DIR, f"{COLLECTION_NAME}.pkl")
        self.documents = []
        self.embeddings = []
        self.metadatas = []
        
        self._load_db()

    def _load_db(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "rb") as f:
                    data = pickle.load(f)
                    self.documents = data.get("documents", [])
                    self.embeddings = data.get("embeddings", [])
                    self.metadatas = data.get("metadatas", [])
                print(f"[VectorStore] Loaded {len(self.documents)} documents from {self.db_path}")
            except Exception as e:
                print(f"[VectorStore] Failed to load db: {e}. Starting fresh.")

    def _save_db(self):
        try:
            with open(self.db_path, "wb") as f:
                pickle.dump({
                    "documents": self.documents,
                    "embeddings": self.embeddings,
                    "metadatas": self.metadatas
                }, f)
        except Exception as e:
            print(f"[VectorStore] Failed to save db: {e}")

    def add_documents(self, docs: list) -> None:
        if not docs:
            return

        try:
            texts = [d["text"] for d in docs]
            metadatas = []
            for d in docs:
                meta = dict(d.get("metadata", {}))
                meta["source"] = d.get("source", "unknown")
                meta["chunk_id"] = d.get("chunk_id", "unknown")
                metadatas.append(meta)

            print(f"[VectorStore] Encoding {len(texts)} docs...")
            embeddings = self.embedding_model.encode(texts, show_progress_bar=False).tolist()

            self.documents.extend(texts)
            self.embeddings.extend(embeddings)
            self.metadatas.extend(metadatas)
            
            self._save_db()
            print(f"[VectorStore] Successfully added {len(texts)} document chunks.")

        except Exception as e:
            raise RuntimeError(f"[VectorStore] Failed to add documents: {e}")

    def search(self, query: str, top_k: int = 5) -> list:
        if not query or not query.strip() or not self.embeddings:
            return []

        try:
            query_embedding = self.embedding_model.encode([query], show_progress_bar=False)[0]
            
            # Compute cosine similarity
            a = np.array(query_embedding)
            b = np.array(self.embeddings)
            
            # dot product
            dot = np.dot(b, a)
            # norms
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b, axis=1)
            
            similarities = dot / (norm_a * norm_b + 1e-9)
            
            # Get top k indices
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            output = []
            for idx in top_indices:
                output.append({
                    "text": self.documents[idx],
                    "source": self.metadatas[idx].get("source", "unknown"),
                    "score": round(float(similarities[idx]), 4),
                    "metadata": self.metadatas[idx],
                })

            return output

        except Exception as e:
            raise RuntimeError(f"[VectorStore] Search failed for query '{query}': {e}")

    def get_collection_stats(self) -> dict:
        return {
            "total_documents": len(self.documents),
            "collection_name": COLLECTION_NAME,
            "embedding_model": EMBEDDING_MODEL,
        }

    def reset_collection(self) -> None:
        self.documents = []
        self.embeddings = []
        self.metadatas = []
        self._save_db()
        print(f"[VectorStore] Collection '{COLLECTION_NAME}' has been reset.")

if __name__ == "__main__":
    vs = VectorStore()
    print("Stats:", vs.get_collection_stats())
