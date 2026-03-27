"""Groq API client — OpenAI-compatible."""

import json
import httpx


class GroqClient:

    def __init__(self, api_key: str, url: str, model: str):
        self.url = url
        self.model = model
        self.client = httpx.AsyncClient(
            timeout=120,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def chat(self, messages: list, temperature: float = 0.7) -> str:
        r = await self.client.post(
            self.url,
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            },
        )
        data = r.json()
        if "error" in data:
            raise ValueError(f"Groq error: {data['error']}")
        return data["choices"][0]["message"]["content"]
