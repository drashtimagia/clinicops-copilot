import os
import re
import hashlib
from typing import List
from .models import DocumentChunk

class MarkdownParser:
    """
    Parses Markdown files into structured chunks based on headings.
    """
    def __init__(self):
        # A simple regex to match Markdown headings like "# Title" or "## Subtitle"
        self.heading_pattern = re.compile(r"^(#{1,3})\s+(.*)$")

    def parse_file(self, file_path: str, document_type: str) -> List[DocumentChunk]:
        """
        Reads a markdown file and splits it into chunks whenever a new heading is encountered.
        """
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return []

        file_name = os.path.basename(file_path)
        chunks = []
        
        current_section = "Intro"
        current_content = []

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                match = self.heading_pattern.match(line)
                if match:
                    # If we found a new heading, save the previous section if it has content
                    if "".join(current_content).strip():
                        chunks.append(
                            self._create_chunk(file_name, document_type, current_section, "".join(current_content))
                        )
                    
                    # Start a new section
                    current_section = match.group(2).strip()
                    current_content = [line] # Keep the heading inside the content chunk for context
                else:
                    current_content.append(line)
                    
        # Don't forget the last section
        if "".join(current_content).strip():
            chunks.append(
                self._create_chunk(file_name, document_type, current_section, "".join(current_content))
            )

        return chunks

    def _create_chunk(self, file_name: str, doc_type: str, section: str, content: str) -> DocumentChunk:
        """
        Helper to create a DocumentChunk and generate a deterministic chunk_id.
        """
        content = content.strip()
        # Create a tiny hash ID based on the file name and section title for tracking
        unique_string = f"{file_name}-{section}"
        chunk_id = hashlib.md5(unique_string.encode('utf-8')).hexdigest()[:8]
        
        return DocumentChunk(
            chunk_id=chunk_id,
            file_name=file_name,
            document_type=doc_type,
            section_title=section,
            content=content
        )
