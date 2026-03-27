"""Entry Point for BANE"""

import asyncio
from pathlib import Path
from bane.config import as_dict
from bane.core import BaneCore


async def main():
    Path("data").mkdir(exist_ok=True)

    config = as_dict()

    print("🔥 BANE — Self-Evolving Prompt Injection Red Team Agent")
    print(f"   Attacker: Groq {config['groq_model']}")
    print(f"   Target:   {config['target_model']} (local)")
    print(f"   Judge:    Groq {config['groq_model']}")
    print(f"   Analyzer: Groq {config['groq_model']}")
    print(f"   Difficulty: {config['target_difficulty']}")

    bane = BaneCore(config)

    results = await bane.run(n_iterations=50)

    best = bane.log.get_successful(limit=5)
    if best:
        print("\n🏆 TOP ATTACKS DISCOVERED:")
        for i, attack in enumerate(best):
            print(f"\n--- #{i+1} (score: {attack['success_score']}) ---")
            print(f"Category:  {attack['category']}")
            print(f"Strategy:  {attack['mutation_type']}")
            print(f"Generation: {attack['generation']}")
            print(f"Attack:    {attack['text'][:200]}")


if __name__ == "__main__":
    asyncio.run(main())
