"""SQLite Attack Log"""

import sqlite3, json, uuid
from pathlib import Path


class AttackLog:

    def __init__(self, db_path="data/attacks.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS attacks (
                id TEXT PRIMARY KEY, text TEXT NOT NULL,
                sequence TEXT DEFAULT '[]', category TEXT,
                mutation_type TEXT DEFAULT 'seed', parent_id TEXT,
                generation INTEGER DEFAULT 0, target_response TEXT,
                success INTEGER DEFAULT 0, success_score REAL DEFAULT 0.0,
                defense_triggered INTEGER DEFAULT 0, defense_type TEXT,
                reasoning TEXT, latency_ms REAL, timestamp REAL,
                analysis TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_success ON attacks(success);
            CREATE INDEX IF NOT EXISTS idx_score ON attacks(success_score);
            CREATE INDEX IF NOT EXISTS idx_category ON attacks(category);
            CREATE INDEX IF NOT EXISTS idx_mutation ON attacks(mutation_type);
            CREATE INDEX IF NOT EXISTS idx_generation ON attacks(generation);
        """)
        self.conn.commit()

    def log(self, result) -> str:
        aid = result.id or str(uuid.uuid4())[:8]
        self.conn.execute("""
            INSERT OR REPLACE INTO attacks
            (id, text, sequence, category, mutation_type, parent_id,
             generation, target_response, success, success_score,
             defense_triggered, defense_type, reasoning, latency_ms, timestamp)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (aid, result.text, json.dumps(result.sequence), result.category,
             result.mutation_type, result.parent_id, result.generation,
             result.target_response, int(result.success), result.success_score,
             int(result.defense_triggered), result.defense_type,
             result.reasoning, result.latency_ms, result.timestamp))
        self.conn.commit()
        return aid

    def get_successful(self, limit=10):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM attacks WHERE success=1 ORDER BY success_score DESC LIMIT ?", (limit,))]

    def get_near_misses(self, limit=10):
        rows = self.conn.execute(
            """SELECT * FROM attacks 
            WHERE success_score BETWEEN 0.3 AND 0.7
            ORDER BY success_score DESC, RANDOM()
            LIMIT ?""", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_strategy_success_rates(self, last_n=50):
        rows = self.conn.execute(
            "SELECT mutation_type, AVG(success_score) as avg FROM (SELECT * FROM attacks ORDER BY timestamp DESC LIMIT ?) GROUP BY mutation_type", (last_n,))
        return {r["mutation_type"]: r["avg"] for r in rows}

    def get_stats(self):
        total = self.conn.execute("SELECT COUNT(*) FROM attacks").fetchone()[0]
        succ = self.conn.execute("SELECT COUNT(*) FROM attacks WHERE success=1").fetchone()[0]
        avg = self.conn.execute("SELECT AVG(success_score) FROM attacks").fetchone()[0] or 0
        maxg = self.conn.execute("SELECT MAX(generation) FROM attacks").fetchone()[0] or 0
        return {"total_attacks": total, "successful_attacks": succ,
                "success_rate": succ / max(total, 1), "avg_score": round(avg, 3), "max_generation": maxg}

    def get_lineage(self, attack_id):
        lineage, current = [], attack_id
        while current:
            row = self.conn.execute("SELECT * FROM attacks WHERE id=?", (current,)).fetchone()
            if not row: break
            lineage.append(dict(row))
            current = row["parent_id"]
        lineage.reverse()
        return lineage
    def update_analysis(self, attack_id: str, analysis: dict):
        self.conn.execute(
            "UPDATE attacks SET analysis=? WHERE id=?",
            (json.dumps(analysis), attack_id))
        self.conn.commit()

    def get_recent_insights(self, limit=5) -> list:
        rows = self.conn.execute(
            "SELECT analysis FROM attacks WHERE analysis != '{}' ORDER BY timestamp DESC LIMIT ?",
            (limit,))
        results = []
        for r in rows:
            try:
                results.append(json.loads(r["analysis"]))
            except (json.JSONDecodeError, TypeError):
                continue
        return results
    def get_top_attacks(self, limit=5):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM attacks WHERE success=1 ORDER BY success_score DESC LIMIT ?", (limit,))]
    def export_breakthroughs_as_seeds(self) -> list:
        """Export successful attacks as seed format for next run."""
        rows = self.conn.execute(
            "SELECT * FROM attacks WHERE success=1 ORDER BY success_score DESC LIMIT 10"
        ).fetchall()
        seeds = []
        for r in rows:
            seeds.append({
                "id": f"bt_{r['id']}",
                "text": r["text"],
                "sequence": json.loads(r["sequence"]) if r["sequence"] else [],
                "category": r["category"],
                "objective": "reveal_system_prompt",
                "generation": 0,
                "mutation_type": "seed",
                "parent_id": None,
                "success_score": r["success_score"],
                "target_response": r["target_response"],
            })
        return seeds

