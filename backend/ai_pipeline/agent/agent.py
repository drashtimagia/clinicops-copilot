import json
from ai_pipeline.config import config
from ai_pipeline.retrieval.retriever import retrieve_context


def classify_intent(query: str, last_question: str) -> dict:
    """Hybrid intent recognition: Rules first, then tiny LLM fallback."""
    q = query.lower().strip()
    
    # Rule-based shortcuts
    if any(word in q for word in ["thank", "thanks", "goodbye", "bye", "okay", "ok"]):
        return {"intent": "gratitude_or_close", "confidence": 1.0}
    if q in ["yes", "no", "yeah", "nope", "correct", "incorrect"]:
        return {"intent": "answer_followup", "confidence": 1.0}
    if any(word in q for word in ["escalate", "technician", "repair", "broken", "nonfunctional", "broken wire", "sparks", "burning"]):
        return {"intent": "request_escalation", "confidence": 1.0}
    if any(word in q for word in ["another issue", "new issue", "different machine", "start over"]):
        return {"intent": "new_incident", "confidence": 1.0}

    # Slot keyword shortcuts
    roles = ["nurse", "lab technician", "doctor", "front desk", "biomedical technician", "operations manager"]
    rooms = ["lab 1", "lab 2", "icu", "er", "room 101", "room 102", "sterilization", "storage"]
    machines = ["centrifuge", "vitalspro", "monitor", "steripro", "autoclave", "infusion pump", "ecg machine", "blood analyzer", "sample fridge"]
    
    if any(rm in q for rm in rooms):
        return {"intent": "provide_slot_value", "confidence": 0.95}

    # Machine mapping logic
    machine_map = {
        "centrifuge": "Centrifuge C400",
        "monitor": "VitalsPro M5 Monitor",
        "vitalspro": "VitalsPro M5 Monitor",
        "vitals pro": "VitalsPro M5 Monitor",
        "autoclave": "SteriPro Autoclave",
        "steripro": "SteriPro Autoclave",
        "infusion pump": "Infusion Pump X2",
        "pump": "Infusion Pump X2",
        "ecg": "ECG Machine E200",
        "blood analyzer": "Blood Analyzer B100",
        "analyzer": "Blood Analyzer B100",
        "fridge": "Sample Fridge F1",
        "sample fridge": "Sample Fridge F1"
    }
    
    for key, canonical in machine_map.items():
        if key in q:
            print(f"[classify_intent] Rule-based machine match: {canonical}")
            return {"intent": "provide_slot_value", "confidence": 1.0}

    if any(r in q for r in roles):
        return {"intent": "provide_slot_value", "confidence": 0.95}
    
    # LLM fallback
    from ai_pipeline.agent.prompts import build_intent_classifier_prompt
    system_text = "You are a classifier. Return ONLY JSON."
    user_text = build_intent_classifier_prompt(query, [], last_question)
    
    try:
        client = config.bedrock_runtime
        response = client.converse(
            modelId="us.amazon.nova-lite-v1:0",
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            system=[{"text": system_text}],
            inferenceConfig={"temperature": 0.0}
        )
        output_text = response['output']['message']['content'][0]['text']
        output_text = output_text.strip().lstrip('```json').rstrip('```').strip()
        data = json.loads(output_text)
        print(f"[classify_intent] LLM Result: {data.get('intent')} ({data.get('confidence')})")
        return data
    except Exception as e:
        print(f"[classify_intent] LLM Error: {str(e)}")
        return {"intent": "unclear", "confidence": 0.0}


