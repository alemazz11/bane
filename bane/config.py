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
GROQ_API_KEY      = os.getenv("GROQ_API_KEY",      "")
GROQ_URL          = os.getenv("GROQ_URL",          "https://api.groq.com/openai/v1/chat/completions")
GROQ_MODEL        = os.getenv("GROQ_MODEL",        "llama-3.3-70b-versatile")
TARGET_MODEL      = os.getenv("TARGET_MODEL",      "llama3.2:3b")
TARGET_DIFFICULTY  = os.getenv("TARGET_DIFFICULTY",  "medium")
DB_PATH           = os.getenv("DB_PATH",           "data/attacks.db")


def as_dict() -> dict:
    return {
        "ollama_url":        OLLAMA_URL,
        "groq_api_key":      GROQ_API_KEY,
        "groq_url":          GROQ_URL,
        "groq_model":        GROQ_MODEL,
        "target_model":      TARGET_MODEL,
        "target_difficulty": TARGET_DIFFICULTY,
        "db_path":           DB_PATH,
    }
