"""Analyzer to detect executable entrypoints across supported languages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from .base import Analyzer
from .utils import (
    build_node_script_command,
    detect_node_package_manager,
    load_node_dependencies,
    load_package_json,
)
from ..models import RepoManifest, Signal


@dataclass
class EntryPoint:
    """Represents a detected entrypoint with an associated command."""

    name: str
    command: str
    label: str
    priority: int = 50
    framework: Optional[str] = None


class EntryPointAnalyzer(Analyzer):
    """Detect executable entrypoints for quick-start guidance."""

    def supports(self, manifest: RepoManifest) -> bool:
        return bool(manifest.files)

    def analyze(self, manifest: RepoManifest) -> Iterable[Signal]:
        entrypoints: List[EntryPoint] = []
        manifest_paths = {file.path for file in manifest.files}

        entrypoints.extend(self._python_entrypoints(manifest))
        entrypoints.extend(self._node_entrypoints(Path(manifest.root), manifest_paths))
        entrypoints.extend(self._java_entrypoints(manifest))

        signals: List[Signal] = []
        for entry in sorted(entrypoints, key=lambda ep: ep.priority):
            metadata = {
                "command": entry.command,
                "label": entry.label,
                "priority": entry.priority,
            }
            if entry.framework:
                metadata["framework"] = entry.framework
            signals.append(
                Signal(
                    name=f"entrypoint.{entry.name}",
                    value=entry.command,
                    source="entrypoints",
                    metadata=metadata,
                )
            )

        if entrypoints:
            primary = min(entrypoints, key=lambda ep: ep.priority)
            signals.append(
                Signal(
                    name="entrypoint.primary",
                    value=primary.command,
                    source="entrypoints",
                    metadata={
                        "command": primary.command,
                        "label": primary.label,
                        "priority": primary.priority,
                        "framework": primary.framework,
                    },
                )
            )

        return signals

    # ------------------------------------------------------------------
    # Python heuristics

    def _python_entrypoints(self, manifest: RepoManifest) -> List[EntryPoint]:
        entries: List[EntryPoint] = []
        for file in manifest.files:
            if file.language != "Python" or not file.path.endswith(".py"):
                continue
            path = Path(file.path)
            text = _safe_read(Path(manifest.root) / path, max_chars=6000)
            if not text:
                continue

            # FastAPI app detection
            app_match = re.search(r"(\w+)\s*=\s*FastAPI\s*\(", text)
            if "FastAPI" in text and app_match:
                app_var = app_match.group(1)
                module = path.with_suffix("").as_posix().replace("/", ".")
                if module.endswith(".__init__"):
                    module = module[: -len(".__init__")]
                command = f"uvicorn {module}:{app_var} --reload"
                entries.append(
                    EntryPoint(
                        name="python.fastapi",
                        command=command,
                        label="Run FastAPI application",
                        priority=10,
                        framework="FastAPI",
                    )
                )
                continue

            # Django manage.py
            if path.name == "manage.py" and "execute_from_command_line" in text:
                command = "python manage.py runserver"
                entries.append(
                    EntryPoint(
                        name="python.django",
                        command=command,
                        label="Start Django development server",
                        priority=20,
                        framework="Django",
                    )
                )
                continue

            if 'if __name__ == "__main__":' in text:
                command = f"python {path.as_posix()}"
                entries.append(
                    EntryPoint(
                        name=f"python.{path.stem}",
                        command=command,
                        label=f"Run {path.name}",
                        priority=60,
                    )
                )
        return entries

    # ------------------------------------------------------------------
    # Node.js heuristics

    def _node_entrypoints(
        self,
        root: Path,
        manifest_paths: set[str],
    ) -> List[EntryPoint]:
        package_json = load_package_json(root)
        if not package_json:
            return []
        scripts = package_json.get("scripts")
        if not isinstance(scripts, dict):
            return []

        manager = detect_node_package_manager(manifest_paths)
        framework = self._infer_node_framework(root)
        entries: List[EntryPoint] = []

        preferred_scripts = ["dev", "start", "serve"]
        for priority, script in enumerate(preferred_scripts, start=30):
            if script in scripts:
                command = build_node_script_command(script, manager)
                label = (
                    f"{manager.title()} {script}"
                    if script != "start"
                    else "Start application"
                )
                entries.append(
                    EntryPoint(
                        name=f"node.{script}",
                        command=command,
                        label=label,
                        priority=priority,
                        framework=framework,
                    )
                )

        return entries

    def _infer_node_framework(self, root: Path) -> Optional[str]:
        deps = load_node_dependencies(root)
        frameworks = {dep.lower() for dep in deps.get("dependencies", [])}
        if "next" in frameworks:
            return "Next.js"
        if "express" in frameworks:
            return "Express"
        if "react" in frameworks:
            return "React"
        return None

    # ------------------------------------------------------------------
    # Java heuristics

    def _java_entrypoints(self, manifest: RepoManifest) -> List[EntryPoint]:
        root = Path(manifest.root)
        java_files = [file for file in manifest.files if file.path.endswith(".java")]
        if not java_files:
            return []

        found_spring = False
        for file in java_files:
            content = _safe_read(root / file.path, max_chars=8000)
            if "@SpringBootApplication" in content:
                found_spring = True
                break

        if not found_spring:
            return []

        has_mvnw = (root / "mvnw").exists() or (root / "mvnw.cmd").exists()
        has_gradlew = (root / "gradlew").exists() or (root / "gradlew.bat").exists()
        has_pom = any(file.path == "pom.xml" for file in manifest.files)
        has_gradle = any(
            file.path in {"build.gradle", "build.gradle.kts"} for file in manifest.files
        )

        if has_mvnw:
            command = "./mvnw spring-boot:run"
        elif has_pom:
            command = "mvn spring-boot:run"
        elif has_gradlew:
            command = "./gradlew bootRun"
        elif has_gradle:
            command = "gradle bootRun"
        else:
            command = "java -jar target/app.jar"

        return [
            EntryPoint(
                name="java.spring_boot",
                command=command,
                label="Run Spring Boot application",
                priority=40,
                framework="Spring Boot",
            )
        ]


def _safe_read(path: Path, *, max_chars: int) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    return text[:max_chars]
