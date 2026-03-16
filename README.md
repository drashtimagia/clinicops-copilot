# ClinicOps Copilot 🩺

ClinicOps Copilot is an AI-powered assistant designed for clinical staff to troubleshoot medical equipment incidents in real-time. It leverages RAG (Retrieval-Augmented Generation) over device manuals and SOPs to provide grounded, safe, and actionable operational advice.

## 🚀 Key Features

- **Multimodal Interaction**: Supports both text chat and real-time voice (Push-to-Talk).
- **Grounded Intelligence**: Troubleshooting steps are pulled directly from internal knowledge bases (Manuals & SOPs).
- **Flexible Data Intake**: Intelligently extracts "Reporter", "Location", and "Machine" from natural conversational flows.
- **Smart Escalation**: Automatically detects safety hazards or unresolved issues and suggests operational rerouting.
- **Real-time Synchronization**: Live updates to a dashboard "Context Map" as the conversation progresses.

## 🛠️ Technology Stack

- **Frontend**: React (Vite), Framer Motion, Socket.IO Client, Lucide-React.
- **Backend**: Python 3.12, Flask, Flask-SocketIO (Eventlet), FAISS.
- **AI Brain**: 
  - **Reasoning**: Amazon Bedrock (Nova Lite)
  - **Embeddings**: Amazon Titan G1
  - **STT**: Amazon Transcribe (via S3 integration)
  - **TTS**: Amazon Polly (Arthur voice)

## 📂 Project Structure

```text
clinicops-copilot/
├── backend/
│   ├── ai_pipeline/       # Core AI Logic (Agent, Retrieval, Voice)
│   ├── requirements.txt   # Backend dependencies
│   └── server.py          # Entry point (Flask + Socket.IO)
├── frontend/
│   ├── src/               # React components & styles
│   ├── dist/              # Production build artifacts
│   └── vite.config.js     # Frontend build configuration
├── data/
│   ├── manuals/           # Device manuals in Markdown
│   └── sops/              # Standard Operating Procedures
└── README.md
```

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.12+
- Node.js & npm (for frontend development)
- AWS Credentials with access to Bedrock, Transcribe, Polly, and S3.

### 1. Project Initialization
```bash
# Clone the repository
git clone https://github.com/drashtimagia/clinicops-copilot.git
cd clinicops-copilot

# Set up backend environment
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Configuration
Create a `.env` file in `backend/` with the following:
```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key_id
AWS_SECRET_ACCESS_KEY=your_secret_key
ENABLE_VOICE=true
```

### 3. Running the Application
```bash
# Start the Backend (Port 8080)
# From project root:
.venv/bin/python backend/server.py

# Access the UI
# Open in your browser: http://localhost:8080
```

## 🧪 Development & Testing
- **Frontend Build**: `cd frontend && npm run build`
- **Manual Verification**: Use the Text HUD for rapid iterating over slot-filling and reasoning without consuming audio tokens.
