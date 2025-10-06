"""Persistent cache for analyzer outputs."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from ..models import Signal

_CACHE_VERSION = 1


class AnalyzerCache:
    """Stores analyzer signals keyed by analyzer identity and manifest fingerprint."""

    def __init__(self, path: Path | None) -> None:
        self._path = path
        self._entries: Dict[str, Dict[str, object]] = {}
        self._dirty = False
        if self._path is not None:
            self._load(self._path)

    def get(
        self, key: str, *, signature: str, fingerprint: str
    ) -> Optional[List[Signal]]:
        entry = self._entries.get(key)
        if not entry:
            return None
        if entry.get("signature") != signature:
            return None
        if entry.get("fingerprint") != fingerprint:
            return None
        signals_payload = entry.get("signals")
        if not isinstance(signals_payload, list):
            return None
        signals: List[Signal] = []
        for payload in signals_payload:
            signal = _signal_from_dict(payload)
            if signal is not None:
                signals.append(signal)
        return signals

    def store(
        self,
        key: str,
        *,
        signature: str,
        fingerprint: str,
        signals: Sequence[Signal],
    ) -> None:
        serialised = [_signal_to_dict(signal) for signal in signals]
        self._entries[key] = {
            "signature": signature,
            "fingerprint": fingerprint,
            "signals": serialised,
            "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        self._dirty = True

    def prune(self, keys_to_keep: Iterable[str]) -> None:
        keep = set(keys_to_keep)
        removed = [key for key in self._entries if key not in keep]
        if removed:
            for key in removed:
                self._entries.pop(key, None)
            self._dirty = True

    def persist(self) -> None:
        if not self._dirty or self._path is None:
            return
        payload = {
            "version": _CACHE_VERSION,
            "entries": self._entries,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        self._dirty = False

    def clear(self) -> None:
        self._entries.clear()
        self._dirty = True

    # ------------------------------------------------------------------
    # Internal helpers

    def _load(self, path: Path) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict) or data.get("version") != _CACHE_VERSION:
            return
        entries = data.get("entries")
        if not isinstance(entries, dict):
            return
        valid_entries: Dict[str, Dict[str, object]] = {}
        for key, raw in entries.items():
            if not isinstance(key, str) or not isinstance(raw, dict):
                continue
            if (
                "signature" not in raw
                or "fingerprint" not in raw
                or "signals" not in raw
            ):
                continue
            valid_entries[key] = raw
        self._entries = valid_entries
        self._dirty = False


def _signal_to_dict(signal: Signal) -> Dict[str, object]:
    data = asdict(signal)
    metadata = data.get("metadata", {})
    if isinstance(metadata, dict):
        data["metadata"] = metadata
    else:
        data["metadata"] = {}
    return data


def _signal_from_dict(payload: object) -> Optional[Signal]:
    if not isinstance(payload, dict):
        return None
    name = payload.get("name")
    value = payload.get("value")
    source = payload.get("source")
    metadata = payload.get("metadata", {})
    if (
        not isinstance(name, str)
        or not isinstance(value, str)
        or not isinstance(source, str)
    ):
        return None
    if not isinstance(metadata, dict):
        metadata = {}
    return Signal(name=name, value=value, source=source, metadata=metadata)


__all__ = ["AnalyzerCache"]
