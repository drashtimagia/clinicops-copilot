from typing import List, Tuple
from ai_pipeline.data_ingestion.models import DocumentChunk
from .interfaces import EmbeddingProvider, VectorStore
from .providers import BedrockNovaProvider, BaselineLocalProvider
from .store import SimpleMemoryVectorStore
from ai_pipeline.config import config

class RetrievalService:
    """
    High-level abstraction that coordinates generating embeddings 
    and searching the vector store.
    """
    def __init__(self, chunks: List[DocumentChunk] = None):
        if config.MOCK_LLM_RESPONSE:
            print("[RetrievalService] Initializing Baseline Local Provider (USE_MOCK_MODEL=1)")
            self.provider: EmbeddingProvider = BaselineLocalProvider()
        else:
            print(f"[RetrievalService] Initializing Bedrock Nova Provider: {config.NOVA_EMBED_MODEL_ID}")
            self.provider: EmbeddingProvider = BedrockNovaProvider()
            
        self.store: VectorStore = SimpleMemoryVectorStore()
        
        # Optionally pre-fill the store on init
        if chunks:
            self.index_documents(chunks)

    def index_documents(self, chunks: List[DocumentChunk]):
        """
        Embed and store a list of document chunks.
        """
        print(f"Indexing {len(chunks)} chunks...")
        embeddings = []
        for chunk in chunks:
            # We embed the section title plus the content for maximum context
            text_to_embed = f"{chunk.section_title}\n{chunk.content}"
            embedding = self.provider.embed_text(text_to_embed)
            embeddings.append(embedding)
            
        self.store.add_chunks(chunks, embeddings)
        print("Indexing complete.")

    def search(self, query: str, top_k: int = 3) -> List[Tuple[DocumentChunk, float]]:
        """
        Search for the most relevant chunks given a text query.
        """
        query_embedding = self.provider.embed_text(query)
        return self.store.search(query_embedding, top_k)
