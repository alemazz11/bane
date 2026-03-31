"""Ollama Client — same interface as GroqClient but calls local Ollama."""

import httpx


class OllamaClient:

    def __init__(self, url="http://localhost:11434", model="llama3.2:3b"):
        self.url = url
        self.model = model
        self.client = httpx.AsyncClient(timeout=120)

    async def chat(self, messages: list, temperature: float = 0.7) -> str:
        """OpenAI-compatible chat endpoint."""
        resp = await self.client.post(
            f"{self.url}/v1/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            },
        )
        data = resp.json()
        if "error" in data:
            raise ValueError(f"Ollama error: {data['error']}")
        return data["choices"][0]["message"]["content"]
