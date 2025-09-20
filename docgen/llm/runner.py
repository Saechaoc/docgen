"""Adapters around local model runtimes (Model Runner / Ollama)."""

from __future__ import annotations

import ipaddress
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_AUTO_BASE_URL = object()
_AUTO_API_KEY = object()


@dataclass
class LLMRequest:
    """Represents an inference request for the local runner."""

    prompt: str
    system: Optional[str]
    model: str
    temperature: Optional[float]
    max_tokens: Optional[int]
    executable: Optional[str]
    base_url: Optional[str]
    api_key: Optional[str]
    request_timeout: Optional[float]


class LLMRunner:
    """Executes prompts against the configured local model runtime."""

    DEFAULT_MODEL = "ai/smollm2:360M-Q4_K_M"
    DEFAULT_BASE_URLS = (
        "http://localhost:12434/engines/v1",
        "http://model-runner.docker.internal/engines/v1",
    )
    ENV_MODEL_KEYS = ("DOCGEN_LLM_MODEL", "MODEL_RUNNER_MODEL", "OPENAI_MODEL")
    ENV_BASE_URL_KEYS = (
        "DOCGEN_LLM_BASE_URL",
        "MODEL_RUNNER_BASE_URL",
        "OPENAI_BASE_URL",
    )
    ENV_API_KEY_KEYS = (
        "DOCGEN_LLM_API_KEY",
        "MODEL_RUNNER_API_KEY",
        "OPENAI_API_KEY",
    )

    def __init__(
        self,
        model: str | None = None,
        *,
        base_url: str | None | object = _AUTO_BASE_URL,
        executable: str = "ollama",
        temperature: Optional[float] = 0.2,
        max_tokens: Optional[int] = None,
        api_key: str | None | object = _AUTO_API_KEY,
        request_timeout: Optional[float] = 60.0,
        runner: Callable[[LLMRequest], str] | None = None,
    ) -> None:
        self.model = self._resolve_model(model)
        self.base_url = self._resolve_base_url(base_url)
        self.executable = executable
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = self._resolve_api_key(api_key)
        self.request_timeout = request_timeout
        if runner is not None:
            self._runner = runner
        else:
            self._runner = self._http_runner if self.base_url else self._cli_runner

    def run(self, prompt: str, *, system: str | None = None) -> str:
        """Send the prompt to the configured local model and return the response text."""
        request = LLMRequest(
            prompt=prompt,
            system=system,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            executable=self.executable,
            base_url=self.base_url,
            api_key=self.api_key,
            request_timeout=self.request_timeout,
        )
        return self._runner(request)

    @staticmethod
    def _normalize_base_url(url: str) -> str:
        return url.rstrip("/")

    @staticmethod
    def _cli_runner(request: LLMRequest) -> str:
        args = [request.executable or "ollama", "run", request.model]
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

    @staticmethod
    def _http_runner(request: LLMRequest) -> str:
        if not request.base_url:
            raise RuntimeError("HTTP runner requires a base_url to be configured.")
        endpoint = f"{request.base_url}/chat/completions"
        payload: dict[str, object] = {
            "model": request.model,
            "messages": LLMRunner._build_messages(request.system, request.prompt),
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if request.api_key:
            headers["Authorization"] = f"Bearer {request.api_key}"

        http_request = Request(endpoint, data=data, headers=headers, method="POST")
        timeout = request.request_timeout or 60.0

        try:
            with urlopen(http_request, timeout=timeout) as response:  # type: ignore[arg-type]
                raw = response.read()
        except HTTPError as exc:  # pragma: no cover - depends on runtime
            detail = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
            message = detail.strip() or exc.reason
            raise RuntimeError(
                f"LLM HTTP runner failed with status {exc.code}: {message}"
            ) from exc
        except URLError as exc:  # pragma: no cover - depends on runtime
            raise RuntimeError(f"LLM HTTP runner failed: {exc.reason}") from exc

        try:
            response_payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM HTTP runner returned invalid JSON") from exc

        content = LLMRunner._extract_content(response_payload)
        if not content:
            raise RuntimeError("LLM HTTP runner returned an empty response")
        return content.strip()

    @staticmethod
    def _build_messages(system: str | None, prompt: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def _extract_content(payload: dict[str, object]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        message = first.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content
        text = first.get("text")
        if isinstance(text, str):
            return text
        return ""

    def _resolve_model(self, model: str | None) -> str:
        if model:
            return model
        env_value = self._first_env_value(self.ENV_MODEL_KEYS)
        if env_value:
            return env_value
        return self.DEFAULT_MODEL

    def _resolve_base_url(self, base_url: str | None | object) -> str | None:
        if base_url is None:
            return None
        if base_url is not _AUTO_BASE_URL:
            return self._ensure_local_url(str(base_url))
        env_value = self._first_env_value(self.ENV_BASE_URL_KEYS)
        if env_value:
            return self._ensure_local_url(env_value)
        for candidate in self.DEFAULT_BASE_URLS:
            if candidate:
                return self._ensure_local_url(candidate)
        return None

    def _resolve_api_key(self, api_key: str | None | object) -> str | None:
        if api_key is _AUTO_API_KEY:
            return self._first_env_value(self.ENV_API_KEY_KEYS)
        return api_key  # type: ignore[return-value]

    @staticmethod
    def _first_env_value(keys: Sequence[str]) -> str | None:
        for key in keys:
            value = os.getenv(key)
            if value:
                return value
        return None

    @classmethod
    def _ensure_local_url(cls, url: str) -> str:
        normalized = cls._normalize_base_url(url)
        parsed = urlparse(normalized)
        host = parsed.hostname
        if host is None:
            return normalized
        if cls._is_local_host(host):
            return normalized
        raise RuntimeError(
            f"Remote base_url '{url}' is not permitted. Configure a local model runner."
        )

    @staticmethod
    def _is_local_host(host: str) -> bool:
        lowered = host.lower()
        allowed_hosts = {
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "::1",
            "model-runner.docker.internal",
        }
        if lowered in allowed_hosts:
            return True
        if lowered.endswith(".local") or lowered.endswith(".localdomain"):
            return True
        try:
            ip = ipaddress.ip_address(lowered)
        except ValueError:
            return False
        return ip.is_loopback
