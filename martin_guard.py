"""Стена Мартина: lint, типы, тесты и лимиты чистого кода."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from martin_limits import check_complexity, check_file_length, check_function_shape
from martin_structure import check_import_cycles, check_nesting

COVERAGE_MIN = 90


def _print_errors(errors: list[str]) -> int:
    if not errors:
        return 0
    for item in errors:
        print(item, file=sys.stderr)
    return 1


def cmd_length(root: Path) -> int:
    return _print_errors(check_file_length(root))


def cmd_complexity(root: Path) -> int:
    return _print_errors(check_complexity(root))


def cmd_shape(root: Path) -> int:
    return _print_errors(check_function_shape(root))


def cmd_structure(root: Path) -> int:
    return _print_errors(check_nesting(root) + check_import_cycles(root))


def _wall_errors(root: Path) -> list[str]:
    return (
        check_file_length(root)
        + check_complexity(root)
        + check_function_shape(root)
        + check_nesting(root)
        + check_import_cycles(root)
    )


def _tool_steps() -> list[list[str]]:
    return [
        [sys.executable, "-m", "black", "."],
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "mypy", "."],
        [
            sys.executable,
            "-m",
            "pytest",
            "--cov=content_api_migrator",
            f"--cov-fail-under={COVERAGE_MIN}",
        ],
    ]


def cmd_all(root: Path) -> int:
    for cmd in _tool_steps():
        print("+", " ".join(cmd))
        if subprocess.call(cmd, cwd=root) != 0:
            return 1
    errors = _wall_errors(root)
    if errors:
        print("Стена Мартина: найдены нарушения")
    return _print_errors(errors)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Стена Роберта Мартина")
    parser.add_argument(
        "command", choices=("length", "complexity", "shape", "structure", "all")
    )
    parser.add_argument("--root", type=Path, default=Path())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    if args.command == "length":
        return cmd_length(root)
    if args.command == "complexity":
        return cmd_complexity(root)
    if args.command == "shape":
        return cmd_shape(root)
    if args.command == "structure":
        return cmd_structure(root)
    return cmd_all(root)


if __name__ == "__main__":
    raise SystemExit(main())
