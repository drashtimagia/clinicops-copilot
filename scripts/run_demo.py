import os, sys
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import json
from ai_pipeline.core.orchestrator import Orchestrator

def run():
    print("=========================================")
    print(" ClinicOps Copilot - AI Pipeline Demo ")
    print("=========================================\n")
    
    orchestrator = Orchestrator()
    
    test_incidents = [
        "The centrifuge in Lab A is throwing an E-04 error. The lid seems stuck open but we need to run these samples right away. I am going to force the lid down to start it.",
        "Mobile vital signs monitor #4 shut off in the hallway again. I put it on the dock last night."
    ]
    
    for i, incident in enumerate(test_incidents, 1):
        print(f"--- INCIDENT {i} ---")
        print(f"INPUT: {incident}")
        
        # Run AI Pipeline
        response = orchestrator.handle_incident(incident)
        
        # Display Results
        print("\n[AI Recommendation]")
        # Output strictly structured JSON
        print(json.dumps(response.to_dict(), indent=2))
        print("\n" + "="*40 + "\n")

if __name__ == "__main__":
    run()
