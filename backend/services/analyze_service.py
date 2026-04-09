from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from fastapi import HTTPException

from db.models import User
from services.llm_service import llm_service
from services.vitals_service import VitalsService
from rag.pinecone_client import rag_service


class AnalyzeService:
    @staticmethod
    def _is_definition_query(query: str) -> bool:
        q = (query or "").strip().lower()
        patterns = [
            r"^what\s+is\s+",
            r"^what\s+are\s+",
            r"^define\s+",
            r"^explain\s+",
            r"^tell\s+me\s+about\s+",
            r"^meaning\s+of\s+",
        ]
        return any(re.match(pattern, q) for pattern in patterns)

    @staticmethod
    def _requires_personal_vitals(query: str) -> bool:
        """Heuristic intent check: only vitals-centric/personal queries should require vitals."""
        q = (query or "").lower()

        vitals_terms = [
            "heart rate", "pulse", "bpm", "sleep", "steps", "calories", "distance",
            "oxygen", "spo2", "blood pressure", "bp", "vitals", "fitness data",
            "my", "mine", "today", "this week", "last week", "my history",
        ]
        return any(term in q for term in vitals_terms)

    @staticmethod
    async def analyze(query: str, user_id: str, db_session: AsyncSession) -> dict:
        user = (await db_session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        is_definition_query = AnalyzeService._is_definition_query(query)
        requires_vitals = AnalyzeService._requires_personal_vitals(query)

        user_name = user.display_name if user.display_name else "You"

        vitals_bundle = {
            "source": "none",
            "summary": "No personal vitals were used for this query.",
        }

        # For personalized/vitals queries, vitals are required.
        if requires_vitals:
            if not user.access_token or not user.refresh_token:
                raise HTTPException(status_code=401, detail="Connect Google Fit for vitals-based analysis")

            vitals_bundle = await VitalsService.build_vitals_bundle(
                user_id=user_id,
                db_session=db_session,
                user_name=user_name,
            )
            if vitals_bundle["source"] == "none":
                raise HTTPException(status_code=422, detail="No personalized vitals found. Sync Google Fit first.")
        # For generic medical queries, vitals are optional (best effort only).
        else:
            try:
                vitals_bundle = await VitalsService.build_vitals_bundle(
                    user_id=user_id,
                    db_session=db_session,
                    user_name=user_name,
                )
            except Exception:
                pass

        vitals_context = vitals_bundle.get("summary") or "No personal vitals were used for this query."
        
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

        # For pure definition/explainer questions, avoid personal context leakage.
        if is_definition_query:
            rag_context["user_docs_context"] = []
            rag_context["vitals_history_context"] = []
            vitals_context = "Not used for this general medical explanation query."

        # Final inference using real LLM (Async) with RAG
        inference = await llm_service.analyze(
            query=query,
            vitals_context=vitals_context,
            rag_context=rag_context,
            mode="general" if is_definition_query else "personalized",
        )

        return {
            "user_id": user_id,
            "query": query,
            "vitals_context": vitals_context,
            "vitals_source": vitals_bundle.get("source", "none"),
            "analysis_mode": "general_explainer" if is_definition_query else ("personalized_rag" if requires_vitals else "general_rag"),
            "requires_personal_vitals": requires_vitals,
            **inference,
        }
