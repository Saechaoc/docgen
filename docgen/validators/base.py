"""Core validation data structures and helpers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
from typing import (
    Collection,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Protocol,
    Sequence,
    Set,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing aid
    from docgen.models import RepoManifest, Signal
    from docgen.prompting.builder import Section

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*")
_CAMEL_PATTERN = re.compile(r"(?<!^)(?=[A-Z])")
_STOPWORDS = {
    "about",
    "after",
    "against",
    "all",
    "also",
    "and",
    "any",
    "are",
    "because",
    "being",
    "between",
    "both",
    "but",
    "docs",
    "docgen",
    "context",
    "follow",
    "highlight",
    "highlights",
    "step",
    "steps",
    "started",
    "rest",
    "consistent",
    "designed",
    "powered",
    "below",
    "each",
    "from",
    "have",
    "into",
    "its",
    "more",
    "must",
    "only",
    "other",
    "over",
    "some",
    "than",
    "that",
    "the",
    "their",
    "them",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "under",
    "using",
    "very",
    "were",
    "when",
    "where",
    "which",
    "will",
    "with",
    "within",
}


@dataclass
class ValidationIssue:
    """Represents a single validation failure for a README section."""

    section: str
    sentence: str
    missing_terms: List[str]
    detail: str


class ValidationError(RuntimeError):
    """Raised when validation fails for one or more sections."""

    def __init__(self, message: str, issues: Sequence[ValidationIssue]) -> None:
        super().__init__(message)
        self.issues = list(issues)


class Validator(Protocol):
    """Protocol implemented by README validators."""

    name: str

    def validate(self, context: "ValidationContext") -> List[ValidationIssue]:
        """Run validation and return any issues."""


@dataclass
class EvidenceSnapshot:
    """Summarises evidence contributing tokens for audit logs."""

    token: str
    source: str
    snippet: str


class EvidenceIndex:
    """Collects normalized evidence terms from signals, contexts, and metadata."""

    _OBSERVED = "observed"
    _INFERRED = "inferred"
    _TIER_PRIORITY = {_OBSERVED: 2, _INFERRED: 1}

    def __init__(self) -> None:
        self._global_terms: Dict[str, str] = {}
        self._section_terms: MutableMapping[Optional[str], Dict[str, str]] = (
            defaultdict(dict)
        )
        self._token_sources: MutableMapping[str, List[EvidenceSnapshot]] = defaultdict(
            list
        )

    def add(
        self,
        text: str,
        *,
        section: Optional[str],
        source: str,
        tier: str = _OBSERVED,
    ) -> None:
        tokens = list(self._tokenize(text))
        if not tokens:
            return
        for token in tokens:
            self._store_token(token, section, tier)
            if not self._token_sources[token]:
                snippet = text.strip()
                if len(snippet) > 120:
                    snippet = snippet[:117].rstrip() + "..."
                self._token_sources[token].append(
                    EvidenceSnapshot(token=token, source=source, snippet=snippet)
                )

    def merge(self, other: "EvidenceIndex") -> None:
        for token, tier in other._global_terms.items():
            self._store_token(token, None, tier)
        for section, mapping in other._section_terms.items():
            for token, tier in mapping.items():
                self._store_token(token, section, tier)
        for token, snapshots in other._token_sources.items():
            existing = self._token_sources[token]
            for snap in snapshots:
                if all(
                    s.source != snap.source or s.snippet != snap.snippet
                    for s in existing
                ):
                    existing.append(snap)

    def has_token(
        self,
        token: str,
        *,
        section: Optional[str] = None,
        allowed_tiers: Optional[Collection[str]] = None,
    ) -> bool:
        tier = self._get_token_tier(token, section)
        if tier and self._tier_allowed(tier, allowed_tiers):
            return True
        if section is not None:
            tier = self._global_terms.get(token)
            if tier and self._tier_allowed(tier, allowed_tiers):
                return True
        return False

    def has_any(
        self,
        tokens: Iterable[str],
        *,
        section: Optional[str] = None,
        allowed_tiers: Optional[Collection[str]] = None,
    ) -> bool:
        return any(
            self.has_token(token, section=section, allowed_tiers=allowed_tiers)
            for token in tokens
        )

    def missing_tokens(
        self,
        tokens: Iterable[str],
        *,
        section: Optional[str] = None,
        allowed_tiers: Optional[Collection[str]] = None,
    ) -> List[str]:
        return [
            token
            for token in tokens
            if not self.has_token(token, section=section, allowed_tiers=allowed_tiers)
        ]

    def snapshot(self, token: str) -> Optional[EvidenceSnapshot]:
        snapshots = self._token_sources.get(token)
        return snapshots[0] if snapshots else None

    def _store_token(self, token: str, section: Optional[str], tier: str) -> None:
        tier = tier if tier in self._TIER_PRIORITY else self._INFERRED
        if section is None:
            current = self._global_terms.get(token)
            if (
                current is None
                or self._TIER_PRIORITY[tier] > self._TIER_PRIORITY[current]
            ):
                self._global_terms[token] = tier
            return
        bucket = self._section_terms[section]
        current = bucket.get(token)
        if current is None or self._TIER_PRIORITY[tier] > self._TIER_PRIORITY[current]:
            bucket[token] = tier

    def _get_token_tier(self, token: str, section: Optional[str]) -> Optional[str]:
        if section is not None:
            value = self._section_terms.get(section, {}).get(token)
            if value:
                return value
        return self._global_terms.get(token)

    @staticmethod
    def _tier_allowed(tier: str, allowed: Optional[Collection[str]]) -> bool:
        if not allowed:
            return True
        return tier in allowed

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        tokens: Set[str] = set()
        for match in _TOKEN_PATTERN.finditer(text):
            raw = match.group(0)
            cleaned = raw.strip("`")
            cleaned = cleaned.strip("()[]{}<>")
            cleaned = cleaned.strip(":;,!")
            if len(cleaned) < 3:
                continue
            lowered = cleaned.lower()
            if lowered in _STOPWORDS:
                continue
            tokens.add(lowered)
            if any(c.isupper() for c in raw[1:]):
                parts = [part.lower() for part in _CAMEL_PATTERN.split(raw) if part]
                tokens.update(
                    part for part in parts if len(part) >= 3 and part not in _STOPWORDS
                )
            for splitter in ("-", "_", "/", "."):
                if splitter in raw:
                    tokens.update(
                        subpart.lower()
                        for subpart in raw.split(splitter)
                        if len(subpart) >= 3 and subpart.lower() not in _STOPWORDS
                    )
            if lowered.endswith("s") and len(lowered) > 4:
                tokens.add(lowered[:-1])
            if lowered.endswith("es") and len(lowered) > 5:
                tokens.add(lowered[:-2])
            if any(char.isdigit() for char in raw):
                digits = re.sub(r"\D", "", raw)
                if len(digits) >= 2:
                    tokens.add(digits)
        return tokens


@dataclass
class ValidationContext:
    """Context shared with validators when evaluating README output."""

    manifest: "RepoManifest"
    signals: Sequence["Signal"]
    sections: Mapping[str, "Section"]
    evidence: EvidenceIndex


def build_evidence_index(
    signals: Sequence["Signal"],
    sections: Mapping[str, "Section"],
) -> EvidenceIndex:
    """Construct an evidence index from analyzer signals and section metadata."""
    index = EvidenceIndex()
    for signal in signals:
        index.add(
            signal.value, section=None, source=f"signal:{signal.name}", tier="inferred"
        )
        for item in _flatten(signal.metadata):
            index.add(
                str(item),
                section=None,
                source=f"signal_meta:{signal.name}",
                tier="inferred",
            )
    for name, section in sections.items():
        context_values = (
            section.metadata.get("context", [])
            if isinstance(section.metadata, dict)
            else []
        )
        if isinstance(context_values, Sequence):
            for chunk in context_values:
                as_str = str(chunk)
                index.add(
                    as_str, section=name, source=f"context:{name}", tier="observed"
                )
                index.add(
                    as_str, section=None, source=f"context:{name}", tier="observed"
                )
        for meta_value in _flatten(section.metadata):
            as_str = str(meta_value)
            index.add(as_str, section=name, source=f"metadata:{name}", tier="observed")
            index.add(as_str, section=None, source=f"metadata:{name}", tier="observed")
        if section.title:
            index.add(
                section.title, section=name, source=f"title:{name}", tier="observed"
            )
            index.add(
                section.title, section=None, source=f"title:{name}", tier="observed"
            )
    return index


def _flatten(value: object) -> Iterable[object]:
    if isinstance(value, Mapping):
        for item in value.values():
            yield from _flatten(item)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _flatten(item)
        return
    if isinstance(value, (str, int, float)):
        yield value
