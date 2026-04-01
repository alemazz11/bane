"""Groq API client — OpenAI-compatible, with retry for rate limits."""

import re
import asyncio
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
        for attempt in range(5):
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
                err = str(data["error"])
                if "rate_limit" in err.lower() or r.status_code == 429:
                    # Try multiple patterns Groq uses
                    wait = None
                    for pattern in [
                        r"try again in (\d+\.?\d*)s",
                        r"in (\d+\.?\d*)\s*s",
                        r"(\d+\.?\d*)\s*second",
                        r"Please retry after (\d+\.?\d*)",
                    ]:
                        match = re.search(pattern, err, re.I)
                        if match:
                            wait = float(match.group(1)) + 2
                            break
                    if wait is None:
                        wait = min(30 * (attempt + 1), 90)  # 30, 60, 90s
                    print(f"  [groq] rate limited, waiting {wait:.0f}s (attempt {attempt+1}/5)...")
                    await asyncio.sleep(wait)
                    continue
                raise ValueError(f"Groq error: {data['error']}")
            return data["choices"][0]["message"]["content"]
        raise ValueError("Groq: max retries exceeded")
