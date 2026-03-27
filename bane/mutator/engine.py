"""Core mutation engine — uses Groq to generate new attacks"""

import json
import random
from ..groq_client import GroqClient
from .strategies import MutationType
from .prompts import build_mutation_prompt, MUTATOR_SYSTEM_PROMPT


class MutatorEngine:

    def __init__(self, groq_client: GroqClient):
        self.groq = groq_client

    async def mutate(self, parent, strategy, recent_successes,
                     recent_failures, target_info, benign_probe_results=None) -> dict:
        prompt = build_mutation_prompt(
            parent_attack=parent,
            strategy=strategy.value,
            recent_successes=recent_successes,
            recent_failures=recent_failures,
            target_info=target_info,
            benign_probe_results=benign_probe_results,
        )
        raw = await self.groq.chat(
            messages=[
                {"role": "system", "content": MUTATOR_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
        )

        return self._parse_response(raw, parent, strategy)

    def _parse_response(self, raw: str, parent: dict, strategy: MutationType) -> dict:
        try:
            s, e = raw.find("{"), raw.rfind("}") + 1
            if s != -1 and e > s:
                parsed = json.loads(raw[s:e])
            else:
                raise ValueError("No JSON found")

            return {
                "text": parsed.get("attack_text", ""),
                "sequence": parsed.get("attack_sequence", []),
                "reasoning": parsed.get("reasoning", ""),
                "category": parsed.get("category", parent.get("category")),
                "mutation_type": strategy.value,
                "parent_id": parent.get("id"),
                "generation": parent.get("generation", 0) + 1,
            }
        except (json.JSONDecodeError, ValueError):
            return {
                "text": raw.strip(),
                "sequence": [],
                "reasoning": "Failed to parse JSON, using raw output",
                "category": parent.get("category", "unknown"),
                "mutation_type": strategy.value,
                "parent_id": parent.get("id"),
                "generation": parent.get("generation", 0) + 1,
            }

    def select_strategy(self, attack_log) -> MutationType:
        stats = attack_log.get_strategy_success_rates(last_n=50)
        if random.random() < 0.7 and stats:
            strategies = list(stats.keys())
            weights = [max(stats[s], 0.01) for s in strategies]
            chosen = random.choices(strategies, weights=weights, k=1)[0]
            try:
                return MutationType(chosen)
            except ValueError:
                pass
        return random.choice(list(MutationType))

    def select_parent(self, attack_log, seed_library: list) -> dict:
        roll = random.random()
        if roll < 0.4:
            candidates = attack_log.get_near_misses(limit=10)
            if candidates:
                return random.choice(candidates)
        elif roll < 0.7:
            candidates = attack_log.get_successful(limit=10)
            if candidates:
                return random.choice(candidates)
        return random.choice(seed_library)
