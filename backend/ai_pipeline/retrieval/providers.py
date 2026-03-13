import json
from typing import List
from .interfaces import EmbeddingProvider
from ai_pipeline.config import config

class BedrockNovaProvider(EmbeddingProvider):
    """
    Real integration with AWS Bedrock using the configured Nova Model.
    """
    def __init__(self):
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 is required for the BedrockNovaProvider. Please run `pip install boto3`")
            
        # Initialize client based on available config auth
        if config.AWS_BEARER_TOKEN_BEDROCK:
             # In a real environment, you might need a custom endpoint or specific boto3 session configuration 
             # to support bearer tokens, but for standard AWS access we use the keys.
             pass
             
        self.client = boto3.client(
            service_name='bedrock-runtime',
            region_name=config.AWS_REGION,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            aws_session_token=config.AWS_SESSION_TOKEN
        )
        self.model_id = config.NOVA_EMBED_MODEL_ID

    def embed_text(self, text: str) -> List[float]:
        body = json.dumps({"inputText": text})
        
        try:
            response = self.client.invoke_model(
                body=body,
                modelId=self.model_id,
                accept='application/json',
                contentType='application/json'
            )
            response_body = json.loads(response.get('body').read())
            # typical response format for amazon titan/nova embeddings
            return response_body.get('embedding', [])
        except Exception as e:
            print(f"Error calling Bedrock embeddings: {e}")
            return []


class BaselineLocalProvider(EmbeddingProvider):
    """
    A hackathon-friendly offline provider. 
    It hashes words into a fixed 500-dimension 'dense' vector to simulate true embeddings.
    This allows local disconnected testing while using the exact same VectorStore math.
    """
    def __init__(self, vocab_size=500):
        self.vocab_size = vocab_size

    def embed_text(self, text: str) -> List[float]:
        import re
        import hashlib
        
        # Initialize zero vector
        vector = [0.0] * self.vocab_size
        
        if not text:
            return vector
            
        # Basic tokenization
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Hash trick to map words to indices
        for word in words:
            # simple deterministic hash
            idx = int(hashlib.md5(word.encode('utf-8')).hexdigest(), 16) % self.vocab_size
            vector[idx] += 1.0
            
        # L2 Normalize the vector so cosine similarity works out of the box
        magnitude = sum(x**2 for x in vector) ** 0.5
        if magnitude > 0:
            vector = [x / magnitude for x in vector]
            
        return vector
