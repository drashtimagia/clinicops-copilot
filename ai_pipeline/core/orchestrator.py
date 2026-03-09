import json
from .models import PipelineResponse, Citation
from .retriever import Retriever
from .. import config

class Orchestrator:
    def __init__(self):
        self.retriever = Retriever()

    def handle_incident(self, incident_text: str) -> PipelineResponse:
        """
        Main entry point for evaluating an incident.
        1. Retrieves relevant SOPs and past instances limit.
        2. Constructs a prompt for the model.
        3. Calls Amazon Nova (or a mock) and parses the strict JSON output.
        """
        # 1. Retrieve Context
        context = self.retriever.get_context(incident_text)
        sops = context.get('sops', [])
        incidents = context.get('past_incidents', [])

        # 2. Construct Prompt (Not heavily used in MVP MOCK mode, but shows architecture)
        prompt = self._build_prompt(incident_text, sops, incidents)

        # 3. Call Generative Model
        if config.MOCK_LLM_RESPONSE:
            raw_response = self._mock_call_llm(incident_text, sops, incidents)
        else:
            raw_response = self._call_amazon_nova(prompt)

        # 4. Parse and return structured response
        return self._parse_json_response(raw_response)

    def _build_prompt(self, text, sops, incidents):
        prompt = f"{config.SYSTEM_PROMPT}\n\nINCIDENT:\n{text}\n\nRELEVANT SOPS:\n"
        for s in sops:
            prompt += f"- {s.get('id')}: {s.get('title')}\n"
        prompt += "\nPAST INCIDENTS:\n"
        for i in incidents:
            prompt += f"- {i.get('id')}: {i.get('issue')} -> {i.get('lessons_learned')}\n"
        return prompt

    def _call_amazon_nova(self, prompt: str) -> dict:
        """
        Placeholder for real boto3 call.
        e.g. boto3.client('bedrock-runtime').invoke_model(...)
        """
        raise NotImplementedError("Real AWS calls are disabled in config.MOCK_LLM_RESPONSE = True")

    def _mock_call_llm(self, text: str, sops: list, incidents: list) -> dict:
        """
        A robust mock to guarantee demo reliability.
        We inspect the input text to return a convincing simulated JSON response.
        """
        text_lower = text.lower()
        
        # Scenario 1: Centrifuge error
        if "centrifuge" in text_lower or "e-04" in text_lower:
            return {
                "next_best_action": "Power cycle the centrifuge and verify tube weights are symmetrically balanced. Do not force the lid open.",
                "escalate": True if "force" in text_lower else False,
                "confidence_score": 0.95,
                "citations": [
                    {"source_id": "SOP-101", "snippet": "Power cycle the device... If error persists, escalate."},
                    {"source_id": "INC-2023-45", "snippet": "Staff attempted to restart... Resulted in broken latch."}
                ]
            }
            
        # Scenario 2: Monitor error
        elif "monitor" in text_lower or "battery" in text_lower:
            return {
                "next_best_action": "Check the indicator light on the dock. If green, the battery has failed and must be replaced from Supply Room B.",
                "escalate": False,
                "confidence_score": 0.92,
                "citations": [
                    {"source_id": "SOP-102", "snippet": "If green, battery pack has failed and must be replaced"},
                    {"source_id": "INC-2023-89", "snippet": "Always check dock indicator light to ensure charging"}
                ]
            }
            
        # Fallback generic response
        return {
            "next_best_action": "Assess the situation and consult the device manual.",
            "escalate": True,
            "confidence_score": 0.5,
            "citations": []
        }

    def _parse_json_response(self, response_dict: dict) -> PipelineResponse:
        """
        Validates and converts the raw dictionary into our enforced Data Schema.
        """
        citations = []
        for c in response_dict.get('citations', []):
            citations.append(Citation(
                source_id=c.get('source_id', 'Unknown'),
                relevance_snippet=c.get('snippet', '')
            ))
            
        return PipelineResponse(
            next_best_action=response_dict.get('next_best_action', 'Error processing action.'),
            escalate=response_dict.get('escalate', True),
            confidence_score=response_dict.get('confidence_score', 0.0),
            citations=citations
        )
