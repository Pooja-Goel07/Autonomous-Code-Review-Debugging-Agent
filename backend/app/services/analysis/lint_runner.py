"""Lint runner — executes ruff on changed files in a subprocess.

Runs `ruff check --output-format=json` and parses the structured output
into LintFinding objects.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

from app.services.analysis.models import LintFinding

logger = logging.getLogger(__name__)

# Timeout for the ruff subprocess (seconds)
_LINT_TIMEOUT = 30


async def run_lint(work_dir: Path, filenames: list[str]) -> list[LintFinding]:
    """Run ruff on the specified files within work_dir.

    Args:
        work_dir: The working directory (isolated clone/checkout).
        filenames: Relative paths of files to lint within work_dir.

    Returns:
        List of LintFinding objects. Empty list on timeout or error.
    """
    if not filenames:
        return []

    # Filter to files that actually exist in work_dir
    existing = [f for f in filenames if (work_dir / f).is_file()]
    if not existing:
        return []

    cmd = [
        sys.executable, "-m", "ruff",
        "check",
        "--output-format=json",
        "--no-fix",
        *existing,
    ]

    logger.info("Running ruff on %d files in %s", len(existing), work_dir)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(work_dir),
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=_LINT_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.warning("Ruff timed out after %ds", _LINT_TIMEOUT)
        proc.kill()
        return []
    except Exception:
        logger.exception("Failed to run ruff")
        return []

    # ruff returns exit code 1 when it finds issues — that's expected
    raw_output = stdout.decode("utf-8", errors="replace").strip()
    if not raw_output:
        return []

    try:
        issues = json.loads(raw_output)
    except json.JSONDecodeError:
        logger.warning("Could not parse ruff JSON output: %s", raw_output[:200])
        return []

    findings: list[LintFinding] = []
    for issue in issues:
        findings.append(
            LintFinding(
                file=issue.get("filename", ""),
                line=issue.get("location", {}).get("row", 0),
                column=issue.get("location", {}).get("column", 0),
                rule=issue.get("code", ""),
                message=issue.get("message", ""),
                severity="error" if issue.get("code", "").startswith("E") else "warning",
            )
        )

    logger.info("Ruff found %d issues", len(findings))
    return findings
