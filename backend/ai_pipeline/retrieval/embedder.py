from typing import List
import json
from ai_pipeline.config import config


def embed_text(text: str) -> List[float]:
    """
    Embeds text using Amazon Titan Text Embeddings V2 via AWS Bedrock.
    Model: amazon.titan-embed-text-v2:0
    Returns: List of 1024 floats.
    """
    client = config.bedrock_runtime
    model_id = "amazon.titan-embed-text-v2:0"

    request_body = {
        "inputText": text,
        "dimensions": 1024,
        "normalize": True
    }

    try:
        response = client.invoke_model(
            body=json.dumps(request_body),
            modelId=model_id,
            accept='application/json',
            contentType='application/json'
        )
        body = json.loads(response.get('body').read())
        return body.get('embedding', [])

    except Exception as e:
        import traceback
        print(f"[embed_text] Embedding failed:\n{traceback.format_exc()}")
        return []
