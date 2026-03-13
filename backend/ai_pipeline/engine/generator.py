from typing import List, Tuple
from abc import ABC, abstractmethod
import json

from ai_pipeline.config import config
from ai_pipeline.data_ingestion.models import DocumentChunk
from ai_pipeline.memory.models import MemoryMatchResult
from .models import DecisionOutput
from .prompts import build_system_prompt, build_user_prompt

class DecisionEngine(ABC):
    @abstractmethod
    def evaluate_incident(self, incident_text: str, incident_id: str,
                          retrieved_chunks: List[Tuple[DocumentChunk, float]],
                          memory_result: MemoryMatchResult) -> DecisionOutput:
        pass

class BedrockNovaGenerator(DecisionEngine):
    """
    Live Amazon Bedrock Nova integration using the converse API.
    """
    def __init__(self):
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 is required. Please run `pip install boto3`")
            
        self.client = boto3.client(
            service_name='bedrock-runtime',
            region_name=config.AWS_REGION,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            aws_session_token=config.AWS_SESSION_TOKEN
        )
        self.model_id = config.NOVA_TEXT_MODEL_ID
        
    def evaluate_incident(self, incident_text: str, incident_id: str,
                          retrieved_chunks: List[Tuple[DocumentChunk, float]],
                          memory_result: MemoryMatchResult) -> DecisionOutput:
                              
        system_text = build_system_prompt()
        user_text = build_user_prompt(incident_text, incident_id, retrieved_chunks, memory_result)

        try:
            response = self.client.converse(
                modelId=self.model_id,
                messages=[{"role": "user", "content": [{"text": user_text}]}],
                system=[{"text": system_text}],
                inferenceConfig={"temperature": 0.0} # We want factual, grounded extraction
            )
            
            output_text = response['output']['message']['content'][0]['text']
            # Basic json cleanup in case the LLM wrapped it despite instructions
            output_text = output_text.strip().lstrip('```json').rstrip('```').strip()
            
            data = json.loads(output_text)
            return DecisionOutput(**data)
            
        except Exception as e:
            print(f"Error calling Bedrock Nova: {e}")
            return self._fallback(incident_id)

    def _fallback(self, inc_id: str) -> DecisionOutput:
        return DecisionOutput(inc_id, "Unknown", "AWS Call Failed", [], 0.0, False, True, "API Offline", [])

class MockOfflineGenerator(DecisionEngine):
    """
    Offline mock wrapper for rapid local testing. Rules based heuristics to simulate Nova reasoning.
    """
    def evaluate_incident(self, incident_text: str, incident_id: str,
                          retrieved_chunks: List[Tuple[DocumentChunk, float]],
                          memory_result: MemoryMatchResult) -> DecisionOutput:
                              
        # Simulate LLM thinking time and rule-following
        escalate = False
        reasoning = None
        device_type = "Unknown Device"
        
        # Rule 1: Memory matches
        if memory_result.bias_escalation:
            escalate = True
            reasoning = "Memory Match: " + memory_result.reasoning
        
        # Rule 2: Basic keyword hazards
        text_lower = incident_text.lower()
        if "biohazard" in text_lower or "blood has spilled" in text_lower or "blood sample" in text_lower:
            escalate = True
            if not reasoning:
                reasoning = "Biohazard detected in issue description."
                
        if "biological indicator" in text_lower or "sterile" in text_lower or "low pressure" in text_lower or "cracked" in text_lower:
            escalate = True
            if not reasoning:
                reasoning = "Critical safety or sterilization failure detected."
        
        if "monitor" in text_lower or "VPM" in incident_text:
            device_type = "Vitals Monitor M5"
        elif "centrifuge" in text_lower or "C400" in incident_text:
            device_type = "Centrifuge C400"
        
        actions = ["Check power connection.", "Review device manual for error codes."]
        downtime = "unknown_awaiting_repair"
        reroute = "Awaiting initial assessment."
        notification = "Device reported offline. Stand by."
        impacts = [{"role": "Nurse", "impact": "Delay use of device until assessed."}]
        
        if "E-04" in incident_text:
             actions = ["Power cycle the device.", "Do not force lid open."]
             downtime = "temporarily_unavailable_same_shift"
             reroute = "Use backup manual centrifuge in Lab B."
             notification = "Lab A centrifuge restarting. Divert STAT samples to Lab B."
             impacts = [
                 {"role": "Phlebotomist", "impact": "Walk samples to Lab B for next 30 mins."},
                 {"role": "Lab Tech", "impact": "Run E-04 clear sequence."}
             ]
             
        if escalate and "biohazard" in text_lower:
             downtime = "unavailable_same_day"
             reroute = "Room quarantined. Reroute completely to alternate suites."
             notification = "BIOHAZARD PROTOCOL. Standard cleaning halted, hazmat notified."
             impacts = [
                 {"role": "Doctor", "impact": "Reschedule procedures for this suite."},
                 {"role": "Janitorial", "impact": "DO NOT ENTER. Specialized team dispatched."}
             ]
             
        data = {
            "incident_id": incident_id,
            "device_type": device_type,
            "diagnosis": "Simulated evaluation of input issue.",
            "recommended_actions": actions,
            "confidence": 0.95,
            "memory_match": len(memory_result.similar_incidents) > 0,
            "escalate": escalate,
            "escalation_reason": reasoning,
            "downtime_bucket": downtime,
            "reroute_recommendation": reroute,
            "staff_notification": notification,
            "reported_by_role": {"role": "Nurse", "location": "Room 1"},
            "affected_roles": impacts,
            "citations": [c[0].file_name for c in retrieved_chunks]
        }
        
        return DecisionOutput(**data)
        
def get_decision_engine() -> DecisionEngine:
    if config.MOCK_LLM_RESPONSE:
        print("[DecisionEngine] Using Mock Offline Generator")
        return MockOfflineGenerator()
    else:
        print(f"[DecisionEngine] Using AWS Bedrock Nova: {config.NOVA_TEXT_MODEL_ID}")
        return BedrockNovaGenerator()
