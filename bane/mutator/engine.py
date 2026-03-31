"""Core mutation engine — Thompson Sampling + Groq mutation"""

import json
import random
from ..groq_client import GroqClient
from .strategies import MutationType, STRATEGY_CLUSTERS
from .prompts import build_mutation_prompt, MUTATOR_SYSTEM_PROMPT


class MutatorEngine:

    def __init__(self, groq_client: GroqClient):
        self.groq = groq_client
        # Thompson Sampling: Beta(alpha, beta) per cluster
        self.cluster_params = {
            name: {"alpha": 1.0, "beta": 1.0}
            for name in STRATEGY_CLUSTERS
        }

    def select_strategy(self, attack_log) -> MutationType:
        """Thompson Sampling over clusters, then random strategy in cluster."""
        # Sample from Beta(alpha, beta) for each cluster
        samples = {}
        for cluster, params in self.cluster_params.items():
            samples[cluster] = random.betavariate(params["alpha"], params["beta"])

        # Pick cluster with highest sample
        best_cluster = max(samples, key=samples.get)

        # Random strategy within cluster
        strategies_in_cluster = STRATEGY_CLUSTERS[best_cluster]
        chosen = random.choice(strategies_in_cluster)
        return MutationType(chosen)

    def update_cluster(self, strategy_value: str, score: float):
        """Update Thompson Sampling params after seeing a score."""
        for cluster_name, strategies in STRATEGY_CLUSTERS.items():
            if strategy_value in strategies:
                self.cluster_params[cluster_name]["alpha"] += score
                self.cluster_params[cluster_name]["beta"] += (1.0 - score)
                break

    def get_cluster_for_strategy(self, strategy_value: str) -> str:
        """Return which cluster a strategy belongs to."""
        for cluster_name, strategies in STRATEGY_CLUSTERS.items():
            if strategy_value in strategies:
                return cluster_name
        return "unknown"

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

    async def mutate(self, parent, strategy, recent_successes,
                     recent_failures, target_info,
                     recent_insights=None, seed_library=None) -> dict:
        # Find seed examples matching the strategy
        strategy_examples = []
        if seed_library:
            strategy_examples = [
                s for s in seed_library
                if s.get("category") == strategy.value
            ][:2]

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
