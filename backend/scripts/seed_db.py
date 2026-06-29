"""Seed the PostgreSQL database with sample data for frontend verification.

Creates repos, PRs, reviews, findings, proposed fixes, and test runs
so the dashboard has real data to display.

Usage: python scripts/seed_db.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal, engine  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.models.repo import Repo  # noqa: E402
from app.models.pull_request import PullRequest  # noqa: E402
from app.models.review import Review  # noqa: E402
from app.models.finding import Finding  # noqa: E402
from app.models.proposed_fix import ProposedFix  # noqa: E402
from app.models.test_run import TestRun  # noqa: E402


async def seed() -> None:
    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        # Check if data already exists
        result = await session.execute(select(Repo).limit(1))
        if result.scalar_one_or_none():
            print("Database already has data -- skipping seed.")
            return

    async with SessionLocal() as session:
        # Repos
        repos = [
            Repo(github_url="https://github.com/acme/main-api-service", webhook_status="active", created_at=now - timedelta(days=30)),
            Repo(github_url="https://github.com/acme/frontend-core-v2", webhook_status="active", created_at=now - timedelta(days=20)),
            Repo(github_url="https://github.com/acme/auth-middleware", webhook_status="active", created_at=now - timedelta(days=15)),
            Repo(github_url="https://github.com/acme/data-pipeline-py", webhook_status="error", created_at=now - timedelta(days=10)),
        ]
        session.add_all(repos)
        await session.flush()

        # Pull Requests
        prs = [
            PullRequest(repo_id=repos[0].id, pr_number=1024, title="refactor: optimize database query execution in user service", status="open", created_at=now - timedelta(hours=2)),
            PullRequest(repo_id=repos[0].id, pr_number=1023, title="feat: add OAuth2 provider support for enterprise login", status="open", created_at=now - timedelta(hours=5)),
            PullRequest(repo_id=repos[0].id, pr_number=1022, title="fix: solve memory leak in websocket connection handler", status="open", created_at=now - timedelta(hours=8)),
            PullRequest(repo_id=repos[1].id, pr_number=501, title="chore: update dependency versions for security compliance", status="open", created_at=now - timedelta(days=1)),
            PullRequest(repo_id=repos[1].id, pr_number=500, title="feat: implement caching layer for product metadata", status="open", created_at=now - timedelta(days=2)),
            PullRequest(repo_id=repos[2].id, pr_number=78, title="fix: rate limiter bypass via header injection", status="open", created_at=now - timedelta(hours=3)),
            PullRequest(repo_id=repos[2].id, pr_number=77, title="feat: add JWT refresh token rotation", status="open", created_at=now - timedelta(days=3)),
            PullRequest(repo_id=repos[3].id, pr_number=42, title="fix: data corruption in batch ETL pipeline", status="open", created_at=now - timedelta(hours=12)),
        ]
        session.add_all(prs)
        await session.flush()

        # Reviews with varied decisions and confidence
        reviews = [
            Review(pr_id=prs[0].id, confidence_score=0.98, decision="accepted", created_at=now - timedelta(hours=1)),
            Review(pr_id=prs[1].id, confidence_score=0.72, decision="needs_human_review", created_at=now - timedelta(hours=4)),
            Review(pr_id=prs[2].id, confidence_score=0.45, decision="error", created_at=now - timedelta(hours=7)),
            Review(pr_id=prs[3].id, confidence_score=1.0, decision="accepted", created_at=now - timedelta(hours=20)),
            Review(pr_id=prs[4].id, confidence_score=0.81, decision="needs_human_review", created_at=now - timedelta(days=2)),
            Review(pr_id=prs[5].id, confidence_score=0.93, decision="accepted", created_at=now - timedelta(hours=2)),
            Review(pr_id=prs[6].id, confidence_score=0.67, decision="needs_human_review", created_at=now - timedelta(days=3)),
            Review(pr_id=prs[7].id, confidence_score=0.35, decision="error", created_at=now - timedelta(hours=11)),
        ]
        session.add_all(reviews)
        await session.flush()

        # Findings
        findings = [
            Finding(review_id=reviews[0].id, type="lint:F841", description="Local variable `unused_var` is assigned but never used", file="src/service.py", line=42),
            Finding(review_id=reviews[0].id, type="lint:E501", description="Line too long (120 > 100 characters)", file="src/service.py", line=55),
            Finding(review_id=reviews[1].id, type="test_failure", description="test_oauth_login failed: AssertionError", file="tests/test_auth.py", line=30),
            Finding(review_id=reviews[3].id, type="lint:F841", description="Unused import `os`", file="src/updater.py", line=3),
            Finding(review_id=reviews[4].id, type="security", description="Potential SQL injection in raw query", file="src/cache.py", line=88),
            Finding(review_id=reviews[5].id, type="lint:E711", description="Comparison to None", file="middleware/limiter.py", line=44),
            Finding(review_id=reviews[5].id, type="test_failure", description="test_rate_limit_bypass: expected 429 got 200", file="tests/test_limiter.py", line=15),
        ]
        session.add_all(findings)

        # Proposed fixes
        fixes = [
            ProposedFix(review_id=reviews[0].id, diff_text="- unused_var = 42\n+ # removed", reasoning_text="Removed unused variable.", accepted=True),
            ProposedFix(review_id=reviews[3].id, diff_text="- import os\n+ # removed unused import", reasoning_text="Cleaned up unused import.", accepted=True),
            ProposedFix(review_id=reviews[5].id, diff_text="- if x == None:\n+ if x is None:", reasoning_text="Use `is None` instead of `== None`.", accepted=True),
        ]
        session.add_all(fixes)

        # Test runs
        test_runs = [
            TestRun(review_id=reviews[0].id, passed=True, failed=False, traceback_text=None),
            TestRun(review_id=reviews[1].id, passed=False, failed=True, traceback_text="FAILED test_oauth_login: expected 200 got 401"),
            TestRun(review_id=reviews[3].id, passed=True, failed=False, traceback_text=None),
            TestRun(review_id=reviews[4].id, passed=False, failed=True, traceback_text="FAILED test_cache_query: SQL injection detected"),
            TestRun(review_id=reviews[5].id, passed=True, failed=False, traceback_text=None),
        ]
        session.add_all(test_runs)

        await session.commit()

    print("Seeded database with:")
    print(f"  {len(repos)} repos")
    print(f"  {len(prs)} pull requests")
    print(f"  {len(reviews)} reviews")
    print(f"  {len(findings)} findings")
    print(f"  {len(fixes)} proposed fixes")
    print(f"  {len(test_runs)} test runs")
    print("Done!")


if __name__ == "__main__":
    asyncio.run(seed())
