"""CLI parser behaviour tests."""

from __future__ import annotations

from docgen.cli import _build_parser


def test_cli_accepts_verbose_before_command() -> None:
    parser = _build_parser()
    args = parser.parse_args(["--verbose", "update"])
    assert args.verbose is True
    assert args.command == "update"


def test_cli_accepts_verbose_after_command() -> None:
    parser = _build_parser()
    args = parser.parse_args(["update", "--verbose"])
    assert args.verbose is True
    assert args.command == "update"


def test_cli_accepts_dry_run_flag() -> None:
    parser = _build_parser()
    args = parser.parse_args(["update", "--dry-run"])
    assert args.command == "update"
    assert args.dry_run is True


def test_cli_accepts_skip_validation_flag() -> None:
    parser = _build_parser()
    args = parser.parse_args(["init", "--skip-validation"])
    assert args.command == "init"
    assert args.skip_validation is True
