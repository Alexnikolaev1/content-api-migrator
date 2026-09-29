"""Чистые проверки стены: размер файла, сложность, форма функций."""

from __future__ import annotations

import ast
from pathlib import Path

from radon.complexity import cc_visit  # type: ignore[import-untyped]

MAX_LINES = 300
MAX_COMPLEXITY = 10
MAX_FN_LINES = 25
MAX_ARGS = 4
SKIP_ARGS = frozenset({"self", "cls"})
EXCLUDE_DIRS = frozenset(
    {
        "venv",
        ".venv",
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".mutmut-cache",
        "htmlcov",
        "node_modules",
        ".tox",
    }
)


def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)


def iter_py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file() and not is_excluded(p))


def check_file_length(root: Path) -> list[str]:
    errors: list[str] = []
    for path in iter_py_files(root):
        count = len(path.read_text(encoding="utf-8").splitlines())
        if count > MAX_LINES:
            errors.append(f"{path}: {count} строк (лимит {MAX_LINES})")
    return errors


def check_complexity(root: Path) -> list[str]:
    errors: list[str] = []
    for path in iter_py_files(root):
        errors.extend(_complexity_errors(path, path.read_text(encoding="utf-8")))
    return errors


def check_function_shape(root: Path) -> list[str]:
    errors: list[str] = []
    for path in iter_py_files(root):
        errors.extend(_shape_errors(path))
    return errors


def _complexity_errors(path: Path, source: str) -> list[str]:
    # Given a module, When radon visits it, Then report funcs above 10.
    try:
        blocks = cc_visit(source)
    except SyntaxError as exc:
        return [f"{path}: синтаксическая ошибка: {exc}"]
    return [
        (
            f"{path}:{block.lineno} {block.name} "
            f"сложность {block.complexity} (лимит {MAX_COMPLEXITY})"
        )
        for block in blocks
        if block.complexity > MAX_COMPLEXITY
    ]


def _shape_errors(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return [f"{path}: синтаксическая ошибка: {exc}"]
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            errors.extend(_one_fn_errors(path, node))
    return errors


def _one_fn_errors(
    path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef
) -> list[str]:
    errors: list[str] = []
    args = [arg.arg for arg in node.args.args if arg.arg not in SKIP_ARGS]
    if len(args) > MAX_ARGS:
        errors.append(
            f"{path}:{node.lineno} {node.name} "
            f"аргументов {len(args)} (лимит {MAX_ARGS})"
        )
    end = node.end_lineno or node.lineno
    length = end - node.lineno + 1
    if length > MAX_FN_LINES:
        errors.append(
            f"{path}:{node.lineno} {node.name} {length} строк (лимит {MAX_FN_LINES})"
        )
    return errors
