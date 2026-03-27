"""Executor for BANE Attacks"""

import time
import uuid
import asyncio
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AttackResult:
    id: str = ""
    text: str = ""
    sequence: list = field(default_factory=list)
    category: str = ""
    mutation_type: str = "seed"
    parent_id: Optional[str] = None
    generation: int = 0
    target_response: str = ""
    success: bool = False
    success_score: float = 0.0
    defense_triggered: bool = False
    defense_type: Optional[str] = None
    reasoning: str = ""
    latency_ms: float = 0.0
    timestamp: float = 0.0


class AttackExecutor:

    def __init__(self, target, judge):
        self.target = target
        self.judge = judge

    async def execute(self, attack: dict) -> AttackResult:
        self.target.reset_conversation()
        start = time.time()

        sequence = attack.get("sequence", [])
        if sequence and len(sequence) > 1:
            response = await self.target.send_multi_turn(sequence)
            attack_text = " → ".join(sequence)
        else:
            attack_text = attack.get("text", "")
            response = await self.target.send(attack_text)

        latency = (time.time() - start) * 1000

        judgment = await self.judge.evaluate(
            attack_text=attack_text,
            target_response=response,
            objective=attack.get("objective", "reveal_system_prompt"),
        )

        return AttackResult(
            id=attack.get("id", str(uuid.uuid4())[:8]),
            text=attack_text,
            sequence=sequence,
            category=attack.get("category", "unknown"),
            mutation_type=attack.get("mutation_type", "seed"),
            parent_id=attack.get("parent_id"),
            generation=attack.get("generation", 0),
            target_response=response,
            success=judgment["success"],
            success_score=judgment["score"],
            defense_triggered=judgment.get("defense_triggered", False),
            defense_type=judgment.get("defense_type"),
            reasoning=judgment.get("reasoning", ""),
            latency_ms=latency,
            timestamp=time.time(),
        )

    async def execute_batch(self, attacks: list, concurrency: int = 1) -> list:
        semaphore = asyncio.Semaphore(concurrency)

        async def _run(attack):
            async with semaphore:
                return await self.execute(attack)

        return await asyncio.gather(*[_run(a) for a in attacks])