import json
import io
from ai_pipeline.api import process_voice_incident

def test_voice_entrypoint():
    print("=========================================")
    print(" ClinicOps Copilot - Voice API Test ")
    print("=========================================\n")
    
    # 1. Create a dummy audio byte dump representing a 100kb .mp3 file
    # (Since we are likely in offline Mock Mode, the actual bytes don't matter, 
    # the Mock transcriber just reads them and outputs a hardcoded string)
    dummy_wav_bytes = b"RIFF$" + (b"\x00" * 1024) 
    
    payload_metadata = {
      "incident_id": "VOICE-TEST-001",
      "device_id": "Centrifuge C400",
      "reporter": "Nurse Jane"
      # Notice: No description field! The voice pipeline creates it.
    }
    
    print(f"Simulating Push-To-Talk inbound payload (metadata + {len(dummy_wav_bytes)} audio bytes)...")
    print("Running process_voice_incident()...\n")
    
    # Run the voice wrapper
    result = process_voice_incident(
        audio_bytes=dummy_wav_bytes,
        audio_format='wav',
        payload=payload_metadata
    )
    
    print("--- NEW MULTIMODAL ISOLATED OUTPUT ---")
    print(f">> TRANSCRIPT:\n{result['transcript']}\n")
    
    print(f">> FINAL TEXT RESPONSE:\n{result['final_text_response']}\n")
    
    print(f">> PIPELINE HANDOFF PAYLOAD (Core Engine JSON):")
    print(json.dumps(result['pipeline_handoff_payload'], indent=2))
    
    print(f"\n>> RESPONSE AUDIO:")
    audio_out = result['spoken_response_data']
    if audio_out:
        print(f"Successfully generated {len(audio_out)} bytes of TTS audio.")
    else:
        print("No audio bytes returned (Mock Mode or missing AWS Polly).")

if __name__ == "__main__":
    test_voice_entrypoint()
