# ClinicOps Copilot

AI-powered clinic---

## Hackathon Demos

We provide two pre-configured zero-dependency demo entries to evaluate the Copilot output schema without needing keys:

### 1. Batch Text Demo
Runs the medical pipeline over all 10 mock incident files and tracks escalation correctness.
```bash
python evaluate_pipeline.py
```

### 2. Live Voice Web UI Demo
A complete Vanilla HTML/JS Push-to-Talk interface running with Amazon Nova 2 Sonic multimodality.
1. Start the backend: `python server.py`
2. Open in browser: `http://localhost:8080`
3. Click and hold the microphone to synthesize a clinical recommendation.

### 3. Scripted Voice Backend Scenario Tests
Runs 3 specific text-grounded HTTP unit tests against the voice API (Normal, Safety Hazard, and Repeated Memory Matches). Note: You must start `server.py` first.
```bash
python demo_voice_scenarios.py
```
## Features
- Incident troubleshooting from manuals and SOPs
- RAG-powered grounded responses
- Memory for repeated incidents
- Smart escalation for unresolved or unsafe cases

## Tech Stack
- Amazon Nova
- Python / FastAPI
- Vector search / RAG
- React / Next.js

