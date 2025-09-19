"""Adapters around local model runtimes (Ollama, llama.cpp)."""


class LLMRunner:
    """Executes prompts against the configured local model."""

    def run(self, prompt: str) -> str:
        raise NotImplementedError
