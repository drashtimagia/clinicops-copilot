from abc import ABC, abstractmethod
from typing import List, Tuple
from ai_pipeline.data_ingestion.models import DocumentChunk

class EmbeddingProvider(ABC):
    """
    Abstract interface for embedding text into dense vectors.
    """
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """
        Convert a string into a list of floats representing its semantic meaning.
        """
        pass

class VectorStore(ABC):
    """
    Abstract interface for storing and retrieving DocumentChunks by vector similarity.
    """
    @abstractmethod
    def add_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]):
        """
        Store the given chunks and their corresponding embeddings.
        """
        pass

    @abstractmethod
    def search(self, query_embedding: List[float], top_k: int = 3) -> List[Tuple[DocumentChunk, float]]:
        """
        Find the top_k most similar chunks to the query_embedding.
        Returns a list of tuples containing the chunk and its similarity score.
        """
        pass
