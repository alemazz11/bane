"""Core mutation engine — uses Groq to generate new attacks"""

import json
import math
import random
from ..groq_client import GroqClient
from .strategies import MutationType
from .prompts import build_mutation_prompt, MUTATOR_SYSTEM_PROMPT


class MutatorEngine:

    def __init__(self, groq_client: GroqClient):
        self.groq = groq_client

    async def mutate(self, parent, strategy, recent_successes,
                     recent_failures, target_info,
                     recent_insights=None, seed_library=None) -> dict:
        # Find seed examples matching the strategy (category name = strategy value)
        strategy_examples = []
        if seed_library:
            strategy_examples = [
                s for s in seed_library
                if s.get("category") == strategy.value
            ][:2]  # max 2 examples

        prompt = build_mutation_prompt(
            parent_attack=parent,
            strategy=strategy.value,
            recent_successes=recent_successes,
            recent_failures=recent_failures,
            target_info=target_info,
            recent_insights=recent_insights,
            strategy_examples=strategy_examples,
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
        all_strategies = list(MutationType)
        stats = attack_log.get_strategy_stats(last_n=100)
        total_pulls = sum(s["count"] for s in stats.values()) if stats else 0

        # Not enough data yet — explore randomly
        if total_pulls < 10:
            # Pick a strategy we haven't tried, or random if all tried
            untried = [s for s in all_strategies if s.value not in stats]
            if untried:
                return random.choice(untried)
            return random.choice(all_strategies)

        # UCB1: score = avg_reward + C * sqrt(ln(total) / strategy_count)
        C = 1.4  # exploration constant (sqrt(2) ≈ 1.41)
        ln_total = math.log(total_pulls)

        best_score = -1
        best_strategy = None

        for strategy in all_strategies:
            s = stats.get(strategy.value)
            if s is None:
                # Never tried — infinite exploration bonus, pick it
                return strategy
            ucb = s["avg"] + C * math.sqrt(ln_total / s["count"])
            if ucb > best_score:
                best_score = ucb
                best_strategy = strategy

        return best_strategy or random.choice(all_strategies)

    def select_parent(self, attack_log, seed_library: list) -> dict:
        roll = random.random()
        if roll < 0.4:
            candidates = attack_log.get_near_misses(limit=10)
            if candidates:
                weights = [(c.get("success_score", 0.3) ** 2) for c in candidates]
                total = sum(weights)
                if total > 0:
                    return random.choices(candidates, weights=weights, k=1)[0]
                return random.choice(candidates)
        elif roll < 0.7:
            candidates = attack_log.get_successful(limit=10)
            if candidates:
                weights = [c.get("success_score", 0.5) for c in candidates]
                total = sum(weights)
                if total > 0:
                    return random.choices(candidates, weights=weights, k=1)[0]
                return random.choice(candidates)
        # Prefer breakthrough seeds over base seeds
        breakthroughs = [s for s in seed_library if s.get("success_score", 0) > 0]
        if breakthroughs and random.random() < 0.6:
            weights = [s.get("success_score", 0.1) for s in breakthroughs]
            total = sum(weights)
            if total > 0:
                return random.choices(breakthroughs, weights=weights, k=1)[0]
            return random.choice(breakthroughs)
        return random.choice(seed_library)
