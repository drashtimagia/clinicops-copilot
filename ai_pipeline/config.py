import os
import io

# Zero-dependency manual .env loader
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with io.open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                clean_key = key.strip()
                clean_val = val.strip()
                # Stop Botocore from breaking on empty strings!
                if clean_key not in os.environ and clean_val:
                    os.environ[clean_key] = clean_val

class Config:
    # Environment Variables
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID") or None
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY") or None
    AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN") or None
    AWS_BEARER_TOKEN_BEDROCK = os.getenv("AWS_BEARER_TOKEN_BEDROCK") or None
    
    NOVA_TEXT_MODEL_ID = os.getenv("NOVA_TEXT_MODEL_ID", "amazon.nova-micro-v1:0")
    NOVA_EMBED_MODEL_ID = os.getenv("NOVA_EMBED_MODEL_ID", "amazon.titan-embed-text-v1")
    
    # Multimodal Voice Support (Nova 2 Sonic MVP)
    _enable_voice_str = str(os.getenv("ENABLE_VOICE", "1")).lower()
    ENABLE_VOICE = _enable_voice_str in ('1', 'true', 't', 'yes', 'y')
    NOVA_VOICE_MODEL_ID = os.getenv("NOVA_VOICE_MODEL_ID", "amazon.nova-2-sonic-v1:0")
    VOICE_LOCALE = os.getenv("VOICE_LOCALE", "en-US")
    VOICE_ID = os.getenv("VOICE_ID", "Ruth")
    
    # Toggle whether to actually call AWS/Amazon Nova. 
    # Defaults to True (1) for MVP demo reliability without live credentials.
    _mock_val = str(os.getenv("USE_MOCK_MODEL", "1")).lower()
    USE_MOCK_MODEL = _mock_val in ('1', 'true', 't', 'yes', 'y')
    MOCK_LLM_RESPONSE = USE_MOCK_MODEL

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
            has_explicit_keys = cls.AWS_ACCESS_KEY_ID and cls.AWS_SECRET_ACCESS_KEY
            has_bearer_token = cls.AWS_BEARER_TOKEN_BEDROCK
            
            has_boto3_default = False
            try:
                import boto3
                if boto3.Session().get_credentials():
                    has_boto3_default = True
            except ImportError:
                pass
            
            if not has_explicit_keys and not has_bearer_token and not has_boto3_default:
                raise ValueError(
                    "Configuration Error: USE_MOCK_MODEL is disabled (real calls enabled), "
                    "but no AWS credentials were found.\n"
                    "Please provide explicit keys in .env, OR run `aws configure` in your terminal."
                )
                
            if not cls.NOVA_TEXT_MODEL_ID or not cls.NOVA_EMBED_MODEL_ID:
                raise ValueError("Configuration Error: Nova Model IDs missing from environment.")
                
            if cls.ENABLE_VOICE and not cls.NOVA_VOICE_MODEL_ID:
                 raise ValueError("Configuration Error: NOVA_VOICE_MODEL_ID must be set if ENABLE_VOICE=1 and USE_MOCK_MODEL=0.")

# Instantiate a global config object correctly pointing to attributes
config = Config()
config.validate()
