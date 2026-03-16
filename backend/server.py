import os
import sys
import json
import base64
import eventlet
eventlet.monkey_patch()
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import eventlet

# Ensure backend/ is on path when run from project root
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend', 'dist')
sys.path.insert(0, BACKEND_DIR)

# Load the core pipeline API
from ai_pipeline.api import _initialize_services, process_voice_incident, process_text_incident
# Global store for active voice sessions (sid -> bytearray)
voice_sessions = {}

app = Flask(__name__)
CORS(app) # Enable CORS for development
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

@app.before_request
def log_request_info():
    if request.path.startswith('/api'):
        print(f"[Backend] Request: {request.method} {request.path}")

# ---------------------------------------------------------------------------
# Socket.IO Events for real-time voice
# ---------------------------------------------------------------------------

@socketio.on('connect')
def handle_connect():
    print(f"[socket] Client connected: {request.sid}")

@socketio.on('start_voice')
def handle_start_voice(data):
    sid = request.sid
    print(f"[socket] Starting voice session for {sid}")
    voice_sessions[sid] = bytearray()

@socketio.on('audio_chunk')
def handle_audio_chunk(chunk):
    sid = request.sid
    if sid in voice_sessions:
        # chunk is binary (WebM/Opus) from MediaRecorder
        voice_sessions[sid].extend(chunk)

@socketio.on('stop_voice')
def handle_stop_voice(data):
    sid = request.sid
    if sid not in voice_sessions:
        return
        
    print(f"[socket] Stopping voice session for {sid}")
    audio_data = bytes(voice_sessions.pop(sid))
    session_id = data.get('session_id', 'default_session')

    if not audio_data:
        emit('final_response', {"status": "error", "message": "No audio received."})
        return

    # Trigger discrete transcription + processing
    try:
        # The process_voice_incident helper in api.py handles STT -> Agent -> TTS
        result = process_voice_incident(
            audio_bytes=audio_data,
            audio_format="webm", # MediaRecorder output
            payload={"session_id": session_id}
        )
        emit('final_response', {"status": "success", "data": result})
    except Exception as e:
        print(f"[socket] Error processing voice: {e}")
        emit('final_response', {"status": "error", "message": str(e)})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"[socket] Client disconnected: {request.sid}")
    voice_sessions.pop(request.sid, None)

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

@app.route('/')
def serve_frontend():
    """Serve the React production build."""
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/assets/<path:path>')
def serve_assets(path):
    """Serve Vite build assets."""
    return send_from_directory(os.path.join(FRONTEND_DIR, 'assets'), path)

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve legacy or additional static assets if needed."""
    return send_from_directory(FRONTEND_DIR, path)

# Keep the old voice incident endpoint as a fallback or for verification
@app.route('/api/v1/voice/incident', methods=['POST'])
def handle_voice_incident():
    # ... (existing code preserved below)
    try:
        if 'audio' not in request.files:
            return jsonify({"status": "error", "message": "Missing 'audio' file payload"}), 400
        file = request.files['audio']
        if file.filename == '':
            return jsonify({"status": "error", "message": "Empty 'audio' file name"}), 400
        machine = request.form.get('machine', '')
        room = request.form.get('room', '')
        staff_role = request.form.get('staff_role', 'Staff')
        metadata = {}
        metadata_str = request.form.get('metadata')
        if metadata_str:
            try: metadata = json.loads(metadata_str)
            except: pass
        payload = {
            "session_id": metadata.get("session_id", "default_session"),
            "machine": machine or metadata.get("device_id", ""),
            "room": room or metadata.get("room", "Unknown"),
            "staff_role": staff_role or metadata.get("reporter", "Staff"),
            "conversation_history": metadata.get("conversation_history", [])
        }
        audio_bytes = file.read()
        extension = file.filename.split('.')[-1] if '.' in file.filename else 'mp3'
        data = process_voice_incident(audio_bytes=audio_bytes, audio_format=extension, payload=payload)
        return jsonify({"status": "success", "data": data}), 200
    except Exception as e:
        print(f"Exception during voice processing: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    # Default to 8080 for standard local development
    port = int(os.environ.get("PORT", 8080))
    # Use socketio.run instead of app.run for eventlet/socket support
    socketio.run(app, host='0.0.0.0', port=port, debug=True, use_reloader=False)
