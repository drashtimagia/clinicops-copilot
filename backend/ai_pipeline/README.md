# ClinicOps Copilot AI Pipeline

This folder contains the AI layer for the ClinicOps Copilot MVP. It is designed to be minimal, simple, and auditable for hackathon purposes.

## Core Features
- **Retrieval Engine**: Finds relevant Standard Operating Procedures (SOPs) and past incidents given a new incident report.
- **Orchestration**: Combines retrieved context with a large language model (Amazon Nova) to determine the Next Best Action and Escalation status.
- **Structured Output**: Guarantees that the pipeline always outputs clean, structured JSON containing the recommendation, escalation flag, and citations.

## Structure
- `mock_data/`: Contains static JSON files acting as our database of SOPs and past incident memory.
- `core/`: 
  - `models.py`: Data classes defining our structured output schema.
  - `retriever.py`: Logic to mock-search the static JSON files based on incident text or keywords.
  - `orchestrator.py`: The main AI flow that manages context, prompt generation, and calls to the generative model.
- `config.py`: Configuration details for prompt templates and mock environment toggles.

## Environment Setup & Credentials
To switch from local Mock mode to live AWS Bedrock calls, you must configure your environment securely:
1. Copy the example file: `cp ai_pipeline/.env.example ai_pipeline/.env`
2. Open `ai_pipeline/.env` and paste in your `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (or your temporary `AWS_BEARER_TOKEN_BEDROCK`).
3. Set `USE_MOCK_MODEL=0` in the `.env` file to enable live API calls.

**Security Warning**: Ensure that `.env` is never committed to GitHub. It has already been added to `.gitignore`.
