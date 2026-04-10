import asyncio
from config import settings

class Embedder:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Embedder, cls).__new__(cls)
            cls._instance.model = None
        return cls._instance

    def _ensure_model(self):
        if self.model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
            import torch
        except Exception as exc:
            raise RuntimeError(
                "Embedding dependencies are missing. Install requirements before using AI/vector features."
            ) from exc

        self.model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        if torch.cuda.is_available():
            self.model.to("cuda")

    async def encode(self, text: str) -> list[float]:
        if self.model is None:
            # Load model in a background thread so we don't block the FastAPI async event loop
            await asyncio.to_thread(self._ensure_model)
        # SentenceTransformer.encode is CPU/GPU intensive and blocking, run in thread
        embedding = await asyncio.to_thread(self.model.encode, text)
        return embedding.tolist()

    async def encode_batch(self, texts: list[str]) -> list[list[float]]:
        if self.model is None:
            await asyncio.to_thread(self._ensure_model)
        embeddings = await asyncio.to_thread(self.model.encode, texts)
        return embeddings.tolist()

embedder = Embedder()
