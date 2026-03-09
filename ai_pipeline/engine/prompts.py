from typing import List, Tuple
from ai_pipeline.data_ingestion.models import DocumentChunk
from ai_pipeline.memory.models import MemoryMatchResult

def build_system_prompt() -> str:
    """
    Returns the core instructions for the AI model, enforcing safety rules and JSON output.
    """
    return """You are the ClinicOps AI Copilot.
Your job is to analyze clinical device incidents, cross-reference them with retrieved manuals/SOPs, and review historical incident memory to recommend the Next Best Action for clinic staff.

SAFETY RULES:
1. If the Incident Memory indicates a "Three Strikes" or recurrent issue (memory_bias_escalation is true), you MUST set "escalate" to true and "escalation_reason" should cite the memory match.
2. If the manual indicates a safety hazard (e.g., pressurized display warnings, biohazard spills), you MUST set "escalate" to true.
3. If an incident is routine and non-recurrent, provide the steps and set "escalate" to false.
4. Voice output constraint: The items in the "recommended_actions" array MUST be strictly imperative, short clinical commands (e.g., "Power cycle device."). Do not use ANY conversational filler like "I recommend" or "Please try to".

OUTPUT FORMAT:
You must output STRICTLY raw JSON matching the following schema. Do not wrap it in markdown block quotes (e.g., ```json).
{
  "incident_id": "<string>",
  "device_type": "<string>",
  "diagnosis": "<string>",
  "recommended_actions": ["<string>", "<string>"],
  "confidence": <float between 0.0 and 1.0>,
  "memory_match": <boolean>,
  "escalate": <boolean>,
  "escalation_reason": "<string or null>",
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
        
    prompt += "\n--- RETRIEVED MANUALS / SOPS ---\n"
    if retrieved_chunks:
        for chunk, score in retrieved_chunks:
            prompt += f"SOURCE: {chunk.file_name} (Section: {chunk.section_title})\n"
            prompt += f"CONTENT:\n{chunk.content}\n\n"
    else:
        prompt += "No documents retrieved.\n"

    prompt += "\nBased on the above context, output the JSON decision payload."
    return prompt
