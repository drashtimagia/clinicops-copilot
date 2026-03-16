from typing import Dict
from ai_pipeline.config import config


def generate_speech(text: str) -> Dict[str, bytes]:
    """
    Converts text to speech using Amazon Polly.
    Uses voice: Joanna.
    Returns: {"audio": audio_bytes} (mp3 format)
    """
    client = config.polly_client
    voice_id = config.VOICE_ID

    # Polly has a 3000-character limit; truncate if necessary
    MAX_CHARS = 3000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        print(f"[generate_speech] Text truncated to {MAX_CHARS} characters for Polly.")

    try:
        response = client.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId=voice_id,
            Engine='neural'
        )
        audio_stream = response.get('AudioStream')
        if audio_stream:
            return {"audio": audio_stream.read()}
        return {"audio": b""}

    except Exception as e:
        import traceback
        print(f"[generate_speech] Error: {str(e)}")
        traceback.print_exc()
        return {"audio": b""}
