"""Configuration loading for docgen (.docgen.yml)."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class DocGenConfig:
    """Represents the high-level settings defined in .docgen.yml."""

    root: Path
    publish: bool = False
    llm: Optional[str] = None
    style: Optional[str] = None
    analyzers: List[str] = field(default_factory=list)
    templates_dir: Optional[Path] = None


def load_config(config_path: Path) -> DocGenConfig:
    """Load configuration from disk (implementation pending)."""
    raise NotImplementedError
