from dataclasses import dataclass
from typing import List

@dataclass
class Citation:
    source_id: str
    relevance_snippet: str

@dataclass
class PipelineResponse:
    next_best_action: str
    escalate: bool
    confidence_score: float
    citations: List[Citation]
    
    def to_dict(self):
        return {
            "next_best_action": self.next_best_action,
            "escalate": self.escalate,
            "confidence_score": self.confidence_score,
            "citations": [{"source_id": c.source_id, "snippet": c.relevance_snippet} for c in self.citations]
        }
