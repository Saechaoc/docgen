"""Core data models shared across docgen components."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FileMeta:
    """Metadata for an individual repository file."""

    path: str
    size: int
    language: Optional[str]
    role: str
    hash: str


@dataclass
class RepoManifest:
    """Normalized view of the repository for analyzers."""

    root: str
    files: List[FileMeta]


@dataclass
class Signal:
    """Structured fact emitted by analyzers for downstream use."""

    name: str
    value: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
