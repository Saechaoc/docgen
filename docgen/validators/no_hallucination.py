"""Validator that blocks README hallucinations."""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Set

from .base import EvidenceIndex, ValidationContext, ValidationIssue, Validator

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9`])")
_SAFE_PREFIXES = (
    "Replace this text",
    "Document the project structure",
    "Ready for continuous README generation",
    "Use this section",
    "Add deployment details",
    "Add troubleshooting guidance",
    "Add configuration details",
    "docgen could not populate",
    "docgen could not gather",
    "Follow the steps below",
    "_Observed frameworks",
)
_SAFE_EXACT = {
    "This README was bootstrapped by ``docgen init`` to summarize the repository at a glance.",
    "Replace this text with a concise mission statement for the repository.",
    "Document the project structure here.",
    "Document how to set up and run the project locally.",
    "Container image can be built with `docker build -t <image> .`.",
    "Outline deployment strategies or hosting targets here.",
}


class NoHallucinationValidator(Validator):
    """Rejects README content that is not grounded in repository evidence."""

    name = "no_hallucination"

    def __init__(self, *, min_overlap: int = 1) -> None:
        self._min_overlap = min_overlap

    def validate(self, context: ValidationContext) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        for section_name, section in context.sections.items():
            sentences = list(self._iter_sentences(section.body))
            for sentence in sentences:
                if self._should_skip(sentence):
                    continue
                tokens = self._extract_tokens(sentence)
                if not tokens:
                    continue
                overlap = self._count_overlap(tokens, context.evidence, section_name)
                if overlap >= self._min_overlap:
                    continue
                missing = context.evidence.missing_tokens(tokens, section=section_name)
                if not missing:
                    # fall back to global check
                    missing = context.evidence.missing_tokens(tokens, section=None)
                detail = self._build_detail(missing, context.evidence)
                issues.append(
                    ValidationIssue(
                        section=section_name,
                        sentence=sentence.strip(),
                        missing_terms=missing[:8],
                        detail=detail,
                    )
                )
        return issues

    @staticmethod
    def _iter_sentences(body: str) -> Iterable[str]:
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#") or line.startswith("`"):
                continue
            line = re.sub(r"^[*-]\s+", "", line)
            line = re.sub(r"^\d+\.\s+", "", line)
            pieces = _SENTENCE_BOUNDARY.split(line)
            for piece in pieces:
                fragment = piece.strip()
                if fragment:
                    yield fragment

    @staticmethod
    def _should_skip(sentence: str) -> bool:
        normalized = sentence.strip()
        if not normalized:
            return True
        if normalized in _SAFE_EXACT:
            return True
        for prefix in _SAFE_PREFIXES:
            if normalized.startswith(prefix):
                return True
        if normalized.startswith("_") and normalized.endswith(":"):
            return True
        lower = normalized.lower()
        if len(lower) < 20:
            return True
        return False

    @staticmethod
    def _extract_tokens(sentence: str) -> Set[str]:
        tokens = EvidenceIndex._tokenize(sentence)
        return {token for token in tokens if len(token) >= 3}

    @staticmethod
    def _count_overlap(tokens: Set[str], evidence: EvidenceIndex, section: str) -> int:
        overlap = 0
        for token in tokens:
            if evidence.has_token(token, section=section) or evidence.has_token(token, section=None):
                overlap += 1
        return overlap

    @staticmethod
    def _build_detail(missing: Sequence[str], evidence: EvidenceIndex) -> str:
        if not missing:
            return "Sentence lacks overlap with repository evidence."
        examples: List[str] = []
        for token in missing[:3]:
            snapshot = evidence.snapshot(token)
            if snapshot:
                examples.append(f"{token} ↔ {snapshot.source}")
        missing_display = ", ".join(missing[:5])
        if examples:
            example_text = "; ".join(examples)
            return f"Missing evidence for: {missing_display} (nearest: {example_text})"
        return f"Missing evidence for: {missing_display}"
