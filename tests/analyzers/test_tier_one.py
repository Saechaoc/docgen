"""Integration-style tests for analyzers."""

from __future__ import annotations

from pathlib import Path

from docgen.analyzers.build import BuildAnalyzer
from docgen.analyzers.dependencies import DependencyAnalyzer
from docgen.analyzers.language import LanguageAnalyzer
from docgen.repo_scanner import RepoScanner


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_repo(root: Path) -> None:
    _write(root / "src" / "app.py", "print('hi')\n")
    _write(root / "src" / "index.js", "console.log('hi');\n")
    _write(root / "src" / "Main.java", "public class Main { }\n")

    _write(
        root / "requirements.txt",
        "fastapi==0.111\npytest\n",
    )
    _write(
        root / "pyproject.toml",
        '[project]\ndependencies = ["django==4.2"]\n',
    )

    _write(
        root / "package.json",
        '{"name": "demo", "dependencies": {"express": "^4.18.2"}, "devDependencies": {"react": "18"}}\n',
    )
    _write(root / "pnpm-lock.yaml", "lockfileVersion: 6\n")

    _write(
        root / "pom.xml",
        """
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>demo</groupId>
  <artifactId>demo</artifactId>
  <version>1.0.0</version>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
  </dependencies>
</project>
""",
    )
    _write(root / "mvnw", "#!/bin/sh\n")


def test_language_analyzer_detects_frameworks(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))

    analyzer = LanguageAnalyzer()
    signals = list(analyzer.analyze(manifest))
    frameworks = {
        signal.metadata.get("language"): signal.metadata.get("frameworks")
        for signal in signals
        if signal.name.startswith("language.frameworks.")
    }

    assert frameworks.get("Python") == ["FastAPI", "Django"]
    assert frameworks.get("JavaScript") == ["Express", "React"]
    assert frameworks.get("Java") == ["Spring Boot"]


def test_dependency_analyzer_reports_tier_one_packages(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))
    analyzer = DependencyAnalyzer()
    signals = {signal.name: signal for signal in analyzer.analyze(manifest)}

    assert "dependencies.python" in signals
    assert "fastapi" in signals["dependencies.python"].metadata["packages"]
    assert "django" in signals["dependencies.python"].metadata["packages"]

    assert "dependencies.node" in signals
    node_meta = signals["dependencies.node"].metadata
    assert "express" in node_meta["dependencies"]
    assert "react" in node_meta["devDependencies"]

    assert "dependencies.java" in signals
    assert any(
        "spring-boot" in pkg
        for pkg in signals["dependencies.java"].metadata["packages"]
    )


def test_build_analyzer_emits_commands_for_each_ecosystem(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))
    analyzer = BuildAnalyzer()
    signals = {signal.name: signal for signal in analyzer.analyze(manifest)}

    assert "build.python" in signals
    assert any("pip" in cmd for cmd in signals["build.python"].metadata["commands"])

    assert "build.node" in signals
    assert signals["build.node"].value == "pnpm"
    assert "pnpm install" in signals["build.node"].metadata["commands"]

    assert "build.java" in signals
    java_cmds = signals["build.java"].metadata["commands"]
    assert any("mvn" in cmd for cmd in java_cmds)
