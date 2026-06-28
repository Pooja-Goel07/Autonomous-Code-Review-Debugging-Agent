"""Stage 3 verification — tests the LangGraph agent loop with mock LLM.

Two scenarios using the same sample.py / test_sample.py fixture from Stage 2:

Scenario 1 (Happy Path):
  Mock LLM returns a fix that actually corrects sample.py
  Expected: analyze -> propose -> verify (pass) -> decide (accepted)

Scenario 2 (Retry then Escalate):
  Mock LLM returns a "bad fix" that doesn't fix the failing test
  Expected: analyze -> propose -> verify (fail) -> decide (retry) x2
            -> decide (needs_human_review)

Does NOT require real LLM API keys, GitHub, or a database.
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

from app.agent.graph import run_agent  # noqa: E402
from app.agent.llm_client import MockLLMClient  # noqa: E402
from app.services.analysis.engine import run_static_analysis  # noqa: E402
from app.services.analysis.models import (  # noqa: E402
    ChangedFile,
    PRIngestionResult,
)

# ---------------------------------------------------------------------------
# Fixture content (same as Stage 2)
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

# The "good fix" that corrects test_sample.py so all tests pass
GOOD_FIX = '''\
===FILE: test_sample.py===
"""Tests for the sample module."""
from sample import add, multiply


def test_add_positive():
    """This test should pass."""
    assert add(2, 3) == 5


def test_multiply_correct():
    """This test now uses the correct expected value."""
    assert multiply(2, 3) == 6
===END_FILE===

REASONING: The test_multiply_wrong test expected multiply(2, 3) to return 7,
but 2*3=6. Fixed the expected value to 6 and renamed the test to
test_multiply_correct.'''

# The "bad fix" that doesn't actually fix anything
BAD_FIX = '''\
===FILE: sample.py===
"""Sample module with an intentional bug for verification."""


def add(a, b):
    """Add two numbers."""
    return a + b


def multiply(a, b):
    """Multiply two numbers."""
    return a * b


def compute(x, y):
    """Compute a result using add and multiply."""
    total = add(x, y)
    product = multiply(x, y)
    return total + product


class Calculator:
    """Simple calculator class."""

    def run(self, a, b):
        return compute(a, b)
===END_FILE===

REASONING: Removed the unused variable. However, this does not fix the
failing test (test_multiply_wrong still expects 7 instead of 6).'''


def _create_fixture(work_dir: Path) -> tuple[list[ChangedFile], PRIngestionResult]:
    """Write fixture files and return ChangedFile objects + PRIngestionResult."""
    (work_dir / "sample.py").write_text(SAMPLE_PY, encoding="utf-8")
    (work_dir / "test_sample.py").write_text(TEST_SAMPLE_PY, encoding="utf-8")

    changed_files = [
        ChangedFile(
            filename="sample.py",
            status="added",
            patch="(mock patch)",
            content=SAMPLE_PY,
        ),
        ChangedFile(
            filename="test_sample.py",
            status="added",
            patch="(mock patch)",
            content=TEST_SAMPLE_PY,
        ),
    ]

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

    return changed_files, ingestion


def _print_separator(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print("=" * 70)


def _print_result(final_state: dict) -> None:
    """Print the agent's final state in a readable format."""
    print(f"\n  Node trace:     {' -> '.join(final_state['node_trace'])}")
    print(f"  Decision:       {final_state['decision']}")
    print(f"  Confidence:     {final_state['confidence_score']:.2f}")
    print(f"  Retry count:    {final_state['retry_count']}")
    print(f"  Verification:   {'PASSED' if final_state['verification_passed'] else 'FAILED'}")
    print(f"  Diagnosis:      {final_state['diagnosis'][:100]}...")
    print(f"  Reasoning:      {final_state['reasoning_text'][:100]}...")


