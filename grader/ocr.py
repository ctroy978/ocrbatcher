from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import regex
from google.cloud.vision_v1 import AnnotateImageResponse


@dataclass(slots=True)
class OCRStats:
    provider: str
    total_tokens: int
    masked_tokens: int


@dataclass(slots=True)
class OCRResult:
    raw_text: str
    masked_text: str
    stats: OCRStats
    artifacts: Dict[str, str]


def _build_masked_text(
    raw_text: str, tokens: Iterable[str], confidences: Iterable[int], threshold: int
) -> Tuple[str, int]:
    masked_text = raw_text
    masked_count = 0
    search_start = 0
    for token, confidence in zip(tokens, confidences):
        token = token.strip()
        if not token:
            continue
        try:
            confidence_val = float(confidence)
        except ValueError:
            continue
        if confidence_val < threshold and confidence_val >= 0:
            is_word = regex.match(r"^\w+$", token) is not None
            pattern = regex.compile(rf"\b{regex.escape(token)}\b") if is_word else regex.compile(
                regex.escape(token)
            )
            match = pattern.search(masked_text, search_start)
            if match:
                masked_text = masked_text[: match.start()] + "[[UNK]]" + masked_text[match.end() :]
                search_start = match.start() + len("[[UNK]]")
                masked_count += 1
    return masked_text, masked_count


def _extract_tokens_from_vision(response: AnnotateImageResponse) -> Tuple[List[str], List[int]]:
    tokens: List[str] = []
    confidences: List[int] = []

    if not response.full_text_annotation:
        return tokens, confidences

    for page in response.full_text_annotation.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    word_text = "".join(symbol.text for symbol in word.symbols)
                    if not word_text.strip():
                        continue
                    if word.confidence is not None and word.confidence > 0:
                        confidence = int(round(word.confidence * 100))
                    elif word.symbols:
                        confidences_sum = sum((symbol.confidence or 0.0) for symbol in word.symbols)
                        confidence = int(round((confidences_sum / len(word.symbols)) * 100))
                    else:
                        confidence = 100
                    tokens.append(word_text)
                    confidences.append(confidence)
    return tokens, confidences


async def ocr_google_vision(image_path: Path, *, client, threshold: int) -> OCRResult:
    response = await client.document_text(image_path)
    annotation = response.full_text_annotation
    if annotation and annotation.text:
        raw_text = annotation.text
    elif response.text_annotations:
        raw_text = response.text_annotations[0].description
    else:
        raw_text = ""

    tokens, confidences = _extract_tokens_from_vision(response)
    masked_text, masked_count = _build_masked_text(raw_text, tokens, confidences, threshold)
    stats = OCRStats(provider="google-vision", total_tokens=len(tokens), masked_tokens=masked_count)
    artifacts = {
        "raw": raw_text,
        "masked": masked_text,
    }
    return OCRResult(raw_text=raw_text, masked_text=masked_text, stats=stats, artifacts=artifacts)

