from bane.memory.attack_log import AttackLog

log = AttackLog()
stats = log.get_stats()
print(f"Totale attacchi: {stats['total_attacks']}")
print(f"Successi:        {stats['successful_attacks']}")
print(f"Success rate:    {stats['success_rate']:.1%}")
print(f"Avg score:       {stats['avg_score']:.3f}")
print(f"Max generation:  {stats['max_generation']}")

print("\n--- NEAR MISSES ---")
best = log.get_near_misses(limit=5)
for a in best:
    print(f"score={a['success_score']} | {a['text'][:80]}")
