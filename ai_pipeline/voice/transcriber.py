
from typing import Optional, Dict, Any
from ai_pipeline.config import config

class NovaSonicTranscriber:
    """
    Push-to-talk Speech-to-Text using Amazon Nova 2 Sonic via the Bedrock Converse API.
    """
    def __init__(self):
        self.model_id = config.NOVA_VOICE_MODEL_ID 
        
        # When in mock mode, do not require real AWS credentials
        if config.MOCK_LLM_RESPONSE:
            self.client = None
            return
            
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 is required for live voice transcription. Please run `pip install boto3`")
            
        self.client = boto3.client(
            service_name='bedrock-runtime',
            region_name=config.AWS_REGION,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            aws_session_token=config.AWS_SESSION_TOKEN
        )

    def transcribe(self, audio_bytes: bytes, audio_format: str = "mp3", metadata: Dict[str, Any] = None) -> str:
        """
        Calls Amazon Nova 2 Sonic to convert the audio into text.
        """
        if config.USE_MOCK_MODEL:
            print("[VoiceTranscriber] Using Mock Offline Mode")
            desc = metadata.get("description", "") if metadata else ""
            return desc
            
        try:
            # The Converse API supports multimodal input including audio blocks
            message = {
                "role": "user",
                "content": [
                    {
                        "audio": {
                            "format": audio_format,
                            "source": {
                                "bytes": audio_bytes
                            }
                        }
                    },
                    {
                        "text": "Please transcribe this audio exactly as spoken, with no additions."
                    }
                ]
            }
            
            response = self.client.converse(
                modelId=self.model_id,
                messages=[message],
                inferenceConfig={"temperature": 0.0} # We want literal transcription
            )
            
            result_text = response['output']['message']['content'][0]['text']
            return result_text.strip()
            
        except Exception as e:
            print(f"Error calling Amazon Nova Sonic for transcription: {e}")
            return "Error: Could not transcribe audio."
