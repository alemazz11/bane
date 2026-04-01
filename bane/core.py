"""BANE Core Engine"""

import asyncio
import yaml
from pathlib import Path
from .groq_client import GroqClient
from .mutator.engine import MutatorEngine
from .runner.executor import AttackExecutor
from .runner.targets import (
    make_easy_target, make_medium_target, make_hard_target,
    make_v2_target, make_v3_target,
)
from .runner.judge import AttackJudge
from .memory.attack_log import AttackLog


class BaneCore:

    def __init__(self, config: dict = None):
        config = config or {}

        ollama_url = config.get("ollama_url", "http://localhost:11434")
        difficulty = config.get("target_difficulty", "easy")

        # Groq client for attacker/mutator (the creative brain)
        groq_attacker = GroqClient(
            api_key=config.get("groq_api_key", ""),
            url=config.get("groq_url", "https://api.groq.com/openai/v1/chat/completions"),
            model=config.get("groq_model", "llama-3.3-70b-versatile"),
        )

        self.mutator = MutatorEngine(groq_client=groq_attacker)

        target_makers = {
            "easy":   make_easy_target,
            "medium": make_medium_target,
            "hard":   make_hard_target,
            "v2":     make_v2_target,
            "v3":     make_v3_target,
        }
        self.target = target_makers[difficulty](
            model=config.get("target_model", "llama3.2:3b"),
            ollama_url=ollama_url,
        )

        # Judge is pure rule-based — no LLM needed
        self.judge = AttackJudge(
            target_system_prompt=self.target.system_prompt,
        )

        self.executor = AttackExecutor(self.target, self.judge)
        self.log = AttackLog(
            db_path=config.get("db_path", "data/attacks.db"),
            target_id=difficulty,
        )
        self.seeds = self._load_seeds()
        self.iteration = 0
        self.running = False

        # Load persisted Thompson Sampling params
        saved_params = self.log.load_cluster_params()
        if saved_params:
            self.mutator.cluster_params = saved_params
            print(f"   Loaded Thompson Sampling params from previous run")

    def _load_seeds(self) -> list:
        seeds = []
        seeds_dir = Path(__file__).parent / "taxonomy" / "seeds"
        if not seeds_dir.exists():
            print(f"Warning: seeds directory not found at {seeds_dir}")
            return seeds
        for yaml_file in seeds_dir.glob("*.yaml"):
            with open(yaml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                category = data.get("category", "unknown")
                for seed in data.get("seeds", []):
                    seed["category"]      = category
                    seed["generation"]    = 0
                    seed["mutation_type"] = "seed"
                    seed["parent_id"]     = None
                    if "text" not in seed and "sequence" in seed:
                        seed["text"] = seed["sequence"][0]
                    seeds.append(seed)
        # Add breakthroughs from previous runs as seeds
        breakthroughs = self.log.export_breakthroughs_as_seeds()
        if breakthroughs:
            seeds.extend(breakthroughs)
            print(f"   Loaded {len(breakthroughs)} breakthrough seeds from previous runs")

        return seeds

    async def run_iteration(self) -> dict:
        self.iteration += 1

        strategy = self.mutator.select_strategy(self.log)
        parent   = self.mutator.select_parent(self.log, self.seeds)

        mutated = await self.mutator.mutate(
            parent=parent,
            strategy=strategy,
            recent_successes=self.log.get_successful(limit=3),
            recent_failures=self.log.get_near_misses(limit=3),
            target_info=self.target.get_info(),
            seed_library=self.seeds,
        )

        result    = await self.executor.execute(mutated)
        attack_id = self.log.log(result)

        # Update Thompson Sampling with the score
        self.mutator.update_cluster(strategy.value, result.success_score)

        # Persist Thompson params every 10 iterations
        if self.iteration % 10 == 0:
            self.log.save_cluster_params(self.mutator.cluster_params)

        cluster = self.mutator.get_cluster_for_strategy(strategy.value)

        return {
            "iteration":        self.iteration,
            "attack_id":        attack_id,
            "strategy":         strategy.value,
            "cluster":          cluster,
            "category":         result.category,
            "generation":       result.generation,
            "score":            result.success_score,
            "success":          result.success,
            "defense_triggered": result.defense_triggered,
            "attack_preview":   result.text,
            "response_preview": result.target_response,
            "stealth_score":    mutated.get("stealth_score", "?"),
        }

    async def run(self, n_iterations: int = 200, callback=None) -> list:
        self.running = True
        results = []

        print(f"\n\U0001f525 BANE starting \u2014 {n_iterations} iterations")
        print(f"   Target:    {self.target.description}")
        print(f"   Model:     {self.target.model}")
        print(f"   Seeds:     {len(self.seeds)}")
        print(f"   Judge:     Rule-based (39 indicators)")
        print(f"   Mutator:   Groq (with stealth self-rating)")
        print(f"   Selection: Thompson Sampling (10 clusters)")
        print(f"   {'='*50}\n")

        for i in range(n_iterations):
            if not self.running:
                print("\n\u23f9 Stopped.")
                break
            try:
                if i > 0:
                    await asyncio.sleep(3)
                result = await self.run_iteration()
                results.append(result)

                emoji     = "\u2705" if result["success"] else "\u274c"
                bar_fill  = "\u2588" * int(result["score"] * 10)
                bar_empty = "\u2591" * (10 - int(result["score"] * 10))

                print(
                    f"[{result['iteration']:4d}] {emoji} "
                    f"score={result['score']:.2f} [{bar_fill}{bar_empty}] "
                    f"gen={result['generation']} "
                    f"strategy={result['strategy']:20s} "
                    f"cluster={result['cluster']:12s} "
                    f"stealth={result['stealth_score']}"
                )
                print(f"       Attack: {result['attack_preview']}")
                print(f"       Response: {result['response_preview']}")

                if result["success"]:
                    print(f"       \U0001f3af BREAKTHROUGH!")

                if callback:
                    callback(result)

            except Exception as e:
                print(f"[{i+1:4d}] \u26a0\ufe0f  Error: {e}")
                continue

        # Save Thompson params at end
        self.log.save_cluster_params(self.mutator.cluster_params)

        stats = self.log.get_stats()
        print(f"\n{'='*50}")
        print(f"\U0001f525 BANE complete \u2014 {stats['total_attacks']} attacks")
        print(f"   Success rate:  {stats['success_rate']:.1%}")
        print(f"   Avg score:     {stats['avg_score']:.3f}")
        print(f"   Max generation: {stats['max_generation']}")
        print(f"   Breakthroughs: {stats['successful_attacks']}")

        # Print Thompson cluster rankings
        print(f"\n   \U0001f4ca Cluster Rankings (Thompson \u03b1/\u03b2):")
        ranked = sorted(
            self.mutator.cluster_params.items(),
            key=lambda x: x[1]["alpha"] / (x[1]["alpha"] + x[1]["beta"]),
            reverse=True,
        )
        for name, p in ranked:
            ratio = p["alpha"] / (p["alpha"] + p["beta"])
            print(f"      {name:20s} \u03b1={p['alpha']:.1f} \u03b2={p['beta']:.1f} win_rate={ratio:.3f}")

        return results

    def stop(self):
        self.running = False
