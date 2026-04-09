import faiss
import numpy as np
import os
import json
import pickle
from pathlib import Path
from utils.embeddings import embedder

class FaissService:
    def __init__(self, base_path: str = "vectors"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        self.dimension = 384 # all-MiniLM-L6-v2

    def _get_user_paths(self, user_id: str, store_name: str):
        user_dir = self.base_path / user_id
        user_dir.mkdir(exist_ok=True)
        index_path = user_dir / f"{store_name}.index"
        meta_path = user_dir / f"{store_name}.pkl"
        return index_path, meta_path

    async def add_documents(self, user_id: str, store_name: str, documents: list[str]):
        """Append new documents to a user's local FAISS store."""
        if not documents: return
        
        index_path, meta_path = self._get_user_paths(user_id, store_name)
        
        # 1. Generate embeddings
        embeddings = await embedder.encode(documents)
        embeddings = np.array(embeddings).astype('float32')
        
        # 2. Load or create index
        if index_path.exists():
            index = faiss.read_index(str(index_path))
            with open(meta_path, 'rb') as f:
                metadata = pickle.load(f)
        else:
            index = faiss.IndexFlatL2(self.dimension)
            metadata = []
            
        # 3. Add to index and metadata
        index.add(embeddings)
        metadata.extend(documents)
        
        # 4. Save back
        faiss.write_index(index, str(index_path))
        with open(meta_path, 'wb') as f:
            pickle.dump(metadata, f)
            
        print(f"📦 FAISS: Added {len(documents)} chunks to '{store_name}' for user {user_id}")

    async def search(self, user_id: str, store_name: str, query: str, top_k: int = 5) -> list[str]:
        """Search a user's local FAISS store."""
        index_path, meta_path = self._get_user_paths(user_id, store_name)
        
        if not index_path.exists():
            return []
            
        # 1. Load index and metadata
        index = faiss.read_index(str(index_path))
        with open(meta_path, 'rb') as f:
            metadata = pickle.load(f)
            
        # 2. Embed query
        query_vec = await embedder.encode([query])
        query_vec = np.array(query_vec).astype('float32')
        
        # 3. Search
        distances, indices = index.search(query_vec, top_k)
        
        # 4. Filter results
        results = []
        for idx in indices[0]:
            if idx != -1 and idx < len(metadata):
                results.append(metadata[idx])
                
        return results

faiss_service = FaissService()
