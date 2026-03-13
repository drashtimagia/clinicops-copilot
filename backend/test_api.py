from ai_pipeline.api import process_incident
import json

def test_api_entrypoint():
    print("Simulating a backend API call to process_incident()...\n")
    
    # Simulate a JSON payload from a frontend client
    payload = {
      "incident_id": "API-TEST-001",
      "device_id": "VPM5-9002",
      "description": "The monitor shut off while moving the patient down the hall.",
      "reporter": "Nurse Jane"
    }
    
    print(f"REQUEST PAYLOAD:\n{json.dumps(payload, indent=2)}\n")
    
    # The magical one-liner the backend engineer uses
    response_dict = process_incident(payload)
    
    print(f"RESPONSE DICT:\n{json.dumps(response_dict, indent=2)}")
    
if __name__ == "__main__":
    test_api_entrypoint()
