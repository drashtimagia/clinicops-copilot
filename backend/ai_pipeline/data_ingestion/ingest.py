import os
import json
from .parser import MarkdownParser
from .models import DocumentChunk
from typing import List

# BASE_DIR = project root (4 levels up from backend/ai_pipeline/data_ingestion/ingest.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MANUALS_DIR = os.path.join(BASE_DIR, 'data', 'manuals')
SOPS_DIR = os.path.join(BASE_DIR, 'data', 'sops')
INCIDENTS_FILE = os.path.join(BASE_DIR, 'data', 'incidents', 'reports.json')

def load_incidents_as_chunks() -> List[DocumentChunk]:
    """
    Reads data/incidents/reports.json and converts each entry into a DocumentChunk
    so historical incidents can be embedded and retrieved via the vector store.
    """
    if not os.path.exists(INCIDENTS_FILE):
        print(f"Warning: Incidents file not found at {INCIDENTS_FILE}")
        return []

    with open(INCIDENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    chunks = []
    for item in data:
        content = (
            f"Incident ID: {item.get('id', 'N/A')}\n"
            f"Device: {item.get('device', 'Unknown')}\n"
            f"Reporter: {item.get('reporter', 'Unknown')}\n"
            f"Timestamp: {item.get('timestamp', 'Unknown')}\n"
            f"Description: {item.get('description', '')}"
        )
        chunk = DocumentChunk(
            chunk_id=item.get('id', f'incident-{len(chunks)}'),
            file_name="incidents/reports.json",
            section_title=item.get('id', 'Unknown Incident'),
            content=content,
            document_type="incident"
        )
        chunks.append(chunk)

    print(f"Loaded {len(chunks)} historical incident chunks from reports.json")
    return chunks

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
