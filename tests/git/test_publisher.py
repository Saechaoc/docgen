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
    result = publisher.commit(str(repo), [readme], message="docs: add readme")

    assert calls[0][0] == ["git", "add", "README.md"]
    assert calls[0][1] == repo
    assert calls[1][0] == ["git", "status", "--porcelain"]
    assert calls[2][0][:3] == ["git", "commit", "-m"]
    assert "docs: add readme" in calls[2][0]
    assert result is True


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
    result = publisher.commit(str(repo), [readme])

    assert not calls
    assert result is False


def test_publisher_publish_pr_runs_git_commands(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    readme = repo / "README.md"
    readme.write_text("content", encoding="utf-8")

    calls = []

    def runner(args, cwd, env=None, capture_output=False):  # type: ignore[no-untyped-def]
        calls.append((list(args), Path(cwd), env, capture_output))
        if args == ["git", "status", "--porcelain"]:
            return " M README.md\n"
        return ""

    publisher = Publisher(runner=runner)
    result = publisher.publish_pr(
        str(repo),
        [readme],
        branch_name="docgen/test",
        base_branch="origin/main",
        title="docs: update",
        body="summary",
    )

    assert result is True
    assert calls[0][0] == ["git", "checkout", "-B", "docgen/test", "origin/main"]
    assert calls[1][0] == ["git", "add", "README.md"]
    assert calls[2][0] == ["git", "status", "--porcelain"]
    assert calls[3][0][:3] == ["git", "commit", "-m"]
    assert calls[4][0][:3] == ["git", "push", "-u"]
    assert calls[5][0][:3] == ["gh", "pr", "create"]


def test_publisher_publish_pr_applies_labels(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    readme = repo / "README.md"
    readme.write_text("content", encoding="utf-8")

    calls = []

    def runner(args, cwd, env=None, capture_output=False):  # type: ignore[no-untyped-def]
        calls.append((list(args), Path(cwd), capture_output))
        if args == ["git", "status", "--porcelain"]:
            return " M README.md\n"
        return ""

    publisher = Publisher(runner=runner)
    result = publisher.publish_pr(
        str(repo),
        [readme],
        branch_name="docgen/test",
        base_branch=None,
        title="docs: update",
        body="summary",
        labels=["docs:auto"],
    )

    assert result is True
    label_call = [call for call in calls if call[0][:4] == ["gh", "pr", "edit", "docgen/test"]][-1]
    assert "--add-label" in label_call[0]


def test_publisher_publish_pr_updates_existing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    readme = repo / "README.md"
    readme.write_text("content", encoding="utf-8")

    calls = []

    def runner(args, cwd, env=None, capture_output=False):  # type: ignore[no-untyped-def]
        calls.append((list(args), Path(cwd), capture_output))
        if args == ["git", "status", "--porcelain"]:
            return " M README.md\n"
        if args[:4] == ["gh", "pr", "view", "docgen/test"]:
            return "{\"number\":1}"
        return ""

    publisher = Publisher(runner=runner)
    result = publisher.publish_pr(
        str(repo),
        [readme],
        branch_name="docgen/test",
        base_branch="main",
        title="docs: update",
        body="summary",
        update_existing=True,
    )

    assert result is True
    # ensure edit was invoked instead of create
    edit_calls = [call for call in calls if call[0][:3] == ["gh", "pr", "edit"]]
    assert edit_calls
