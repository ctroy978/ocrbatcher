from __future__ import annotations

from dataclasses import dataclass

import regex


@dataclass(slots=True)
class CleanupResult:
    restored_text: str
    attempts: int
    guardrail_triggered: bool
    guardrail_violated: bool


def _guardrail_ok(masked_text: str, restored_text: str) -> bool:
    if masked_text == restored_text:
        return True

    parts = regex.split(r"(\[\[UNK]])", masked_text)
    idx = 0
    restored_length = len(restored_text)
    position = 0

    while idx < len(parts):
        part = parts[idx]
        if part == "[[UNK]]":
            next_literal = ""
            for look_ahead in parts[idx + 1 :]:
                if look_ahead != "[[UNK]]":
                    next_literal = look_ahead
                    break
            if not next_literal:
                # Remaining text belongs to the final [[UNK]] slot.
                position = restored_length
            else:
                next_pos = restored_text.find(next_literal, position)
                if next_pos == -1:
                    return False
                position = next_pos
            idx += 1
            continue

        if not part:
            idx += 1
            continue

        end_pos = position + len(part)
        if restored_text[position:end_pos] != part:
            return False
        position = end_pos
        idx += 1

    return True


async def restore(masked_text: str, *, client, logger=None) -> CleanupResult:
    attempts = 0
    guardrail_triggered = False
    guardrail_violated = False
    temps = [0.2, 0.0]
    restored_text = masked_text

    for idx, temperature in enumerate(temps, start=1):
        attempts = idx
        restored_text = await client.restore(masked_text, temperature=temperature)
        if _guardrail_ok(masked_text, restored_text):
            if idx > 1:
                guardrail_triggered = True
            return CleanupResult(
                restored_text=restored_text,
                attempts=attempts,
                guardrail_triggered=guardrail_triggered,
                guardrail_violated=False,
            )
        guardrail_triggered = True
        if logger:
            logger.warning("Guardrail violation detected; retrying cleanup with temperature=0.0")

    guardrail_violated = not _guardrail_ok(masked_text, restored_text)
    if guardrail_violated and logger:
        logger.warning("Guardrail violation persists after retry; accepting restored text with warning.")

    return CleanupResult(
        restored_text=restored_text,
        attempts=attempts,
        guardrail_triggered=guardrail_triggered,
        guardrail_violated=guardrail_violated,
    )
