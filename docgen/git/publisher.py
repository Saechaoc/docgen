"""Git publishing utilities."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable, Iterable, Sequence


class Publisher:
    """Handles branch management and PR creation for README updates."""

    def __init__(self, runner: Callable[..., str] | None = None) -> None:
        self._runner = runner or self._default_runner

    def commit(
        self,
        repo_path: str,
        files: Sequence[Path | str],
        *,
        message: str = "docs: bootstrap README via docgen init",
    ) -> bool:
        """Stage the provided files and create a commit if changes exist."""
        repo = Path(repo_path)
        if not (repo / ".git").exists():
            return False

        relative_files = [self._to_relative(repo, Path(file)) for file in files]
        for rel in relative_files:
            self._run(["git", "add", rel], cwd=repo)

        status = self._run(["git", "status", "--porcelain"], cwd=repo, capture_output=True)
        if not status.strip():
            return False

        env = os.environ.copy()
        env.setdefault("GIT_AUTHOR_NAME", "docgen")
        env.setdefault("GIT_AUTHOR_EMAIL", "docgen@example.com")
        env.setdefault("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"])
        env.setdefault("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"])

        self._run(["git", "commit", "-m", message], cwd=repo, env=env)
        return True

    def publish_pr(
        self,
        repo_path: str,
        files: Sequence[Path | str],
        *,
        branch_name: str,
        base_branch: str | None = None,
        title: str,
        body: str,
        push: bool = True,
        labels: Sequence[str] | None = None,
        update_existing: bool = False,
    ) -> bool:
        """Create a branch, commit the files, and open a PR via the GitHub CLI."""
        repo = Path(repo_path)
        if not (repo / ".git").exists():
            return False

        checkout_cmd = ["git", "checkout", "-B", branch_name]
        if base_branch:
            checkout_cmd.append(base_branch)
        try:
            self._run(checkout_cmd, cwd=repo)
        except Exception:
            return False

        committed = self.commit(
            repo_path,
            files,
            message="docs: update README via docgen",
        )
        if not committed:
            return False

        if push:
            try:
                self._run(["git", "push", "-u", "origin", branch_name], cwd=repo)
            except Exception:
                return False

        existing_pr = False
        if update_existing:
            try:
                self._run(
                    ["gh", "pr", "view", branch_name, "--json", "number"],
                    cwd=repo,
                    capture_output=True,
                )
                existing_pr = True
            except Exception:
                existing_pr = False

        try:
            if existing_pr:
                self._run(
                    ["gh", "pr", "edit", branch_name, "--title", title, "--body", body],
                    cwd=repo,
                )
            else:
                pr_args = [
                    "gh",
                    "pr",
                    "create",
                    "--title",
                    title,
                    "--body",
                    body,
                ]
                if base_branch:
                    pr_args.extend(["--base", base_branch])
                pr_args.extend(["--head", branch_name])
                self._run(pr_args, cwd=repo)
        except Exception:
            return False

        if labels:
            for label in labels:
                if not label:
                    continue
                try:
                    self._run(
                        ["gh", "pr", "edit", branch_name, "--add-label", label],
                        cwd=repo,
                    )
                except Exception:
                    return False

        return True

    # ------------------------------------------------------------------
    # Helpers

    @staticmethod
    def _to_relative(repo: Path, file_path: Path) -> str:
        try:
            return file_path.relative_to(repo).as_posix()
        except ValueError:
            return file_path.as_posix()

    def _run(
        self,
        args: Iterable[str],
        *,
        cwd: Path,
        env: dict[str, str] | None = None,
        capture_output: bool = False,
    ) -> str:
        return self._runner(args, cwd=cwd, env=env, capture_output=capture_output)

    @staticmethod
    def _default_runner(
        args: Iterable[str],
        *,
        cwd: Path,
        env: dict[str, str] | None = None,
        capture_output: bool = False,
    ) -> str:
        completed = subprocess.run(
            list(args),
            cwd=str(cwd),
            env=env,
            check=True,
            text=True,
            capture_output=capture_output,
        )
        if capture_output:
            return completed.stdout
        return ""
