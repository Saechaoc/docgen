from __future__ import annotations

from pathlib import Path

import pytest

from tests._fixtures.repo_builder import RepoBuilder


@pytest.fixture
def repo_builder(tmp_path: Path) -> RepoBuilder:
    """Provide a reusable repo builder rooted at the pytest tmp_path."""
    return RepoBuilder(tmp_path)
