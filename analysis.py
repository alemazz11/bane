"""View analyzer insights for attacks scoring above 0.4"""

import sqlite3
import json

conn = sqlite3.connect("data/attacks.db")
rows = conn.execute(
    "SELECT text, success_score, mutation_type, category, target_response, analysis "
    "FROM attacks WHERE success_score > 0.4 AND analysis != '{}' "
    "ORDER BY success_score DESC"
).fetchall()

print(f"Found {len(rows)} attacks with score > 0.4\n")

for text, score, strategy, category, response, analysis in rows:
    print("=" * 70)
    print(f"SCORE: {score:.2f}  |  STRATEGY: {strategy}  |  CATEGORY: {category}")
    print(f"ATTACK: {text[:150]}")
    print(f"RESPONSE: {response[:200]}")
    try:
        a = json.loads(analysis)
        print(f"\n  ANALYZER:")
        print(f"    Technique:  {a.get('key_technique', '?')}")
        print(f"    Defense:    {a.get('defense_interaction', '?')}")
        print(f"    Pattern:    {a.get('pattern', '?')}")
        print(f"    Suggested:  {a.get('suggested_next_mutation', '?')}")
    except (json.JSONDecodeError, TypeError):
        print(f"  RAW ANALYSIS: {analysis[:200]}")
    print()

conn.close()
