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

    # ── Top breakthroughs with lineage ──────────────────────────
    best = bane.log.get_successful(limit=5)
    if best:
        print("\n🏆 TOP ATTACKS DISCOVERED:")
        for i, attack in enumerate(best):
            print(f"\n--- #{i+1} (score: {attack['success_score']}) ---")
            print(f"Category:   {attack['category']}")
            print(f"Strategy:   {attack['mutation_type']}")
            print(f"Generation: {attack['generation']}")
            print(f"Attack:     {attack['text'][:300]}")
            print(f"Response:   {attack['target_response'][:300]}")

            # Show evolution chain
            lineage = bane.log.get_lineage(attack["id"])
            if len(lineage) > 1:
                chain = " → ".join(
                    f"gen{a['generation']}:{a['mutation_type']}({a['success_score']:.1f})"
                    for a in lineage
                )
                print(f"Evolution:  {chain}")
    else:
        print("\n❌ No breakthroughs this run.")


if __name__ == "__main__":
    asyncio.run(main())
