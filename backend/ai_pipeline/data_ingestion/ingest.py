import os
import json
from .parser import MarkdownParser
from .models import DocumentChunk
from typing import List

# Set base paths assuming the caller is running from the repository root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANUALS_DIR = os.path.join(BASE_DIR, 'data', 'manuals')
SOPS_DIR = os.path.join(BASE_DIR, 'data', 'sops')

def process_directory(directory: str, doc_type: str, parser: MarkdownParser) -> List[DocumentChunk]:
    chunks = []
    if not os.path.exists(directory):
        print(f"Warning: Directory {directory} does not exist.")
        return chunks

    for filename in os.listdir(directory):
        if filename.endswith(".md"):
            filepath = os.path.join(directory, filename)
            file_chunks = parser.parse_file(filepath, doc_type)
            chunks.extend(file_chunks)
            print(f"Parsed {len(file_chunks)} chunks from {filename}")
            
    return chunks

def main():
    print("==============================================")
    print(" ClinicOps Copilot - Document Ingestion CLI ")
    print("==============================================\n")
    
    parser = MarkdownParser()
    all_chunks: List[DocumentChunk] = []
    
    print(f"-> Ingesting Manuals from: data/manuals/")
    all_chunks.extend(process_directory(MANUALS_DIR, "manual", parser))
    
    print(f"\n-> Ingesting SOPs from: data/sops/")
    all_chunks.extend(process_directory(SOPS_DIR, "sop", parser))
    
    print(f"\nTotal chunks generated: {len(all_chunks)}")
    
    if all_chunks:
        print("\n--- SAMPLE CHUNKS (Top 3) ---\n")
        # Print the first three chunks as formatted JSON for verification
        sample_dicts = [chunk.to_dict() for chunk in all_chunks[:3]]
        print(json.dumps(sample_dicts, indent=2))
        
if __name__ == "__main__":
    main()
