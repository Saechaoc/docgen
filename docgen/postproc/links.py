"""Link validation helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List


class LinkValidator:
    """Ensures generated links are reachable and consistent."""

    _LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    def validate(self, markdown: str, *, root: Path) -> List[str]:
        """Return a list of issues discovered in the provided markdown."""

        issues: List[str] = []
        for match in self._LINK_PATTERN.finditer(markdown):
            target = match.group(2).strip()
            if not target:
                issues.append("Empty link target detected")
                continue
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if target.startswith("#"):
                continue
            cleaned = target.split("#", 1)[0]
            cleaned = cleaned.split("?", 1)[0]
            normalized = cleaned.replace("\\", "/").lstrip("./")
            if not normalized:
                continue
            candidate = root / normalized
            if not candidate.exists():
                issues.append(f"Link target not found: {target}")
        return issues


__all__ = ["LinkValidator"]
