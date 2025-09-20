"""Built-in endpoint detectors."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .core import Endpoint, EndpointDetector, join_paths, line_of


def _read_text(root: Path, relative: str) -> Optional[str]:
    path = root / relative
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    return None


# ---------------------------------------------------------------------------
# Specification detectors (OpenAPI / Postman / Insomnia)
# ---------------------------------------------------------------------------

_SPEC_PATTERN = re.compile(r"(openapi|swagger).*?\.(json|ya?ml)$", re.IGNORECASE)
_POSTMAN_PATTERN = re.compile(r"postman_collection\.json$", re.IGNORECASE)
_INSOMNIA_PATTERN = re.compile(r"insomnia.*\.json$", re.IGNORECASE)


class SpecDetector(EndpointDetector):
    """Parse API specification files when available."""

    def supports_repo(self, manifest) -> bool:  # noqa: ANN001 - dynamic typing
        return any(
            _SPEC_PATTERN.search(file.path)
            or _POSTMAN_PATTERN.search(file.path)
            or _INSOMNIA_PATTERN.search(file.path)
            for file in manifest.files
        )

    def extract(self, manifest) -> Iterable[Endpoint]:  # noqa: ANN001 - dynamic typing
        root = Path(manifest.root)
        for file in manifest.files:
            path = file.path
            if _SPEC_PATTERN.search(path):
                yield from self._from_openapi(root, path)
            elif _POSTMAN_PATTERN.search(path):
                yield from self._from_postman(root, path)
            elif _INSOMNIA_PATTERN.search(path):
                yield from self._from_insomnia(root, path)

    def _from_openapi(self, root: Path, relative: str) -> Iterable[Endpoint]:
        text = _read_text(root, relative)
        if text is None:
            return []
        try:
            if relative.lower().endswith((".yaml", ".yml")):
                try:
                    import yaml  # type: ignore
                except Exception:
                    return []
                data = yaml.safe_load(text)  # type: ignore[attr-defined]
            else:
                data = json.loads(text)
        except Exception:
            return []
        if not isinstance(data, dict):
            return []
        paths = data.get("paths")
        if not isinstance(paths, dict):
            return []
        for raw_path, mapping in paths.items():
            if not isinstance(mapping, dict):
                continue
            for method in mapping.keys():
                verb = method.upper()
                if verb not in {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}:
                    continue
                yield Endpoint(
                    method=verb,
                    path=raw_path,
                    file=relative,
                    framework="spec",
                    confidence=1.0,
                )
        return []

    def _from_postman(self, root: Path, relative: str) -> Iterable[Endpoint]:
        text = _read_text(root, relative)
        if text is None:
            return []
        try:
            data = json.loads(text)
        except Exception:
            return []
        items = data.get("item")
        if not isinstance(items, list):
            return []
        for method, path in self._walk_postman(items):
            yield Endpoint(
                method=method,
                path=path,
                file=relative,
                framework="spec",
                confidence=1.0,
            )
        return []

    def _walk_postman(self, items) -> Iterator[tuple[str, str]]:
        for item in items:
            if not isinstance(item, dict):
                continue
            nested = item.get("item")
            if isinstance(nested, list):
                yield from self._walk_postman(nested)
                continue
            request = item.get("request")
            if not isinstance(request, dict):
                continue
            method = (request.get("method") or "").upper()
            if not method:
                continue
            url = request.get("url") or {}
            path_segments = url.get("path") if isinstance(url, dict) else None
            if isinstance(path_segments, list) and path_segments:
                path = "/" + "/".join(segment.strip("/") for segment in path_segments if isinstance(segment, str))
            else:
                raw = url.get("raw") if isinstance(url, dict) else None
                path = raw or "/"
            yield method, path or "/"

    def _from_insomnia(self, root: Path, relative: str) -> Iterable[Endpoint]:
        text = _read_text(root, relative)
        if text is None:
            return []
        try:
            data = json.loads(text)
        except Exception:
            return []
        resources: list = []
        if isinstance(data, list):
            resources = data
        elif isinstance(data, dict):
            maybe = data.get("resources")
            if isinstance(maybe, list):
                resources = maybe
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            if resource.get("_type") != "request":
                continue
            method = (resource.get("method") or "").upper()
            url = resource.get("url") or ""
            if not method or not url:
                continue
            match = re.search(r"https?://[^/]+(/[^?#]*)", url)
            path = match.group(1) if match else url
            yield Endpoint(
                method=method,
                path=path,
                file=relative,
                framework="spec",
                confidence=1.0,
            )
        return []

# ---------------------------------------------------------------------------
# FastAPI detector
# ---------------------------------------------------------------------------

_FASTAPI_PATTERN = re.compile(
    r"@(?P<router>\w+)\.(?P<verb>get|post|put|delete|patch)\((['\"])(?P<path>[^'\"]+)\3",
    re.IGNORECASE,
)


class FastAPIDetector(EndpointDetector):
    """Locate FastAPI route decorators."""

    def supports_repo(self, manifest) -> bool:  # noqa: ANN001 - dynamic typing
        return any(file.language == "Python" for file in manifest.files)

    def extract(self, manifest) -> Iterable[Endpoint]:  # noqa: ANN001 - dynamic typing
        root = Path(manifest.root)
        for file in manifest.files:
            if file.language != "Python":
                continue
            text = _read_text(root, file.path)
            if not text:
                continue
            for match in _FASTAPI_PATTERN.finditer(text):
                yield Endpoint(
                    method=match.group("verb").upper(),
                    path=match.group("path"),
                    file=file.path,
                    line=line_of(text, match.start()),
                    framework="FastAPI",
                    language="Python",
                    confidence=0.95,
                )


# ---------------------------------------------------------------------------
# Express detector
# ---------------------------------------------------------------------------

_EXPRESS_PATTERN = re.compile(
    r"(?:\b(app|router)\b)\.(?P<verb>get|post|put|delete|patch)\s*\(\s*(['\"])(?P<path>[^'\"]+)\3",
    re.IGNORECASE,
)


class ExpressDetector(EndpointDetector):
    """Detect Express-style router verb invocations."""

    def supports_repo(self, manifest) -> bool:  # noqa: ANN001 - dynamic typing
        return any(file.language in {"JavaScript", "TypeScript"} for file in manifest.files)

    def extract(self, manifest) -> Iterable[Endpoint]:  # noqa: ANN001 - dynamic typing
        root = Path(manifest.root)
        for file in manifest.files:
            if file.language not in {"JavaScript", "TypeScript"}:
                continue
            if not file.path.endswith((".js", ".jsx", ".ts", ".tsx")):
                continue
            text = _read_text(root, file.path)
            if not text:
                continue
            for match in _EXPRESS_PATTERN.finditer(text):
                yield Endpoint(
                    method=match.group("verb").upper(),
                    path=match.group("path"),
                    file=file.path,
                    line=line_of(text, match.start()),
                    framework="Express",
                    language=file.language,
                    confidence=0.93,
                )


# ---------------------------------------------------------------------------
# Spring MVC detector
# ---------------------------------------------------------------------------

_SPRING_SHORT = re.compile(
    r"@(?P<verb>Get|Post|Put|Delete|Patch)Mapping\s*\(\s*(?:value|path\s*=\s*)?(?P<quote>['\"])(?P<path>[^'\"]+)(?P=quote)",
    re.IGNORECASE,
)
_SPRING_REQUEST_MAPPING = re.compile(r"@RequestMapping\s*\(\s*(?P<args>[^)]*)\)", re.DOTALL | re.IGNORECASE)


class SpringDetector(EndpointDetector):
    """Extract Spring MVC request mappings."""

    def supports_repo(self, manifest) -> bool:  # noqa: ANN001 - dynamic typing
        return any(
            file.language in {"Java", "Kotlin"} and file.path.endswith((".java", ".kt"))
            for file in manifest.files
        )

    def extract(self, manifest) -> Iterable[Endpoint]:  # noqa: ANN001 - dynamic typing
        root = Path(manifest.root)
        for file in manifest.files:
            if file.language not in {"Java", "Kotlin"}:
                continue
            if not file.path.endswith((".java", ".kt")):
                continue
            text = _read_text(root, file.path)
            if not text:
                continue
            class_base = self._resolve_class_base(text)
            for match in _SPRING_SHORT.finditer(text):
                yield Endpoint(
                    method=match.group("verb").upper(),
                    path=join_paths(class_base, match.group("path")),
                    file=file.path,
                    line=line_of(text, match.start()),
                    framework="Spring",
                    language=file.language,
                    confidence=0.95,
                )
            for match in _SPRING_REQUEST_MAPPING.finditer(text):
                verb = self._extract_request_method(match.group("args"))
                route = self._extract_request_path(match.group("args"))
                if not verb or not route:
                    continue
                yield Endpoint(
                    method=verb,
                    path=join_paths(class_base, route),
                    file=file.path,
                    line=line_of(text, match.start()),
                    framework="Spring",
                    language=file.language,
                    confidence=0.95,
                )

    @staticmethod
    def _resolve_class_base(text: str) -> str:
        class_mapping = re.search(r"@RequestMapping\s*\(\s*(?P<args>[^)]*)\)\s*(?:public\s+|protected\s+|private\s+)?class", text, re.DOTALL | re.IGNORECASE)
        if not class_mapping:
            return ""
        path = SpringDetector._extract_request_path(class_mapping.group("args"))
        return path or ""

    @staticmethod
    def _extract_request_method(args: str) -> Optional[str]:
        match = re.search(r"method\s*=\s*RequestMethod\.(GET|POST|PUT|DELETE|PATCH)", args, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None

    @staticmethod
    def _extract_request_path(args: str) -> Optional[str]:
        named = re.search(r"(?:value|path)\s*=\s*(?P<quote>['\"])(?P<path>[^'\"]+)(?P=quote)", args)
        if named:
            return named.group("path")
        positional = re.search(r"(?P<quote>['\"])(?P<path>[^'\"]+)(?P=quote)", args)
        if positional:
            return positional.group("path")
        return None


__all__ = [
    "SpecDetector",
    "FastAPIDetector",
    "ExpressDetector",
    "SpringDetector",
]
