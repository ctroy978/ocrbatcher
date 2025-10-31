import asyncio

import pytest

from grader import ai_cleanup


class DummyClient:
    def __init__(self, responses):
        self._responses = responses
        self.calls = 0

    async def restore(self, masked_text: str, temperature: float):
        if self.calls >= len(self._responses):
            raise RuntimeError("No more responses configured")
        response = self._responses[self.calls]
        self.calls += 1
        return response


def run(coro):
    return asyncio.run(coro)


def test_cleanup_success_on_first_attempt():
    masked = "Hello [[UNK]] world"
    responses = ["Hello friend world"]
    client = DummyClient(responses)

    result = run(ai_cleanup.restore(masked, client=client))
    assert result.restored_text == "Hello friend world"
    assert result.attempts == 1
    assert not result.guardrail_triggered
    assert not result.guardrail_violated


def test_cleanup_retries_on_guardrail_trigger():
    masked = "Hello [[UNK]] world"
    responses = ["Hi friend world", "Hello pal world"]
    client = DummyClient(responses)

    result = run(ai_cleanup.restore(masked, client=client))
    assert result.restored_text == "Hello pal world"
    assert result.attempts == 2
    assert result.guardrail_triggered
    assert not result.guardrail_violated


def test_cleanup_reports_guardrail_violation():
    masked = "Hello [[UNK]] world"
    responses = ["Hi friend world", "Greetings pal world"]
    client = DummyClient(responses)

    result = run(ai_cleanup.restore(masked, client=client))
    assert result.restored_text == "Greetings pal world"
    assert result.attempts == 2
    assert result.guardrail_triggered
    assert result.guardrail_violated

