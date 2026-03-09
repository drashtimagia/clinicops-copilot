import os

class Config:
    # Environment Variables
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
    AWS_BEARER_TOKEN_BEDROCK = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
    
    NOVA_TEXT_MODEL_ID = os.getenv("NOVA_TEXT_MODEL_ID", "amazon.nova-micro-v1:0")
    NOVA_EMBED_MODEL_ID = os.getenv("NOVA_EMBED_MODEL_ID", "amazon.titan-embed-text-v1")
    
    # Multimodal Voice Support (Nova 2 Sonic MVP)
    _enable_voice_str = str(os.getenv("ENABLE_VOICE", "1")).lower()
    ENABLE_VOICE = _enable_voice_str in ('1', 'true', 't', 'yes', 'y')
    NOVA_VOICE_MODEL_ID = os.getenv("NOVA_VOICE_MODEL_ID", "amazon.nova-2-sonic-v1:0")
    VOICE_LOCALE = os.getenv("VOICE_LOCALE", "en-US")
    VOICE_ID = os.getenv("VOICE_ID", "Joanna")
    
    # Toggle whether to actually call AWS/Amazon Nova. 
    # Defaults to True (1) for MVP demo reliability without live credentials.
    _mock_val = str(os.getenv("USE_MOCK_MODEL", "1")).lower()
    MOCK_LLM_RESPONSE = _mock_val in ('1', 'true', 't', 'yes', 'y')

    SYSTEM_PROMPT = """You are the ClinicOps AI Copilot.
Your job is to analyze clinical device incidents and recommend the Next Best Action for clinic staff.
You must ground your answers in the provided SOPs and Historical Incidents.

Output REQUIREMENTS:
1. "next_best_action": Clear, actionable step for the user to take.
2. "escalate": Boolean. True if the situation is dangerous, repeatedly failing, or explicitly requires escalation based on SOPs.
3. "confidence_score": 0.0 to 1.0.
4. "citations": Array of objects detailing which SOP or Incident informed the action.

Analyze the user's issue, map it to the retrieved context, and return strictly JSON."""

    @classmethod
    def validate(cls):
        """
        Validates that required credentials are present if MOCK mode is disabled.
        Throws a ValueError with helpful instructions if validation fails.
        """
        if not cls.MOCK_LLM_RESPONSE:
            missing_keys = []
            
            # For this MVP, we want either standard AWS access keys OR the bearer token
            has_standard_keys = cls.AWS_ACCESS_KEY_ID and cls.AWS_SECRET_ACCESS_KEY
            has_bearer_token = cls.AWS_BEARER_TOKEN_BEDROCK
            
            if not has_standard_keys and not has_bearer_token:
                raise ValueError(
                    "Configuration Error: USE_MOCK_MODEL is disabled (real calls enabled), "
                    "but no AWS credentials were found.\n"
                    "Please provide either AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or an AWS_BEARER_TOKEN_BEDROCK "
                    "in your environment or .env file."
                )
                
            if not cls.NOVA_TEXT_MODEL_ID or not cls.NOVA_EMBED_MODEL_ID:
                raise ValueError("Configuration Error: Nova Model IDs missing from environment.")
                
            if cls.ENABLE_VOICE and not cls.NOVA_VOICE_MODEL_ID:
                 raise ValueError("Configuration Error: NOVA_VOICE_MODEL_ID must be set if ENABLE_VOICE=1 and USE_MOCK_MODEL=0.")

# Instantiate a global config object correctly pointing to attributes
config = Config()
config.validate()
