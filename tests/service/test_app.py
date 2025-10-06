"""Tests for the FastAPI service mode."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pytest.skip("fastapi not installed", allow_module_level=True)

from docgen.orchestrator import UpdateOutcome
from docgen.service import create_app


class _StubOrchestrator:
    def __init__(self) -> None:
        self.init_calls: list[dict[str, object]] = []
        self.update_calls: list[dict[str, object]] = []

    def run_init(self, path: str, *, skip_validation: bool = False) -> Path:
        self.init_calls.append({"path": path, "skip_validation": skip_validation})
        target = Path(path).resolve() / "README.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("sample", encoding="utf-8")
        return target

    def run_update(
        self,
        path: str,
        diff_base: str,
        *,
        dry_run: bool = False,
        skip_validation: bool = False,
    ) -> UpdateOutcome | None:
        self.update_calls.append(
            {
                "path": path,
                "diff_base": diff_base,
                "dry_run": dry_run,
                "skip_validation": skip_validation,
            }
        )
        if dry_run:
            return UpdateOutcome(path=Path(path) / "README.md", diff="diff", dry_run=True)
        return None


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    orchestrator = _StubOrchestrator()
    app = create_app(lambda: orchestrator)
    app.state._orchestrator = orchestrator  # type: ignore[attr-defined]
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_init_endpoint(client: TestClient, tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    response = client.post("/init", json={"path": str(repo_path)})
    assert response.status_code == 200
    data = response.json()
    assert data["readme_path"].endswith("README.md")


def test_update_dry_run_endpoint(client: TestClient, tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    response = client.post(
        "/update",
        json={"path": str(repo_path), "dry_run": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["dry_run"] is True
    assert data["diff"] == "diff"