async def scenario_1_happy_path() -> bool:
    """Scenario 1: Mock LLM returns a good fix, tests pass on first try."""
    _print_separator("SCENARIO 1: Happy Path (fix works on first try)")

    work_dir = Path(tempfile.mkdtemp(prefix="s3_happy_"))
    try:
        _, ingestion = _create_fixture(work_dir)

        # Run static analysis first (to get AnalysisContext)
        context = await run_static_analysis(ingestion, work_dir)

        # Create mock LLM that returns the good fix
        mock_llm = MockLLMClient(fix_content=GOOD_FIX)

        # Run the agent graph
        final_state = await run_agent(
            analysis_context=context,
            work_dir=work_dir,
            llm_client=mock_llm,
            max_retries=3,
        )

        _print_result(final_state)

        # Validate expectations
        ok = True
        checks = [
            ("Decision is 'accepted'", final_state["decision"] == "accepted"),
            ("Confidence is 0.85", abs(final_state["confidence_score"] - 0.85) < 0.01),
            ("No retries", final_state["retry_count"] == 0),
            ("Verification passed", final_state["verification_passed"]),
            (
                "Trace is analyze->propose->verify->decide",
                final_state["node_trace"] == ["analyze", "propose", "verify", "decide"],
            ),
        ]

        print("\n  Checks:")
        for label, passed in checks:
            status = "[PASS]" if passed else "[FAIL]"
            print(f"    {status}  {label}")
            if not passed:
                ok = False

        return ok

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


async def scenario_2_retry_then_escalate() -> bool:
    """Scenario 2: Mock LLM returns bad fix, retries exhaust, escalates."""
    _print_separator("SCENARIO 2: Retry then Escalate (fix never works)")

    work_dir = Path(tempfile.mkdtemp(prefix="s3_retry_"))
    try:
        _, ingestion = _create_fixture(work_dir)

        # Run static analysis
        context = await run_static_analysis(ingestion, work_dir)

        # Create mock LLM that returns the bad fix (never fixes the test)
        mock_llm = MockLLMClient(fix_content=BAD_FIX)

        # Run agent with max_retries=2
        final_state = await run_agent(
            analysis_context=context,
            work_dir=work_dir,
            llm_client=mock_llm,
            max_retries=2,
        )

        _print_result(final_state)

        # Validate expectations
        ok = True
        expected_trace = [
            "analyze", "propose", "verify", "decide",  # attempt 1
            "analyze", "propose", "verify", "decide",  # attempt 2 (retry 1)
            "analyze", "propose", "verify", "decide",  # attempt 3 (retry 2 -> escalate)
        ]

        checks = [
            ("Decision is 'needs_human_review'", final_state["decision"] == "needs_human_review"),
            ("Confidence is 0.20", abs(final_state["confidence_score"] - 0.20) < 0.01),
            ("Retry count is 2", final_state["retry_count"] == 2),
            ("Verification failed", not final_state["verification_passed"]),
            (
                "Trace shows 3 full loops (12 entries)",
                final_state["node_trace"] == expected_trace,
            ),
        ]

        print("\n  Checks:")
        for label, passed in checks:
            status = "[PASS]" if passed else "[FAIL]"
            print(f"    {status}  {label}")
            if not passed:
                ok = False
                if "Trace" in label:
                    print(f"           Got:      {final_state['node_trace']}")
                    print(f"           Expected: {expected_trace}")

        return ok

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


async def main() -> None:
    """Run both verification scenarios."""
    print("=" * 70)
    print("STAGE 3 VERIFICATION -- LangGraph Agent Loop (Mock LLM)")
    print("=" * 70)

    s1_ok = await scenario_1_happy_path()
    s2_ok = await scenario_2_retry_then_escalate()

    _print_separator("VERIFICATION SUMMARY")

    results = [
        ("Scenario 1: Happy path (accepted on first try)", s1_ok),
        ("Scenario 2: Retry then escalate (needs_human_review)", s2_ok),
    ]

    all_passed = True
    for label, ok in results:
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status}  {label}")
        if not ok:
            all_passed = False

    print()
    if all_passed:
        print("  >> ALL CHECKS PASSED -- Stage 3 verified!")
    else:
        print("  >> SOME CHECKS FAILED -- see details above.")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
