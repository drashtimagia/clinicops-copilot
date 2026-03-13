import os
import json
from ai_pipeline.data_ingestion.parser import MarkdownParser
from ai_pipeline.data_ingestion.ingest import process_directory, MANUALS_DIR, SOPS_DIR
from ai_pipeline.retrieval.service import RetrievalService

def load_all_chunks():
    """Helper to reuse our ingestion logic."""
    parser = MarkdownParser()
    chunks = []
    chunks.extend(process_directory(MANUALS_DIR, "manual", parser))
    chunks.extend(process_directory(SOPS_DIR, "sop", parser))
    return chunks

def main():
    print("=========================================")
    print(" ClinicOps Copilot - Retrieval Evaluation ")
    print("=========================================\n")
    
    # 1. Ingest Data
    chunks = load_all_chunks()
    if not chunks:
        print("No chunks found. Ensure data/ directories are populated.")
        return
        
    # 2. Initialize Retrieval Service
    # Note: If USE_MOCK_MODEL=1 in .env, this defaults to the local baseline sparse-dense embedder.
    retrieval_service = RetrievalService(chunks)
    
    # 3. Test queries
    test_queries = [
        "The centrifuge E-04 error popped up and the lid is stuck.",
        "A biohazard spill happened, blood is inside the centrifuge.",
        "The Vitals monitor battery is completely dead."
    ]
    
    print("\n" + "-"*40)
    for i, query in enumerate(test_queries, 1):
        print(f"\nQUERY {i}: '{query}'")
        
        results = retrieval_service.search(query, top_k=2)
        
        for rank, (chunk, score) in enumerate(results, 1):
            print(f"  [Match {rank} | Score: {score:.3f}]")
            print(f"  Source: {chunk.file_name} -> {chunk.section_title}")
            # Snippet the content
            snippet = chunk.content[:100].replace('\n', ' ') + "..."
            print(f"  Content: {snippet}\n")

if __name__ == "__main__":
    main()
