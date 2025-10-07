"""Validator that blocks README hallucinations."""

from __future__ import annotations

import re
from typing import Collection, Dict, Iterable, List, Optional, Sequence, Set

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
_SYNONYM_GROUPS = [
    {"dynamodb", "aws dynamodb", "aws-dynamodb", "amazon dynamodb"},
    {"terraform", "iac", "hashicorp terraform"},
    {"postgres", "postgresql"},
    {"kubernetes", "k8s"},
]

_SYNONYM_MAP: Dict[str, Set[str]] = {}
for group in _SYNONYM_GROUPS:
    lowered = {token.lower() for token in group}
    for token in lowered:
        _SYNONYM_MAP[token] = lowered


class NoHallucinationValidator(Validator):
    """Rejects README content that is not grounded in repository evidence."""

    name = "no_hallucination"

    def __init__(
        self,
        *,
        min_overlap: int = 1,
        mode: str = "balanced",
        allow_inferred: Optional[bool] = None,
    ) -> None:
        self._min_overlap = min_overlap
        normalized_mode = (mode or "strict").strip().lower()
        if normalized_mode not in {"strict", "balanced"}:
            normalized_mode = "strict"
        self._mode = normalized_mode
        if allow_inferred is None:
            allow_inferred = normalized_mode == "balanced"
        self._allowed_tiers: Collection[str] = (
            ("observed", "inferred") if allow_inferred else ("observed",)
        )
        self._synonyms_enabled = normalized_mode == "balanced"

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
                overlap = self._count_overlap(
                    tokens, context.evidence, section_name, self._allowed_tiers
                )
                if overlap >= self._min_overlap:
                    continue
                global_overlap = self._count_overlap(
                    tokens, context.evidence, None, self._allowed_tiers
                )
                if global_overlap >= self._min_overlap:
                    continue
                missing = self._missing_with_synonyms(
                    tokens, context.evidence, None, self._allowed_tiers
                )
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

    def _count_overlap(
        self,
        tokens: Set[str],
        evidence: EvidenceIndex,
        section: Optional[str],
        allowed_tiers: Collection[str],
    ) -> int:
        overlap = 0
        for token in tokens:
            for candidate in self._expand_token(token):
                if evidence.has_token(
                    candidate, section=section, allowed_tiers=allowed_tiers
                ):
                    overlap += 1
                    break
        return overlap

    def _missing_with_synonyms(
        self,
        tokens: Set[str],
        evidence: EvidenceIndex,
        section: Optional[str],
        allowed_tiers: Collection[str],
    ) -> List[str]:
        missing: List[str] = []
        for token in tokens:
            has_match = False
            for candidate in self._expand_token(token):
                if evidence.has_token(
                    candidate, section=section, allowed_tiers=allowed_tiers
                ):
                    has_match = True
                    break
            if not has_match:
                missing.append(token)
        return missing

    def _expand_token(self, token: str) -> Set[str]:
        base = token.lower()
        if self._synonyms_enabled and base in _SYNONYM_MAP:
            return _SYNONYM_MAP[base]
        return {base}

    @staticmethod
    def _build_detail(missing: Sequence[str], evidence: EvidenceIndex) -> str:
        if not missing:
            return "Sentence lacks overlap with repository evidence."
        examples: List[str] = []
        for token in missing[:3]:
            snapshot = evidence.snapshot(token)
            if snapshot:
                examples.append(f"{token} -> {snapshot.source}")
        missing_display = ", ".join(missing[:5])
        if examples:
            example_text = "; ".join(examples)
            return f"Missing evidence for: {missing_display} (nearest: {example_text})"
        return f"Missing evidence for: {missing_display}"
