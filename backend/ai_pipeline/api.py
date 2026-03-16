from typing import Dict, Any
import base64
import time
from ai_pipeline.config import config
from ai_pipeline.ingestion.ingest_data import ingest_all_to_store
from ai_pipeline.retrieval.retriever import retrieve_context
from ai_pipeline.agent.agent import Agent, run_agent
from ai_pipeline.voice.transcribe import transcribe_audio
from ai_pipeline.voice.speak import generate_speech
from ai_pipeline.session_manager import session_manager

# ---------------------------------------------------------------------------
# Module-level warm-start (initialised once at import time)
# ---------------------------------------------------------------------------

_agent: Agent = None


def _initialize_services():
    global _agent

    config.validate()
    print("[AI Pipeline] Initializing core services...")

    # 1. Load data and index in FAISS
    ingest_all_to_store()
    _agent = Agent()

    print("[AI Pipeline] Services warm and ready.")


_initialize_services()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_incident(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main text-based incident analysis endpoint.

    Expected payload:
    {
      "incident_id": "string",
      "device_id":   "string",   # optional
      "description": "string",
      "reporter":    "string"
    }
    """
    incident_id = payload.get("incident_id", "UNKNOWN_ID")
    device_id = payload.get("device_id", "")
    description = payload.get("description", "")

    if not description:
        raise ValueError("The 'description' field is required.")

    search_text = f"Device: {device_id}\nDescription: {description}"
    retrieved_chunks = retrieve_context(search_text)

    decision = _agent.evaluate_incident(
        incident_text=description,
        incident_id=incident_id,
        retrieved_chunks=retrieved_chunks,
        memory_result=None
    )
    return decision


def process_text_incident(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Text-based incident endpoint.
    Reuse the same conversation controller as voice.
    """
    start_time = time.time()
    session_id = payload.get("session_id", "default_session")
    text = payload.get("message", "").strip()
    
    print(f"[api] process_text_incident: session={session_id}, text='{text}'")
    
    # 0. Retrieve persistent session state
    session_state = session_manager.get_session(session_id)
    
    if not text:
         return {
            "status": "success",
            "data": _get_fallback_response(session_state, "I didn't catch that. Please type your message.")
        }

    # 1. Run Troubleshooting Agent
    perf = {"stt": 0.0}
    agent_start = time.time()
    
    try:
        current_slots = {
            "reported_by_role": session_state.get("staff_role"),
            "room": session_state.get("room"),
            "machine": session_state.get("machine"),
            "problem": session_state.get("problem"),
            "escalate": session_state.get("escalate", False)
        }
        history = session_state.get("conversation_history", [])
        last_question = session_state.get("last_question")

        agent_result = run_agent(
            query=text,
            slots=current_slots,
            conversation_history=history,
            last_question=last_question
        )
        perf["agent"] = round(time.time() - agent_start, 2)
        
        response_text = agent_result.get("message", "I am standing by.")
        agent_status = agent_result.get("status", "troubleshooting")
        escalate = agent_result.get("escalate", False)
        
        # Persist updates
        new_slots = agent_result.get("extracted_slots", {})
        session_manager.update_session(session_id, {
            "staff_role": new_slots.get("reported_by_role"),
            "room": new_slots.get("room"),
            "machine": new_slots.get("machine"),
            "problem": new_slots.get("problem"),
            "troubleshooting_stage": agent_status,
            "escalate": escalate,
            "last_question": response_text,
            "conversation_history": history + [
                {"role": "user", "text": text},
                {"role": "assistant", "text": response_text}
            ],
            "last_handoff": agent_result.get("pipeline_handoff_payload", {})
        })
    except Exception as e:
        print(f"[api] Error: {e}")
        response_text = "I encountered an error. Please try again."
        agent_status = "complete"
        agent_result = {}

    # 2. Synthesize Speech (Optional for text, but good for consistency)
    tts_start = time.time()
    base64_audio = ""
    try:
        audio_result = generate_speech(response_text)
        audio_bytes = audio_result.get("audio", b"")
        if audio_bytes:
            base64_audio = base64.b64encode(audio_bytes).decode('utf-8')
    except: pass
    perf["tts"] = round(time.time() - tts_start, 2)
    
    perf["total"] = round(time.time() - start_time, 2)
    print(f"[perf] text: {perf}")

    # 3. Final Data
    updated_session = session_manager.get_session(session_id)
    return _build_final_data(updated_session, agent_result, response_text, base64_audio)


def process_voice_incident(audio_bytes: bytes, audio_format: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Voice-based incident endpoint.
    Pipeline: audio -> transcribe_audio -> run_agent -> generate_speech
    """
    total_start = time.time()
    perf = {}
    
    session_id = payload.get("session_id", "default_session")
    print(f"[api] process_voice_incident: session={session_id}")
    
    if not config.ENABLE_VOICE:
        raise ValueError("ENABLE_VOICE is disabled.")

    session_state = session_manager.get_session(session_id)

    # 1. Transcribe audio
    stt_start = time.time()
    transcript = transcribe_audio(audio_bytes)
    perf["stt"] = round(time.time() - stt_start, 2)
    print(f"[api] transcript: '{transcript}'")

    if not transcript or transcript.strip() == "" or transcript == "Transcription failed":
        return _get_fallback_response(session_state, "I didn't catch that. Please repeat.")

    # 1b. Completion Stickiness
    if session_state.get("troubleshooting_stage") == "complete":
        q = transcript.lower().strip()
        if any(word in q for word in ["thank", "thanks", "okay", "ok", "goodbye"]):
            return _get_fallback_response(session_state, "You're welcome. Standing by.")
        elif any(word in q for word in ["new", "another", "start over"]):
             session_manager.update_session(session_id, {
                 "staff_role": None, "room": None, "machine": None, "problem": None,
                 "troubleshooting_stage": "intake", "last_question": None, "escalate": False,
                 "conversation_history": []
             })
             session_state = session_manager.get_session(session_id)

    # 2. Agent
    agent_start = time.time()
    try:
        current_slots = {
            "reported_by_role": session_state.get("staff_role"),
            "room": session_state.get("room"),
            "machine": session_state.get("machine"),
            "problem": session_state.get("problem"),
            "escalate": session_state.get("escalate", False)
        }
        history = session_state.get("conversation_history", [])
        last_question = session_state.get("last_question")

        agent_result = run_agent(transcript, current_slots, history, last_question)
        perf["agent"] = round(time.time() - agent_start, 2)
        
        response_text = agent_result.get("message", "I am standing by.")
        agent_status = agent_result.get("status", "troubleshooting")
        escalate = agent_result.get("escalate", False)
        
        session_manager.update_session(session_id, {
            "staff_role": agent_result.get("extracted_slots", {}).get("reported_by_role"),
            "room": agent_result.get("extracted_slots", {}).get("room"),
            "machine": agent_result.get("extracted_slots", {}).get("machine"),
            "problem": agent_result.get("extracted_slots", {}).get("problem"),
            "troubleshooting_stage": agent_status,
            "escalate": escalate,
            "last_question": response_text,
            "conversation_history": history + [
                {"role": "user", "text": transcript},
                {"role": "assistant", "text": response_text}
            ],
            "last_handoff": agent_result.get("pipeline_handoff_payload", {})
        })
    except Exception as e:
        print(f"[api] Agent error: {e}")
        response_text = "Internal error."
        agent_status = "complete"
        agent_result = {}

    # 3. TTS
    tts_start = time.time()
    base64_audio = ""
    try:
        audio_result = generate_speech(response_text)
        audio_bytes_out = audio_result.get("audio", b"")
        if audio_bytes_out:
            base64_audio = base64.b64encode(audio_bytes_out).decode('utf-8')
    except: pass
    perf["tts"] = round(time.time() - tts_start, 2)
    
    perf["total"] = round(time.time() - total_start, 2)
    print(f"[perf] voice: {perf}")

    updated_session = session_manager.get_session(session_id)
    return _build_final_data(updated_session, agent_result, response_text, base64_audio)


def _get_fallback_response(session_state: dict, msg: str) -> dict:
    return {
        "transcript": "...",
        "response_text": msg,
        "response_audio": "",
        "status": session_state.get("troubleshooting_stage", "gathering"),
        "extracted_slots": {
            "reported_by_role": session_state.get("staff_role"),
            "room": session_state.get("room"),
            "machine": session_state.get("machine"),
            "problem": session_state.get("problem")
        },
        "pipeline_handoff_payload": session_state.get("last_handoff", {})
    }

def _build_final_data(session: dict, agent_result: dict, response_text: str, base64_audio: str) -> dict:
    handoff = agent_result.get("pipeline_handoff_payload") if agent_result else None
    if handoff is None:
        handoff = session.get("last_handoff") or {}
    
    if not handoff.get("recommended_actions"):
        handoff["recommended_actions"] = [response_text]
    if not handoff.get("affected_roles"):
        handoff["affected_roles"] = [{"role": "Clinical Staff", "impact": "Awaiting details"}]

    return {
        "history": session.get("conversation_history", []),
        "extracted_slots": {
            "reported_by_role": session.get("staff_role"),
            "room": session.get("room"),
            "machine": session.get("machine"),
            "problem": session.get("problem")
        },
        "status": session.get("troubleshooting_stage"),
        "pipeline_handoff_payload": handoff,
        "spoken_response_base64": base64_audio
    }
