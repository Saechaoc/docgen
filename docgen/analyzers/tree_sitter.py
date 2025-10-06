"""Tree-sitter powered symbol analyzer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .base import Analyzer
from ..models import RepoManifest, Signal

try:  # pragma: no cover - optional dependency
    from tree_sitter import Parser
    from tree_sitter_languages import get_language

    TREE_SITTER_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    Parser = None  # type: ignore[assignment]
    get_language = None  # type: ignore[assignment]
    TREE_SITTER_AVAILABLE = False


_SUPPORTED_LANGUAGES = {
    "Python": "python",
    "Java": "java",
    "TypeScript": "typescript",
}


@dataclass
class _ParsedSymbol:
    name: str
    kind: str
    signature: Optional[str]


class TreeSitterAnalyzer(Analyzer):
    """Extracts function and class symbols using tree-sitter parsers."""

    cache_version = "1"

    def __init__(self, enabled: Optional[bool] = None) -> None:
        self._enabled = TREE_SITTER_AVAILABLE if enabled is None else enabled
        self._parsers: Dict[str, Parser] = {}

    def supports(self, manifest: RepoManifest) -> bool:
        if not self._enabled:
            return False
        return any(self._language_for_file(meta.path, meta.language) for meta in manifest.files)

    def analyze(self, manifest: RepoManifest) -> Iterable[Signal]:
        if not self._enabled:
            return []

        signals: List[Signal] = []
        for meta in manifest.files:
            language_key = self._language_for_file(meta.path, meta.language)
            if not language_key:
                continue
            parser = self._get_parser(language_key)
            if parser is None:
                continue
            path = Path(manifest.root) / meta.path
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            source_bytes = source.encode("utf-8")
            tree = parser.parse(source_bytes)
            for symbol in self._collect_symbols(language_key, tree.root_node, source_bytes):
                signals.append(
                    Signal(
                        name=f"symbol.{symbol.kind}",
                        value=symbol.name,
                        source="tree_sitter",
                        metadata={
                            "language": language_key,
                            "file": meta.path,
                            "signature": symbol.signature,
                        },
                    )
                )
        return signals

    def _get_parser(self, language_key: str) -> Optional[Parser]:
        parser = self._parsers.get(language_key)
        if parser is not None:
            return parser
        if not TREE_SITTER_AVAILABLE:
            return None
        language = get_language(language_key)
        parser = Parser()
        parser.set_language(language)
        self._parsers[language_key] = parser
        return parser

    @staticmethod
    def _language_for_file(path: str, manifest_language: Optional[str]) -> Optional[str]:
        if manifest_language in _SUPPORTED_LANGUAGES:
            return _SUPPORTED_LANGUAGES[manifest_language]
        lower = path.lower()
        if lower.endswith(".py"):
            return "python"
        if lower.endswith(".java"):
            return "java"
        if lower.endswith(".ts") or lower.endswith(".tsx"):
            return "typescript"
        return None

    def _collect_symbols(self, language_key, node, source_bytes) -> Iterable[_ParsedSymbol]:  # type: ignore[no-untyped-def]
        if language_key == "python":
            yield from self._collect_python_symbols(node, source_bytes)
        elif language_key == "java":
            yield from self._collect_java_symbols(node, source_bytes)
        elif language_key == "typescript":
            yield from self._collect_typescript_symbols(node, source_bytes)

    @staticmethod
    def _node_text(node, source_bytes) -> str:  # type: ignore[no-untyped-def]
        return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

    def _collect_python_symbols(self, node, source_bytes) -> Iterable[_ParsedSymbol]:  # type: ignore[no-untyped-def]
        for child in node.children:
            if child.type == "function_definition":
                name_node = child.child_by_field_name("name")
                parameters = child.child_by_field_name("parameters")
                name = self._node_text(name_node, source_bytes) if name_node else ""
                params = self._node_text(parameters, source_bytes) if parameters else ""
                if name:
                    yield _ParsedSymbol(name=name, kind="function", signature=params)
            elif child.type == "class_definition":
                name_node = child.child_by_field_name("name")
                name = self._node_text(name_node, source_bytes) if name_node else ""
                if name:
                    yield _ParsedSymbol(name=name, kind="class", signature=None)
            yield from self._collect_python_symbols(child, source_bytes)

    def _collect_java_symbols(self, node, source_bytes) -> Iterable[_ParsedSymbol]:  # type: ignore[no-untyped-def]
        for child in node.children:
            if child.type == "class_declaration":
                name_node = child.child_by_field_name("name")
                name = self._node_text(name_node, source_bytes) if name_node else ""
                if name:
                    yield _ParsedSymbol(name=name, kind="class", signature=None)
            if child.type in {"method_declaration", "constructor_declaration"}:
                name_node = child.child_by_field_name("name")
                params = child.child_by_field_name("parameters")
                name = self._node_text(name_node, source_bytes) if name_node else ""
                signature = self._node_text(params, source_bytes) if params else None
                if name:
                    yield _ParsedSymbol(name=name, kind="function", signature=signature)
            yield from self._collect_java_symbols(child, source_bytes)

    def _collect_typescript_symbols(self, node, source_bytes) -> Iterable[_ParsedSymbol]:  # type: ignore[no-untyped-def]
        for child in node.children:
            if child.type == "class_declaration":
                name_node = child.child_by_field_name("name")
                name = self._node_text(name_node, source_bytes) if name_node else ""
                if name:
                    yield _ParsedSymbol(name=name, kind="class", signature=None)
            if child.type in {"function_declaration", "method_definition"}:
                name_node = child.child_by_field_name("name")
                params = child.child_by_field_name("parameters")
                name = self._node_text(name_node, source_bytes) if name_node else ""
                signature = self._node_text(params, source_bytes) if params else None
                if name:
                    yield _ParsedSymbol(name=name, kind="function", signature=signature)
            yield from self._collect_typescript_symbols(child, source_bytes)


__all__ = ["TreeSitterAnalyzer", "TREE_SITTER_AVAILABLE"]
