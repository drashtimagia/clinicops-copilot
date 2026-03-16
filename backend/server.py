import os
import sys
import json
import base64
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Ensure backend/ is on path when run from project root
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend', 'dist')
sys.path.insert(0, BACKEND_DIR)

# Load the core pipeline API
from ai_pipeline.api import _initialize_services, process_voice_incident, process_text_incident

app = Flask(__name__)
CORS(app) # Enable CORS for development

@app.before_request
def log_request_info():
    if request.path.startswith('/api'):
        print(f"[Backend] Request: {request.method} {request.path}")

# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@app.route('/api/v1/text/incident', methods=['POST'])
def handle_text_incident():
    """
    Text-only incident endpoint.
    Expects JSON: { "session_id": "...", "message": "..." }
    """
    try:
        data = request.json
        session_id = data.get("session_id", "default_session")
        message = data.get("message", "")

        result_data = process_text_incident({
            "session_id": session_id,
            "message": message
        })

        return jsonify({
            "status": "success",
            "data": result_data
        }), 200

    except Exception as e:
        print(f"Error in text incident: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/v1/voice/incident', methods=['POST'])
def handle_voice_incident():
    """
    Process an audio incident.
    Expects multi-part form data with an 'audio' file.
    """
    try:
        if 'audio' not in request.files:
            return jsonify({"status": "error", "message": "Missing 'audio' file payload"}), 400
        
        file = request.files['audio']
        if file.filename == '':
            return jsonify({"status": "error", "message": "Empty 'audio' file name"}), 400
            
        session_id = request.form.get('session_id', 'default_session')
        
        # Metadata handling for compatibility with frontend components
        machine = request.form.get('machine', '')
        room = request.form.get('room', '')
        staff_role = request.form.get('staff_role', 'Staff')
        
        payload = {
            "session_id": session_id,
            "machine": machine,
            "room": room,
            "staff_role": staff_role
        }
        
        audio_bytes = file.read()
        # Extension could be webm or mp3
        extension = file.filename.split('.')[-1] if '.' in file.filename else 'webm'
        
        print(f"[Backend] Processing voice for session {session_id}, size: {len(audio_bytes)}")
        
        data = process_voice_incident(
            audio_bytes=audio_bytes, 
            audio_format=extension, 
            payload=payload
        )
        
        return jsonify({"status": "success", "data": data}), 200
        
    except Exception as e:
        print(f"Exception during voice processing: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def serve_frontend():
    """Serve the React production build."""
    if not os.path.exists(os.path.join(FRONTEND_DIR, 'index.html')):
        return "Frontend dist not found. Please run 'npm run build' in the frontend folder.", 404
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/assets/<path:path>')
def serve_assets(path):
    """Serve Vite build assets."""
    return send_from_directory(os.path.join(FRONTEND_DIR, 'assets'), path)

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve legacy or additional static assets if needed."""
    return send_from_directory(FRONTEND_DIR, path)

if __name__ == '__main__':
    # Default to 8080 for standard local development
    port = int(os.environ.get("PORT", 8080))
    # Standard Flask app.run for REST
    app.run(host='0.0.0.0', port=port, debug=True)
