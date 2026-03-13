# ClinicOps Copilot - Backend Integration Guide

Welcome to the AI Pipeline component. This guide instructs backend engineers on how to securely configure and consume the AI decision engine.

## 1. Quick Start
The AI pipeline exposes a single, clean Python entrypoint. Standard web frameworks (Flask, FastAPI, Django) can simply import it:

```python
from ai_pipeline.api import process_incident

@app.post("/api/incidents")
def handle_incident(request):
    payload = request.json
    
    try:
        # Blocks while calling AWS Bedrock (or mock generator locally)
        ai_decision_json = process_incident(payload)
        
        # Save to DB, return to frontend...
        return ai_decision_json, 200
        
    except ValueError as e:
         return {"error": str(e)}, 400
    except Exception as e:
         return {"error": "AI Service failure"}, 500
```

## 2. API Contract

### Text Request Schema (Input)
`process_incident(payload: dict)` expects the following dictionary:
```json
{
  "incident_id": "INC-011",
  "device_id": "VPM5-9002",
  "description": "Monitor shut off mid transport, battery drain.",
  "reporter": "Nurse Jane"
}
```
*Note: `description` is required for text processing.*

### Voice Request Schema (Input)
`process_voice_incident(audio_format, audio_bytes, payload: dict)` expects raw audio in bytes and the same metadata above (but without `description`, as the transcriber generates it).

### Response Schema (Output)
`process_incident` returns a strict JSON-compatible dictionary. 
`process_voice_incident` wraps the decision dictionary inside a larger multimodal payload:
```json
{
  "decision": {
    "incident_id": "INC-011",
    "device_type": "Vitals Monitor M5",
    "diagnosis": "...",
    "recommended_actions": ["..."],
    "confidence": 0.95,
    "memory_match": true,
    "escalate": true,
    "escalation_reason": "...",
    "citations": ["vitals-monitor-m5.md"]
  },
  "transcript": "literal spoken text",
  "response_audio": b"..."
}
```

## 3. Configuration & Secrets Management

The AI Pipeline uses standard Environment Variables (`os.getenv`). At module load, it validates everything. **Do not hardcode secrets.**

See `.env.example` in the `ai_pipeline` folder.

**Required for MOCK offline testing (`USE_MOCK_MODEL=1`):**
- No AWS credentials required. The pipeline uses deterministic word-hashing embeddings and heuristic JSON generation.

**Required for LIVE Amazon Nova mode (`USE_MOCK_MODEL=0`):**
You must provide *either*:
1. Standard AWS Credentials: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_REGION`
2. OR Bearer Token: `AWS_BEARER_TOKEN_BEDROCK` and `AWS_REGION`

You must also define Core properties:
- `NOVA_TEXT_MODEL_ID` (e.g., `amazon.nova-micro-v1:0`)
- `NOVA_EMBED_MODEL_ID` (e.g., `amazon.titan-embed-text-v1`)

You can define Voice properties (Defaults to enabled):
- `ENABLE_VOICE=1`
- `NOVA_VOICE_MODEL_ID` (e.g. `amazon.nova-2-sonic-v1:0`)
- `VOICE_LOCALE` (e.g. `en-US`)
- `VOICE_ID` (e.g. `tiffany`)

## 4. Failure Modes
When the web server starts and imports `ai_pipeline.api`:
- **`ValueError: Missing required environment variable...`**: The config validator failed. You forgot to set an access key when `USE_MOCK_MODEL=0`. The app will intentionally crash on boot to prevent silent production failures.
- **`ImportError: boto3 is required...`**: When switching to live mode, ensure you have `$ pip install boto3`.
- **Runtime AWS Errors**: If `process_incident()` fails mid-call (throttle limit, network drop), it automatically degrades safely, returning an output with `diagnosis: "AWS Call Failed"` and `escalate: True` as a fail-safe.
