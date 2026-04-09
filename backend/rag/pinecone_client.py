import asyncio
try:
    from pinecone import Pinecone, ServerlessSpec
except Exception:
    Pinecone = None
    ServerlessSpec = None
from config import settings
from utils.embeddings import embedder
import time

DISEASE_NAMESPACE = "default"
USER_DOCS_NAMESPACE = "user_docs"
USER_VITALS_NAMESPACE = "user_vitals"

class RakshakRAG:
    def __init__(self, api_key: str):
        self._pc = None
        self.api_key = api_key
        self.offline = False

        if not api_key:
            print("⚠️ RAG Warning: PINECONE_API_KEY is missing in .env")
            self.offline = True
            return

    @property
    def pc(self):
        if self._pc is None and not self.offline:
            try:
                from pinecone import Pinecone
                self._pc = Pinecone(api_key=self.api_key)
                print("📡 Pinecone Client connected on-demand")
            except Exception as e:
                print(f"❌ Pinecone Connection Error: {e}")
                self.offline = True
        return self._pc

    async def initialize(self):
        """Pre-warm the embedding model and check Pinecone indexes."""
        if self.offline: return
        print("🚀 Initializing RAG Service (Embedding model & Pinecone)...")
        from utils.embeddings import embedder
        await embedder.encode("warmup") # Pre-load model
        await asyncio.to_thread(self._ensure_indexes)
        print("✅ RAG Service Ready")
        
    def _ensure_indexes(self):
        if not self.pc:
            return

        # Use one shared index and separate namespaces for each data domain.
        index_specs = [settings.PINECONE_INDEX_DISEASES]

        existing = [idx.name for idx in self.pc.list_indexes()]

        for idx_name in index_specs:
            if idx_name not in existing:
                self.pc.create_index(
                    name=idx_name,
                    dimension=384,
                    metric='cosine',
                    spec=ServerlessSpec(cloud='aws', region='us-east-1')
                )

    def get_index(self):
        if not self.pc:
            return None
        return self.pc.Index(settings.PINECONE_INDEX_DISEASES)

    async def upsert_doc_chunks(self, user_id: str, doc_name: str, chunks: list[str]):
        """Store user medical history chunks in the shared index under user_docs namespace."""
        index = self.get_index()
        if not index:
            raise RuntimeError("Pinecone index unavailable")

        vectors = []
        for i, chunk in enumerate(chunks):
            embedding = await embedder.encode(chunk)
            vectors.append({
                "id": f"{user_id}_{doc_name}_{i}",
                "values": embedding,
                "metadata": {
                    "user_id": user_id,
                    "doc_name": doc_name,
                    "text": chunk,
                    "upload_date": str(time.time())
                }
            })

        index.upsert(vectors=vectors, namespace=USER_DOCS_NAMESPACE)
        print(
            f"✅ Upserted {len(vectors)} document chunks to '{settings.PINECONE_INDEX_DISEASES}' "
            f"(namespace: {USER_DOCS_NAMESPACE}, user: {user_id})"
        )

    async def upsert_vitals_summary(self, user_id: str, summary_text: str, date_str: str):
        """Store weekly/daily vitals summary in the shared index under user_vitals namespace."""
        index = self.get_index()
        if not index:
            raise RuntimeError("Pinecone index unavailable")

        embedding = await embedder.encode(summary_text)
        vector = {
            "id": f"vitals_{user_id}_{date_str}",
            "values": embedding,
            "metadata": {
                "user_id": user_id,
                "date": date_str,
                "text": summary_text,
                "type": "vitals_history",
            },
        }
        index.upsert(vectors=[vector], namespace=USER_VITALS_NAMESPACE)

    async def retrieve_context(
        self,
        query: str,
        user_id: str,
        disease_top_k: int = 5,
        user_docs_top_k: int = 3,
        vitals_top_k: int = 2,
    ):
        if self.offline or not self.pc:
            return {
                "disease_context": [],
                "user_docs_context": [],
                "vitals_history_context": [],
            }

        query_vec = await embedder.encode(query)

        # Run Pinecone queries in parallel using threads (since index.query is blocking)
        async def _query_index(namespace=None, top_k=5, filter_payload=None):
            index = self.get_index()
            if not index:
                return None
            return await asyncio.to_thread(
                index.query,
                vector=query_vec,
                top_k=top_k,
                namespace=namespace,
                filter=filter_payload,
                include_metadata=True
            )

        tasks = [
            _query_index(namespace=DISEASE_NAMESPACE, top_k=disease_top_k),
            _query_index(
                namespace=USER_DOCS_NAMESPACE,
                top_k=user_docs_top_k,
                filter_payload={"user_id": {"$eq": user_id}},
            ),
            _query_index(
                namespace=USER_VITALS_NAMESPACE,
                top_k=vitals_top_k,
                filter_payload={"user_id": {"$eq": user_id}},
            ),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        disease_results, doc_results, vitals_results = results

        def get_pinecone_text(res):
            if isinstance(res, Exception) or not res:
                return []
            return [m.metadata['text'] for m in res.matches if 'text' in m.metadata]

        return {
            "disease_context": get_pinecone_text(disease_results),
            "user_docs_context": get_pinecone_text(doc_results),
            "vitals_history_context": get_pinecone_text(vitals_results),
        }

rag_service = RakshakRAG(settings.PINECONE_API_KEY)
