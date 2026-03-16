import os
import re
import json
from typing import List, Dict

from ai_pipeline.retrieval.embedder import embed_text
from ai_pipeline.retrieval.retriever import get_store

# Project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MANUALS_DIR = os.path.join(BASE_DIR, 'data', 'manuals')
SOPS_DIR = os.path.join(BASE_DIR, 'data', 'sops')
INCIDENTS_FILE = os.path.join(BASE_DIR, 'data', 'incidents', 'reports.json')


def _get_device_from_filename(filename: str) -> str:
    """Infers device name from manuals/sops filenames."""
    # centrifuge-c400.md -> Centrifuge C400
    base = os.path.splitext(filename)[0]
    return base.replace('-', ' ').title()


def _chunk_text(text: str, target_min: int = 1200, target_max: int = 2000) -> List[str]:
    """
    Sub-chunks large text blocks into chunks of approx 300-500 tokens.
    Uses double-newlines (paragraphs) as primary split points.
    Heuristic: ~4 chars per token.
    """
    if len(text) <= target_max:
        return [text]

    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_length = 0

    for p in paragraphs:
        p_len = len(p)
        if current_length + p_len > target_max and current_chunk:
            # Finish current chunk
            chunks.append("\n\n".join(current_chunk))
            current_chunk = []
            current_length = 0
        
        # If a single paragraph is larger than target_max, split it by newlines or sentences (simplified)
        if p_len > target_max:
            # For simplicity, split by sentence-like boundaries if a paragraph is huge
            sub_splits = re.split(r'(?<=[.!?])\s+', p)
            for s in sub_splits:
                if current_length + len(s) > target_max and current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_length = 0
                current_chunk.append(s)
                current_length += len(s)
        else:
            current_chunk.append(p)
            current_length += p_len
    
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    
    return chunks


def _parse_markdown(file_path: str, document_type: str) -> List[dict]:
    """Splits markdown into logical sections, then sub-chunks to target token sizes."""
    heading_pattern = re.compile(r"^(#{1,3})\s+(.*)$")
    file_name = os.path.basename(file_path)
    device = _get_device_from_filename(file_name)
    
    sections = []
    current_section = "Intro"
    current_content: List[str] = []

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = heading_pattern.match(line)
            if match:
                if "".join(current_content).strip():
                    sections.append({
                        "text": "".join(current_content).strip(),
                        "section": current_section
                    })
                current_section = match.group(2).strip()
                current_content = [line]
            else:
                current_content.append(line)

    if "".join(current_content).strip():
        sections.append({
            "text": "".join(current_content).strip(),
            "section": current_section
        })

    # Final chunking pass
    final_chunks = []
    for sec in sections:
        sub_chunks = _chunk_text(sec["text"])
        for chunk_text in sub_chunks:
            final_chunks.append({
                "text": chunk_text,
                "source": f"{file_name} > {sec['section']}",
                "document_type": document_type,
                "device": device
            })

    return final_chunks


def _load_directory(directory: str, doc_type: str) -> List[dict]:
    chunks = []
    if not os.path.exists(directory):
        return chunks
    for filename in os.listdir(directory):
        if filename.endswith(".md"):
            fp = os.path.join(directory, filename)
            chunks.extend(_parse_markdown(fp, doc_type))
    return chunks


def _load_incidents() -> List[dict]:
    if not os.path.exists(INCIDENTS_FILE):
        return []

    with open(INCIDENTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    chunks = []
    for item in data:
        content = (
            f"Incident ID: {item.get('id', 'N/A')}\n"
            f"Device: {item.get('device', 'Unknown')}\n"
            f"Reporter: {item.get('reporter', 'Unknown')}\n"
            f"Description: {item.get('description', '')}"
        )
        # Incident reports are usually small, but we chunk just in case
        for sub in _chunk_text(content):
            chunks.append({
                "text": sub,
                "source": "reports.json",
                "document_type": "incident",
                "device": item.get('device', 'Unknown')
            })
    return chunks


def ingest_all_to_store():
    """Loads all data, embeds it, and populates the FAISS store."""
    print("[Ingest] Starting ingestion...")
    raw_chunks = []
    raw_chunks.extend(_load_directory(MANUALS_DIR, "manual"))
    raw_chunks.extend(_load_directory(SOPS_DIR, "sop"))
    raw_chunks.extend(_load_incidents())

    if not raw_chunks:
        print("[Ingest] No data found to ingest.")
        return

    texts = [c["text"] for c in raw_chunks]
    sources = [c["source"] for c in raw_chunks]
    doc_types = [c["document_type"] for c in raw_chunks]
    devices = [c["device"] for c in raw_chunks]

    print(f"[Ingest] Embedding {len(texts)} chunks...")
    embeddings = []
    for i, text in enumerate(texts):
        if i % 10 == 0 and i > 0:
            print(f"  Embedded {i}/{len(texts)}...")
        emb = embed_text(text)
        embeddings.append(emb)

    # Filter out any failed embeddings
    valid_indices = [i for i, e in enumerate(embeddings) if e]
    
    filtered_texts = [texts[i] for i in valid_indices]
    filtered_embs = [embeddings[i] for i in valid_indices]
    filtered_sources = [sources[i] for i in valid_indices]
    filtered_doc_types = [doc_types[i] for i in valid_indices]
    filtered_devices = [devices[i] for i in valid_indices]

    store = get_store()
    store.add(
        texts=filtered_texts,
        embeddings=filtered_embs,
        sources=filtered_sources,
        doc_types=filtered_doc_types,
        devices=filtered_devices
    )
    print(f"[Ingest] Successfully indexed {len(filtered_texts)} chunks in FAISS.")
