import os, sys
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import json
import requests
import time

def run_scenario(scenario_name, metadata, audio_bytes=None):
    """Hits the local Flask Endpoint with a mocked audio byte array to test the strict grounding."""
    url = "http://localhost:8080/api/v1/voice/incident"
    
    print(f"\n{'='*50}")
    print(f" SCENARIO: {scenario_name}")
    print(f"{'='*50}")
    
    # We send a dummy audio byte string (the backend transcriber reads it, but in mock mode
    # it uses the `diagnosis` side-channel or just processes it gracefully). 
    # For a purely backend-less test without hitting AWS models, our offline transcriber 
    # mock just echoes a static string, but let's test the Engine's schema matching.
    
    dummy_audio = audio_bytes if audio_bytes else b"RIFF$" + (b"\x00" * 1024)
    
    files = {
        'audio': ('test_recording.mp3', dummy_audio, 'audio/mpeg')
    }
    
    data = {
        'metadata': json.dumps(metadata)
    }
    
    try:
        response = requests.post(url, files=files, data=data)
        if response.status_code == 200:
            payload = response.json()['data']
            print("\n✔️  TRANSCRIPT HEARD:")
            print(f"   \"{payload['transcript']}\"")
            
            print("\n✔️  FINAL SPOKEN RESPONSE (Synthesized TTS):")
            print(f"   🗣️ \"{payload['final_text_response']}\"")
            
            print("\n✔️  UI JSON PAYLOAD (Recommended Actions):")
            actions = payload['pipeline_handoff_payload']['recommended_actions']
            for i, act in enumerate(actions, 1):
                print(f"   {i}. {act}")
                
            if payload['pipeline_handoff_payload'].get('escalate'):
                print(f"   🚨 ESCALATION FLAG SET: {payload['pipeline_handoff_payload'].get('escalation_reason')}")
        else:
            print(f"❌ ERROR: {response.text}")
            
    except Exception as e:
        print(f"Request failed. Is server.py running? Error: {e}")
        
    time.sleep(1)

def main():
    print("Initializing ClinicOps Voice Demo Script...")
    
    # 1. Normal Incident (No Escalation)
    # The nurse reports a simple device disconnect.
    run_scenario(
        scenario_name="1. Normal Routine Incident",
        metadata={
            "incident_id": "DEMO-001",
            "device_id": "Centrifuge C400",
            "reporter": "Nurse Jane",
            "description": "The centrifuge is showing an E-04 door open error." # Mocking the transcript
        }
    )
    
    # 2. Safety Escalation (Hazard)
    # The nurse reports a biohazard spill, the prompt mandates escalation.
    run_scenario(
        scenario_name="2. Safety Hazard Escalation",
        metadata={
            "incident_id": "DEMO-002",
            "device_id": "Centrifuge C400",
            "reporter": "Nurse Jane",
            "description": "The centrifuge tube cracked and there is blood everywhere inside." 
        }
    )
    
    # 3. Repeated Incident Memory Case
    # The nurse reports an issue that triggers the Memory Matcher "Three Strikes" rule.
    run_scenario(
        scenario_name="3. Repeated Incident (Three Strikes)",
        metadata={
            "incident_id": "DEMO-003",
            "device_id": "Autoclave SteriPro",
            "reporter": "Nurse Jane",
            "description": "The autoclave failed the vacuum test again, throwing error 44."
        }
    )

if __name__ == "__main__":
    main()
