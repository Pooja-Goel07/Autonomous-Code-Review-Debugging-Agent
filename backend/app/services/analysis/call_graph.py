"""Call graph builder — 1-hop dependency graph from changed files.

Uses ast.NodeVisitor to extract function/method call relationships,
then builds a networkx DiGraph scoped to changed files plus their
immediate (1-hop) callers and callees.
"""

from __future__ import annotations

import ast
import logging

import networkx as nx

from app.services.analysis.models import CallGraphResult, ChangedFile

logger = logging.getLogger(__name__)


class _DefinitionCollector(ast.NodeVisitor):
    """First pass: collect all function/method/class definitions in a file."""

    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self.definitions: list[str] = []
        self._class_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualified = f"{self.module_name}.{node.name}"
        self.definitions.append(qualified)
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_func(node)

    def _visit_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if self._class_stack:
            qualified = f"{self.module_name}.{self._class_stack[-1]}.{node.name}"
        else:
            qualified = f"{self.module_name}.{node.name}"
        self.definitions.append(qualified)
        self.generic_visit(node)


class _CallCollector(ast.NodeVisitor):
    """Second pass: extract call edges from function bodies."""

    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self.edges: list[tuple[str, str]] = []
        self._current_scope: str | None = None
        self._class_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_func_body(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_func_body(node)

    def _visit_func_body(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if self._class_stack:
            caller = f"{self.module_name}.{self._class_stack[-1]}.{node.name}"
        else:
            caller = f"{self.module_name}.{node.name}"

        old_scope = self._current_scope
        self._current_scope = caller
        self.generic_visit(node)
        self._current_scope = old_scope

    def visit_Call(self, node: ast.Call) -> None:
        if self._current_scope is None:
            self.generic_visit(node)
            return

        callee = self._resolve_call_name(node.func)
        if callee:
            self.edges.append((self._current_scope, callee))
        self.generic_visit(node)

    def _resolve_call_name(self, node: ast.expr) -> str | None:
        """Try to resolve a call target to a dotted name."""
        if isinstance(node, ast.Name):
            return f"{self.module_name}.{node.id}"
        if isinstance(node, ast.Attribute):
            # e.g. self.method() or module.func()
            value = self._resolve_call_name(node.value)
            if value:
                return f"{value}.{node.attr}"
            return node.attr
        return None


def _module_name_from_filename(filename: str) -> str:
    """Convert a filename to a module-like dotted name."""
    name = filename.replace("\\", "/")
    if name.endswith(".py"):
        name = name[:-3]
    return name.replace("/", ".")


def build_call_graph(changed_files: list[ChangedFile]) -> CallGraphResult:
    """Build a 1-hop call graph from the changed Python files.

    1. Parse each file and collect definitions + call edges.
    2. Build a networkx DiGraph.
    3. Scope to definitions in changed files + their immediate neighbors.

    Args:
        changed_files: List of changed files with content.

    Returns:
        CallGraphResult with nodes and edges.
    """
    graph = nx.DiGraph()
    defined_in_changed: set[str] = set()

    for cf in changed_files:
        if not cf.filename.endswith(".py") or cf.content is None:
            continue

        module = _module_name_from_filename(cf.filename)

        try:
            tree = ast.parse(cf.content, filename=cf.filename)
        except SyntaxError:
            logger.warning("Skipping %s due to SyntaxError", cf.filename)
            continue

        # Pass 1: collect definitions
        defn_collector = _DefinitionCollector(module)
        defn_collector.visit(tree)
        for defn in defn_collector.definitions:
            defined_in_changed.add(defn)
            graph.add_node(defn)

        # Pass 2: collect call edges
        call_collector = _CallCollector(module)
        call_collector.visit(tree)
        for caller, callee in call_collector.edges:
            graph.add_edge(caller, callee)

    # Scope to 1-hop: keep defined nodes + their immediate neighbors
    nodes_to_keep: set[str] = set(defined_in_changed)
    for node in defined_in_changed:
        if node in graph:
            nodes_to_keep.update(graph.predecessors(node))
            nodes_to_keep.update(graph.successors(node))

    # Build the subgraph
    subgraph = graph.subgraph(nodes_to_keep)

    return CallGraphResult(
        nodes=sorted(subgraph.nodes()),
        edges=sorted(subgraph.edges()),
    )
