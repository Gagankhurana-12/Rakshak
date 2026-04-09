import asyncio
try:
    from pinecone import Pinecone, ServerlessSpec
except Exception:
    Pinecone = None
    ServerlessSpec = None
from config import settings
from utils.embeddings import embedder
import time

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

        index_specs = [
            settings.PINECONE_INDEX_DISEASES,
            settings.PINECONE_INDEX_USER_DOCS,
            settings.PINECONE_INDEX_USER_VITALS
        ]
        
        existing = [idx.name for idx in self.pc.list_indexes()]
        
        for idx_name in index_specs:
            if idx_name not in existing:
                self.pc.create_index(
                    name=idx_name,
                    dimension=384, # all-MiniLM-L6-v2 dimension is 384
                    metric='cosine',
                    spec=ServerlessSpec(cloud='aws', region='us-east-1') # Adjust region as per need
                )
    
    def get_index(self, name: str):
        if not self.pc:
            return None
        return self.pc.Index(name)

    async def upsert_doc_chunks(self, user_id: str, doc_name: str, chunks: list[str]):
        """Store document chunks for a specific user into PINECONE_INDEX_USER_DOCS."""
        index = self.get_index(settings.PINECONE_INDEX_USER_DOCS)
        
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
        
        index.upsert(vectors=vectors, namespace=user_id)
        print(f"✅ Successfully upserted {len(vectors)} chunks to Pinecone index '{settings.PINECONE_INDEX_USER_DOCS}' (Namespace: {user_id})")

    async def upsert_vitals_summary(self, user_id: str, summary_text: str, date_str: str):
        """Store a natural language vitals summary for searching history."""
        from rag.faiss_client import faiss_service
        try:
            await faiss_service.add_documents(user_id, "vitals_history", [summary_text])
        except Exception as e:
            print(f"⚠️ FAISS Vitals Backup Failed: {e}")

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
        async def _query_index(idx_name, namespace=None, top_k=5):
            index = self.get_index(idx_name)
            if not index:
                return None
            return await asyncio.to_thread(
                index.query, 
                vector=query_vec, 
                top_k=top_k, 
                namespace=namespace, 
                include_metadata=True
            )

        from rag.faiss_client import faiss_service

        tasks = [
            _query_index(settings.PINECONE_INDEX_DISEASES, top_k=disease_top_k),
            faiss_service.search(user_id, "user_docs", query, top_k=5),
            faiss_service.search(user_id, "vitals_history", query, top_k=3)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        pinecone_disease, doc_results, vitals_results = results

        def get_pinecone_text(res):
            if isinstance(res, Exception) or not res:
                return []
            return [m.metadata['text'] for m in res.matches if 'text' in m.metadata]

        def get_faiss_text(res):
            if isinstance(res, Exception) or not res:
                return []
            return res

        return {
            "disease_context": get_pinecone_text(pinecone_disease),
            "user_docs_context": get_faiss_text(doc_results),
            "vitals_history_context": get_faiss_text(vitals_results)
        }

rag_service = RakshakRAG(settings.PINECONE_API_KEY)
