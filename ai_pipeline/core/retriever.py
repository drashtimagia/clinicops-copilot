import json
import os
from typing import List, Dict

# Paths to the mock data files
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOPS_PATH = os.path.join(BASE_DIR, 'mock_data', 'sops.json')
INCIDENTS_PATH = os.path.join(BASE_DIR, 'mock_data', 'past_incidents.json')

class Retriever:
    def __init__(self):
        self.sops = self._load_json(SOPS_PATH)
        self.incidents = self._load_json(INCIDENTS_PATH)
        
    def _load_json(self, path: str) -> List[Dict]:
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load data from {path}: {e}")
            return []

    def get_context(self, query: str) -> Dict[str, List[Dict]]:
        """
        Mock implementation of a retrieval step.
        In a real scenario, this would embed the query and perform a vector search
        against an OpenSearch or Pinecone index.
        Here we use simple keyword matching for demo reliability.
        """
        query_lower = query.lower()
        
        # Simple keyword matching
        relevant_sops = [
            sop for sop in self.sops 
            if any(word in sop.get('title', '').lower() or word in sop.get('content', '').lower() for word in query_lower.split())
        ][:2] # Return top 2
        
        relevant_incidents = [
            inc for inc in self.incidents
            if any(word in inc.get('device', '').lower() or word in inc.get('issue', '').lower() for word in query_lower.split())
        ][:2] # Return top 2
        
        # Fallback if no keywords match perfectly
        if not relevant_sops and self.sops:
            relevant_sops = [self.sops[0]]
            
        if not relevant_incidents and self.incidents:
            relevant_incidents = [self.incidents[0]]

        return {
            "sops": relevant_sops,
            "past_incidents": relevant_incidents
        }
