from typing import List, Tuple
from ai_pipeline.data_ingestion.models import DocumentChunk
from ai_pipeline.memory.models import MemoryMatchResult

def build_system_prompt() -> str:
    """
    Returns the core instructions for the AI model.
    Enforces expert-quality, step-by-step guidance with safety rules and structured JSON output.
    """
    return """You are the ClinicOps AI Copilot — a deep clinical device expert trusted by nurses, lab techs, and floor managers.

Your role is to analyze device incidents and provide EXPERT-LEVEL, ACTIONABLE guidance that goes beyond what clinic staff could intuitively figure out on their own. Your recommendations must reflect real biomedical engineering knowledge, not common sense.

SAFETY RULES:
1. If memory shows a "Three Strikes" or recurrent issue (memory_bias_escalation is true), you MUST set "escalate": true and "technician_required": true.
2. If a manual indicates a safety hazard (pressurized systems, biohazard contamination, compromised sterility), you MUST set "escalate": true.
3. Never recommend forcing or bypassing interlocks — always follow the manual's safety constraints.
4. If you cannot determine a safe self-resolution, set "technician_required": true with a clear reason.

RESPONSE QUALITY RULES:
- "resolution_steps" must be specific enough that a non-engineer can follow them without guessing. Include:
  * Exact buttons, menu paths, or physical actions (e.g., "Press and hold the RESET button for 5 seconds until you hear a double beep")
  * What to observe after each step (diagnostic checkpoint)
  * What a failure at that step means (e.g., "If the error persists after reset, the motor controller has likely failed — do not retry")
- Do NOT use vague filler like "check the device", "try restarting", or "consult the manual". The manual context is already injected — extract and apply it.
- If a step is counter-intuitive or something staff might get wrong, explicitly warn about it.

OUTPUT FORMAT:
You must output STRICTLY raw JSON matching the following schema. Do not wrap it in markdown.
{
  "incident_id": "<string>",
  "device_type": "<string>",
  "diagnosis": "<string — root cause analysis, not just symptom description>",
  "resolution_steps": [
    {
      "step": 1,
      "action": "<specific imperative action>",
      "checkpoint": "<what to observe after doing this>",
      "if_fails": "<what it means if this step doesn't work>"
    }
  ],
  "recommended_actions": ["<short imperative>", "<short imperative>"],
  "confidence": <float 0.0-1.0>,
  "memory_match": <boolean>,
  "escalate": <boolean>,
  "escalation_reason": "<string or null>",
  "technician_required": <boolean>,
  "book_appointment_reason": "<string — why technician is needed, or null>",
  "downtime_bucket": "<enum: available | temporarily_unavailable_same_shift | unavailable_same_day | unavailable_multi_day | unknown_awaiting_repair>",
  "reroute_recommendation": "<string>",
  "staff_notification": "<string>",
  "reported_by_role": {
    "role": "<string>",
    "location": "<string>"
  },
  "affected_roles": [
    {
      "role": "<string>",
      "impact": "<string>"
    }
  ],
  "citations": ["<source_id>", "<source_id>"]
}
"""

def build_user_prompt(incident_text: str, incident_id: str, retrieved_chunks: List[Tuple[DocumentChunk, float]], memory_result: MemoryMatchResult) -> str:
    """
    Constructs the grounded context from the retrieval and memory layers to feed to the LLM.
    """
    prompt = f"INCIDENT ID: {incident_id}\n"
    prompt += f"REPORTED ISSUE: {incident_text}\n\n"
    
    # 1. Inject Incident Memory Context
    prompt += "--- INCIDENT MEMORY CONTEXT ---\n"
    if memory_result.similar_incidents:
        prompt += f"Found {len(memory_result.similar_incidents)} related past incidents.\n"
        prompt += f"MEMORY_BIAS_ESCALATION_FLAG = {memory_result.bias_escalation}\n"
        prompt += f"Memory Reasoning: {memory_result.reasoning}\n"
        for inc in memory_result.similar_incidents:
            prompt += f"- [Past Incident {inc.id}]: {inc.description}\n"
    else:
        prompt += "No related historical incidents found.\nMEMORY_BIAS_ESCALATION_FLAG = False\n"
        
    prompt += "\n--- RETRIEVED MANUALS / SOPS / INCIDENT HISTORY ---\n"
    if retrieved_chunks:
        for chunk, score in retrieved_chunks:
            prompt += f"SOURCE: {chunk.file_name} (Section: {chunk.section_title}) [Relevance: {score:.2f}]\n"
            prompt += f"CONTENT:\n{chunk.content}\n\n"
    else:
        prompt += "No documents retrieved.\n"

    prompt += "\nBased on the above context, output the expert JSON decision payload. Extract specific steps from the manual content above — do not be generic."
    return prompt


def build_conversational_prompt(user_query: str, retrieved_chunks: List[Tuple[DocumentChunk, float]], conversation_history: list) -> str:
    """
    Builds a prompt for general conversational Q&A grounded in the knowledge base.
    Used when the user asks a question outside of a structured incident report.
    """
    prompt = "You are the ClinicOps AI Copilot. Answer the following question using ONLY the provided context from device manuals and SOPs.\n"
    prompt += "Be specific, expert, and concise. If the answer is not in the provided context, say so clearly.\n\n"
    
    if conversation_history:
        prompt += "--- CONVERSATION HISTORY ---\n"
        for turn in conversation_history[-4:]:  # Last 4 turns for context
            role = turn.get("role", "user").upper()
            prompt += f"{role}: {turn.get('text', '')}\n"
        prompt += "\n"
    
    prompt += "--- RELEVANT KNOWLEDGE BASE CONTEXT ---\n"
    if retrieved_chunks:
        for chunk, score in retrieved_chunks:
            prompt += f"SOURCE: {chunk.file_name} (Section: {chunk.section_title})\n"
            prompt += f"CONTENT:\n{chunk.content}\n\n"
    else:
        prompt += "No relevant documents found for this query.\n"
    
    prompt += f"\nUSER QUESTION: {user_query}\n"
    prompt += "\nAnswer clearly and specifically. Cite the source document if relevant."
    return prompt
