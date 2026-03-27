"""Central configuration for BANE. Reads from .env file."""

import os
from pathlib import Path


def _load_env(path: str = ".env"):
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env()

OLLAMA_URL        = os.getenv("OLLAMA_URL",        "http://localhost:11434")
ATTACKER_MODEL    = os.getenv("ATTACKER_MODEL",    "qwen2.5:7b")
TARGET_MODEL      = os.getenv("TARGET_MODEL",      "llama3.2:3b")
JUDGE_MODEL       = os.getenv("JUDGE_MODEL",       "qwen2.5:7b")
ANALYZER_MODEL    = os.getenv("ANALYZER_MODEL",    "phi3.5:latest")
TARGET_DIFFICULTY = os.getenv("TARGET_DIFFICULTY", "easy")
DB_PATH           = os.getenv("DB_PATH",           "data/attacks.db")


def as_dict() -> dict:
    return {
        "ollama_url":        OLLAMA_URL,
        "attacker_model":    ATTACKER_MODEL,
        "target_model":      TARGET_MODEL,
        "judge_model":       JUDGE_MODEL,
        "analyzer_model":    ANALYZER_MODEL,
        "target_difficulty": TARGET_DIFFICULTY,
        "db_path":           DB_PATH,
    }