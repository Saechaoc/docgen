"""README scorecard computation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from ..prompting.constants import DEFAULT_SECTIONS


@dataclass
class ReadmeScorecard:
    """Evaluates README content against basic quality gates."""

    def evaluate(self, markdown: str, *, link_issues: List[str] | None = None) -> Dict[str, object]:
        link_issues = link_issues or []
        coverage = self._section_coverage(markdown)
        quickstart_ok = self._quickstart_has_commands(markdown)
        badges_present = "<!-- docgen:begin:badges -->" in markdown

        # score 100 minus penalties
        score = 100
        score -= int((1 - coverage) * 40)
        if not quickstart_ok:
            score -= 20
        if link_issues:
            score -= min(len(link_issues) * 5, 20)
        if not badges_present:
            score -= 5
        score = max(score, 0)

        return {
            "score": score,
            "section_coverage": coverage,
            "missing_sections": self._missing_sections(markdown),
            "quickstart_has_commands": quickstart_ok,
            "badges_present": badges_present,
            "link_issues": link_issues,
        }

    def save(self, repo_path: Path, data: Dict[str, object]) -> None:
        output = repo_path / ".docgen" / "scorecard.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def _section_coverage(self, markdown: str) -> float:
        total = len(DEFAULT_SECTIONS)
        present = total - len(self._missing_sections(markdown))
        if total == 0:
            return 1.0
        return present / total

    def _missing_sections(self, markdown: str) -> List[str]:
        missing: List[str] = []
        for section in DEFAULT_SECTIONS:
            token = f"<!-- docgen:begin:{section} -->"
            if token not in markdown:
                missing.append(section)
        return missing

    def _quickstart_has_commands(self, markdown: str) -> bool:
        lower = markdown.lower()
        if "## quick start" not in lower:
            return False
        if "```" not in markdown:
            return False
        return True


__all__ = ["ReadmeScorecard"]
