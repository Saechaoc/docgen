"""Shared helper utilities for analyzer implementations."""

from __future__ import annotations

import json
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Set

# Python dependency helpers


def load_python_dependencies(root: Path) -> List[str]:
    """Collect Python dependencies from requirements.txt and pyproject.toml."""
    deps: Set[str] = set()

    requirements = root / "requirements.txt"
    if requirements.exists():
        deps.update(_parse_requirements(requirements))

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        deps.update(_parse_pyproject(pyproject))

    return sorted(deps)


def _parse_requirements(path: Path) -> List[str]:
    packages: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "-r")):
            continue
        name = re.split(r"[<>=!~]", stripped, 1)[0].strip()
        if name:
            packages.append(name)
    return packages


def _parse_pyproject(path: Path) -> List[str]:
    packages: Set[str] = set()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    dependencies = []
    project = data.get("project")
    if isinstance(project, dict):
        dependencies.extend(project.get("dependencies", []) or [])
        optional = project.get("optional-dependencies", {}) or {}
        for values in optional.values():
            dependencies.extend(values or [])

    poetry = data.get("tool", {}).get("poetry", {}) if isinstance(data.get("tool"), dict) else {}
    if isinstance(poetry, dict):
        poetry_deps = poetry.get("dependencies", {}) or {}
        dependencies.extend(poetry_deps.keys())

    for dep in dependencies:
        if isinstance(dep, str):
            name = re.split(r"[<>=!~]", dep, 1)[0].strip()
            if name and name.lower() != "python":
                packages.add(name)
        elif isinstance(dep, dict):
            packages.update(dep.keys())
    return sorted(packages)


# Node.js dependency helpers


def load_node_dependencies(root: Path) -> Dict[str, List[str]]:
    """Return Node.js dependencies separated into runtime/dev lists."""
    package_json = root / "package.json"
    if not package_json.exists():
        return {"dependencies": [], "devDependencies": []}

    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"dependencies": [], "devDependencies": []}

    def _extract(key: str) -> List[str]:
        deps = data.get(key, {})
        if isinstance(deps, dict):
            return sorted(deps.keys())
        return []

    return {
        "dependencies": _extract("dependencies"),
        "devDependencies": _extract("devDependencies"),
    }


def load_package_json(root: Path) -> Dict[str, object]:
    """Return the parsed package.json contents or an empty dict."""
    package_json = root / "package.json"
    if not package_json.exists():
        return {}
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def detect_node_package_manager(manifest_paths: Set[str]) -> str:
    """Infer the preferred Node package manager based on lockfiles."""
    if "pnpm-lock.yaml" in manifest_paths:
        return "pnpm"
    if "yarn.lock" in manifest_paths:
        return "yarn"
    if "package-lock.json" in manifest_paths:
        return "npm"
    return "npm"


def build_node_script_command(script: str, manager: str) -> str:
    manager = manager.lower()
    if manager == "pnpm":
        return f"pnpm {script}"
    if manager == "yarn":
        return f"yarn {script}"
    # npm run <script>, except start which can be `npm start`
    if script == "start":
        return "npm start"
    return f"npm run {script}"


# Java dependency helpers


def load_java_dependencies(root: Path) -> List[str]:
    """Collect Java dependencies from pom.xml and build.gradle files."""
    deps: Set[str] = set()
    pom = root / "pom.xml"
    if pom.exists():
        deps.update(_parse_pom_dependencies(pom))

    build_gradle = root / "build.gradle"
    if build_gradle.exists():
        deps.update(_parse_gradle_dependencies(build_gradle.read_text(encoding="utf-8")))

    build_gradle_kts = root / "build.gradle.kts"
    if build_gradle_kts.exists():
        deps.update(_parse_gradle_dependencies(build_gradle_kts.read_text(encoding="utf-8")))

    return sorted(deps)


def _parse_pom_dependencies(path: Path) -> Set[str]:
    deps: Set[str] = set()
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8"))
    except ET.ParseError:
        return deps

    namespace = _detect_xml_namespace(root)
    tag = f"{{{namespace}}}dependency" if namespace else "dependency"
    group_tag = f"{{{namespace}}}groupId" if namespace else "groupId"
    artifact_tag = f"{{{namespace}}}artifactId" if namespace else "artifactId"

    for dep in root.findall(f".//{tag}"):
        group = dep.findtext(group_tag, default="")
        artifact = dep.findtext(artifact_tag, default="")
        if group and artifact:
            deps.add(f"{group}:{artifact}")
    return deps


def _detect_xml_namespace(element: ET.Element) -> str | None:
    match = re.match(r"\{(.+)}", element.tag)
    return match.group(1) if match else None


def _parse_gradle_dependencies(content: str) -> Set[str]:
    deps: Set[str] = set()
    pattern = re.compile(r"['\"]([\w\-.]+:[\w\-.]+)(?::[\w\-.]+)?['\"]")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        if any(token in line for token in ("implementation", "api", "compile", "runtimeOnly")):
            match = pattern.search(line)
            if match:
                deps.add(match.group(1))
    return deps


# Framework heuristics


def detect_python_frameworks(dependencies: Iterable[str]) -> List[str]:
    frameworks: List[str] = []
    mapping = {
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
    }
    lower_deps = {dep.lower() for dep in dependencies}
    for key, label in mapping.items():
        if key in lower_deps:
            frameworks.append(label)
    return frameworks


def detect_node_frameworks(node_dependencies: Dict[str, List[str]]) -> List[str]:
    frameworks: List[str] = []
    mapping = {
        "express": "Express",
        "next": "Next.js",
        "react": "React",
    }
    lower = {dep.lower() for deps in node_dependencies.values() for dep in deps}
    for key, label in mapping.items():
        if key in lower:
            frameworks.append(label)
    return frameworks


def detect_java_frameworks(java_dependencies: Iterable[str]) -> List[str]:
    frameworks: List[str] = []
    for dep in java_dependencies:
        lower = dep.lower()
        if "spring-boot" in lower or "springframework" in lower:
            frameworks.append("Spring Boot")
            break
    return frameworks
