import os, sys
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import requests
import json
import base64

def test_live_server():
    """
    Tests the Flask HTTP endpoint by mocking a cURL request 
    identical to what the React frontend would send.
    """
    url = "http://localhost:8080/api/v1/voice/incident"
    
    # Dummy audio binary
    dummy_audio = b"RIFF$" + (b"\x00" * 1024)
    
    # Send it as multipart/form-data
    files = {
        'audio': ('test_recording.mp3', dummy_audio, 'audio/mpeg')
    }
    
    data = {
        'metadata': json.dumps({
            "incident_id": "WEB-TEST-001",
            "device_id": "Centrifuge C400",
            "reporter": "Nurse Jane via Web"
        })
    }
    
    print(f"Sending POST {url}...")
    try:
        response = requests.post(url, files=files, data=data)
        
        print(f"\nResponse Status: {response.status_code}")
        
        # Parse JSON
        resp_json = response.json()
        print(f"Status: {resp_json.get('status')}")
        
        if response.status_code == 200:
            payload = resp_json['data']
            print(f"\nTranscript: {payload['transcript']}")
            print(f"Final Response: {payload['final_text_response']}")
            
            # Show snippet of the Base64 audio
            b64 = payload['spoken_response_base64']
            b64_preview = b64[:40] + "..." if len(b64) > 40 else b64
            print(f"Audio B64 Payload Length: {len(b64)} chars (Preview: {b64_preview})")
            
        else:
            print(f"Error Message: {resp_json.get('message')}")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_live_server()
