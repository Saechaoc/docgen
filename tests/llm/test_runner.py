"""Tests for the local LLM runner."""

from __future__ import annotations

from docgen.llm.runner import LLMRunner


def test_llm_runner_constructs_request() -> None:
    captured = {}

    def fake_runner(request):
        captured["prompt"] = request.prompt
        captured["system"] = request.system
        captured["model"] = request.model
        captured["temperature"] = request.temperature
        captured["max_tokens"] = request.max_tokens
        captured["executable"] = request.executable
        return "response"

    runner = LLMRunner(
        model="custom-model",
        executable="ollama",
        temperature=0.15,
        max_tokens=256,
        runner=fake_runner,
    )
    result = runner.run("Hello world", system="system message")

    assert result == "response"
    assert captured == {
        "prompt": "Hello world",
        "system": "system message",
        "model": "custom-model",
        "temperature": 0.15,
        "max_tokens": 256,
        "executable": "ollama",
    }
