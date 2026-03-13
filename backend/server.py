import os
import json
import base64
from flask import Flask, request, jsonify, send_from_directory

# Load the core pipeline API
from ai_pipeline.api import _initialize_services, process_voice_incident

FRONTEND_STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend/static'))
app = Flask(__name__)

# Warm up the services on boot (validates env variables)
try:
    _initialize_services()
except Exception as e:
    print(f"FAILED TO INITIALIZE AI PIPELINE: {e}")
    # We still allow Flask to boot so it can return 500s rather than crashing
    # the container orchestrator endlessly in a reboot loop.

@app.route('/')
def serve_frontend():
    """Serve the static Vanilla HTML/JS Voice App."""
    return send_from_directory(FRONTEND_STATIC_DIR, 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve JS and CSS assets."""
    return send_from_directory(FRONTEND_STATIC_DIR, path)

@app.route('/api/v1/voice/incident', methods=['POST'])
def handle_voice_incident():
    """
    Hackathon-friendly Voice Ingestion Endpoint.
    Expects multipart/form-data:
      - 'audio': The raw audio file payload
      - 'metadata': JSON string with { "incident_id": "...", "device_id": "...", "reporter": "..."}
    """
    try:
        # 1. Input Validation
        if 'audio' not in request.files:
            return jsonify({"status": "error", "message": "Missing 'audio' file payload"}), 400
            
        file = request.files['audio']
        if file.filename == '':
            return jsonify({"status": "error", "message": "Empty 'audio' file name"}), 400
            
        metadata_str = request.form.get('metadata')
        if not metadata_str:
            return jsonify({"status": "error", "message": "Missing 'metadata' parameter"}), 400
            
        try:
            metadata = json.loads(metadata_str)
        except json.JSONDecodeError:
            return jsonify({"status": "error", "message": "Invalid JSON in 'metadata' parameter"}), 400
            
        # Extract binary bytes and extension
        audio_bytes = file.read()
        extension = file.filename.split('.')[-1] if '.' in file.filename else 'mp3'
        
        # 2. Pipeline Execution
        result = process_voice_incident(
            audio_bytes=audio_bytes,
            audio_format=extension,
            payload=metadata
        )
        
        # 3. Base64 Audio Encoding for Response
        # Convert the raw bytes to Base64 so the React frontend can consume it natively in JSON.
        audio_bytes_returned = result.get('spoken_response_data')
        b64_audio = ""
        if audio_bytes_returned:
            b64_audio = base64.b64encode(audio_bytes_returned).decode('utf-8')
            
        # 4. Formulate the highly structured JSON return
        response_payload = {
            "status": "success",
            "data": {
                "transcript": result.get("transcript"),
                "status": result.get("status"),
                "history": result.get("history", []),
                "extracted_slots": result.get("extracted_slots", {}),
                "final_text_response": result.get("final_text_response"),
                "pipeline_handoff_payload": result.get("pipeline_handoff_payload"),
                "spoken_response_base64": b64_audio
            }
        }
        
        return jsonify(response_payload), 200

    except ValueError as ve:
        # Config errors (like ENABLE_VOICE is false, or missing Bedrock tokens)
        print(f"Configuration Error: {ve}")
        return jsonify({"status": "error", "message": str(ve)}), 500
    except Exception as e:
        # Catch-all for boto3 timeouts, Bedrock Throttling, formatting errors
        print(f"Exception during voice processing: {e}")
        return jsonify({"status": "error", "message": "Internal Server Error during voice processing.", "details": str(e)}), 500


if __name__ == '__main__':
    # Default to 8080 for standard local development
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
