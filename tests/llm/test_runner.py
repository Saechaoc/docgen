"""Tests for the local LLM runner."""

from __future__ import annotations

import json

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
        captured["base_url"] = request.base_url
        captured["api_key"] = request.api_key
        captured["request_timeout"] = request.request_timeout
        return "response"

    runner = LLMRunner(
        model="custom-model",
        base_url=None,
        executable="ollama",
        temperature=0.15,
        max_tokens=256,
        request_timeout=42.0,
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
        "base_url": None,
        "api_key": None,
        "request_timeout": 42.0,
    }


def test_llm_runner_http_posts_payload(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def read(self):
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse({"choices": [{"message": {"content": "Whales are mammals."}}]})

    monkeypatch.setattr("docgen.llm.runner.urlopen", fake_urlopen)

    runner = LLMRunner(
        model="ai/smollm2:360M-Q4_K_M",
        base_url="http://localhost:12434/engines/v1/",
        api_key="local-key",
        temperature=0.05,
        max_tokens=128,
        request_timeout=25.0,
    )
    result = runner.run("Give me a fact about whales.", system="Act like a marine biologist.")

    assert result == "Whales are mammals."
    assert captured["url"] == "http://localhost:12434/engines/v1/chat/completions"
    headers = captured["headers"]
    assert headers["content-type"] == "application/json"
    assert headers["authorization"] == "Bearer local-key"
    payload = captured["payload"]
    assert payload["model"] == "ai/smollm2:360M-Q4_K_M"
    assert payload["messages"][0] == {"role": "system", "content": "Act like a marine biologist."}
    assert payload["messages"][1] == {
        "role": "user",
        "content": "Give me a fact about whales.",
    }
    assert payload["temperature"] == 0.05
    assert payload["max_tokens"] == 128
    assert captured["timeout"] == 25.0
