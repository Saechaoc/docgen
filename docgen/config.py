"""Configuration loading for docgen (.docgen.yml)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:  # pragma: no cover - optional dependency
    import yaml as _yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    _yaml = None


class ConfigError(RuntimeError):
    """Raised when the configuration file cannot be parsed."""


@dataclass
class LLMConfig:
    """LLM runtime settings from .docgen.yml."""

    runner: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    request_timeout: Optional[float] = None


@dataclass
class PublishConfig:
    """Publish strategy for README updates."""

    mode: Optional[str] = None
    branch_prefix: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    update_existing: bool = False


@dataclass
class AnalyzerConfig:
    """Analyzer enablement and exclusions."""

    enabled: List[str] = field(default_factory=list)
    exclude_paths: List[str] = field(default_factory=list)


@dataclass
class CIConfig:
    """Continuous integration triggers."""

    watched_globs: List[str] = field(default_factory=list)


@dataclass
class DocGenConfig:
    """Represents the high-level settings defined in .docgen.yml."""

    root: Path
    llm: Optional[LLMConfig] = None
    readme_style: Optional[str] = None
    analyzers: AnalyzerConfig = field(default_factory=AnalyzerConfig)
    publish: Optional[PublishConfig] = None
    ci: CIConfig = field(default_factory=CIConfig)
    exclude_paths: List[str] = field(default_factory=list)
    templates_dir: Optional[Path] = None
    template_pack: Optional[str] = None


def load_config(config_path: Path) -> DocGenConfig:
    """Load configuration from disk."""
    config_file = _resolve_config_path(config_path)
    root = config_file.parent.resolve()

    if not config_file.exists():
        return DocGenConfig(root=root)

    data = _read_config(config_file)
    if not isinstance(data, dict):
        raise ConfigError(".docgen.yml must contain a mapping at the root")

    llm_data = _as_dict(data.get("llm"))
    llm = None
    if llm_data:
        llm = LLMConfig(
            runner=_as_str(llm_data.get("runner")),
            model=_as_str(llm_data.get("model")),
            temperature=_as_float(llm_data.get("temperature")),
            max_tokens=_as_int(llm_data.get("max_tokens")),
            base_url=_as_str(llm_data.get("base_url")),
            api_key=_as_str(llm_data.get("api_key")),
            request_timeout=_as_float(llm_data.get("request_timeout")),
        )
        if not any(
            (
                llm.runner,
                llm.model,
                llm.temperature,
                llm.max_tokens,
                llm.base_url,
                llm.api_key,
                llm.request_timeout,
            )
        ):
            llm = None

    readme_data = _as_dict(data.get("readme"))
    style = _as_str(readme_data.get("style")) if readme_data else None
    templates_dir_str = _as_str(readme_data.get("templates_dir")) if readme_data else None
    template_pack = _as_str(readme_data.get("template_pack")) if readme_data else None
    templates_dir = root / templates_dir_str if templates_dir_str else None

    analyzer_data = _as_dict(data.get("analyzers"))
    analyzers = AnalyzerConfig()
    if analyzer_data:
        analyzers.enabled = _as_str_list(analyzer_data.get("enabled"))
        analyzers.exclude_paths = _as_str_list(analyzer_data.get("exclude_paths"))

    publish_data = _as_dict(data.get("publish"))
    publish = None
    if publish_data:
        publish = PublishConfig(
            mode=_as_str(publish_data.get("mode")),
            branch_prefix=_as_str(publish_data.get("branch_prefix")),
            labels=_as_str_list(publish_data.get("labels")),
            update_existing=_as_bool(publish_data.get("update_existing")) or False,
        )
        if not any((publish.mode, publish.branch_prefix, publish.labels, publish.update_existing)):
            publish = None

    ci_data = _as_dict(data.get("ci"))
    ci = CIConfig()
    if ci_data:
        ci.watched_globs = _as_str_list(ci_data.get("watched_globs"))

    exclude_paths = _as_str_list(data.get("exclude_paths"))

    return DocGenConfig(
        root=root,
        llm=llm,
        readme_style=style,
        analyzers=analyzers,
        publish=publish,
        ci=ci,
        exclude_paths=exclude_paths,
        templates_dir=templates_dir,
        template_pack=template_pack,
    )


def _resolve_config_path(config_path: Path) -> Path:
    config_path = config_path.expanduser()
    if config_path.is_dir():
        return (config_path / ".docgen.yml").resolve()
    if config_path.name != ".docgen.yml":
        return (config_path.parent / ".docgen.yml").resolve()
    return config_path.resolve()


def _read_config(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}

    if _yaml is not None:
        try:
            loaded = _yaml.safe_load(text)  # type: ignore[no-untyped-call]
        except Exception as exc:  # pragma: no cover - defensive guard
            raise ConfigError(f"Failed to parse {path.name}: {exc}") from exc
        return loaded or {}

    return _parse_simple_yaml(text)


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    lines = text.splitlines()
    mapping, index = _parse_mapping(lines, 0, 0)
    # ensure remaining lines are blank/comments
    for remainder in lines[index:]:
        if remainder.strip() and not remainder.lstrip().startswith("#"):
            raise ConfigError("Unsupported YAML syntax encountered")
    return mapping


def _parse_mapping(lines: Sequence[str], start: int, indent: int) -> tuple[Dict[str, Any], int]:
    result: Dict[str, Any] = {}
    index = start
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        current_indent = len(raw) - len(raw.lstrip(" "))
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ConfigError("Invalid indentation in YAML mapping")
        if ":" not in stripped:
            raise ConfigError("Expected key-value pair in YAML mapping")
        key_part, value_part = stripped.split(":", 1)
        key = key_part.strip()
        value_part = value_part.strip()
        index += 1
        if not value_part:
            if index >= len(lines):
                result[key] = None
                continue
            next_line = lines[index]
            next_indent = len(next_line) - len(next_line.lstrip(" "))
            if next_indent <= current_indent:
                result[key] = None
                continue
            if next_line.strip().startswith("- "):
                items, index = _parse_sequence(lines, index, next_indent)
                result[key] = items
            else:
                nested, index = _parse_mapping(lines, index, next_indent)
                result[key] = nested
        else:
            if value_part.startswith("[") and value_part.endswith("]"):
                result[key] = _parse_inline_sequence(value_part)
            else:
                result[key] = _parse_scalar(value_part)
    return result, index


def _parse_sequence(lines: Sequence[str], start: int, indent: int) -> tuple[List[Any], int]:
    items: List[Any] = []
    index = start
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        current_indent = len(raw) - len(raw.lstrip(" "))
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ConfigError("Invalid indentation in YAML sequence")
        if not stripped.startswith("- "):
            break
        value_part = stripped[2:].strip()
        index += 1
        if not value_part:
            if index >= len(lines):
                items.append(None)
                continue
            next_line = lines[index]
            next_indent = len(next_line) - len(next_line.lstrip(" "))
            if next_indent <= current_indent:
                items.append(None)
                continue
            if next_line.strip().startswith("- "):
                nested_list, index = _parse_sequence(lines, index, next_indent)
                items.append(nested_list)
            else:
                nested_map, index = _parse_mapping(lines, index, next_indent)
                items.append(nested_map)
        else:
            if value_part.startswith("[") and value_part.endswith("]"):
                items.append(_parse_inline_sequence(value_part))
            else:
                items.append(_parse_scalar(value_part))
    return items, index


def _parse_inline_sequence(value: str) -> List[Any]:
    inner = value[1:-1].strip()
    if not inner:
        return []
    parts: List[str] = []
    current = []
    in_quote: Optional[str] = None
    for char in inner:
        if char in {'"', "'"}:
            if in_quote == char:
                in_quote = None
            elif in_quote is None:
                in_quote = char
            current.append(char)
            continue
        if char == "," and in_quote is None:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current).strip())
    return [_parse_scalar(part) for part in parts if part]


def _parse_scalar(value: str) -> Any:
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    lower = value.lower()
    if lower == "null" or lower == "~":
        return None
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        if "." in value or "e" in lower:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_str(value: Any) -> Optional[str]:
    return str(value) if isinstance(value, (str, int, float, bool)) else None


def _as_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _as_int(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return None


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        result = [str(item) for item in value if isinstance(item, (str, int, float, bool))]
        return result
    return []
