import uuid
import re
from datetime import datetime, timezone
from fastapi import UploadFile, HTTPException
from utils.ocr import ocr_service
from rag.pinecone_client import rag_service
from utils.embeddings import embedder
import time

class DocumentService:
    @staticmethod
    def chunk_text(text: str, max_tokens: int = 500) -> list[str]:
        """Simple chunking by sentences roughly matching max_tokens."""
        # Using 5 chars/token rule of thumb: 500 tokens ~ 2500 chars
        max_chars = max_tokens * 5
        sentences = re.split(r'(?<=[.!?]) +', text)
        chunks = []
        current_chunk = ""
        
        for s in sentences:
            if len(current_chunk) + len(s) < max_chars:
                current_chunk += s + " "
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = s + " "
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        return chunks

    @staticmethod
    async def process_upload(user_id: str, file: UploadFile):
        """
        - Accept PDF/image
        - Extract text
        - Chunk into 500 tokens
        - Upsert to Pinecone (user_docs index)
        """
        content = await file.read()
        file_ext = file.filename.split('.')[-1].lower()
        
        if file_ext == "pdf":
            text = ocr_service.extract_text_from_pdf(content)
        elif file_ext in ["jpg", "jpeg", "png"]:
            text = ocr_service.extract_text_from_image(content)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        if not text.strip():
            raise HTTPException(status_code=400, detail="No readable text found in document")

        chunks = DocumentService.chunk_text(text, max_tokens=500)
        
        # Store in Pinecone shared index under user_docs namespace.
        vector_store = "pinecone_namespace:user_docs"
        try:
            await rag_service.upsert_doc_chunks(user_id, file.filename, chunks)
        except Exception as e:
            print(f"❌ Pinecone Upsert Failed: {e}")
            vector_store = "error"
        
        return {
            "doc_name": file.filename,
            "chunks_processed": len(chunks),
            "status": "stored",
            "vector_store": vector_store,
            "upload_date": datetime.now(timezone.utc).isoformat()
        }

document_service = DocumentService()
