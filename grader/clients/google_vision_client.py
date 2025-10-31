from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from google.cloud import vision
from google.oauth2 import service_account

from ..config import GoogleVisionConfig


class GoogleVisionClient:
    def __init__(self, config: GoogleVisionConfig) -> None:
        self._config = config
        self._client: Optional[vision.ImageAnnotatorClient] = None

    async def __aenter__(self) -> "GoogleVisionClient":
        self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client:
            transport_close = getattr(self._client.transport, "close", None)
            if transport_close:
                await asyncio.to_thread(transport_close)
            self._client = None

    def _ensure_client(self) -> vision.ImageAnnotatorClient:
        if not self._client:
            credentials = service_account.Credentials.from_service_account_file(
                str(self._config.credentials_path)
            )
            self._client = vision.ImageAnnotatorClient(credentials=credentials)
        return self._client

    async def document_text(self, image_path: Path) -> vision.AnnotateImageResponse:
        client = self._ensure_client()

        def _call():
            content = image_path.read_bytes()
            image = vision.Image(content=content)
            image_context = {}
            if self._config.language_hints:
                image_context["language_hints"] = self._config.language_hints
            response = client.document_text_detection(
                image=image,
                image_context=image_context or None,
            )
            if response.error.message:
                raise RuntimeError(f"Google Vision error: {response.error.message}")
            return response

        return await asyncio.to_thread(_call)
