import os
from typing import Dict, Any

from ai_pipeline.config import config
from ai_pipeline.data_ingestion.parser import MarkdownParser
from ai_pipeline.data_ingestion.ingest import process_directory, load_incidents_as_chunks, MANUALS_DIR, SOPS_DIR
from ai_pipeline.retrieval.service import RetrievalService
from ai_pipeline.memory.matcher import MemoryMatcher
from ai_pipeline.engine.generator import get_decision_engine
from ai_pipeline.voice.service import VoiceService

# -------------------------------------------------------------
# Module State (Warm Start)
# We initialize these heavily loaded classes once at module level
# so the backend doesn't suffer latency on every web request.
# -------------------------------------------------------------

_retrieval_service = None
_memory_matcher = None
_decision_engine = None
_voice_service = None

def _initialize_services():
    global _retrieval_service, _memory_matcher, _decision_engine, _voice_service
    
    # 1. Validate Config environment immediately
    try:
        config.validate()
    except Exception as e:
        print(f"CRITICAL API STARTUP FAILURE: {str(e)}")
        raise
        
    print("[AI Pipeline] Initializing core services...")
    
    # 2. Load and embed knowledge base (manuals + SOPs + historical incidents)
    parser = MarkdownParser()
    chunks = []
    chunks.extend(process_directory(MANUALS_DIR, "manual", parser))
    chunks.extend(process_directory(SOPS_DIR, "sop", parser))
    chunks.extend(load_incidents_as_chunks())
    
    _retrieval_service = RetrievalService(chunks)
    _memory_matcher = MemoryMatcher()
    _decision_engine = get_decision_engine()
    
    if config.ENABLE_VOICE:
        _voice_service = VoiceService(
            retrieval_service=_retrieval_service,
            memory_matcher=_memory_matcher
        )
    
    print("[AI Pipeline] Services warm and ready.")

# Auto-initialize when the backend imports this file
_initialize_services()


def process_incident(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entrypoint for the backend web server.
    
    Expected `payload` schema:
    {
      "incident_id": "string",
      "device_id": "string",  # Optional, but helps Memory Matching
      "description": "string",
      "reporter": "string"
    }
    
    Returns the JSON `DecisionOutput` dictionary schema.
    """
    incident_id = payload.get("incident_id", "UNKNOWN_ID")
    device_id = payload.get("device_id", "")
    description = payload.get("description", "")
    
    if not description:
        raise ValueError("The 'description' field is required in the incident payload.")
        
    # Build a combined text for the memory layer to analyze
    search_text = f"Device: {device_id}\nDescription: {description}"
    
    # 1. Retrieve SOPs/Manuals
    # We fetch top 3 most relevant chunks
    retrieved_chunks = _retrieval_service.search(search_text, top_k=3)
    
    # 2. Check Incident Memory (The "Three Strikes" rule)
    memory_result = _memory_matcher.analyze_incident(search_text)
    
    # 3. Generate structured decision using AWS Nova (or Mock)
    decision = _decision_engine.evaluate_incident(
        incident_text=description,
        incident_id=incident_id,
        retrieved_chunks=retrieved_chunks,
        memory_result=memory_result
    )
    
    # 4. Return pure Python Dictionary to the web framework for JSON serialization
    return decision.to_dict()

def process_voice_incident(audio_bytes: bytes, audio_format: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Multimodal Push-To-Talk voice extension for the core pipeline.
    
    Takes raw audio bytes, an audio format string, and dict metadata.
    Delegates audio transcription, multimodal extraction, and synthesis 
    entirely to the isolated VoiceService layer.
    
    Returns standard payload:
    {
      "transcript": "string",
      "spoken_response_data": bytes,
      "final_text_response": "string",
      "pipeline_handoff_payload": dict
    }
    """
    if not config.ENABLE_VOICE:
        raise ValueError("ENABLE_VOICE is false in config. Voice endpoint is unavailable.")
        
    return _voice_service.process_push_to_talk(
        audio_bytes=audio_bytes, 
        audio_format=audio_format, 
        incident_metadata=payload,
        core_pipeline_func=process_incident
    )

