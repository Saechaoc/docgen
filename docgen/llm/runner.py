"""Adapters around local model runtimes (Ollama, llama.cpp)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class LLMRequest:
    """Represents an inference request for the local runner."""

    prompt: str
    system: Optional[str]
    model: str
    temperature: Optional[float]
    max_tokens: Optional[int]
    executable: str


class LLMRunner:
    """Executes prompts against the configured local model (Ollama)."""

    def __init__(
        self,
        model: str = "llama3:8b-instruct",
        *,
        executable: str = "ollama",
        temperature: Optional[float] = 0.2,
        max_tokens: Optional[int] = None,
        runner: Callable[[LLMRequest], str] | None = None,
    ) -> None:
        self.model = model
        self.executable = executable
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._runner = runner or self._default_runner

    def run(self, prompt: str, *, system: str | None = None) -> str:
        """Send the prompt to the local model and return the response text."""
        request = LLMRequest(
            prompt=prompt,
            system=system,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            executable=self.executable,
        )
        return self._runner(request)

    @staticmethod
    def _default_runner(request: LLMRequest) -> str:
        args = [request.executable, "run", request.model]
        if request.system:
            args.extend(["--system", request.system])
        if request.temperature is not None:
            args.extend(["--temperature", str(request.temperature)])
        if request.max_tokens is not None:
            args.extend(["--num-predict", str(request.max_tokens)])
        args.append(request.prompt)
        try:
            completed = subprocess.run(
                args,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                f"Unable to locate '{request.executable}'. Install Ollama or provide a custom runner."
            ) from exc
        except subprocess.CalledProcessError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                f"LLM runner failed with exit code {exc.returncode}: {exc.stderr.strip()}"
            ) from exc
        return completed.stdout.strip()
