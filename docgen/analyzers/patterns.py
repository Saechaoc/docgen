"""Analyzer for repository infrastructure and layout patterns."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence

from .base import Analyzer
from ..models import RepoManifest, Signal


class PatternAnalyzer(Analyzer):
    """Finds infrastructure and layout patterns within the repo."""

    def supports(self, manifest: RepoManifest) -> bool:
        return bool(manifest.files)

    def analyze(self, manifest: RepoManifest) -> Iterable[Signal]:
        root = Path(manifest.root)
        paths = [file.path for file in manifest.files]

        signals: List[Signal] = []

        docker_files = _collect(paths, {"Dockerfile", "docker-compose.yml", "docker-compose.yaml"})
        if docker_files:
            quickstart: List[str] = []
            if "Dockerfile" in docker_files:
                quickstart.append("docker build -t <image> .")
            if any(name in docker_files for name in {"docker-compose.yml", "docker-compose.yaml"}):
                quickstart.append("docker compose up")
            signals.append(
                Signal(
                    name="pattern.containerization",
                    value="docker",
                    source="patterns",
                    metadata={
                        "files": sorted(docker_files),
                        "summary": "Docker artifacts detected",
                        "quickstart": quickstart,
                    },
                )
            )

        if _has_prefix(paths, ("k8s/", "helm/", "charts/")):
            signals.append(
                Signal(
                    name="pattern.kubernetes",
                    value="kubernetes",
                    source="patterns",
                    metadata={
                        "summary": "Kubernetes manifests detected under deployment directories",
                    },
                )
            )

        ci_files = _collect(
            paths,
            {
                ".github/workflows/",
                ".gitlab-ci.yml",
                ".gitlab-ci.yaml",
                "azure-pipelines.yml",
                "bitbucket-pipelines.yml",
            },
        )
        if ci_files:
            signals.append(
                Signal(
                    name="pattern.ci",
                    value="ci",
                    source="patterns",
                    metadata={
                        "files": sorted(ci_files),
                        "summary": "Continuous integration configuration present",
                    },
                )
            )

        if _looks_like_monorepo(paths, root):
            signals.append(
                Signal(
                    name="pattern.monorepo",
                    value="monorepo",
                    source="patterns",
                    metadata={
                        "summary": "Multiple packages/apps detected (monorepo layout)",
                    },
                )
            )

        return signals


def _collect(paths: Sequence[str], targets: set[str]) -> set[str]:
    results: set[str] = set()
    for path in paths:
        norm = path.replace("\\", "/")
        for target in targets:
            if target.endswith("/"):
                if norm.startswith(target):
                    results.add(target.rstrip("/"))
            elif norm == target:
                results.add(target)
    return results


def _has_prefix(paths: Sequence[str], prefixes: Sequence[str]) -> bool:
    for path in paths:
        norm = path.replace("\\", "/")
        if any(norm.startswith(prefix) for prefix in prefixes):
            return True
    return False


def _looks_like_monorepo(paths: Sequence[str], root: Path) -> bool:
    workspace_markers = {
        "pnpm-workspace.yaml",
        "pnpm-workspace.yml",
        "lerna.json",
        "turbo.json",
        "nx.json",
    }
    if any(path in workspace_markers for path in paths):
        return True

    candidate_dirs = {"packages", "apps", "services", "modules"}
    has_multiple_packages = 0
    for candidate in candidate_dirs:
        if any(path.startswith(f"{candidate}/") for path in paths):
            has_multiple_packages += 1
    if has_multiple_packages >= 2:
        return True

    # look for multiple package.json files beyond the root
    package_json_count = sum(1 for path in paths if path.endswith("package.json"))
    if package_json_count > 1:
        return True

    # detect multiple python package roots
    pyproject_count = sum(1 for path in paths if path.endswith("pyproject.toml"))
    if pyproject_count > 1:
        return True

    return False
