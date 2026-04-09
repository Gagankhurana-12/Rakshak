import asyncio
from sentence_transformers import SentenceTransformer
import torch
from config import settings

class Embedder:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Embedder, cls).__new__(cls)
            cls._instance.model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
            if torch.cuda.is_available():
                cls._instance.model.to("cuda")
        return cls._instance

    async def encode(self, text: str) -> list[float]:
        # SentenceTransformer.encode is CPU/GPU intensive and blocking, run in thread
        embedding = await asyncio.to_thread(self.model.encode, text)
        return embedding.tolist()

    async def encode_batch(self, texts: list[str]) -> list[list[float]]:
        embeddings = await asyncio.to_thread(self.model.encode, texts)
        return embeddings.tolist()

embedder = Embedder()
