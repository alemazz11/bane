"""Entry Point for BANE"""

import asyncio
from pathlib import Path
from bane.config import as_dict
from bane.core import BaneCore


async def main():
    Path("data").mkdir(exist_ok=True)

    config = as_dict()

    print("\U0001f525 BANE \u2014 Self-Evolving Prompt Injection Red Team Agent")
    print(f"   Attacker:    Groq {config['groq_model']}")
    print(f"   Target:      {config['target_model']} (local Ollama)")
    print(f"   Judge:       Rule-based (39 leak indicators)")
    print(f"   Selection:   Thompson Sampling (10 clusters)")
    print(f"   Difficulty:  {config['target_difficulty']}")

    bane = BaneCore(config)

    results = await bane.run(n_iterations=200)

    # Strategy effectiveness
    strat_rates = bane.log.get_strategy_success_rates(last_n=200)
    if strat_rates:
        sorted_strats = sorted(strat_rates.items(), key=lambda x: x[1], reverse=True)
        print("\n\U0001f4ca STRATEGY EFFECTIVENESS:")
        for strat, avg in sorted_strats[:10]:
            bar = "\u2588" * int(avg * 20) + "\u2591" * (20 - int(avg * 20))
            print(f"   {strat:25s} [{bar}] {avg:.3f}")

if __name__ == "__main__":
    asyncio.run(main())
