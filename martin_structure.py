"""Структурные запахи: глубокая вложенность и циклы импортов."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from martin_limits import iter_py_files

MAX_NESTING = 3
NEST_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Match,
)


@dataclass
class _CycleState:
    graph: dict[str, set[str]]
    path: list[str] = field(default_factory=list)
    in_path: set[str] = field(default_factory=set)
    done: set[str] = field(default_factory=set)
    cycles: list[list[str]] = field(default_factory=list)


def check_nesting(root: Path) -> list[str]:
    errors: list[str] = []
    for path in iter_py_files(root):
        errors.extend(_nesting_errors(path))
    return errors


def check_import_cycles(root: Path) -> list[str]:
    modules = _project_modules(root)
    graph = {
        name: _project_imports(path, name, modules) for name, path in modules.items()
    }
    return ["цикл импортов: " + " -> ".join(cycle) for cycle in _find_cycles(graph)]


def _nesting_errors(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return [f"{path}: синтаксическая ошибка: {exc}"]
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            depth = _max_nesting(node)
            if depth > MAX_NESTING:
                errors.append(
                    f"{path}:{node.lineno} {node.name} "
                    f"вложенность {depth} (лимит {MAX_NESTING})"
                )
    return errors


def _adds_nesting(node: ast.AST, parent: ast.AST) -> bool:
    elif_arm = isinstance(parent, ast.If) and parent.orelse == [node]
    if isinstance(node, ast.If) and elif_arm:
        return False
    return isinstance(node, NEST_NODES)


def _max_nesting(fn_node: ast.AST) -> int:
    deepest = 0
    stack: list[tuple[ast.AST, int, ast.AST]] = [
        (child, 0, fn_node) for child in ast.iter_child_nodes(fn_node)
    ]
    while stack:
        node, depth, parent = stack.pop()
        current = depth + (1 if _adds_nesting(node, parent) else 0)
        deepest = max(deepest, current)
        stack.extend((child, current, node) for child in ast.iter_child_nodes(node))
    return deepest


def _project_modules(root: Path) -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for path in iter_py_files(root):
        if "tests" in path.parts:
            continue
        rel = path.relative_to(root).with_suffix("")
        modules[".".join(rel.parts)] = path
    return modules


def _project_imports(path: Path, module: str, modules: dict[str, Path]) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    names = set(modules)
    hits = {_match_project(item, names) for item in _imported_modules(tree, module)}
    return {item for item in hits if item and item != module}


def _imported_modules(tree: ast.AST, module: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.extend(_from_modules(module, node))
    return found


def _from_modules(module: str, node: ast.ImportFrom) -> list[str]:
    if node.level == 0:
        return [node.module] if node.module else []
    parts = module.split(".")[: -node.level]
    if node.module:
        parts.append(node.module)
        return [".".join(parts)]
    return [".".join([*parts, alias.name]) for alias in node.names]


def _match_project(imported: str, names: set[str]) -> str:
    if imported in names:
        return imported
    return ""


def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    state = _CycleState(graph)
    for start in sorted(graph):
        _visit(start, state)
    return state.cycles


def _visit(node: str, state: _CycleState) -> None:
    if node in state.done:
        return
    if node in state.in_path:
        start = state.path.index(node)
        state.cycles.append([*state.path[start:], node])
        return
    state.path.append(node)
    state.in_path.add(node)
    for nxt in sorted(state.graph.get(node, ())):
        _visit(nxt, state)
    state.path.pop()
    state.in_path.remove(node)
    state.done.add(node)
