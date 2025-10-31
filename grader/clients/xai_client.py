from __future__ import annotations

import asyncio
import random
from typing import Optional

import httpx

from ..config import XAIConfig

SYSTEM_PROMPT = (
    "You are a precise text restorer. You receive OCR'd student writing with some tokens marked [[UNK]] "
    "for low confidence.\n\n"
    "Rules:\n"
    "- ONLY replace [[UNK]] tokens with the most likely word(s) using immediate sentence context.\n"
    "- Do NOT change any other words, punctuation, spacing, or line breaks.\n"
    "- Preserve original casing wherever possible.\n"
    "- If context is insufficient, replace [[UNK]] with your best single-word guess.\n"
    "- Output ONLY the restored text, with no explanations or formatting."
)

USER_PROMPT_TEMPLATE = (
    "Restore the following text by filling ONLY the [[UNK]] tokens:\n\n<BEGIN_TEXT>\n{masked}\n<END_TEXT>"
)


class XAIClient:
    def __init__(self, config: XAIConfig, *, timeout: Optional[httpx.Timeout] = None) -> None:
        self._config = config
        self._timeout = timeout or httpx.Timeout(60.0, read=120.0)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "XAIClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if not self._client:
            headers = {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            }
            self._client = httpx.AsyncClient(base_url=self._config.base_url, headers=headers, timeout=self._timeout)
        return self._client

    async def restore(
        self,
        masked_text: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        max_attempts: int = 3,
    ) -> str:
        payload = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(masked=masked_text)},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        retryable = {429, 500, 502, 503, 504}
        attempt = 0
        last_error: Optional[Exception] = None
        client = await self._ensure_client()

        while attempt < max_attempts:
            attempt += 1
            try:
                response = await client.post("chat/completions", json=payload)
                if response.status_code in retryable:
                    await self._handle_retry(response, attempt, max_attempts)
                    continue
                response.raise_for_status()
                data = response.json()
                choices = data.get("choices") or []
                if not choices:
                    raise ValueError("XAI cleanup response missing choices")
                content = choices[0].get("message", {}).get("content")
                if content is None:
                    raise ValueError("XAI cleanup response missing content")
                return content.strip("\n")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= max_attempts:
                    raise
                await asyncio.sleep(2 ** attempt)

        raise RuntimeError("Failed to obtain cleanup result") from last_error

    async def _handle_retry(self, response: httpx.Response, attempt: int, max_attempts: int) -> None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                delay = 2 ** attempt
        else:
            delay = 2 ** attempt
        delay += random.uniform(0, 1)
        if attempt >= max_attempts:
            response.raise_for_status()
        await asyncio.sleep(delay)
