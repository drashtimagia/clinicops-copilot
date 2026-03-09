from typing import List, Tuple
from .interfaces import VectorStore
from ai_pipeline.data_ingestion.models import DocumentChunk
import math

class SimpleMemoryVectorStore(VectorStore):
    """
    An in-memory vector store that uses pure Python cosine similarity.
    Perfect for hackathons where documents < 10,000 chunks and avoiding 
    heavy dependencies (like faiss or pinecone) is desired.
    """
    def __init__(self):
        self.chunks: List[DocumentChunk] = []
        self.embeddings: List[List[float]] = []

    def add_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]):
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings.")
        
        self.chunks.extend(chunks)
        self.embeddings.extend(embeddings)

    def search(self, query_embedding: List[float], top_k: int = 3) -> List[Tuple[DocumentChunk, float]]:
        if not self.chunks or not query_embedding:
            return []
            
        scored_chunks = []
        for chunk, chunk_embedding in zip(self.chunks, self.embeddings):
            score = self._cosine_similarity(query_embedding, chunk_embedding)
            scored_chunks.append((chunk, score))
            
        # Sort by score descending
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        return scored_chunks[:top_k]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Pure python cosine similarity. O(N) where N is vector length.
        """
        if len(vec1) != len(vec2):
            return 0.0
            
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        mag1 = sum(a * a for a in vec1) ** 0.5
        mag2 = sum(b * b for b in vec2) ** 0.5
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
            
        return dot_product / (mag1 * mag2)
