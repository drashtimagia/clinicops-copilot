from dataclasses import dataclass

@dataclass
class DocumentChunk:
    """
    Represents a parsed chunk of a document, ready for embedding.
    """
    chunk_id: str
    file_name: str
    document_type: str  # 'manual' or 'sop'
    section_title: str
    content: str
    
    def to_dict(self):
        return {
            "chunk_id": self.chunk_id,
            "file_name": self.file_name,
            "document_type": self.document_type,
            "section_title": self.section_title,
            "content": self.content
        }
