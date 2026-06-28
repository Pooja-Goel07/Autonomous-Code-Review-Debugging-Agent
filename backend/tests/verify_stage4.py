"""Stage 4 verification — tests REST API endpoints with seeded data.

Uses an in-memory SQLite database and FastAPI's TestClient to:
1. Seed fake repos, PRs, reviews, findings, proposed fixes, test runs
2. Test auth (login, /me, 401 without token)
3. Test each endpoint and print the JSON response
4. Confirm protected endpoints reject unauthenticated requests

Does NOT require PostgreSQL, GitHub, or any external services.

ORDER DEPENDENCY: The test sections share a single in-memory database and
are NOT isolated from each other. Specifically:

  Section 5 (RERUN) mutates review #1 (resets decision to "pending" and
  confidence to 0.0). Section 4 (ANALYTICS) asserts exact numeric values
  that depend on review #1 being in its original seeded state.

  Therefore: ANALYTICS must run BEFORE RERUN. Do not reorder these sections
  without verifying that analytics assertions still hold.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure the backend package is importable
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Override settings BEFORE importing anything that uses them
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-verification")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///")

from datetime import datetime, timedelta, timezone  # noqa: E402

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base  # noqa: E402
from app.models.finding import Finding  # noqa: E402
from app.models.proposed_fix import ProposedFix  # noqa: E402
from app.models.pull_request import PullRequest  # noqa: E402
from app.models.repo import Repo  # noqa: E402
from app.models.review import Review  # noqa: E402
from app.models.test_run import TestRun  # noqa: E402

# ---------------------------------------------------------------------------
# Test database setup (in-memory SQLite)
# ---------------------------------------------------------------------------

_test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
_TestSession = async_sessionmaker(
    bind=_test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def _override_get_db():
    async with _TestSession() as session:
        try:
            yield session
        finally:
            await session.close()


async def _seed_data():
    """Create test database tables and seed with fake data."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    now = datetime.now(timezone.utc)

    async with _TestSession() as session:
        async with session.begin():
            # Repos
            repo1 = Repo(
                id=1,
                github_url="https://github.com/acme/main-api-service",
                webhook_status="active",
                created_at=now - timedelta(days=30),
            )
            repo2 = Repo(
                id=2,
                github_url="https://github.com/acme/frontend-core-v2",
                webhook_status="active",
                created_at=now - timedelta(days=20),
            )
            session.add_all([repo1, repo2])

            # Pull Requests
            pr1 = PullRequest(
                id=1,
                repo_id=1,
                pr_number=1024,
                title="refactor: optimize database query execution",
                status="open",
                created_at=now - timedelta(hours=2),
            )
            pr2 = PullRequest(
                id=2,
                repo_id=1,
                pr_number=1023,
                title="feat: add OAuth2 provider support",
                status="open",
                created_at=now - timedelta(hours=5),
            )
            pr3 = PullRequest(
                id=3,
                repo_id=2,
                pr_number=501,
                title="fix: memory leak in connection handler",
                status="open",
                created_at=now - timedelta(days=1),
            )
            session.add_all([pr1, pr2, pr3])

            # Reviews
            review1 = Review(
                id=1,
                pr_id=1,
                confidence_score=0.98,
                decision="accepted",
                created_at=now - timedelta(hours=1),
            )
            review2 = Review(
                id=2,
                pr_id=2,
                confidence_score=0.72,
                decision="needs_human_review",
                created_at=now - timedelta(hours=4),
            )
            review3 = Review(
                id=3,
                pr_id=3,
                confidence_score=0.45,
                decision="error",
                created_at=now - timedelta(hours=20),
            )
            session.add_all([review1, review2, review3])

            # Findings
            f1 = Finding(
                id=1,
                review_id=1,
                type="lint:F841",
                description="Local variable `unused_var` is assigned but never used",
                file="src/service.py",
                line=42,
            )
            f2 = Finding(
                id=2,
                review_id=1,
                type="lint:E501",
                description="Line too long (120 > 100 characters)",
                file="src/service.py",
                line=55,
            )
            f3 = Finding(
                id=3,
                review_id=2,
                type="test_failure",
                description="test_oauth_login failed: AssertionError",
                file="tests/test_auth.py",
                line=30,
            )
            session.add_all([f1, f2, f3])

            # Proposed Fixes
            pf1 = ProposedFix(
                id=1,
                review_id=1,
                diff_text="- unused_var = 42\n+ # removed unused variable",
                reasoning_text="Removed unused variable to fix F841 lint warning.",
                accepted=True,
            )
            session.add(pf1)

            # Test Runs
            tr1 = TestRun(
                id=1,
                review_id=1,
                passed=True,
                failed=False,
                traceback_text=None,
            )
            tr2 = TestRun(
                id=2,
                review_id=2,
                passed=False,
                failed=True,
                traceback_text="FAILED test_oauth_login: AssertionError: expected 200 got 401",
            )
            session.add_all([tr1, tr2])


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def _pp(label: str, data: dict | list) -> None:
    """Pretty-print a JSON response."""
    print(f"\n  {label}:")
    print(f"  {json.dumps(data, indent=2, default=str)}")


