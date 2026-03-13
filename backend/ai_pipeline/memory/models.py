from dataclasses import dataclass
from typing import List, Optional

@dataclass
class PastIncident:
    """Represents a single historical incident report."""
    id: str
    timestamp: str
    device: str
    description: str
    reporter: str

@dataclass
class MemoryMatchResult:
    """Result of searching the Incident Memory Layer."""
    similar_incidents: List[PastIncident]
    bias_escalation: bool
    reasoning: str
    
    def to_dict(self):
        return {
            "similar_incidents": [{"id": i.id, "device": i.device, "description": i.description} for i in self.similar_incidents],
            "bias_escalation": self.bias_escalation,
            "reasoning": self.reasoning
        }
