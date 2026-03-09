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
        
        # Simple in-memory session store for MVP
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
    def _get_or_create_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "history": [],
                "slots": {
                    "reported_by_role": None,
                    "problem": None,
                    "machine": None,
                    "room": None
                }
            }
        return self.sessions[session_id]
        
    def _extract_slots(self, transcript: str, current_slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mock LLM Slot Extractor for MVP.
        In production, this is an Amazon Nova 2 Lite structured output call.
        """
        t = transcript.lower()
        
        if "nurse" in t: current_slots["reported_by_role"] = "Nurse"
        elif "doctor" in t or "dr" in t: current_slots["reported_by_role"] = "Doctor"
        elif "reception" in t: current_slots["reported_by_role"] = "Receptionist"
        elif "tech" in t: current_slots["reported_by_role"] = "Technician"
        
        if "room 1" in t: current_slots["room"] = "Room 1"
        elif "room 2" in t: current_slots["room"] = "Room 2"
        elif "room 3" in t: current_slots["room"] = "Room 3"
        elif "room 4" in t: current_slots["room"] = "Room 4"
        elif "lab a" in t: current_slots["room"] = "Lab A"
        elif "lab b" in t: current_slots["room"] = "Lab B"
        elif "hallway" in t: current_slots["room"] = "Hallway"
        
        if "centrifuge" in t or "c400" in t: current_slots["machine"] = "Centrifuge C400"
        elif "ecg" in t or "ekg" in t: current_slots["machine"] = "ECG Machine"
        elif "infusion pump" in t or "a10" in t: current_slots["machine"] = "Infusion Pump A10"
        elif "monitor" in t or "vpm" in t: current_slots["machine"] = "Vitals Monitor M5"
        elif "autoclave" in t or "steripro" in t: current_slots["machine"] = "Autoclave SteriPro"
        
        if "e-04" in t or "door open error" in t: current_slots["problem"] = "E-04 door open error."
        elif "blood" in t or "cracked" in t: current_slots["problem"] = "Tube cracked, biohazard blood spill."
        elif "vacuum test" in t or "error 44" in t: current_slots["problem"] = "Failed vacuum test (error 44)."
        elif "waveform" in t: current_slots["problem"] = "Not showing a waveform."
        elif "alarm keeps repeating" in t: current_slots["problem"] = "Alarm keeps repeating."
        elif "shut off" in t or "failed again" in t: current_slots["problem"] = "Device shut off or failed unexpectedly."
        elif "down" in t or "broken" in t: current_slots["problem"] = "Device reported as down/broken."
        
        return current_slots
        
    def _generate_clarification(self, slots: Dict[str, Any]) -> Optional[str]:
        """Determines what is missing and asks the user."""
        if not slots["machine"]: return "What type of machine is affected?"
        if not slots["problem"]: return "Can you describe the problem or error you are seeing?"
        if not slots["room"]: return "Which room is the machine in?"
        if not slots["reported_by_role"]: return "Are you reporting this as a nurse, doctor, receptionist, or technician?"
        return None
        
    def process_push_to_talk(self, audio_bytes: bytes, audio_format: str, 
                             incident_metadata: Dict[str, Any], 
                             core_pipeline_func: callable) -> Dict[str, Any]:
        """
        Stateful Multi-Turn Conversation processing.
        1. Transcribe audio to text
        2. Extract slots into Session
        3. If incomplete, return Clarification string and Audio
        4. If complete, Execute core text pipeline
        """
        print("[VoiceService] Processing Push-To-Talk inbound voice snippet...")
        
        session_id = incident_metadata.get("session_id", "default_session")
        session = self._get_or_create_session(session_id)
        
        # 1. Transcript Isolation
        transcript = self.transcriber.transcribe(audio_bytes, audio_format, metadata=incident_metadata)
        session["history"].append({"role": "user", "text": transcript})
        
        # 2. Slot Extraction
        extracted_slots = self._extract_slots(transcript, session["slots"])
        session["slots"] = extracted_slots
        
        missing_question = self._generate_clarification(extracted_slots)
        
        # 3. Conversational Loop (Incomplete)
        if missing_question:
            session["history"].append({"role": "assistant", "text": missing_question})
            spoken_audio = self.synthesizer.synthesize(missing_question)
            return {
                "status": "clarifying",
                "transcript": transcript,
                "history": session["history"],
                "extracted_slots": extracted_slots,
                "final_text_response": missing_question,
                "spoken_response_data": spoken_audio,
                "pipeline_handoff_payload": None
            }
            
        # 4. Pipeline Handoff (Complete)
        print(f"[VoiceService] Slots complete for session {session_id}. Handing off to Core.")
        
        # Synthesize the final problem description combining all gathered slots
        combined_description = (
            f"Reported by {extracted_slots['reported_by_role']} in {extracted_slots['room']}. "
            f"Machine: {extracted_slots['machine']}. "
            f"Problem: {extracted_slots['problem']}"
        )
        
        handoff_payload = incident_metadata.copy()
        handoff_payload["description"] = combined_description
        handoff_payload["device_id"] = extracted_slots['machine']
        
        # Invoke core Pipeline
        decision_dict = core_pipeline_func(handoff_payload)
        
        # 5. Generative Response Synthesis
        actions_text = " ".join(decision_dict.get("recommended_actions", []))
        escalate = decision_dict.get("escalate", False)
        reasoning = decision_dict.get("escalation_reason", "")
        
        if escalate:
            final_text_response = f"Escalation required. {reasoning}. Required actions: {actions_text}"
        else:
            final_text_response = f"Incident assessed. Required actions: {actions_text}"
            
        session["history"].append({"role": "assistant", "text": final_text_response})
        spoken_audio = self.synthesizer.synthesize(final_text_response)
        
        # Return strict combined payload
        return {
            "status": "complete",
            "transcript": transcript,
            "history": session["history"],
            "extracted_slots": extracted_slots,
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