def run_agent(query: str, slots: dict, conversation_history: list, last_question: str = None) -> dict:
    """
    Standalone multi-turn troubleshooting agent with intent recognition and routing.
    """
    from ai_pipeline.agent.prompts import build_troubleshooting_system_prompt, build_troubleshooting_user_prompt
    
    # 0. Intent Recognition
    intent_data = classify_intent(query, last_question)
    intent = intent_data.get("intent", "unclear")
    
    # Partial Phrase Detection (Strict for Intake)
    partial_phrases = ["i am using the", "i'm using the", "it is in", "it's in", "i am a", "i'm a", "my role is", "i am at", "i'm at"]
    if any(query.lower().strip() == p for p in partial_phrases):
        print(f"[run_agent] Partial phrase detected: '{query}'. Reprompting.")
        intent = "unclear"

    # High-risk term shortcut
    high_risk = any(word in query.lower() for word in ["sparks", "burning", "smoke", "overheating", "broken wire", "electrical"])
    if high_risk:
        intent = "request_escalation"

    # Slot Commitment for Issue Description (Backup)
    if intent == "describe_issue" and not slots.get("problem"):
        print(f"[run_agent] Manual problem commit: {query}")
        slots["problem"] = query

    # Routing
    context = []
    # Skip retrieval for intake or simple turns
    if intent in ["describe_issue", "answer_followup", "unclear", "provide_slot_value"] and not high_risk:
        # Run retrieval if we have a machine and something that looks like an issue
        has_machine = slots.get("machine")
        is_describing = intent == "describe_issue" or (intent == "provide_slot_value" and len(query.split()) > 5)
        if has_machine and is_describing:
            context = retrieve_context(query)
            
    elif intent == "gratitude_or_close":
        return {
            "message": "You're welcome. Standing by if you need anything else.",
            "confidence": 1.0, "escalate": slots.get("escalate", False),
            "status": "complete", "extracted_slots": slots,
            "pipeline_handoff_payload": {}
        }
    elif intent == "request_escalation" or high_risk:
        reason = "User requested escalation" if not high_risk else "High-risk safety issue detected"
        print(f"[run_agent] Routing to immediate escalation. Reason: {reason}")
        return {
            "message": f"{'SAFETY ALERT: ' if high_risk else ''}Escalating to biomedical technician.\n- Shut off and unplug device.\n- Label as out of service.\n- Wait for technician.",
            "confidence": 1.0, "escalate": True, "status": "complete",
            "extracted_slots": slots,
            "pipeline_handoff_payload": {
                "escalation_reason": reason,
                "recommended_actions": ["Unplug device", "Label out of service", "Call BioMed"],
                "downtime_bucket": "temporarily_unavailable"
            }
        }

    # 2. Build normal troubleshooting prompt
    system_text = build_troubleshooting_system_prompt()
    user_text = build_troubleshooting_user_prompt(query, slots, context, conversation_history)
    
    client = config.bedrock_runtime
    model_id = "us.amazon.nova-lite-v1:0"
    
    try:
        print(f"[run_agent] dispatching to LLM (Intent: {intent})")
        response = client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            system=[{"text": system_text}],
            inferenceConfig={"temperature": 0.0}
        )
        
        output_text = response['output']['message']['content'][0]['text']
        output_text = output_text.strip().lstrip('```json').rstrip('```').strip()
        data = json.loads(output_text)
        
        # Merge manually committed problem if LLM missed it or returned null
        if slots.get("problem") and not data.get("extracted_slots", {}).get("problem"):
             if "extracted_slots" not in data: data["extracted_slots"] = {}
             data["extracted_slots"]["problem"] = slots["problem"]
             
        return data
        
    except Exception as e:
        import traceback
        print(f"[run_agent] Error: {str(e)}")
        traceback.print_exc()
        return {
            "message": "I'm having trouble connecting to my knowledge base. Please try again or contact support.",
            "confidence": 0.0,
            "escalate": True,
            "status": "complete",
            "extracted_slots": slots,
            "pipeline_handoff_payload": {
                "escalation_reason": "Agent execution failure",
                "recommended_actions": ["Contact technical support"],
                "downtime_bucket": "temporarily_unavailable",
                "reroute_recommendation": "Use alternative devices.",
                "staff_notification": "Technical error in assistant.",
                "affected_roles": [{"role": "Clinical Staff", "impact": "Troubleshooting unavailable"}]
            }
        }


class Agent:
    """Legacy Agent class for existing text-only routes."""
    def __init__(self):
        self.client = config.bedrock_runtime
        self.model_id = config.NOVA_TEXT_MODEL_ID

    def evaluate_incident(self, incident_text: str, incident_id: str,
                          retrieved_chunks: list, memory_result=None) -> dict:
        # Keeping this for backward compatibility if needed by process_incident
        slots = {
            "reported_by_role": None,
            "room": None,
            "machine": None,
            "problem": incident_text
        }
        return run_agent(incident_text, slots, [])
