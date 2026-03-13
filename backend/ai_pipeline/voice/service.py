from typing import Dict, Any, Optional, List, Tuple
from ai_pipeline.voice.transcriber import NovaSonicTranscriber
from ai_pipeline.voice.synthesizer import VoiceSynthesizer
from ai_pipeline.config import config

# Intent classification signals
_GENERAL_QUESTION_SIGNALS = [
    "what", "how", "why", "when", "who", "can you", "tell me", "explain",
    "is there", "help", "what is", "what are", "what does", "do you know",
    "show me", "give me", "what should", "what happens", "difference",
    "list", "steps", "procedure", "protocol", "sop", "manual", "guide"
]
_INCIDENT_REPORT_SIGNALS = [
    "broken", "error", "not working", "failed", "failure", "spill", "alarm",
    "down", "cracked", "shut off", "won't start", "not starting", "keeps",
    "stuck", "beeping", "leaking", "smoke", "sparks", "damage", "contaminated",
    "offline", "unresponsive", "malfunction", "issue", "problem", "trouble"
]
_RESOLUTION_FAILURE_SIGNALS = [
    "still", "didn't work", "not working still", "same issue", "same problem",
    "no change", "still broken", "failed again", "tried", "already did",
    "doesn't help", "nothing happened", "still showing", "persists"
]


