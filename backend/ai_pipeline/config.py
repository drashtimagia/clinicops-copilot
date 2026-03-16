import os
import io
import boto3

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
                if clean_key not in os.environ and clean_val:
                    os.environ[clean_key] = clean_val

class Config:
    # Environment Variables
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
    
    # Models
    NOVA_TEXT_MODEL_ID = os.getenv("NOVA_TEXT_MODEL_ID", "us.amazon.nova-lite-v1:0")
    NOVA_EMBED_MODEL_ID = os.getenv("NOVA_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
    
    # Voice Settings
    VOICE_ID = os.getenv("VOICE_ID", "Arthur")
    ENABLE_VOICE = str(os.getenv("ENABLE_VOICE", "1")).lower() in ('1', 'true', 't', 'yes', 'y')

    def __init__(self):
        self.validate()
        # Initialize centralized clients
        self.bedrock_runtime = boto3.client(
            "bedrock-runtime",
            region_name=self.AWS_REGION,
            aws_access_key_id=self.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY,
            aws_session_token=self.AWS_SESSION_TOKEN
        )
        self.polly_client = boto3.client(
            "polly",
            region_name=self.AWS_REGION,
            aws_access_key_id=self.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY,
            aws_session_token=self.AWS_SESSION_TOKEN
        )

    def validate(self):
        """Validates AWS credentials and model IDs are present."""
        has_explicit_keys = self.AWS_ACCESS_KEY_ID and self.AWS_SECRET_ACCESS_KEY
        
        has_boto3_default = False
        try:
            if boto3.Session().get_credentials():
                has_boto3_default = True
        except Exception:
            pass

        if not has_explicit_keys and not has_boto3_default:
            raise ValueError(
                "No AWS credentials found. "
                "Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env."
            )

        if not self.NOVA_TEXT_MODEL_ID or not self.NOVA_EMBED_MODEL_ID:
            raise ValueError("Cloud models (NOVA_TEXT_MODEL_ID/NOVA_EMBED_MODEL_ID) must be set.")

# Instantiate a global config object
config = Config()
