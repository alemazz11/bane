"""SQLite Attack Log"""

import sqlite3, json, uuid
from pathlib import Path


class AttackLog:

    def __init__(self, db_path="data/attacks.db", target_id=None):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.target_id = target_id or "default"
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
        # Migrate: add target_id column if missing (existing DBs)
        try:
            self.conn.execute("SELECT target_id FROM attacks LIMIT 1")
        except sqlite3.OperationalError:
            self.conn.execute("ALTER TABLE attacks ADD COLUMN target_id TEXT DEFAULT 'default'")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_target ON attacks(target_id)")
        # Thompson Sampling params table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cluster_params (
                target_id TEXT PRIMARY KEY,
                params TEXT DEFAULT '{}',
                updated_at REAL
            )
        """)
        self.conn.commit()

    def log(self, result) -> str:
        aid = result.id or str(uuid.uuid4())[:8]
        self.conn.execute("""
            INSERT OR REPLACE INTO attacks
            (id, text, sequence, category, mutation_type, parent_id,
             generation, target_response, success, success_score,
             defense_triggered, defense_type, reasoning, latency_ms, timestamp,
             target_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (aid, result.text, json.dumps(result.sequence), result.category,
             result.mutation_type, result.parent_id, result.generation,
             result.target_response, int(result.success), result.success_score,
             int(result.defense_triggered), result.defense_type,
             result.reasoning, result.latency_ms, result.timestamp,
             self.target_id))
        self.conn.commit()
        return aid

    def _t(self):
        """Target filter clause."""
        return "target_id = ?"

    def _tp(self):
        """Target filter param."""
        return (self.target_id,)

    def get_successful(self, limit=10):
        return [dict(r) for r in self.conn.execute(
            f"SELECT * FROM attacks WHERE success=1 AND {self._t()} ORDER BY success_score DESC LIMIT ?",
            self._tp() + (limit,))]

    def get_near_misses(self, limit=10):
        rows = self.conn.execute(
            f"""SELECT * FROM attacks
            WHERE success_score BETWEEN 0.3 AND 0.7 AND {self._t()}
            ORDER BY success_score DESC, RANDOM()
            LIMIT ?""", self._tp() + (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_strategy_success_rates(self, last_n=50):
        rows = self.conn.execute(
            f"SELECT mutation_type, AVG(success_score) as avg FROM (SELECT * FROM attacks WHERE {self._t()} ORDER BY timestamp DESC LIMIT ?) GROUP BY mutation_type",
            self._tp() + (last_n,))
        return {r["mutation_type"]: r["avg"] for r in rows}

    def get_strategy_stats(self, last_n=100):
        """Returns {strategy: {"avg": float, "count": int}} for UCB1."""
        rows = self.conn.execute(
            f"""SELECT mutation_type, AVG(success_score) as avg, COUNT(*) as cnt
               FROM (SELECT * FROM attacks WHERE {self._t()} ORDER BY timestamp DESC LIMIT ?)
               GROUP BY mutation_type""", self._tp() + (last_n,))
        return {r["mutation_type"]: {"avg": r["avg"], "count": r["cnt"]} for r in rows}

    def get_stats(self):
        t, tp = self._t(), self._tp()
        total = self.conn.execute(f"SELECT COUNT(*) FROM attacks WHERE {t}", tp).fetchone()[0]
        succ = self.conn.execute(f"SELECT COUNT(*) FROM attacks WHERE success=1 AND {t}", tp).fetchone()[0]
        avg = self.conn.execute(f"SELECT AVG(success_score) FROM attacks WHERE {t}", tp).fetchone()[0] or 0
        maxg = self.conn.execute(f"SELECT MAX(generation) FROM attacks WHERE {t}", tp).fetchone()[0] or 0
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
            f"SELECT analysis FROM attacks WHERE analysis != '{{}}'  AND {self._t()} ORDER BY timestamp DESC LIMIT ?",
            self._tp() + (limit,))
        results = []
        for r in rows:
            try:
                results.append(json.loads(r["analysis"]))
            except (json.JSONDecodeError, TypeError):
                continue
        return results
    def get_top_attacks(self, limit=5):
        return [dict(r) for r in self.conn.execute(
            f"SELECT * FROM attacks WHERE success=1 AND {self._t()} ORDER BY success_score DESC LIMIT ?",
            self._tp() + (limit,))]
    def get_aggregated_insights(self, limit=20) -> list:
        """Aggregate recent analyses into top patterns with frequency."""
        raw = self.get_recent_insights(limit=limit)
        if not raw:
            return []

        pattern_counts = {}
        technique_counts = {}
        suggestion_counts = {}

        for ins in raw:
            p = ins.get("pattern", "")
            if p:
                pattern_counts[p] = pattern_counts.get(p, 0) + 1
            t = ins.get("key_technique", "")
            if t and t != "unknown":
                technique_counts[t] = technique_counts.get(t, 0) + 1
            s = ins.get("suggested_next_mutation", "")
            if s:
                suggestion_counts[s] = suggestion_counts.get(s, 0) + 1

        total = len(raw)
        aggregated = []

        for pattern, count in sorted(pattern_counts.items(), key=lambda x: -x[1])[:5]:
            aggregated.append({
                "type": "pattern",
                "value": pattern,
                "frequency": count,
                "confidence": round(count / total, 2),
            })
        for technique, count in sorted(technique_counts.items(), key=lambda x: -x[1])[:3]:
            aggregated.append({
                "type": "technique",
                "value": technique,
                "frequency": count,
                "confidence": round(count / total, 2),
            })
        for suggestion, count in sorted(suggestion_counts.items(), key=lambda x: -x[1])[:3]:
            aggregated.append({
                "type": "suggestion",
                "value": suggestion,
                "frequency": count,
                "confidence": round(count / total, 2),
            })

        return aggregated
    def export_breakthroughs_as_seeds(self) -> list:
        """Export successful attacks as seed format for next run."""
        rows = self.conn.execute(
            f"SELECT * FROM attacks WHERE success=1 AND {self._t()} ORDER BY success_score DESC LIMIT 10",
            self._tp()
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

    def save_cluster_params(self, params: dict):
        """Save Thompson Sampling params to DB."""
        import time
        self.conn.execute(
            "INSERT OR REPLACE INTO cluster_params (target_id, params, updated_at) VALUES (?, ?, ?)",
            (self.target_id, json.dumps(params), time.time()))
        self.conn.commit()

    def load_cluster_params(self) -> dict:
        """Load Thompson Sampling params from DB. Returns None if not found."""
        row = self.conn.execute(
            "SELECT params FROM cluster_params WHERE target_id = ?",
            (self.target_id,)).fetchone()
        if row:
            try:
                return json.loads(row["params"])
            except (json.JSONDecodeError, TypeError):
                pass
        return None

