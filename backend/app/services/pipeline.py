"""Pipeline orchestrator — background task that runs ingestion + analysis.

This is the entry point enqueued by the webhook handler. It:
1. Ingests PR data from GitHub
2. Clones the repo at the PR head into a temp directory
3. Runs static analysis
4. Persists findings and test results to the database
5. Updates the review record

NOTE: Does NOT invoke the agent loop — that is Stage 3.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.finding import Finding
from app.models.review import Review
from app.models.test_run import TestRun
from app.services.analysis.engine import run_static_analysis
from app.services.github_auth import get_installation_token
from app.services.ingestion import clone_pr_head, ingest_pr

logger = logging.getLogger(__name__)


async def run_ingestion_and_analysis(
    repo_full_name: str,
    pr_number: int,
    review_id: int,
    session_factory: async_sessionmaker,
) -> None:
    """Background task: ingest PR data, run analysis, persist results.

    Args:
        repo_full_name: "owner/repo" format.
        pr_number: Pull request number.
        review_id: ID of the Review record created by the webhook handler.
        session_factory: Async session factory for database operations.
    """
    work_dir: Path | None = None

    try:
        logger.info(
            "Starting pipeline for %s PR #%d (review_id=%d)",
            repo_full_name, pr_number, review_id,
        )

        # 1. Ingest PR metadata and diff via GitHub API
        ingestion_result = ingest_pr(repo_full_name, pr_number)

        # 2. Clone the repo at the PR head branch into a temp directory
        work_dir = Path(tempfile.mkdtemp(prefix="cr_review_"))
        token = get_installation_token(repo_full_name)
        await clone_pr_head(
            repo_full_name,
            ingestion_result.head_branch,
            work_dir,
            token,
        )

        # 3. Run static analysis on the cloned repo
        context = await run_static_analysis(ingestion_result, work_dir)

        # 4. Persist findings and test results to the database
        async with session_factory() as session:
            async with session.begin():
                # Persist lint findings
                for lf in context.lint_findings:
                    finding = Finding(
                        review_id=review_id,
                        type=f"lint:{lf.rule}",
                        description=lf.message,
                        file=lf.file,
                        line=lf.line,
                    )
                    session.add(finding)

                # Persist test result
                if context.test_result:
                    test_run = TestRun(
                        review_id=review_id,
                        passed=(context.test_result.failed == 0 and not context.test_result.timed_out),
                        failed=(context.test_result.failed > 0 or context.test_result.timed_out),
                        traceback_text="\n---\n".join(context.test_result.tracebacks) or None,
                    )
                    session.add(test_run)

                # Update review status
                result = await session.execute(
                    select(Review).where(Review.id == review_id)
                )
                review = result.scalar_one_or_none()
                if review:
                    review.decision = "analysis_complete"
                    # Store confidence as 0.0 for now — agent (Stage 3) will update it
                    review.confidence_score = 0.0

        logger.info(
            "Pipeline complete for %s PR #%d: %d findings, tests=%s",
            repo_full_name,
            pr_number,
            len(context.lint_findings),
            f"{context.test_result.passed}p/{context.test_result.failed}f"
            if context.test_result else "N/A",
        )

    except Exception:
        logger.exception(
            "Pipeline failed for %s PR #%d (review_id=%d)",
            repo_full_name, pr_number, review_id,
        )
        # Mark review as failed
        try:
            async with session_factory() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Review).where(Review.id == review_id)
                    )
                    review = result.scalar_one_or_none()
                    if review:
                        review.decision = "error"
        except Exception:
            logger.exception("Failed to update review status to 'error'")

    finally:
        # Clean up temp directory
        if work_dir and work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
            logger.info("Cleaned up work_dir: %s", work_dir)
