"""CLI entrypoints for docgen commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .orchestrator import Orchestrator
from .logging import configure_logging


def _add_verbose_option(
    parser: argparse.ArgumentParser, *, suppress_default: bool = False
) -> None:
    kwargs: dict[str, object] = {
        "action": "store_true",
        "help": "Increase log verbosity for troubleshooting.",
    }
    if suppress_default:
        kwargs["default"] = argparse.SUPPRESS
    else:
        kwargs["default"] = False
    parser.add_argument(
        "-v",
        "--verbose",
        **kwargs,
    )


def _add_skip_validation_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip README validation guards for this run (not recommended).",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docgen",
        description="Generate and maintain README files using repository analysis.",
    )
    _add_verbose_option(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a README for a repository that lacks one.",
    )
    _add_verbose_option(init_parser, suppress_default=True)
    _add_skip_validation_option(init_parser)
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
    _add_verbose_option(update_parser, suppress_default=True)
    _add_skip_validation_option(update_parser)
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
    update_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview README changes without writing or publishing.",
    )
    regenerate_parser = subparsers.add_parser(
        "regenerate",
        help="Force regeneration of README sections.",
    )
    _add_verbose_option(regenerate_parser, suppress_default=True)
    _add_skip_validation_option(regenerate_parser)

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for docgen commands."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    configure_logging(verbose=bool(args.verbose))

    orchestrator = Orchestrator()

    if args.command == "init":
        try:
            readme_path = orchestrator.run_init(
                args.path,
                skip_validation=bool(getattr(args, "skip_validation", False)),
            )
        except FileExistsError as exc:
            parser.exit(1, f"{exc}\n")
        except Exception as exc:  # pragma: no cover - defensive guard
            parser.exit(1, f"docgen init failed: {exc}\nRun with --verbose for more details.\n")
        rel_path = _relativize(readme_path)
        print(f"README created at {rel_path}")
    elif args.command == "update":
        try:
            result = orchestrator.run_update(
                args.path,
                args.diff_base,
                dry_run=bool(getattr(args, "dry_run", False)),
                skip_validation=bool(getattr(args, "skip_validation", False)),
            )
        except FileNotFoundError as exc:
            parser.exit(1, f"{exc}\n")
        except RuntimeError as exc:
            parser.exit(1, f"docgen update failed: {exc}\nRun with --verbose for more details.\n")
        except Exception as exc:  # pragma: no cover - defensive guard
            parser.exit(1, f"docgen update failed: {exc}\nRun with --verbose for more details.\n")
        dry_run = bool(getattr(args, "dry_run", False))
        if result is None:
            message = "README already up to date"
            if dry_run:
                message += " (dry-run)"
            print(message)
        else:
            if dry_run:
                print("README changes (dry-run):")
                diff = result.diff or "(no diff)"
                print(diff)
            else:
                rel_path = _relativize(result.path)
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
