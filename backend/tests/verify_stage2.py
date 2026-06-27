"""Stage 2 verification script — tests the analysis pipeline with a mock fixture.

Creates a temporary directory with:
  - sample.py: Python file with an intentional unused variable (ruff F841)
    and a simple call chain for the call graph
  - test_sample.py: pytest tests with 1 passing and 1 intentionally failing test

Runs each analysis component and prints results.
Does NOT require GitHub, a database, or any external services.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

# Ensure the backend package is importable
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.services.analysis.engine import run_static_analysis  # noqa: E402
from app.services.analysis.models import ChangedFile, PRIngestionResult  # noqa: E402


# ---------------------------------------------------------------------------
# Mock fixture content
# ---------------------------------------------------------------------------

SAMPLE_PY = '''\
"""Sample module with an intentional bug for verification."""


def add(a, b):
    """Add two numbers."""
    return a + b


def multiply(a, b):
    """Multiply two numbers."""
    return a * b


def compute(x, y):
    """Compute a result using add and multiply."""
    unused_var = 42  # intentional: ruff F841 (unused variable)
    total = add(x, y)
    product = multiply(x, y)
    return total + product


class Calculator:
    """Simple calculator class."""

    def run(self, a, b):
        return compute(a, b)
'''

TEST_SAMPLE_PY = '''\
"""Tests for the sample module."""
from sample import add, multiply


def test_add_positive():
    """This test should pass."""
    assert add(2, 3) == 5


def test_multiply_wrong():
    """This test intentionally fails."""
    assert multiply(2, 3) == 7  # wrong: 2*3=6, not 7
'''


def _create_fixture(work_dir: Path) -> list[ChangedFile]:
    """Write the mock fixture files and return ChangedFile objects."""
    # Write sample.py
    sample_path = work_dir / "sample.py"
    sample_path.write_text(SAMPLE_PY, encoding="utf-8")

    # Write test_sample.py
    test_path = work_dir / "test_sample.py"
    test_path.write_text(TEST_SAMPLE_PY, encoding="utf-8")

    return [
        ChangedFile(
            filename="sample.py",
            status="added",
            patch="(mock patch for sample.py)",
            content=SAMPLE_PY,
        ),
        ChangedFile(
            filename="test_sample.py",
            status="added",
            patch="(mock patch for test_sample.py)",
            content=TEST_SAMPLE_PY,
        ),
    ]


async def main() -> None:
    """Run the full Stage 2 verification."""
    print("=" * 70)
    print("STAGE 2 VERIFICATION — Static Analysis Pipeline")
    print("=" * 70)

    work_dir = Path(tempfile.mkdtemp(prefix="verify_stage2_"))

    try:
        # Create mock fixture
        changed_files = _create_fixture(work_dir)
        print(f"\nFixture created in: {work_dir}")
        print(f"Files: {[cf.filename for cf in changed_files]}")

        # Build a mock PRIngestionResult
        ingestion = PRIngestionResult(
            repo_full_name="test-org/test-repo",
            pr_number=1,
            pr_title="test: add sample module with intentional bug",
            base_branch="main",
            head_branch="feature/add-sample",
            head_sha="abc123",
            diff_text="\n".join(cf.patch for cf in changed_files),
            changed_files=changed_files,
        )

        # Run the full analysis pipeline
        context = await run_static_analysis(ingestion, work_dir)

        # --- Print results ---
        print("\n" + "-" * 70)
        print("1. AST SUMMARY")
        print("-" * 70)
        for summary in context.ast_summaries:
            print(f"\n  File: {summary.filename}")
            if summary.parse_error:
                print(f"    PARSE ERROR: {summary.parse_error}")
            for sym in summary.symbols:
                args_str = f"({', '.join(sym.args)})" if sym.args else ""
                print(f"    [{sym.type:>14}] {sym.name}{args_str}  (line {sym.line})")

        print("\n" + "-" * 70)
        print("2. CALL GRAPH")
        print("-" * 70)
        print(f"  Nodes: {context.call_graph.node_count}")
        print(f"  Edges: {context.call_graph.edge_count}")
        for node in context.call_graph.nodes:
            print(f"    node: {node}")
        for caller, callee in context.call_graph.edges:
            print(f"    edge: {caller} -> {callee}")

        print("\n" + "-" * 70)
        print("3. LINT FINDINGS")
        print("-" * 70)
        if context.lint_findings:
            for lf in context.lint_findings:
                print(f"  [{lf.rule}] {lf.file}:{lf.line}:{lf.column} — {lf.message}")
        else:
            print("  (no lint findings)")

        print("\n" + "-" * 70)
        print("4. TEST RESULTS")
        print("-" * 70)
        if context.test_result:
            tr = context.test_result
            print(f"  Passed:  {tr.passed}")
            print(f"  Failed:  {tr.failed}")
            print(f"  Errors:  {tr.errors}")
            print(f"  Total:   {tr.total}")
            print(f"  Timeout: {tr.timed_out}")
            if tr.tracebacks:
                print("\n  Tracebacks:")
                for tb in tr.tracebacks:
                    for line in tb.split("\n"):
                        print(f"    {line}")
        else:
            print("  (no test result)")

        # --- Summary ---
        print("\n" + "=" * 70)
        print("VERIFICATION SUMMARY")
        print("=" * 70)
        ast_ok = len(context.ast_summaries) == 2 and all(
            s.parse_error is None for s in context.ast_summaries
        )
        graph_ok = context.call_graph.node_count > 0 and context.call_graph.edge_count > 0
        lint_ok = any(lf.rule == "F841" for lf in context.lint_findings)
        test_ok = (
            context.test_result is not None
            and context.test_result.passed >= 1
            and context.test_result.failed >= 1
        )

        results = [
            ("AST parsing (2 files, no errors)", ast_ok),
            ("Call graph (nodes > 0, edges > 0)", graph_ok),
            ("Lint (F841 unused variable found)", lint_ok),
            ("Tests (1 pass, 1 fail)", test_ok),
        ]

        all_passed = True
        for label, ok in results:
            status = "[PASS]" if ok else "[FAIL]"
            print(f"  {status}  {label}")
            if not ok:
                all_passed = False

        print()
        if all_passed:
            print("  >> ALL CHECKS PASSED -- Stage 2 verified!")
        else:
            print("  >> SOME CHECKS FAILED -- see details above.")

        sys.exit(0 if all_passed else 1)

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
