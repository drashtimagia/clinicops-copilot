from typing import List, Dict, Any
from ai_pipeline.retrieval.embedder import embed_text
from ai_pipeline.retrieval.vector_store import VectorStore

# Global singleton store for the module
_store = VectorStore()


def get_store() -> VectorStore:
    """Returns the global vector store instance."""
    return _store


def retrieve_context(query: str) -> List[Dict[str, Any]]:
    """
    Retrieves the top 5 most relevant document chunks for a query.
    1. Embed query
    2. Search FAISS
    3. Return results
    """
    query_embedding = embed_text(query)
    if not query_embedding:
        print("[retrieve_context] Empty embedding returned — skipping search.")
        return []

    return _store.search(query_embedding, top_k=5)
