"""CLI entrypoints for docgen commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .orchestrator import Orchestrator


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docgen",
        description="Generate and maintain README files using repository analysis.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init", help="Initialize a README for a repository that lacks one."
    )
    init_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to the repository root (defaults to current directory).",
    )

    update_parser = subparsers.add_parser(
        "update",
        help="Update README sections after repository changes.",
    )
    update_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to the repository root (defaults to current directory).",
    )
    update_parser.add_argument(
        "--diff-base",
        default="origin/main",
        help="Commit or ref to compare against when computing diffs.",
    )
    subparsers.add_parser(
        "regenerate", help="Force regeneration of README sections."
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for docgen commands."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    orchestrator = Orchestrator()

    if args.command == "init":
        try:
            readme_path = orchestrator.run_init(args.path)
        except FileExistsError as exc:
            parser.exit(1, f"{exc}\n")
        except Exception as exc:  # pragma: no cover - defensive guard
            parser.exit(1, f"docgen init failed: {exc}\n")
        rel_path = _relativize(readme_path)
        print(f"README created at {rel_path}")
    elif args.command == "update":
        try:
            result = orchestrator.run_update(args.path, args.diff_base)
        except FileNotFoundError as exc:
            parser.exit(1, f"{exc}\n")
        except RuntimeError as exc:
            parser.exit(1, f"docgen update failed: {exc}\n")
        if result is None:
            print("README already up to date")
        else:
            rel_path = _relativize(result)
            print(f"README updated at {rel_path}")
    elif args.command == "regenerate":
        parser.exit(
            1,
            "`docgen regenerate` is not implemented yet. Use `docgen init` followed by manual edits.\n",
        )
    else:  # pragma: no cover - argparse enforces choices
        parser.exit(1, "Unknown command\n")


def _relativize(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    main(sys.argv[1:])
