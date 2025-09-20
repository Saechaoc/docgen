"""Diff inspection utilities."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable, Iterable, List, Sequence, Set


@dataclass(frozen=True)
class DiffResult:
    """Summary of repository changes and impacted README sections."""

    base: str
    changed_files: Sequence[str]
    sections: Sequence[str]


@dataclass(frozen=True)
class SectionRule:
    """Associates file change patterns with README sections."""

    section: str
    patterns: Sequence[str]

    def matches(self, path: str) -> bool:
        for pattern in self.patterns:
            if _pattern_matches(path, pattern):
                return True
        return False


class DiffAnalyzer:
    """Maps repository changes to affected README sections."""

    _IGNORED_PATHS = {"README.md", "README"}

    _SECTION_RULES: Sequence[SectionRule] = (
        SectionRule(
            section="build_and_test",
            patterns=(
                "requirements.txt",
                "pyproject.toml",
                "poetry.lock",
                "Pipfile",
                "package.json",
                "package-lock.json",
                "pnpm-lock.yaml",
                "yarn.lock",
                "pom.xml",
                "build.gradle",
                "build.gradle.kts",
                "gradle/",
                "Makefile",
                "CMakeLists.txt",
                "setup.cfg",
                "setup.py",
                "tox.ini",
                "tests/",
            ),
        ),
        SectionRule(
            section="quickstart",
            patterns=(
                "requirements.txt",
                "pyproject.toml",
                "Pipfile",
                "package.json",
                "Dockerfile",
                "docker-compose.yml",
                "docker-compose.yaml",
                "Makefile",
                "scripts/",
            ),
        ),
        SectionRule(
            section="deployment",
            patterns=(
                "Dockerfile",
                "docker-compose.yml",
                "docker-compose.yaml",
                "k8s/",
                "helm/",
                "infra/",
                "deploy/",
            ),
        ),
        SectionRule(
            section="configuration",
            patterns=(
                ".env",
                "config/",
                "configs/",
                "configuration/",
                "settings/",
                "appsettings.json",
                "*.env",
                "*.properties",
                "*.yaml",
                "*.yml",
            ),
        ),
        SectionRule(
            section="features",
            patterns=("src/", "app/", "cmd/", "lib/", "services/"),
        ),
        SectionRule(
            section="architecture",
            patterns=("src/", "app/", "cmd/", "lib/", "services/"),
        ),
        SectionRule(
            section="troubleshooting",
            patterns=("docs/troubleshooting", "docs/troubleshooting.md"),
        ),
        SectionRule(
            section="faq",
            patterns=("docs/faq", "docs/faq.md"),
        ),
        SectionRule(
            section="license",
            patterns=("LICENSE", "LICENSE.md", "COPYING"),
        ),
    )

    _DOCS_PREFIXES: Sequence[str] = ("docs/", "documentation/", "handbook/")

    _CODE_SUFFIXES: Sequence[str] = (
        ".py",
        ".pyi",
        ".pyx",
        ".c",
        ".h",
        ".cc",
        ".cpp",
        ".hpp",
        ".java",
        ".kt",
        ".kts",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".cs",
        ".swift",
        ".scala",
        ".m",
        ".mm",
    )

    def __init__(self, runner: Callable[..., str] | None = None) -> None:
        self._runner = runner or self._default_runner

    def compute(self, repo_path: str, diff_base: str) -> DiffResult:
        repo = Path(repo_path)
        if not (repo / ".git").exists():
            raise RuntimeError(f"{repo_path} is not a Git repository")

        changed_files = self._changed_files(repo, diff_base)
        sections = self._sections_for_changes(changed_files)
        ordered_sections = sorted(sections, key=_section_sort_key)
        filtered_files = [path for path in changed_files if path not in self._IGNORED_PATHS]
        return DiffResult(base=diff_base, changed_files=filtered_files, sections=ordered_sections)

    # ------------------------------------------------------------------
    # Internals

    def _changed_files(self, repo: Path, diff_base: str) -> List[str]:
        args = ["git", "diff", "--name-only", f"{diff_base}...HEAD"]
        output = self._run(args, cwd=repo, capture_output=True)
        files = [line.strip() for line in output.splitlines() if line.strip()]
        # Include staged but not committed changes relative to HEAD.
        status = self._run(["git", "status", "--short"], cwd=repo, capture_output=True)
        for line in status.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            path = stripped.split(maxsplit=1)[-1]
            if path not in files:
                files.append(path)
        return files

    def _sections_for_changes(self, paths: Sequence[str]) -> Set[str]:
        sections: Set[str] = set()
        doc_touch = any(self._is_docs_path(path) for path in paths)
        if doc_touch:
            sections.update(_DEFAULT_SECTION_ORDER)
        for path in paths:
            normalized = path.replace("\\", "/")
            if normalized in self._IGNORED_PATHS:
                continue
            for rule in self._SECTION_RULES:
                if rule.matches(normalized):
                    sections.add(rule.section)
            if self._looks_like_code(normalized):
                sections.update({"features", "architecture"})
        # Keep intro aligned with major content updates.
        if sections.intersection({"features", "architecture", "quickstart"}):
            sections.add("intro")
        return sections

    def _is_docs_path(self, path: str) -> bool:
        normalized = path.replace("\\", "/")
        return any(normalized.startswith(prefix) for prefix in self._DOCS_PREFIXES)

    def _looks_like_code(self, path: str) -> bool:
        normalized = path.replace("\\", "/")
        if "/tests/" in f"/{normalized}/" or normalized.startswith("tests/"):
            return False
        if normalized.startswith("docs/"):
            return False
        suffix = Path(normalized).suffix.lower()
        return bool(suffix) and suffix in self._CODE_SUFFIXES

    def _run(
        self,
        args: Iterable[str],
        *,
        cwd: Path,
        capture_output: bool = False,
    ) -> str:
        return self._runner(args, cwd=cwd, capture_output=capture_output)

    @staticmethod
    def _default_runner(
        args: Iterable[str],
        *,
        cwd: Path,
        capture_output: bool = False,
    ) -> str:
        import subprocess

        completed = subprocess.run(
            list(args),
            cwd=str(cwd),
            check=True,
            text=True,
            capture_output=capture_output,
        )
        return completed.stdout if capture_output else ""


def _pattern_matches(path: str, pattern: str) -> bool:
    normalized = path.replace("\\", "/")
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return normalized == prefix or normalized.startswith(prefix)
    if pattern.endswith("/"):
        prefix = pattern
        return normalized.startswith(prefix)
    if pattern.startswith("**/"):
        suffix = pattern[3:]
        return normalized.endswith(suffix) or fnmatch(normalized, pattern)
    if "/" in pattern or any(ch in pattern for ch in "*?["):
        return fnmatch(normalized, pattern)
    if normalized == pattern:
        return True
    return normalized.endswith(f"/{pattern}")


_DEFAULT_SECTION_ORDER: Sequence[str] = (
    "intro",
    "features",
    "architecture",
    "quickstart",
    "configuration",
    "build_and_test",
    "deployment",
    "troubleshooting",
    "faq",
    "license",
)


def _section_sort_key(section: str) -> int:
    try:
        return _DEFAULT_SECTION_ORDER.index(section)
    except ValueError:
        return len(_DEFAULT_SECTION_ORDER)
