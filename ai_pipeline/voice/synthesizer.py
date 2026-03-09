
from typing import Optional
from ai_pipeline.config import config

class VoiceSynthesizer:
    """
    Text-to-Speech using Amazon Bedrock / AWS Services.
    Currently, while Nova handles S2T nicely, pure TTS is often handled via Amazon Polly 
    or specific Bedrock text-to-voice models if available in the region.
    For this MVP, we wrap it cleanly so the underlying AWS engine can be swapped.
    """
    def __init__(self):
        # We'll use Polly for rock-solid TTS if Nova Sonic isn't natively exposing TTS in Converse yet
        if config.MOCK_LLM_RESPONSE:
            self.client = None
            return
            
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 is required for live TTS. Please run `pip install boto3`")
            
        self.client = boto3.client(
            service_name='polly',
            region_name=config.AWS_REGION,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            aws_session_token=config.AWS_SESSION_TOKEN
        )

    def synthesize(self, text: str) -> Optional[bytes]:
        """
        Takes a string and returns MP3 audio bytes.
        """
        if config.MOCK_LLM_RESPONSE:
            print("[VoiceSynthesizer] Using Mock Offline Mode")
            return b"MOCK_AUDIO_BYTES_DATADATADATA"
            
        try:
            response = self.client.synthesize_speech(
                Text=text,
                OutputFormat='mp3',
                VoiceId='Joanna', # Standard clear clinical voice
                Engine='neural'   # Highest quality
            )
            
            if "AudioStream" in response:
                with response["AudioStream"] as stream:
                    return stream.read()
            return None
            
        except Exception as e:
            print(f"Error calling AWS TTS synthesis: {e}")
            return None
