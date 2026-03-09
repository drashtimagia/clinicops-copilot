from typing import Dict, Any, Optional
from ai_pipeline.voice.transcriber import NovaSonicTranscriber
from ai_pipeline.voice.synthesizer import VoiceSynthesizer
from ai_pipeline.config import config

class VoiceService:
    """
    Isolated orchestrator for multimodal voice operations.
    Keeps audio buffering, speech-to-text, and TTS generation 
    cleanly separated from the core text-based Decision Engine.
    """
    def __init__(self):
        self.transcriber = NovaSonicTranscriber()
        self.synthesizer = VoiceSynthesizer()
        
    def process_push_to_talk(self, audio_bytes: bytes, audio_format: str, 
                             incident_metadata: Dict[str, Any], 
                             core_pipeline_func: callable) -> Dict[str, Any]:
        """
        Synchronous MVP processing.
        1. Transcribe audio to text
        2. Execute the existing text-based decision engine 
        3. Synthesize the text response to audio
        4. Package the multimodal response payload
        """
        print("[VoiceService] Processing Push-To-Talk inbound voice snippet...")
        
        # 1. Transcript Isolation
        transcript = self.transcriber.transcribe(audio_bytes, audio_format)
        
        # 2. Pipeline Handoff
        # Inject the transcript dynamically into the dictionary payload 
        # expected by the standard text engine
        handoff_payload = incident_metadata.copy()
        handoff_payload["description"] = transcript
        
        # We invoke the passed-in core process_incident() function
        decision_dict = core_pipeline_func(handoff_payload)
        
        # 3. Conversational Synthesis
        actions_text = " ".join(decision_dict.get("recommended_actions", []))
        escalate = decision_dict.get("escalate", False)
        reasoning = decision_dict.get("escalation_reason", "")
        
        escalation_warning = f"Warning: {reasoning}." if escalate and reasoning else ""
        final_text_response = f"I've analyzed the incident. {escalation_warning} I recommend the following: {actions_text}".strip()
        
        spoken_audio = self.synthesizer.synthesize(final_text_response)
        
        # 4. Strict Payload Fulfillment
        return {
            "transcript": transcript,
            "final_text_response": final_text_response,
            "spoken_response_data": spoken_audio,
            "pipeline_handoff_payload": decision_dict
        }

    def process_streaming_chunk(self, chunk: bytes, session_id: str) -> None:
        """
        STUB FOR FUTURE BIDIRECTIONAL STREAMING SUPPORT
        
        This method documents the integration point for WebSocket/WebRTC wrappers.
        When full streaming is enabled:
        1. This will buffer raw PCM/Opus audio chunks by session_id.
        2. It will utilize Amazon Nova's streaming APIs (which leverage EventStreams) 
           or Amazon Transcribe streaming to emit transcript deltas continuously.
        3. Upon voice activity detection (VAD) silence, it automatically bundles 
           the buffer and hands off to the core text pipeline.
        4. The synthesizer will yield chunked audio frames back down the socket.
        """
        raise NotImplementedError(
            "Full bidirectional streaming is not enabled in this MVP tier. "
            "Please use process_push_to_talk() for discrete voice transactions."
        )
