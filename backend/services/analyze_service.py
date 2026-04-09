from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from fastapi import HTTPException

from db.models import User
from services.llm_service import llm_service
from services.vitals_service import VitalsService
from rag.pinecone_client import rag_service


class AnalyzeService:
    @staticmethod
    async def analyze(query: str, user_id: str, db_session: AsyncSession) -> dict:
        user = (await db_session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not user.access_token or not user.refresh_token:
            raise HTTPException(status_code=401, detail="Connect Google Fit to get personalized analysis")

        user_name = user.display_name if user.display_name else "You"

        vitals_bundle = await VitalsService.build_vitals_bundle(
            user_id=user_id,
            db_session=db_session,
            user_name=user_name,
        )
        if vitals_bundle["source"] == "none":
            raise HTTPException(status_code=422, detail="No personalized vitals found. Sync Google Fit first.")

        vitals_context = vitals_bundle["summary"]
        
        # Retrieve RAG context in parallel with parallelization already in the service
        rag_context = {
            "disease_context": [],
            "user_docs_context": [],
            "vitals_history_context": [],
        }
        try:
            rag_context = await rag_service.retrieve_context(query, user_id)
        except Exception as exc:
            print(f"⚠️ Could not fetch RAG context for analysis: {exc}")

        # Final inference using real LLM (Async) with RAG
        inference = await llm_service.analyze(
            query=query,
            vitals_context=vitals_context,
            rag_context=rag_context,
        )

        return {
            "user_id": user_id,
            "query": query,
            "vitals_context": vitals_context,
            "vitals_source": vitals_bundle.get("source", "none"),
            "analysis_mode": "full_rag_async",
            **inference,
        }
