try:
    from groq import AsyncGroq
except Exception:
    AsyncGroq = None

from config import settings
import asyncio
import json


class LLMService:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self._client = None
        self.model_candidates = [
            settings.LLM_MODEL,
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
        ]

    @property
    def client(self):
        if AsyncGroq is None:
            raise RuntimeError("Groq SDK is not installed")
        if self._client is None:
            self._client = AsyncGroq(api_key=self.api_key)
        return self._client

    @staticmethod
    def _clamp_temperature(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _resolve_temperature(self, mode: str) -> float:
        if mode == "general":
            return self._clamp_temperature(settings.LLM_TEMPERATURE_GENERAL)
        return self._clamp_temperature(settings.LLM_TEMPERATURE_PERSONALIZED)

    async def _call_model(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        timeout: float,
    ) -> dict | None:
        for model_name in dict.fromkeys(self.model_candidates):
            try:
                completion = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=temperature,
                        top_p=0.9,
                        max_completion_tokens=settings.LLM_MAX_TOKENS,
                        response_format={"type": "json_object"},
                    ),
                    timeout=timeout,
                )
                return json.loads(completion.choices[0].message.content)
            except Exception as exc:
                print(f"⚠️ LLM Call error with {model_name}: {exc}")
                continue

        return None

    async def analyze(self, query: str, vitals_context: str, rag_context: dict, mode: str = "personalized") -> dict:
        disease_context = "\n".join(rag_context.get("disease_context", []))[:1000]
        user_docs_context = "\n".join(rag_context.get("user_docs_context", []))[:1000]
        vitals_history_context = "\n".join(rag_context.get("vitals_history_context", []))[:800]
        temperature = self._resolve_temperature(mode)

        if mode == "general":
            system_prompt = """
You are Rakshak Medical Knowledge Assistant.
For definition/explainer questions, answer only from SCIENTIFIC REFERENCE DATA.
Do NOT use personal medical history or vitals to infer patient-specific diagnosis.
Keep output educational, concise, and medically accurate.

YOU MUST RETURN JSON ONLY.
"""

            prompt = f"""
[MEDICAL KNOWLEDGE QUERY]
QUERY: {query}
SCIENTIFIC REFERENCE DATA: {disease_context}

[OUTPUT REQUIREMENTS]
1. 'possible_conditions': should include the queried condition first when identifiable.
2. 'vitals_correlation': Explain that this is a general explanation, not personalized inference.
3. 'urgency': usually 'low' for educational queries unless strong emergency signs are explicitly in query.
4. 'recommendations': include education-focused next steps.

Strict JSON format:
{{
  "possible_conditions": [
    {{ "name": "", "confidence": "low|medium|high", "reason": "" }}
  ],
  "confidence": "low|medium|high",
  "vitals_correlation": "",
  "urgency": "low|medium|high",
  "recommendations": [],
  "disclaimer": "Educational guidance only - Not a final diagnosis."
}}
"""
        else:
            system_prompt = """
You are the Rakshak Chief Medical Officer AI, an elite diagnostic system.
Your goal is to provide high-precision, clinical-grade analysis by correlating biometric data with medical history.

DIAGNOSTIC GUIDELINES:
1. BIOMETRIC CORRELATION: Examine 'PERSONAL VITALS' and 'PAST VITALS'. If heart rate/sleep deviates from the user's historical norm, prioritize this as a physiological trigger.
2. HISTORICAL CONTEXT: Use 'USER HISTORY' (uploaded documents) to identify pre-existing conditions or recurring patterns.
3. KNOWLEDGE INTEGRATION: Apply 'MEDICAL KNOWLEDGE' to symptoms to identify the most statistically likely conditions.
4. TONE: Authoritative, professional, and investigative. Avoid filler phrases like "it's important to consider."

YOU MUST RETURN JSON ONLY.
"""

            prompt = f"""
[PATIENT DATA CASE]
QUERY: {query}
CURRENT BIOMETRICS: {vitals_context}
BIOMETRIC HISTORY: {vitals_history_context}
CLINICAL HISTORY (LOCAL DOCS): {user_docs_context}
SCIENTIFIC REFERENCE DATA: {disease_context}

[OUTPUT REQUIREMENTS]
1. 'possible_conditions': List conditions with a specific 'reason' linking their biometrics to the condition.
2. 'vitals_correlation': A deep analysis of how their current vitals (Pulse, Sleep) match the symptoms.
3. 'urgency': 'low', 'medium', or 'high'.
4. 'recommendations': Specific, actionable next steps.

Strict JSON format:
{{
  "possible_conditions": [
    {{ "name": "", "confidence": "low|medium|high", "reason": "" }}
  ],
  "confidence": "low|medium|high",
  "vitals_correlation": "",
  "urgency": "low|medium|high",
  "recommendations": [],
  "disclaimer": "Clinical Decision Support Tool - Not a final diagnosis."
}}
"""

        try:
            raw = await self._call_model(
                prompt,
                system_prompt,
                temperature=temperature,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        except Exception:
            raw = None

        if not raw:
            if mode == "general":
                return {
                    "possible_conditions": [
                        {
                            "name": "General Medical Explanation",
                            "confidence": "low",
                            "reason": "The explanation engine is temporarily unavailable.",
                        }
                    ],
                    "confidence": "low",
                    "vitals_correlation": "This was a general query; personalized vitals were not required.",
                    "urgency": "low",
                    "recommendations": [
                        "Please try the question again in a moment.",
                        "Use specific wording like: What is asthma?",
                    ],
                    "disclaimer": "Educational guidance only - Not a final diagnosis.",
                }

            return {
                "possible_conditions": [
                    {
                        "name": "Analysis Timeout",
                        "confidence": "low",
                        "reason": "The system could not reach the diagnostic engine.",
                    }
                ],
                "confidence": "low",
                "vitals_correlation": "Biometric analysis was interrupted.",
                "urgency": "medium",
                "recommendations": ["Please try your query again.", "Check your internet connection."],
                "disclaimer": "System busy.",
            }

        return raw


llm_service = LLMService()
