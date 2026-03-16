import faiss
import numpy as np
from typing import List, Dict, Any


class VectorStore:
    """
    FAISS-based vector store for document chunks and metadata.
    Stores: text, source, document_type, device.
    """

    def __init__(self, dimension: int = 1024):
        self.index = faiss.IndexFlatIP(dimension)  # Inner Product for Cosine Similarity (with normalized vectors)
        self.metadata: List[Dict[str, Any]] = []

    def add(self, texts: List[str], embeddings: List[List[float]], 
            sources: List[str], doc_types: List[str], devices: List[str]):
        """
        Adds multiple vectors and their corresponding metadata to the store.
        """
        if not embeddings:
            return

        # FAISS expects float32 numpy arrays
        vectors = np.array(embeddings).astype('float32')
        
        # Normalize vectors for cosine similarity if using IndexFlatIP
        faiss.normalize_L2(vectors)
        
        self.index.add(vectors)
        
        # Store metadata
        for i in range(len(texts)):
            self.metadata.append({
                "text": texts[i],
                "source": sources[i],
                "document_type": doc_types[i],
                "device": devices[i]
            })

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Searches the index and returns top_k results with metadata.
        """
        if self.index.ntotal == 0 or not query_embedding:
            return []

        # Prepare query vector
        query_vec = np.array([query_embedding]).astype('float32')
        faiss.normalize_L2(query_vec)

        # Search
        distances, indices = self.index.search(query_vec, top_k)

        results = []
        for i, idx in enumerate(indices[0]):
            if idx == -1:
                continue
            
            res = self.metadata[idx].copy()
            res["score"] = float(distances[0][i])
            results.append(res)
            
        return results
