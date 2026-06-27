"""AST parser — extracts symbols from Python source files.

Uses Python's built-in ast module to extract function definitions,
class definitions, and imports from each changed Python file.
"""

from __future__ import annotations

import ast
import logging

from app.services.analysis.models import ASTSummary, ASTSymbol

logger = logging.getLogger(__name__)


def parse_python_file(filename: str, source: str) -> ASTSummary:
    """Parse a single Python source file and extract its symbols.

    Args:
        filename: The file path (used for error reporting).
        source: The full Python source code.

    Returns:
        ASTSummary with extracted symbols, or parse_error set on failure.
    """
    symbols: list[ASTSymbol] = []

    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        logger.warning("SyntaxError parsing %s: %s", filename, exc)
        return ASTSummary(
            filename=filename,
            symbols=[],
            parse_error=f"SyntaxError at line {exc.lineno}: {exc.msg}",
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            symbols.append(
                ASTSymbol(
                    name=node.name,
                    type="function",
                    line=node.lineno,
                    args=[arg.arg for arg in node.args.args],
                )
            )
        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append(
                ASTSymbol(
                    name=node.name,
                    type="async_function",
                    line=node.lineno,
                    args=[arg.arg for arg in node.args.args],
                )
            )
        elif isinstance(node, ast.ClassDef):
            symbols.append(
                ASTSymbol(
                    name=node.name,
                    type="class",
                    line=node.lineno,
                )
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                symbols.append(
                    ASTSymbol(
                        name=alias.name,
                        type="import",
                        line=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                symbols.append(
                    ASTSymbol(
                        name=f"{module}.{alias.name}" if module else alias.name,
                        type="import",
                        line=node.lineno,
                    )
                )

    return ASTSummary(filename=filename, symbols=symbols)
