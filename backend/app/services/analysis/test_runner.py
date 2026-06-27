"""Test runner — executes pytest in an isolated subprocess.

Runs pytest in a temp directory checkout of the repo with resource/time
limits. Captures pass/fail counts and failure tracebacks.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from pathlib import Path

from app.services.analysis.models import TestResult

logger = logging.getLogger(__name__)

# Default timeout for the test subprocess (seconds)
_TEST_TIMEOUT = 60


async def run_tests(
    work_dir: Path, timeout_seconds: int = _TEST_TIMEOUT
) -> TestResult:
    """Run pytest in the given working directory.

    The work_dir should be a full shallow clone of the repo (isolated),
    NOT the live repo. It is cleaned up by the caller after use.

    Args:
        work_dir: Directory to run pytest in (isolated clone).
        timeout_seconds: Max time to allow tests to run.

    Returns:
        TestResult with pass/fail counts and tracebacks.
    """
    cmd = [
        sys.executable, "-m", "pytest",
        "--tb=short",
        "-q",
        "--no-header",
    ]

    logger.info("Running pytest in %s (timeout=%ds)", work_dir, timeout_seconds)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(work_dir),
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.warning("pytest timed out after %ds", timeout_seconds)
        proc.kill()
        return TestResult(timed_out=True)
    except Exception:
        logger.exception("Failed to run pytest")
        return TestResult()

    output = stdout.decode("utf-8", errors="replace")
    err_output = stderr.decode("utf-8", errors="replace")
    full_output = output + "\n" + err_output

    return _parse_pytest_output(full_output)


def _parse_pytest_output(output: str) -> TestResult:
    """Parse pytest -q output to extract pass/fail/error counts and tracebacks."""
    passed = 0
    failed = 0
    errors = 0

    # Match the summary line, e.g.:
    #   "2 passed, 1 failed in 0.42s"
    #   "1 passed in 0.10s"
    #   "1 failed, 1 error in 0.30s"
    summary_pattern = re.compile(
        r"(\d+)\s+passed|(\d+)\s+failed|(\d+)\s+error",
    )
    for match in summary_pattern.finditer(output):
        if match.group(1):
            passed = int(match.group(1))
        if match.group(2):
            failed = int(match.group(2))
        if match.group(3):
            errors = int(match.group(3))

    # Extract failure tracebacks — they appear between "FAILURES" and the summary
    tracebacks: list[str] = []
    if "FAILURES" in output or "ERRORS" in output:
        # Capture blocks starting with "___" (pytest failure headers)
        tb_pattern = re.compile(
            r"_{3,}\s+(.+?)\s+_{3,}\n(.*?)(?=_{3,}|\Z)",
            re.DOTALL,
        )
        for match in tb_pattern.finditer(output):
            test_name = match.group(1).strip()
            tb_body = match.group(2).strip()
            tracebacks.append(f"FAILED {test_name}:\n{tb_body}")

    total = passed + failed + errors
    return TestResult(
        passed=passed,
        failed=failed,
        errors=errors,
        total=total,
        tracebacks=tracebacks,
    )
