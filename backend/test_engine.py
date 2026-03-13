import json
from ai_pipeline.data_ingestion.models import DocumentChunk
from ai_pipeline.memory.models import PastIncident, MemoryMatchResult
from ai_pipeline.engine.generator import get_decision_engine

def main():
    print("=========================================")
    print(" ClinicOps Copilot - Engine Evaluation ")
    print("=========================================\n")
    
    engine = get_decision_engine()
    
    # Simulate a pipeline run with mock retrieved data
    mock_chunks = [
        (DocumentChunk("1", "centrifuge-c400.md", "manual", "Error Codes", "E-04 indicates a lid latch issue."), 0.85)
    ]
    
    scenarios = [
        {
            "id": "TEST-01",
            "text": "The centrifuge in Lab A is throwing an E-04 error.",
            "memory": MemoryMatchResult([], False, "No exact memory matches for this device.")
        },
        {
            "id": "TEST-02",
            "text": "Biohazard spill, blood inside the centrifuge.",
            "memory": MemoryMatchResult([], False, "No memory match.")
        },
        {
            "id": "TEST-03",
            "text": "Vital signs monitor VPM5-9002 shut off in the hallway again.",
            "memory": MemoryMatchResult([
                PastIncident("INC-1", "...", "VPM5-9002", "Shut off during transport.", "Jane"),
                PastIncident("INC-2", "...", "VPM5-9002", "Battery died rapidly in hallway.", "Bob")
            ], True, "3rd strike rule activated for VPM5-9002 specific serial.")
        }
    ]
    
    for case in scenarios:
        print(f"\n--- INCIDENT {case['id']} ---")
        print(f"INPUT: {case['text']}")
        
        result = engine.evaluate_incident(
            incident_text=case["text"],
            incident_id=case["id"],
            retrieved_chunks=mock_chunks,
            memory_result=case["memory"]
        )
        
        # The result object has a clean to_dict method
        js_out = json.dumps(result.to_dict(), indent=2)
        print(f"OUTPUT:\n{js_out}")

if __name__ == "__main__":
    main()
