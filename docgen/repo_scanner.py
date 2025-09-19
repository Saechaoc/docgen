"""Repository scanning and manifest building utilities."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Dict, Iterator, List, Sequence

from .config import ConfigError, load_config
from .models import FileMeta, RepoManifest

_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".docgen",
    "sandbox",
}

_EXCLUDED_FILES = {
    "README.md~",
    ".DS_Store",
    "Thumbs.db",
}

_LANGUAGE_BY_SUFFIX = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cc": "C++",
    ".hh": "C++",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".scala": "Scala",
    ".r": "R",
    ".jl": "Julia",
    ".sh": "Shell",
    ".ps1": "PowerShell",
    ".bat": "Batch",
    ".cmd": "Batch",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
}

_ROLE_RULES: tuple[tuple[str, str], ...] = (
    ("tests", "test"),
    ("test", "test"),
    ("docs", "docs"),
    ("doc", "docs"),
    ("examples", "examples"),
    ("example", "examples"),
    ("config", "config"),
    ("infra", "infra"),
)

_CACHE_FILENAME = "manifest_cache.json"
_CACHE_VERSION = 1


@dataclass
class IgnoreRule:
    """Represents an ignore rule parsed from .gitignore or .docgen.yml."""

    pattern: str
    directory_only: bool
    anchored: bool
    negate: bool
    has_slash: bool

    def matches(self, rel_path: str, is_dir: bool) -> bool:
        if not self.pattern:
            return False
        if self.directory_only and not is_dir:
            return False

        target = rel_path
        if self.anchored or self.has_slash:
            if fnmatchcase(target, self.pattern):
                return True
            if self.directory_only and target.startswith(f"{self.pattern}/"):
                return True
            return False

        for part in target.split("/"):
            if fnmatchcase(part, self.pattern):
                return True
        return False


def _build_ignore_rule(pattern: str, negate: bool = False) -> IgnoreRule | None:
    pattern = pattern.strip()
    if not pattern:
        return None

    directory_only = pattern.endswith("/")
    if directory_only:
        pattern = pattern[:-1]

    anchored = pattern.startswith("/")
    if anchored:
        pattern = pattern[1:]

    has_slash = "/" in pattern
    return IgnoreRule(
        pattern=pattern,
        directory_only=directory_only,
        anchored=anchored,
        negate=negate,
        has_slash=has_slash,
    )


def _parse_gitignore(path: Path) -> List[IgnoreRule]:
    if not path.exists():
        return []

    rules: List[IgnoreRule] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        negate = line.startswith("!")
        if negate:
            line = line[1:]
        rule = _build_ignore_rule(line, negate=negate)
        if rule is not None:
            rules.append(rule)
    return rules


def _parse_docgen_excludes(path: Path) -> List[IgnoreRule]:
    try:
        config = load_config(path)
    except ConfigError:
        return []

    patterns = list(config.exclude_paths)
    patterns.extend(config.analyzers.exclude_paths)

    rules: List[IgnoreRule] = []
    for pattern in patterns:
        rule = _build_ignore_rule(pattern)
        if rule is not None:
            rules.append(rule)
    return rules


def _load_ignore_rules(root: Path) -> List[IgnoreRule]:
    rules = _parse_gitignore(root / ".gitignore")
    rules.extend(_parse_docgen_excludes(root / ".docgen.yml"))
    return rules


def _should_ignore(rel_path: str, is_dir: bool, rules: Sequence[IgnoreRule]) -> bool:
    ignored = False
    for rule in rules:
        if rule.matches(rel_path, is_dir):
            ignored = not rule.negate
    return ignored


def _load_manifest_cache(root: Path) -> Dict[str, Dict[str, object]]:
    cache_path = root / ".docgen" / _CACHE_FILENAME
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict) or payload.get("version") != _CACHE_VERSION:
        return {}

    files = payload.get("files")
    if not isinstance(files, dict):
        return {}

    valid: Dict[str, Dict[str, object]] = {}
    for rel_path, entry in files.items():
        if not isinstance(entry, dict):
            continue
        size = entry.get("size")
        mtime_ns = entry.get("mtime_ns")
        file_hash = entry.get("hash")
        if (
            isinstance(rel_path, str)
            and isinstance(size, int)
            and isinstance(mtime_ns, int)
            and isinstance(file_hash, str)
        ):
            valid[rel_path] = {
                "size": size,
                "mtime_ns": mtime_ns,
                "hash": file_hash,
            }
    return valid


def _store_manifest_cache(root: Path, entries: Dict[str, Dict[str, object]]) -> None:
    cache_dir = root / ".docgen"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / _CACHE_FILENAME
        payload = {"version": _CACHE_VERSION, "files": entries}
        cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        pass


def _iter_files(root: Path, rules: Sequence[IgnoreRule]) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)
        rel_dir = current_dir.relative_to(root).as_posix() if current_dir != root else ""

        dirnames[:] = [name for name in dirnames if name not in _EXCLUDED_DIRS]

        filtered_dirs = []
        for name in dirnames:
            rel_path = f"{rel_dir}/{name}" if rel_dir else name
            if _should_ignore(rel_path, True, rules):
                continue
            filtered_dirs.append(name)
        dirnames[:] = filtered_dirs

        for filename in filenames:
            if filename in _EXCLUDED_FILES:
                continue
            rel_path = f"{rel_dir}/{filename}" if rel_dir else filename
            if _should_ignore(rel_path, False, rules):
                continue
            yield current_dir / filename


def _detect_language(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in _LANGUAGE_BY_SUFFIX:
        return _LANGUAGE_BY_SUFFIX[suffix]
    return None


def _detect_role(relative_path: str) -> str:
    parts = relative_path.split("/")
    for segment, role in _ROLE_RULES:
        if segment in parts:
            return role
    if relative_path.endswith((".md", ".rst")):
        return "docs"
    if "/tests/" in f"/{relative_path}/":
        return "test"
    return "src"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RepoScanner:
    """Walks the repository to produce a normalized manifest."""

    def scan(self, root: str) -> RepoManifest:
        """Return a manifest describing project files and roles."""
        root_path = Path(root).expanduser().resolve()
        if not root_path.exists():
            raise FileNotFoundError(f"Repository path not found: {root}")
        if not root_path.is_dir():
            raise NotADirectoryError(f"Repository path is not a directory: {root}")

        rules = _load_ignore_rules(root_path)
        cache = _load_manifest_cache(root_path)
        cache_entries: Dict[str, Dict[str, object]] = {}

        files: List[FileMeta] = []
        for path in _iter_files(root_path, rules):
            rel_path = path.relative_to(root_path).as_posix()
            stat_result = path.stat()
            size = stat_result.st_size
            mtime_ns = getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1_000_000_000))

            cached = cache.get(rel_path)
            if (
                cached
                and cached.get("size") == size
                and cached.get("mtime_ns") == mtime_ns
                and isinstance(cached.get("hash"), str)
            ):
                file_hash = cached["hash"]  # type: ignore[index]
            else:
                file_hash = _hash_file(path)

            language = _detect_language(path)
            role = _detect_role(rel_path)

            files.append(
                FileMeta(
                    path=rel_path,
                    size=size,
                    language=language,
                    role=role,
                    hash=file_hash,
                )
            )

            cache_entries[rel_path] = {
                "size": size,
                "mtime_ns": mtime_ns,
                "hash": file_hash,
            }

        _store_manifest_cache(root_path, cache_entries)

        return RepoManifest(root=str(root_path), files=files)