async def main() -> None:
    print("=" * 70)
    print("STAGE 4 VERIFICATION -- REST API & Authentication")
    print("=" * 70)

    # Seed data
    await _seed_data()

    # Import app and override DB dependency
    from app.db.session import get_db
    from app.main import app

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    results: list[tuple[str, bool]] = []

    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # ---------------------------------------------------------------
        # 1. AUTH — Login
        # ---------------------------------------------------------------
        print("\n" + "-" * 70)
        print("1. AUTH")
        print("-" * 70)

        # Bad credentials
        r = await client.post("/auth/login", json={"username": "admin", "password": "wrong"})
        results.append(("Login with wrong password returns 401", r.status_code == 401))
        print(f"\n  POST /auth/login (wrong pw): {r.status_code}")

        # Good credentials
        r = await client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        results.append(("Login with correct password returns 200", r.status_code == 200))
        token_data = r.json()
        _pp("POST /auth/login (correct)", token_data)
        results.append(("Token response has access_token", "access_token" in token_data))

        token = token_data.get("access_token", "")
        auth_headers = {"Authorization": f"Bearer {token}"}

        # GET /auth/me
        r = await client.get("/auth/me", headers=auth_headers)
        results.append(("GET /auth/me returns 200", r.status_code == 200))
        _pp("GET /auth/me", r.json())

        # GET /auth/me without token
        r = await client.get("/auth/me")
        results.append(("GET /auth/me without token returns 401", r.status_code == 401))
        print(f"\n  GET /auth/me (no token): {r.status_code}")

        # ---------------------------------------------------------------
        # 2. REPOS
        # ---------------------------------------------------------------
        print("\n" + "-" * 70)
        print("2. REPOS")
        print("-" * 70)

        # Unauthenticated
        r = await client.get("/repos")
        results.append(("GET /repos without token returns 401", r.status_code == 401))
        print(f"\n  GET /repos (no token): {r.status_code}")

        # List repos
        r = await client.get("/repos", headers=auth_headers)
        results.append(("GET /repos returns 200", r.status_code == 200))
        repos_data = r.json()
        _pp("GET /repos", repos_data)
        results.append(("Repos list has 2 repos", repos_data.get("total") == 2))

        # Get single repo
        r = await client.get("/repos/1", headers=auth_headers)
        results.append(("GET /repos/1 returns 200", r.status_code == 200))
        _pp("GET /repos/1", r.json())

        # Create repo
        r = await client.post(
            "/repos",
            json={"github_url": "https://github.com/acme/new-service"},
            headers=auth_headers,
        )
        results.append(("POST /repos returns 201", r.status_code == 201))
        _pp("POST /repos (create)", r.json())

        # Duplicate repo
        r = await client.post(
            "/repos",
            json={"github_url": "https://github.com/acme/new-service"},
            headers=auth_headers,
        )
        results.append(("POST /repos duplicate returns 409", r.status_code == 409))

        # 404
        r = await client.get("/repos/999", headers=auth_headers)
        results.append(("GET /repos/999 returns 404", r.status_code == 404))

        # ---------------------------------------------------------------
        # 3. REVIEWS
        # ---------------------------------------------------------------
        print("\n" + "-" * 70)
        print("3. REVIEWS")
        print("-" * 70)

        # List all
        r = await client.get("/reviews", headers=auth_headers)
        results.append(("GET /reviews returns 200", r.status_code == 200))
        reviews_data = r.json()
        _pp("GET /reviews", reviews_data)
        results.append(("Reviews list has 3 reviews", reviews_data.get("total") == 3))

        # Filter by decision
        r = await client.get("/reviews?decision=accepted", headers=auth_headers)
        results.append(("GET /reviews?decision=accepted returns 200", r.status_code == 200))
        filtered = r.json()
        results.append((
            "Filtered reviews: all accepted",
            all(rv["decision"] == "accepted" for rv in filtered.get("reviews", [])),
        ))
        _pp("GET /reviews?decision=accepted", filtered)

        # Filter by min_confidence
        r = await client.get("/reviews?min_confidence=0.9", headers=auth_headers)
        high_conf = r.json()
        results.append((
            "Filtered reviews: confidence >= 0.9",
            all(rv["confidence_score"] >= 0.9 for rv in high_conf.get("reviews", [])),
        ))

        # Pagination
        r = await client.get("/reviews?page=1&page_size=2", headers=auth_headers)
        paged = r.json()
        results.append(("Pagination: page_size=2 returns <= 2", len(paged.get("reviews", [])) <= 2))

        # Detail
        r = await client.get("/reviews/1", headers=auth_headers)
        results.append(("GET /reviews/1 returns 200", r.status_code == 200))
        detail = r.json()
        _pp("GET /reviews/1 (detail)", detail)
        results.append(("Review detail has findings", len(detail.get("findings", [])) > 0))
        results.append(("Review detail has proposed_fixes", len(detail.get("proposed_fixes", [])) > 0))
        results.append(("Review detail has test_runs", len(detail.get("test_runs", [])) > 0))

        # ---------------------------------------------------------------
        # 4. ANALYTICS (run BEFORE rerun, which mutates review data)
        # ---------------------------------------------------------------
        print("\n" + "-" * 70)
        print("4. ANALYTICS")
        print("-" * 70)

        # Summary
        r = await client.get("/analytics/summary", headers=auth_headers)
        results.append(("GET /analytics/summary returns 200", r.status_code == 200))
        summary = r.json()
        _pp("GET /analytics/summary", summary)
        results.append(("Summary has total_prs_analyzed", "total_prs_analyzed" in summary))
        results.append(("Summary total_prs = 3", summary.get("total_prs_analyzed") == 3))
        results.append(("Summary total_bugs = 3", summary.get("total_bugs_caught") == 3))

        # Exact numeric checks:
        # Seeded reviews: 0.98 (accepted), 0.72 (needs_human_review), 0.45 (error)
        # avg_confidence = (0.98 + 0.72 + 0.45) / 3 = 0.7167
        avg_conf = summary.get("avg_confidence_score", 0.0)
        results.append((
            f"Summary avg_confidence ~= 0.7167 (got {avg_conf})",
            abs(avg_conf - 0.7167) < 0.01,
        ))

        # fix_acceptance_rate = accepted / (accepted + needs_human_review) = 1 / (1+1) = 0.5
        acc_rate = summary.get("fix_acceptance_rate", 0.0)
        results.append((
            f"Summary fix_acceptance_rate = 0.5 (got {acc_rate})",
            abs(acc_rate - 0.5) < 0.01,
        ))

        # Trends
        r = await client.get("/analytics/trends?weeks=4", headers=auth_headers)
        results.append(("GET /analytics/trends returns 200", r.status_code == 200))
        trends = r.json()
        _pp("GET /analytics/trends", trends)
        results.append(("Trends has bugs_per_week", "bugs_per_week" in trends))
        results.append(("Trends has acceptance_rate", "acceptance_rate_over_time" in trends))

        # ---------------------------------------------------------------
        # 5. RERUN (mutates review #1 — must run AFTER analytics)
        # ---------------------------------------------------------------
        print("\n" + "-" * 70)
        print("5. RERUN")
        print("-" * 70)

        # Rerun
        r = await client.post("/reviews/1/rerun", headers=auth_headers)
        results.append(("POST /reviews/1/rerun returns 200", r.status_code == 200))
        _pp("POST /reviews/1/rerun", r.json())

        # 404
        r = await client.get("/reviews/999", headers=auth_headers)
        results.append(("GET /reviews/999 returns 404", r.status_code == 404))

    # ---------------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------------
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)

    all_passed = True
    for label, ok in results:
        status_str = "[PASS]" if ok else "[FAIL]"
        print(f"  {status_str}  {label}")
        if not ok:
            all_passed = False

    print()
    if all_passed:
        print(f"  >> ALL {len(results)} CHECKS PASSED -- Stage 4 verified!")
    else:
        failed_count = sum(1 for _, ok in results if not ok)
        print(f"  >> {failed_count}/{len(results)} CHECKS FAILED -- see details above.")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
