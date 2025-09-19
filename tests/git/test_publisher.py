"""Tests for the git publisher."""

from __future__ import annotations

from pathlib import Path

from docgen.git.publisher import Publisher


def test_publisher_adds_and_commits_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    readme = repo / "README.md"
    readme.write_text("content", encoding="utf-8")

    calls = []

    def runner(args, cwd, env=None, capture_output=False):
        calls.append((list(args), Path(cwd), capture_output, env))
        if capture_output and list(args) == ["git", "status", "--porcelain"]:
            return " M README.md\n"
        return ""

    publisher = Publisher(runner=runner)
    publisher.commit(str(repo), [readme], message="docs: add readme")

    assert calls[0][0] == ["git", "add", "README.md"]
    assert calls[0][1] == repo
    assert calls[1][0] == ["git", "status", "--porcelain"]
    assert calls[2][0][:3] == ["git", "commit", "-m"]
    assert "docs: add readme" in calls[2][0]


def test_publisher_noop_without_git_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    readme = repo / "README.md"
    readme.write_text("content", encoding="utf-8")

    calls = []

    def runner(args, cwd, env=None, capture_output=False):
        calls.append(list(args))
        return ""

    publisher = Publisher(runner=runner)
    publisher.commit(str(repo), [readme])

    assert not calls
