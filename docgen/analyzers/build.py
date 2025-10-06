"""Build system analyzer implementation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Optional

from .base import Analyzer
from ..models import RepoManifest, Signal
from .utils import detect_node_package_manager


class BuildAnalyzer(Analyzer):
    """Detects build systems and associated developer workflows."""

    _PY_BUILD_FILES = {
        "pyproject.toml",
        "setup.cfg",
        "requirements.txt",
    }

    def supports(self, manifest: RepoManifest) -> bool:
        return bool(manifest.files)

    def analyze(self, manifest: RepoManifest) -> Iterable[Signal]:
        root = Path(manifest.root)
        manifest_paths = {file.path for file in manifest.files}
        signals: List[Signal] = []

        python_signal = self._python_signal(manifest_paths)
        if python_signal is not None:
            signals.append(python_signal)

        node_signal = self._node_signal(manifest_paths)
        if node_signal is not None:
            signals.append(node_signal)

        java_signal = self._java_signal(root, manifest_paths)
        if java_signal is not None:
            signals.append(java_signal)

        if not signals:
            signals.append(
                Signal(
                    name="build.generic",
                    value="generic",
                    source="build",
                    metadata={"commands": ["# Document build steps here."]},
                )
            )

        return signals

    def _python_signal(self, manifest_paths: set[str]) -> Optional[Signal]:
        python_files = self._PY_BUILD_FILES.intersection(manifest_paths)
        if not python_files:
            return None
        commands = [
            "python -m venv .venv",
            (
                "source .venv/bin/activate"
                if not self._is_windows()
                else ".\\.venv\\Scripts\\activate"
            ),
            (
                "python -m pip install -r requirements.txt"
                if "requirements.txt" in manifest_paths
                else "python -m pip install -e ."
            ),
            "python -m pytest",
        ]
        return Signal(
            name="build.python",
            value="python",
            source="build",
            metadata={
                "files": sorted(python_files),
                "commands": commands,
            },
        )

    def _node_signal(self, manifest_paths: set[str]) -> Optional[Signal]:
        if "package.json" not in manifest_paths:
            return None

        manager = detect_node_package_manager(manifest_paths)

        if manager == "pnpm":
            commands = ["pnpm install", "pnpm test", "pnpm run build"]
        elif manager == "yarn":
            commands = ["yarn install", "yarn test", "yarn build"]
        else:
            commands = ["npm install", "npm test", "npm run build"]

        return Signal(
            name="build.node",
            value=manager,
            source="build",
            metadata={"commands": commands},
        )

    def _java_signal(self, root: Path, manifest_paths: set[str]) -> Optional[Signal]:
        if not {"pom.xml", "build.gradle", "build.gradle.kts"}.intersection(
            manifest_paths
        ):
            return None

        mvnw = "mvnw.cmd" if self._is_windows() else "./mvnw"
        gradlew = "gradlew.bat" if self._is_windows() else "./gradlew"

        commands: List[str] = []
        tool = None

        if "pom.xml" in manifest_paths:
            tool = "maven"
            if (root / "mvnw").exists() or (root / "mvnw.cmd").exists():
                commands.extend([f"{mvnw} clean package", f"{mvnw} test"])
            else:
                commands.extend(["mvn clean package", "mvn test"])

        gradle_files = {"build.gradle", "build.gradle.kts"}.intersection(manifest_paths)
        if gradle_files:
            tool = "gradle"
            if (root / "gradlew").exists() or (root / "gradlew.bat").exists():
                commands.extend([f"{gradlew} build", f"{gradlew} test"])
            else:
                commands.extend(["gradle build", "gradle test"])

        if not commands:
            return None

        return Signal(
            name="build.java",
            value=tool or "java",
            source="build",
            metadata={"commands": commands},
        )

    @staticmethod
    def _is_windows() -> bool:
        return os.name == "nt"
