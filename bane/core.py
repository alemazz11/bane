"""BANE Core Engine"""

import asyncio
from unittest import result
import yaml
from pathlib import Path
from .mutator.engine import MutatorEngine
from .runner.executor import AttackExecutor
from .runner.targets import make_easy_target, make_medium_target, make_hard_target
from .runner.judge import AttackJudge
from .memory.attack_log import AttackLog


class BaneCore:

    def __init__(self, config: dict = None):
        config = config or {}

        ollama_url      = config.get("ollama_url",      "http://localhost:11434")
        attacker_model  = config.get("attacker_model",  "qwen2.5:7b")
        difficulty      = config.get("target_difficulty", "easy")

        self.mutator = MutatorEngine(ollama_url=ollama_url, model=attacker_model)

        target_makers = {
            "easy":   make_easy_target,
            "medium": make_medium_target,
            "hard":   make_hard_target,
        }
        self.target = target_makers[difficulty](
            model=config.get("target_model", "llama3.2:3b"),
            ollama_url=ollama_url,
        )

        self.judge = AttackJudge(
            ollama_url=ollama_url,
            judge_model=config.get("judge_model", attacker_model),
            target_system_prompt=self.target.system_prompt,
        )

        self.executor = AttackExecutor(self.target, self.judge)
        self.log      = AttackLog(config.get("db_path", "data/attacks.db"))
        self.seeds    = self._load_seeds()
        self.iteration = 0
        self.running   = False

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
        print(f"Loaded {len(seeds)} seed attacks")
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
        )

        result    = await self.executor.execute(mutated)
        attack_id = self.log.log(result)

        return {
            "iteration":       self.iteration,
            "attack_id":       attack_id,
            "strategy":        strategy.value,
            "category":        result.category,
            "generation":      result.generation,
            "score":           result.success_score,
            "success":         result.success,
            "defense_triggered": result.defense_triggered,
            "attack_preview":  result.text[:100] + "...",
            "response_preview": result.target_response[:500 ] + "...",
        }

    async def run(self, n_iterations: int = 50, callback=None) -> list:
        self.running = True
        results = []

        print(f"\n🔥 BANE starting — {n_iterations} iterations")
        print(f"   Target:  {self.target.description}")
        print(f"   Model:   {self.target.model}")
        print(f"   Seeds:   {len(self.seeds)}")
        print(f"   {'='*50}\n")

        for i in range(n_iterations):
            if not self.running:
                print("\n⏹ Stopped.")
                break
            try:
                result = await self.run_iteration()
                print(f"       ATTACK:   {result['attack_preview']}")
                print(f"       FULL RESPONSE: {result['response_preview']}")
                results.append(result)

                emoji     = "✅" if result["success"] else "❌"
                bar_fill  = "█" * int(result["score"] * 10)
                bar_empty = "░" * (10 - int(result["score"] * 10))

                print(
                    f"[{result['iteration']:4d}] {emoji} "
                    f"score={result['score']:.2f} [{bar_fill}{bar_empty}] "
                    f"gen={result['generation']} "
                    f"strategy={result['strategy']:15s} "
                    f"cat={result['category']}"
                )

                if result["success"]:
                    print(f"       🎯 BREAKTHROUGH: {result['attack_preview']}")

                if callback:
                    callback(result)

            except Exception as e:
                print(f"[{i+1:4d}] ⚠️  Error: {e}")
                continue

        stats = self.log.get_stats()
        print(f"\n{'='*50}")
        print(f"🔥 BANE complete — {stats['total_attacks']} attacks")
        print(f"   Success rate:  {stats['success_rate']:.1%}")
        print(f"   Avg score:     {stats['avg_score']:.3f}")
        print(f"   Max generation: {stats['max_generation']}")
        print(f"   Breakthroughs: {stats['successful_attacks']}")

        return results

    def stop(self):
        self.running = False