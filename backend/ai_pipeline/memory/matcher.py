import re
from typing import List
from .models import PastIncident, MemoryMatchResult
from .loader import IncidentLoader

class MemoryMatcher:
    """
    Implements a deterministic hybrid strategy to detect recurring issues
    prior to the main AI LLM call.
    """
    def __init__(self):
        self.past_incidents = IncidentLoader.load_all()
        # Common patterns. In production, these might be pulled from a config list.
        self.serial_pattern = re.compile(r'\b([A-Z0-9]{3,}-\d{3,})\b', re.IGNORECASE)
        self.error_pattern = re.compile(r'\b(E-\d{2,})\b', re.IGNORECASE)

    def analyze_incident(self, input_text: str) -> MemoryMatchResult:
        if not self.past_incidents:
            return MemoryMatchResult([], False, "No historical incidents loaded.")

        input_lower = input_text.lower()
        
        # 1. Extract Identifiers
        extracted_serials = set(self.serial_pattern.findall(input_text))
        extracted_errors = set(self.error_pattern.findall(input_text))
        
        matches: List[PastIncident] = []
        is_exact_serial_match = False
        
        # 2. Hard Filtering (Exact matches)
        for inc in self.past_incidents:
            inc_device_lower = inc.device.lower()
            inc_desc_lower = inc.description.lower()
            
            # Check Serial Match
            has_serial_match = any(serial.lower() in inc_device_lower or serial.lower() in inc_desc_lower for serial in extracted_serials)
            
            # Check Error Code Match
            has_error_match = any(err.lower() in inc_desc_lower for err in extracted_errors)
            
            # 3. Soft Filtering (Same device family + very similar description)
            # This is naive text overlap. In a full product, this could use the VectorStore we just built.
            words = set(re.findall(r'\b\w{4,}\b', input_lower))
            inc_words = set(re.findall(r'\b\w{4,}\b', inc_desc_lower))
            overlap = len(words.intersection(inc_words))
            
            if has_serial_match:
                matches.append(inc)
                is_exact_serial_match = True
            elif has_error_match:
                matches.append(inc)
            elif overlap >= 3: # Arbitrary heuristic for hackathon matching
                matches.append(inc)

        # 4. Scoring & Thresholding for Escalation
        bias_escalation = False
        reasoning = "Incident is isolated or does not meet threshold for escalation bias."
        
        if len(matches) >= 2:
            if is_exact_serial_match:
                bias_escalation = True
                reasoning = f"CRITICAL: Found {len(matches)} highly similar prior incidents matching the exact serial number. Strongly bias toward escalation."
            else:
                bias_escalation = False
                reasoning = f"Found {len(matches)} similar prior incidents for this device class, but no exact serial match. Evaluate standard SOPs."
                
        elif matches:
            reasoning = "Found 1 related prior incident. Monitor for potential recurrence."

        return MemoryMatchResult(
            similar_incidents=matches,
            bias_escalation=bias_escalation,
            reasoning=reasoning
        )
