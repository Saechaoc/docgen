"""Builds prompts and templates for the local LLM."""

from typing import Iterable

from ..models import RepoManifest, Signal


class PromptBuilder:
    """Assembles section-aware prompts from templates and signals."""

    def build(
        self,
        manifest: RepoManifest,
        signals: Iterable[Signal],
        sections: Iterable[str],
    ) -> str:
        raise NotImplementedError
