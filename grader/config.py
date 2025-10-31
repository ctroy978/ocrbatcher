from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional, Sequence

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError


BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    dotenv_path = BASE_DIR / ".env"
    load_dotenv(dotenv_path=dotenv_path, override=False)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_list(name: str) -> list[str]:
    value = os.getenv(name)
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


class XAIConfig(BaseModel):
    api_key: Optional[str] = None
    model: str = "grok-4-fast-reasoning"
    base_url: str = "https://api.x.ai/v1"


class GoogleVisionConfig(BaseModel):
    credentials_path: Path = Field(default_factory=lambda: BASE_DIR / "gen-lang-client.json")
    language_hints: list[str] = Field(default_factory=list)
    mime_type: str = "image/jpeg"


class Settings(BaseModel):
    unk_threshold: int = 65
    max_concurrency: int = 3
    dry_run: bool = False
    verbose: bool = False
    keep_images: bool = False
    name_fallback: Optional[str] = None
    output_dir: Path = Field(default_factory=lambda: Path("out"))
    xai: XAIConfig = Field(default_factory=XAIConfig)
    google: GoogleVisionConfig = Field(default_factory=GoogleVisionConfig)


def _build_settings() -> Settings:
    data = {
        "unk_threshold": _env_int("UNK_THRESHOLD", 65),
        "max_concurrency": _env_int("MAX_CONCURRENCY", 3),
        "dry_run": _env_bool("DRY_RUN", False),
        "verbose": _env_bool("VERBOSE", False),
        "keep_images": _env_bool("KEEP_IMAGES", False),
        "name_fallback": os.getenv("NAME_FALLBACK") or None,
        "output_dir": Path(os.getenv("OUTPUT_DIR") or "out"),
        "xai": {
            "api_key": os.getenv("XAI_API_KEY") or None,
            "model": os.getenv("XAI_CLEANUP_MODEL") or "grok-4-fast-reasoning",
            "base_url": os.getenv("XAI_BASE_URL") or "https://api.x.ai/v1",
        },
        "google": {
            "credentials_path": Path(
                os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or (BASE_DIR / "gen-lang-client.json")
            ),
            "language_hints": _env_list("VISION_LANGUAGE_HINTS"),
            "mime_type": os.getenv("VISION_MIME_TYPE") or "image/jpeg",
        },
    }

    try:
        return Settings(**data)
    except ValidationError as exc:  # pragma: no cover - configuration is validated on startup
        raise RuntimeError(f"Invalid configuration: {exc}") from exc


@lru_cache
def get_settings() -> Settings:
    _load_env()
    return _build_settings()