class VoiceService:
    """
    Smart stateful orchestrator for multimodal voice operations.
    Supports: intent detection, RAG-grounded Q&A, back-and-forth resolution,
    memory-aware escalation, and technician appointment booking.
    """

    def __init__(self, retrieval_service=None, memory_matcher=None):
        self.transcriber = NovaSonicTranscriber()
        self.synthesizer = VoiceSynthesizer()
        # Optional injected services for RAG-grounded responses
        self.retrieval_service = retrieval_service
        self.memory_matcher = memory_matcher
        # Simple in-memory session store for MVP
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def _get_or_create_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "history": [],
                "pipeline_completed": False,
                "last_asked_slot": None,
                "resolution_steps": [],
                "resolution_index": 0,
                "escalation_triggered": False,
                "awaiting_appointment_confirm": False,
                "slots": {
                    "reported_by_role": None,
                    "problem": None,
                    "machine": None,
                    "room": None
                }
            }
        return self.sessions[session_id]

    # ------------------------------------------------------------------
    # Intent Detection
    # ------------------------------------------------------------------
    def _detect_intent(self, transcript: str, last_asked_slot: Optional[str], pipeline_completed: bool) -> str:
        """
        Classifies the user's message as:
        - 'slot_answer'      : responding directly to a slot question
        - 'general_question' : asking a knowledge/help question
        - 'resolution_check' : reporting whether the last step worked
        - 'incident_report'  : reporting a new device problem
        """
        t = transcript.lower().strip()

        # If we just asked a slot question, assume they're answering it
        # unless it reads like a completely different question
        if last_asked_slot and not pipeline_completed:
            question_words = sum(1 for w in _GENERAL_QUESTION_SIGNALS[:8] if t.startswith(w))
            if question_words == 0:
                return "slot_answer"

        # Post-pipeline: check if they're reporting resolution failure
        if pipeline_completed:
            if any(sig in t for sig in _RESOLUTION_FAILURE_SIGNALS):
                return "resolution_check"

        # General knowledge question
        if any(t.startswith(w) or f" {w} " in f" {t} " for w in _GENERAL_QUESTION_SIGNALS):
            # Only classify as general if it doesn't also heavily signal an incident
            incident_signals = sum(1 for sig in _INCIDENT_REPORT_SIGNALS if sig in t)
            if incident_signals < 2:
                return "general_question"

        # Incident report
        if any(sig in t for sig in _INCIDENT_REPORT_SIGNALS):
            return "incident_report"

        return "general_question"

    # ------------------------------------------------------------------
    # Slot Extraction
    # ------------------------------------------------------------------
    def _extract_slots(self, transcript: str, current_slots: Dict[str, Any]) -> Dict[str, Any]:
        """Smart keyword-based slot extractor."""
        import re
        t = transcript.lower()

        # Role
        if not current_slots["reported_by_role"]:
            if "nurse" in t:
                current_slots["reported_by_role"] = "Nurse"
            elif "doctor" in t or "dr " in t:
                current_slots["reported_by_role"] = "Doctor"
            elif "reception" in t:
                current_slots["reported_by_role"] = "Receptionist"
            elif "tech" in t:
                current_slots["reported_by_role"] = "Technician"

        # Room
        if not current_slots["room"]:
            room_match = re.search(r'(room\s+[0-9a-z]+)', t)
            if room_match:
                current_slots["room"] = room_match.group(1).title()
            elif "lab a" in t:
                current_slots["room"] = "Lab A"
            elif "lab b" in t:
                current_slots["room"] = "Lab B"
            elif "hallway" in t:
                current_slots["room"] = "Hallway"
            elif "icu" in t:
                current_slots["room"] = "ICU"
            elif "ward" in t:
                current_slots["room"] = "Ward"

        # Machine
        if not current_slots["machine"]:
            if "centrifuge" in t or "c400" in t or "centraspin" in t:
                current_slots["machine"] = "Centrifuge C400"
            elif "ecg" in t or "ekg" in t:
                current_slots["machine"] = "ECG Machine"
            elif "infusion pump" in t or "a10" in t:
                current_slots["machine"] = "Infusion Pump A10"
            elif "vitals" in t or "monitor" in t or "vpm" in t or "vitalspro" in t or "m5" in t:
                current_slots["machine"] = "Vitals Monitor M5"
            elif "autoclave" in t or "steripro" in t or "steriliz" in t:
                current_slots["machine"] = "Autoclave SteriPro"

        # Problem
        if not current_slots["problem"]:
            if "e-04" in t or "e04" in t or "imbalance" in t:
                current_slots["problem"] = "E-04 imbalance error."
            elif "e-02" in t or "lid" in t and "close" in t:
                current_slots["problem"] = "E-02 lid closure error."
            elif "blood" in t and ("spill" in t or "crack" in t or "broke" in t):
                current_slots["problem"] = "Tube cracked — biohazard blood spill."
            elif "vacuum" in t or "error 44" in t:
                current_slots["problem"] = "Failed vacuum test (error 44)."
            elif "waveform" in t or "ecg" in t and "flat" in t:
                current_slots["problem"] = "Not showing a waveform."
            elif "alarm" in t:
                current_slots["problem"] = "Alarm keeps repeating."
            elif "shut off" in t or "powered off" in t or "shuts down" in t:
                current_slots["problem"] = "Device shutting off unexpectedly."
            elif "battery" in t and ("dead" in t or "drain" in t or "die" in t):
                current_slots["problem"] = "Battery dying despite charging."
            elif "not start" in t or "won't start" in t or "not turning on" in t:
                current_slots["problem"] = "Device not starting."
            elif "low pressure" in t or "pressure" in t and "error" in t:
                current_slots["problem"] = "Low pressure error."
            elif "sterile" in t or "steriliz" in t and ("fail" in t or "indicator" in t):
                current_slots["problem"] = "Sterilization test failed."
            elif "down" in t or "broken" in t or "not working" in t:
                current_slots["problem"] = "Device reported as not working."

        return current_slots

    def _get_missing_critical_slot(self, slots: Dict[str, Any]) -> str:
        """Only machine and problem are critical — room/role are optional."""
        if not slots["machine"]:
            return "machine"
        if not slots["problem"]:
            return "problem"
        return ""

    def _generate_clarification(self, slots: Dict[str, Any]) -> str:
        if not slots["machine"]:
            return "Which device is having the issue? For example: centrifuge, vitals monitor, or autoclave?"
        if not slots["problem"]:
            return "Can you describe what's happening? Any error codes, sounds, or specific symptoms?"
        return ""

    # ------------------------------------------------------------------
    # RAG-Grounded General Response
    # ------------------------------------------------------------------
    def _generate_general_response(self, transcript: str, history: list) -> str:
        """
        Answers a general/knowledge question grounded in retrieved SOPs and manuals.
        Uses Nova in live mode; smart mock heuristics in offline mode.
        """
        t = transcript.lower()

        if not config.USE_MOCK_MODEL and self.retrieval_service:
            # Live: retrieve and answer via Bedrock Nova
            try:
                from ai_pipeline.engine.prompts import build_conversational_prompt
                chunks = self.retrieval_service.search(transcript, top_k=3)
                prompt = build_conversational_prompt(transcript, chunks, history)
                # In fully live mode, this would call Nova. For now, fall through to mock.
            except Exception:
                pass

        # Mock / offline heuristics — grounded in actual data
        if "biohazard" in t or "spill" in t:
            return (
                "Per SOP-011 Biohazard Response: (1) Do NOT touch the spill with bare hands — "
                "don protective PPE (gloves, gown, eye protection) immediately. "
                "(2) Alert all nearby staff verbally. "
                "(3) Place a biohazard tent over the spill area. "
                "(4) Use the spill kit from the red cabinet — apply absorbent granules first, "
                "then wipe outward-in with bleach wipes. (5) Bag all materials as biohazardous waste. "
                "(6) Call EVS at ext. 5200 to confirm remediation. Do not resume area use until cleared."
            )
        elif "quarantine" in t or "lock out" in t or "out of service" in t:
            return (
                "Per SOP-012 Device Quarantine: Attach the red 'OUT OF SERVICE' tag to the device, "
                "power it down, and move it to the designated equipment quarantine bay if possible. "
                "Do not allow any clinical use until Biomedical Engineering signs off on return-to-service. "
                "Log the quarantine in the equipment register with the time, device serial, and your name."
            )
        elif "e-04" in t or "imbalance" in t:
            return (
                "E-04 is an imbalance detection error on the centrifuge. Critical: do NOT force the lid open or retry "
                "the spin immediately — this can damage the motor bearings. "
                "Steps: (1) Wait for the rotor to fully stop (listen for silence, ~30 sec). "
                "(2) Press the DOOR RELEASE button — do not pull. "
                "(3) Rebalance tubes exactly opposite each other by weight. "
                "(4) Restart. If E-04 recurs with a balanced load, the motor sensor is likely faulty — quarantine the device."
            )
        elif "battery" in t or "shut off" in t or "charging" in t:
            return (
                "For VitalsPro M5 battery/shutdown issues: (1) Visually inspect the dock — look for the solid green "
                "charging indicator, NOT just any light. An amber light means not charging. "
                "(2) Check dock pins: gently press the device into the dock firmly and listen for a click. "
                "(3) If battery was 'full' but still died during transport, the battery capacity has degraded — "
                "the dock's charge indicator can be misleading. Replace the battery pack (part #M5-BAT-02). "
                "(4) If a third battery has the same issue, the dock or charging circuit is faulty — escalate to Biomed."
            )
        elif "autoclave" in t or "steriliz" in t or "sterile" in t:
            return (
                "For SteriPro autoclave sterilization failures: (1) A failed biological indicator is a Level 1 safety failure "
                "— do NOT use any instruments from that cycle. Quarantine them. "
                "(2) Check the door seal: run a finger around the inner gasket. If it's cracked, brittle, or has residue, "
                "the seal must be replaced before next use. "
                "(3) Run a second Bowie-Dick test cycle. If it also fails, take the autoclave out of service immediately. "
                "(4) All failed indicator strips must be logged in the sterilization record book with date, cycle number, and your signature."
            )
        elif "sop" in t or "procedure" in t or "protocol" in t:
            return (
                "The ClinicOps knowledge base includes: SOP-011 (Biohazard Spill Response), "
                "SOP-012 (Device Quarantine Procedure), plus device manuals for the Centrifuge C400, "
                "VitalsPro M5 Monitor, and SteriPro Autoclave. Which procedure would you like details on?"
            )
        elif "hello" in t or "hi" in t or "hey" in t:
            return (
                "Hello! I'm the ClinicOps AI Copilot. I can help you troubleshoot clinical device issues, "
                "walk you through SOPs, or guide you step-by-step through resolving an incident. "
                "What device or situation can I help with today?"
            )
        else:
            # Retrieve from vector store in mock mode for best-effort answer
            if self.retrieval_service:
                try:
                    chunks = self.retrieval_service.search(transcript, top_k=2)
                    if chunks:
                        best_chunk, score = chunks[0]
                        if score > 0.1:
                            return (
                                f"Based on {best_chunk.file_name} ({best_chunk.section_title}): "
                                f"{best_chunk.content[:400].strip()}... "
                                f"Would you like more detail on any specific step?"
                            )
                except Exception:
                    pass
            return (
                f"I don't have a specific protocol for that in my current knowledge base. "
                f"Could you give me more context — is this about a specific device, error code, or procedure?"
            )

    # ------------------------------------------------------------------
    # Resolution Loop Helpers
    # ------------------------------------------------------------------
    def _generate_next_resolution_step(self, session: Dict[str, Any]) -> str:
        """Returns the next step in the resolution sequence, or triggers escalation."""
        steps = session.get("resolution_steps", [])
        idx = session.get("resolution_index", 0)

        if idx < len(steps):
            step = steps[idx]
            session["resolution_index"] = idx + 1
            action = step.get("action", "")
            checkpoint = step.get("checkpoint", "")
            if_fails = step.get("if_fails", "")
            response = f"Step {idx + 1}: {action}"
            if checkpoint:
                response += f" — After doing this, {checkpoint.lower()}"
            if if_fails and idx + 1 == len(steps):
                response += f". Note: {if_fails}"
            response += ". Let me know if that worked, or if you're still seeing the issue."
            return response
        else:
            # All steps exhausted
            session["escalation_triggered"] = True
            device = session["slots"].get("machine", "the device")
            steps_tried = len(steps)
            return (
                f"I've walked you through all {steps_tried} standard resolution steps for this issue on {device}, "
                f"and the problem persists. This indicates a hardware or internal component failure that "
                f"requires a trained Biomedical Engineer. "
                f"Would you like me to log a repair request and book a Biomedical Engineering appointment? "
                f"I'll include all the steps we've tried so the technician arrives prepared."
            )

    def _generate_repair_request(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Generates a structured repair/appointment payload."""
        slots = session.get("slots", {})
        steps_tried = [s.get("action", "") for s in session.get("resolution_steps", [])]
        return {
            "type": "repair_request",
            "device": slots.get("machine", "Unknown"),
            "problem": slots.get("problem", "Unknown"),
            "location": slots.get("room", "Unknown"),
            "reported_by": slots.get("reported_by_role", "Unknown"),
            "steps_already_tried": steps_tried,
            "urgency": "high" if session.get("escalation_triggered") else "standard",
            "status": "pending_appointment"
        }

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------
    def process_push_to_talk(self, audio_bytes: bytes, audio_format: str,
                             incident_metadata: Dict[str, Any],
                             core_pipeline_func: callable) -> Dict[str, Any]:
        """
        Stateful Smart Multi-Turn Voice Processing:
        1. Transcribe audio
        2. Detect intent (general Q, incident report, slot answer, resolution check)
        3. Route accordingly — general Q gets RAG answer, incident report fills slots
        4. When slots complete → run pipeline → begin step-by-step resolution loop
        5. On resolution failure → escalate to technician appointment
        """
        print("[VoiceService] Processing Push-To-Talk...")

        session_id = incident_metadata.get("session_id", "default_session")
        session = self._get_or_create_session(session_id)

        # 1. Transcribe
        transcript = self.transcriber.transcribe(audio_bytes, audio_format, metadata=incident_metadata)
        session["history"].append({"role": "user", "text": transcript})

        # 2. Detect intent
        intent = self._detect_intent(
            transcript,
            last_asked_slot=session.get("last_asked_slot"),
            pipeline_completed=session.get("pipeline_completed", False)
        )
        print(f"[VoiceService] Intent detected: '{intent}' for transcript: '{transcript}'")

        # ------------------------------------------------------------------
        # PATH A: Awaiting appointment confirmation
        # ------------------------------------------------------------------
        if session.get("awaiting_appointment_confirm"):
            t_lower = transcript.lower()
            if any(w in t_lower for w in ["yes", "please", "go ahead", "confirm", "book", "ok", "okay"]):
                repair_payload = self._generate_repair_request(session)
                session["awaiting_appointment_confirm"] = False
                final_text = (
                    f"Done. I've logged a repair request for {repair_payload['device']} "
                    f"and notified Biomedical Engineering. A technician will be assigned shortly. "
                    f"In the meantime, please apply the OUT-OF-SERVICE tag to the device per SOP-012. "
                    f"Your request ID is REQ-{session_id[:8].upper()}."
                )
            else:
                final_text = (
                    "Understood — I won't book an appointment right now. "
                    "The incident has been logged. Let me know if anything changes or if you need further help."
                )
                repair_payload = None

            session["history"].append({"role": "assistant", "text": final_text})
            return {
                "status": "complete",
                "transcript": transcript,
                "history": session["history"],
                "extracted_slots": session["slots"],
                "final_text_response": final_text,
                "spoken_response_data": self.synthesizer.synthesize(final_text),
                "pipeline_handoff_payload": repair_payload
            }

        # ------------------------------------------------------------------
        # PATH B: General knowledge question — answer with RAG immediately
        # ------------------------------------------------------------------
        if intent == "general_question":
            print(f"[VoiceService] Routing to general RAG response.")
            final_text = self._generate_general_response(transcript, session["history"])
            session["history"].append({"role": "assistant", "text": final_text})
            return {
                "status": "conversational",
                "transcript": transcript,
                "history": session["history"],
                "extracted_slots": session["slots"],
                "final_text_response": final_text,
                "spoken_response_data": self.synthesizer.synthesize(final_text),
                "pipeline_handoff_payload": None
            }

        # ------------------------------------------------------------------
        # PATH C: Post-pipeline resolution loop / resolution failure check
        # ------------------------------------------------------------------
        if session.get("pipeline_completed"):
            t_lower = transcript.lower()

            # Check if they confirmed it worked
            if any(w in t_lower for w in ["worked", "fixed", "resolved", "better", "good", "done", "thank"]):
                final_text = (
                    "Excellent! I'm glad that resolved it. I've updated the incident log. "
                    "Let me know if you run into anything else."
                )
                session["history"].append({"role": "assistant", "text": final_text})
                return {
                    "status": "resolved",
                    "transcript": transcript,
                    "history": session["history"],
                    "extracted_slots": session["slots"],
                    "final_text_response": final_text,
                    "spoken_response_data": self.synthesizer.synthesize(final_text),
                    "pipeline_handoff_payload": session.get("cached_decision")
                }

            # Resolution failure — try next step or escalate
            if intent == "resolution_check" or any(sig in t_lower for sig in _RESOLUTION_FAILURE_SIGNALS):
                # Check if escalation is already triggered and awaiting confirmation
                if session.get("escalation_triggered"):
                    session["awaiting_appointment_confirm"] = True
                    final_text = self._generate_next_resolution_step(session)  # Will return escalation message again
                    # Override since we're already triggered
                    final_text = (
                        "It sounds like the issue is still unresolved. "
                        "Shall I go ahead and log a repair request and book a Biomedical Engineering visit?"
                    )
                else:
                    final_text = self._generate_next_resolution_step(session)
                    if session.get("escalation_triggered"):
                        session["awaiting_appointment_confirm"] = True

                session["history"].append({"role": "assistant", "text": final_text})
                return {
                    "status": "resolving",
                    "transcript": transcript,
                    "history": session["history"],
                    "extracted_slots": session["slots"],
                    "final_text_response": final_text,
                    "spoken_response_data": self.synthesizer.synthesize(final_text),
                    "pipeline_handoff_payload": session.get("cached_decision")
                }

            # Generic post-completion Q&A (same device context)
            final_text = self._generate_general_response(transcript, session["history"])
            session["history"].append({"role": "assistant", "text": final_text})
            return {
                "status": "complete",
                "transcript": transcript,
                "history": session["history"],
                "extracted_slots": session["slots"],
                "final_text_response": final_text,
                "spoken_response_data": self.synthesizer.synthesize(final_text),
                "pipeline_handoff_payload": session.get("cached_decision")
            }

        # ------------------------------------------------------------------
        # PATH D: Incident slot filling
        # ------------------------------------------------------------------

        # Capture slot answer if we explicitly asked last turn
        last_slot = session.get("last_asked_slot")
        if last_slot and not session["slots"][last_slot] and len(transcript.strip()) > 1:
            session["slots"][last_slot] = transcript.strip().title()

        # Extract any additional slots from the full utterance
        session["slots"] = self._extract_slots(transcript, session["slots"])

        # Early memory check: if machine + problem are known, look for recurrence
        if session["slots"]["machine"] and session["slots"]["problem"] and self.memory_matcher:
            try:
                search_text = f"Device: {session['slots']['machine']}\nDescription: {session['slots']['problem']}"
                memory_result = self.memory_matcher.analyze_incident(search_text)
                if memory_result.bias_escalation and not session.get("_memory_warned"):
                    session["_memory_warned"] = True
                    device = session["slots"]["machine"]
                    warning = (
                        f"Heads up — I found {len(memory_result.similar_incidents)} similar past incidents "
                        f"with {device}. This appears to be a recurring issue, "
                        f"which may require escalation to Biomedical Engineering regardless of the immediate fix. "
                        f"I'll continue to help you resolve it now."
                    )
                    session["history"].append({"role": "assistant", "text": warning})
                    # Still continue to slot collection (don't return yet)
            except Exception as e:
                print(f"[VoiceService] Memory check error: {e}")

        # Check if we still need critical slots
        missing_slot_key = self._get_missing_critical_slot(session["slots"])
        if missing_slot_key:
            session["last_asked_slot"] = missing_slot_key
            question = self._generate_clarification(session["slots"])
            session["history"].append({"role": "assistant", "text": question})
            return {
                "status": "clarifying",
                "transcript": transcript,
                "history": session["history"],
                "extracted_slots": session["slots"],
                "final_text_response": question,
                "spoken_response_data": self.synthesizer.synthesize(question),
                "pipeline_handoff_payload": None
            }

        # ------------------------------------------------------------------
        # PATH E: All critical slots filled — run the core pipeline
        # ------------------------------------------------------------------
        print(f"[VoiceService] Slots complete. Handing off to core pipeline.")
        slots = session["slots"]

        combined_description = (
            f"Reported by {slots.get('reported_by_role', 'staff')} "
            f"{'in ' + slots['room'] if slots.get('room') else ''}. "
            f"Machine: {slots['machine']}. "
            f"Problem: {slots['problem']}"
        ).strip()

        handoff_payload = incident_metadata.copy()
        handoff_payload["description"] = combined_description
        handoff_payload["device_id"] = slots["machine"]

        decision_dict = core_pipeline_func(handoff_payload)
        session["pipeline_completed"] = True
        session["cached_decision"] = decision_dict

        # Extract step-by-step resolution steps from decision output
        resolution_steps = decision_dict.get("resolution_steps", [])
        if not resolution_steps:
            # Fallback: wrap recommended_actions as ordered steps
            for i, action in enumerate(decision_dict.get("recommended_actions", []), 1):
                resolution_steps.append({"step": i, "action": action, "checkpoint": "", "if_fails": ""})
        session["resolution_steps"] = resolution_steps
        session["resolution_index"] = 0

        escalate = decision_dict.get("escalate", False)
        technician_required = decision_dict.get("technician_required", False)
        diagnosis = decision_dict.get("diagnosis", "")
        escalation_reason = decision_dict.get("escalation_reason", "")
        book_reason = decision_dict.get("book_appointment_reason", "")

        if escalate or technician_required:
            reason_text = escalation_reason or book_reason or "This issue requires specialist attention."
            final_text = (
                f"I've assessed the incident. {diagnosis} "
                f"This situation requires immediate escalation: {reason_text} "
                f"I recommend taking {slots['machine']} out of service now per SOP-012. "
                f"Would you like me to log a repair request and book a Biomedical Engineering appointment?"
            )
            session["escalation_triggered"] = True
            session["awaiting_appointment_confirm"] = True
        else:
            # Start step-by-step with the first resolution step
            diagnosis_text = f"I've assessed the issue: {diagnosis} " if diagnosis else ""
            first_step_text = self._generate_next_resolution_step(session)
            final_text = f"{diagnosis_text}Let's resolve this step by step. {first_step_text}"

        session["history"].append({"role": "assistant", "text": final_text})
        return {
            "status": "resolving",
            "transcript": transcript,
            "history": session["history"],
            "extracted_slots": slots,
            "final_text_response": final_text,
            "spoken_response_data": self.synthesizer.synthesize(final_text),
            "pipeline_handoff_payload": decision_dict
        }

    def process_streaming_chunk(self, chunk: bytes, session_id: str) -> None:
        """Stub for future bidirectional streaming support."""
        raise NotImplementedError(
            "Full bidirectional streaming is not enabled in this MVP tier. "
            "Please use process_push_to_talk() for discrete voice transactions."
        )
