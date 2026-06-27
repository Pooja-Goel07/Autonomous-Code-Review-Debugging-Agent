"""Analysis engine — orchestrates all static analysis steps.

Coordinates AST parsing, call graph building, linting, and test execution
into a single AnalysisContext object.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.services.analysis.ast_parser import parse_python_file
from app.services.analysis.call_graph import build_call_graph
from app.services.analysis.lint_runner import run_lint
from app.services.analysis.models import (
    AnalysisContext,
    ASTSummary,
    PRIngestionResult,
)
from app.services.analysis.test_runner import run_tests

logger = logging.getLogger(__name__)


async def run_static_analysis(
    ingestion_result: PRIngestionResult,
    work_dir: Path,
) -> AnalysisContext:
    """Run the full static analysis pipeline on a PR.

    The work_dir should be a full shallow clone of the repo at the PR head.
    Changed files for AST/call-graph analysis are taken from the ingestion result;
    lint and tests run against the full cloned repo in work_dir.

    Args:
        ingestion_result: Output from the ingestion service.
        work_dir: Path to the cloned repo (isolated temp directory).

    Returns:
        AnalysisContext combining all analysis results.
    """
    changed_files = ingestion_result.changed_files

    # Filter to Python files with content (skip deleted / non-Python)
    python_files = [
        cf for cf in changed_files
        if cf.filename.endswith(".py") and cf.content is not None
    ]

    logger.info(
        "Running static analysis: %d Python files (of %d total changed)",
        len(python_files),
        len(changed_files),
    )

    # 1. AST parsing
    ast_summaries: list[ASTSummary] = []
    for cf in python_files:
        summary = parse_python_file(cf.filename, cf.content)
        ast_summaries.append(summary)
        if summary.parse_error:
            logger.warning("AST parse error in %s: %s", cf.filename, summary.parse_error)

    # 2. Call graph (scoped to changed files + 1-hop)
    call_graph = build_call_graph(changed_files)

    # 3. Lint — run on changed Python files within the full clone
    python_filenames = [cf.filename for cf in python_files]
    lint_findings = await run_lint(work_dir, python_filenames)

    # 4. Test execution — run on the full cloned repo
    test_result = await run_tests(work_dir)

    context = AnalysisContext(
        ingestion=ingestion_result,
        ast_summaries=ast_summaries,
        call_graph=call_graph,
        lint_findings=lint_findings,
        test_result=test_result,
    )

    logger.info(
        "Analysis complete: %d AST summaries, %d nodes / %d edges in call graph, "
        "%d lint findings, tests: %s",
        len(ast_summaries),
        call_graph.node_count,
        call_graph.edge_count,
        len(lint_findings),
        f"{test_result.passed}p/{test_result.failed}f" if test_result else "N/A",
    )

    return context
