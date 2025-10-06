"""Adapter for llama.cpp local execution."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class LlamaCppRunner:
    """Executes prompts using the llama.cpp CLI binary."""

    def __init__(
        self,
        *,
        model_path: str,
        executable: str | None = None,
        temperature: Optional[float] = 0.2,
        max_tokens: Optional[int] = None,
    ) -> None:
        self.model_path = self._validate_model_path(model_path)
        self.executable = executable or "llama.cpp"
        self.temperature = temperature
        self.max_tokens = max_tokens

    def run(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        full_prompt = self._compose_prompt(system, prompt)
        effective_tokens = max_tokens if max_tokens is not None else self.max_tokens

        args = [self.executable, "-m", str(self.model_path), "-p", full_prompt]
        if self.temperature is not None:
            args.extend(["--temp", str(self.temperature)])
        if effective_tokens is not None:
            args.extend(["-n", str(effective_tokens)])

        try:
            completed = subprocess.run(
                args,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                f"Unable to locate llama.cpp executable '{self.executable}'."
            ) from exc
        except subprocess.CalledProcessError as exc:  # pragma: no cover - environment dependent
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc.returncode)
            raise RuntimeError(f"llama.cpp execution failed: {message}") from exc

        output = completed.stdout.strip()
        if not output:
            raise RuntimeError("llama.cpp returned no output")
        return output

    @staticmethod
    def _compose_prompt(system: str | None, prompt: str) -> str:
        if system:
            return f"{system.strip()}\n\n{prompt}"
        return prompt

    @staticmethod
    def _validate_model_path(model_path: str) -> Path:
        path = Path(model_path).expanduser().resolve()
        if not path.exists():
            raise RuntimeError(f"llama.cpp model not found at {path}")
        if not path.is_file():
            raise RuntimeError(f"llama.cpp model must be a file: {path}")
        return path


__all__ = ["LlamaCppRunner"]
