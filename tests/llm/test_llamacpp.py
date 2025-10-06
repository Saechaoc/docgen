"""Tests for the llama.cpp runner adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from docgen.llm.llamacpp import LlamaCppRunner


def test_llamacpp_runner_invokes_subprocess(monkeypatch, tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_text("dummy", encoding="utf-8")

    recorded_args: list[list[str]] = []

    def fake_run(args, check, capture_output, text):  # type: ignore[no-untyped-def]
        recorded_args.append(list(args))

        class _Completed:
            stdout = "response"

        return _Completed()

    monkeypatch.setattr("docgen.llm.llamacpp.subprocess.run", fake_run)

    runner = LlamaCppRunner(
        model_path=str(model),
        executable="llama-binary",
        max_tokens=128,
        temperature=0.5,
    )
    response = runner.run("Hello", system="Be helpful", max_tokens=64)

    assert response == "response"
    args = recorded_args[0]
    assert args[0] == "llama-binary"
    assert "-m" in args and str(model) in args
    assert "-p" in args
    assert "-n" in args and "64" in args
    assert "--temp" in args and "0.5" in args


def test_llamacpp_runner_validates_model_path(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        LlamaCppRunner(model_path=str(tmp_path / "missing.gguf"))
