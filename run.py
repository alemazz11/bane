"""Entry Point for BANE"""

import asyncio
from pathlib import Path
from bane.config import as_dict
from bane.core import BaneCore


async def main():
    Path("data").mkdir(exist_ok=True)

    config = as_dict()
    judge_model = config.get("groq_judge_model") or config["groq_model"]

    print("🔥 BANE — Self-Evolving Prompt Injection Red Team Agent")
    print(f"   Attacker:  Groq {config['groq_model']}")
    print(f"   Target:    {config['target_model']} (local)")
    print(f"   Judge:     Groq {judge_model}")
    print(f"   Analyzer:  Groq {judge_model}")
    print(f"   Difficulty: {config['target_difficulty']}")

    bane = BaneCore(config)

    results = await bane.run(n_iterations=50)

    # ── Strategy effectiveness ──────────────────────────────────
    strat_rates = bane.log.get_strategy_success_rates(last_n=200)
    if strat_rates:
        sorted_strats = sorted(strat_rates.items(), key=lambda x: x[1], reverse=True)
        print("\n📊 STRATEGY EFFECTIVENESS:")
        for strat, avg in sorted_strats[:10]:
            bar = "█" * int(avg * 20) + "░" * (20 - int(avg * 20))
            print(f"   {strat:25s} [{bar}] {avg:.3f}")

if __name__ == "__main__":
    asyncio.run(main())
