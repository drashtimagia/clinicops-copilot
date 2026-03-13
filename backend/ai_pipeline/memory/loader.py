import json
import os
from typing import List
from .models import PastIncident

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INCIDENTS_PATH = os.path.join(BASE_DIR, 'data', 'incidents', 'reports.json')

class IncidentLoader:
    """Reads historical incident logs from disk."""
    
    @staticmethod
    def load_all() -> List[PastIncident]:
        if not os.path.exists(INCIDENTS_PATH):
            print(f"Warning: Past incidents file not found at {INCIDENTS_PATH}")
            return []
            
        with open(INCIDENTS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        return [
            PastIncident(
                id=item.get("id", ""),
                timestamp=item.get("timestamp", ""),
                device=item.get("device", ""),
                description=item.get("description", ""),
                reporter=item.get("reporter", "")
            )
            for item in data
        ]
