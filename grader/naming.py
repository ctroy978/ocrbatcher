from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Optional

import regex


NAME_COLON = regex.compile(r"(?i)\bname\s*:\s*([\p{L}][\p{L}\-']+)")
NAME_LINE_START = regex.compile(
    r"(?i)^\s*name\b[:\s]*([\p{L}][\p{L}\-']*)\b(?:\s+([\p{L}][\p{L}\-']+))?"
)
CAP_TOKEN = regex.compile(r"^\p{Lu}[\p{L}\-']*$")


@dataclass(slots=True)
class NameResult:
    display_name: str
    filename_stem: str


def _normalize_filename(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_only = ascii_only.strip().lower()
    cleaned = regex.sub(r"[^\w\-]+", "-", ascii_only)
    cleaned = regex.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or "unnamed"


def _fallback_name(fallback: Optional[str], page_index: int) -> str:
    if fallback:
        return f"{fallback}_{page_index + 1:02d}"
    return f"unnamed_{page_index + 1:02d}"


def extract_first_name(text: str, fallback: Optional[str], page_index: int) -> NameResult:
    match = NAME_COLON.search(text)
    if match:
        name = match.group(1).strip()
        return NameResult(display_name=name, filename_stem=_normalize_filename(name))

    lines = text.splitlines()
    for idx, line in enumerate(lines[:5]):
        colon_match = NAME_LINE_START.match(line)
        if colon_match:
            primary = colon_match.group(1)
            if primary:
                return NameResult(display_name=primary.strip(), filename_stem=_normalize_filename(primary))
        tokens = [token for token in regex.findall(r"[\p{L}][\p{L}\-']*", line)]
        if tokens and tokens[0].lower() == "name" and len(tokens) > 1:
            candidate = next((token for token in tokens[1:] if CAP_TOKEN.match(token)), None)
            if candidate:
                return NameResult(display_name=candidate, filename_stem=_normalize_filename(candidate))

    fallback_name = _fallback_name(fallback, page_index)
    return NameResult(display_name=fallback_name, filename_stem=_normalize_filename(fallback_name))
