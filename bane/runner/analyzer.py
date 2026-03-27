"""Analyzes WHY attacks succeed or fail."""

import json
from ..groq_client import GroqClient
from ..mutator.prompts import ANALYZER_PROMPT


class AttackAnalyzer:

    def __init__(self, groq_client: GroqClient):
        self.groq = groq_client

    async def analyze(self, result, target_defenses: list) -> dict:
        outcome = "succeeded" if result.success else "failed"
        prompt = ANALYZER_PROMPT.format(
            outcome=outcome,
            attack_text=result.text[:500],
            category=result.category,
            mutation_type=result.mutation_type,
            score=result.success_score,
            response=result.target_response[:1000],
            defenses=", ".join(target_defenses),
        )
        try:
            raw = await self.groq.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            s, e = raw.find("{"), raw.rfind("}") + 1
            if s != -1 and e > s:
                return json.loads(raw[s:e])
        except Exception as ex:
            print(f"  [analyzer] error: {ex}")
        return {
            "key_technique": "unknown",
            "defense_interaction": "unknown",
            "pattern": "",
            "suggested_next_mutation": "",
        }
