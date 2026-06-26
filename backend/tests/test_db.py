import os
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

# Set up test environment variables BEFORE importing config
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_temp.db"
os.environ["BACKEND_ENV"] = "test"

from app.core.config import settings
from app.models import Base, Repo, PullRequest, Review, Finding, ProposedFix, TestRun
from alembic.config import Config
from alembic import command


@pytest.fixture(scope="module", autouse=True)
def run_migrations():
    """
    Module-level fixture to run migration upgrade before tests
    and downgrade + file cleanup after tests.
    """
    # Initialize alembic configuration relative to backend/
    alembic_cfg = Config("alembic.ini")
    
    # Apply migrations
    command.upgrade(alembic_cfg, "head")
    
    yield
    
    # Rollback migrations
    command.downgrade(alembic_cfg, "base")
    
    # Remove temporary test database file
    if os.path.exists("test_temp.db"):
        try:
            os.remove("test_temp.db")
        except PermissionError:
            pass


@pytest.mark.asyncio
async def test_database_models_lifecycle():
    """
    Verifies creation, querying, relationships, and cascade delete
    behavior of all database models.
    """
    # Create engine and session maker using settings.DATABASE_URL
    engine = create_async_engine(settings.DATABASE_URL)
    Session = async_sessionmaker(bind=engine, expire_on_commit=False)

    # 1. Test insertion and retrieval
    async with Session() as session:
        # Create a repo
        new_repo = Repo(github_url="https://github.com/org/project-repo", webhook_status="active")
        session.add(new_repo)
        await session.commit()
        await session.refresh(new_repo)
        
        assert new_repo.id is not None
        assert new_repo.github_url == "https://github.com/org/project-repo"

        # Create a PR under this repo
        new_pr = PullRequest(
            repo_id=new_repo.id,
            pr_number=42,
            title="refactor: improve connection pooling",
            status="open"
        )
        session.add(new_pr)
        await session.commit()
        await session.refresh(new_pr)

        assert new_pr.id is not None
        assert new_pr.repo_id == new_repo.id

        # Create a review run under this PR
        new_review = Review(
            pr_id=new_pr.id,
            confidence_score=0.94,
            decision="needs_review"
        )
        session.add(new_review)
        await session.commit()
        await session.refresh(new_review)

        assert new_review.id is not None
        assert new_review.pr_id == new_pr.id

        # Add a finding, proposed fix, and test run to the review
        new_finding = Finding(
            review_id=new_review.id,
            type="bug",
            description="Detected event emitter memory leak in heap profile.",
            file="src/core/pool.ts",
            line=45
        )
        session.add(new_finding)

        new_fix = ProposedFix(
            review_id=new_review.id,
            diff_text="@@ -45,3 +45,5 @@\n+ if (conn.isStale()) {\n+   await conn.close();\n+ }",
            reasoning_text="Close stale connections on release to prevent memory leaks.",
            accepted=False
        )
        session.add(new_fix)

        new_test_run = TestRun(
            review_id=new_review.id,
            passed=False,
            failed=True,
            traceback_text="AssertionError: Connection manager did not close pool socket"
        )
        session.add(new_test_run)

        await session.commit()

        # Refresh instances
        await session.refresh(new_finding)
        await session.refresh(new_fix)
        await session.refresh(new_test_run)

        assert new_finding.id is not None
        assert new_fix.id is not None
        assert new_test_run.id is not None

    # 2. Test fetching and relationship lookups
    async with Session() as session:
        # Check repos query
        repo_stmt = select(Repo).where(Repo.github_url == "https://github.com/org/project-repo")
        db_repo = (await session.execute(repo_stmt)).scalar_one()
        assert db_repo.webhook_status == "active"

        # Check pull requests query
        pr_stmt = select(PullRequest).where(PullRequest.repo_id == db_repo.id)
        db_pr = (await session.execute(pr_stmt)).scalar_one()
        assert db_pr.pr_number == 42

    # 3. Test CASCADE DELETE behavior
    async with Session() as session:
        # Delete repo
        result = await session.execute(select(Repo).where(Repo.github_url == "https://github.com/org/project-repo"))
        repo_to_delete = result.scalar_one()
        await session.delete(repo_to_delete)
        await session.commit()

    # Verify everything has cascaded and been deleted
    async with Session() as session:
        repos_count = len((await session.execute(select(Repo))).scalars().all())
        prs_count = len((await session.execute(select(PullRequest))).scalars().all())
        reviews_count = len((await session.execute(select(Review))).scalars().all())
        findings_count = len((await session.execute(select(Finding))).scalars().all())
        fixes_count = len((await session.execute(select(ProposedFix))).scalars().all())
        test_runs_count = len((await session.execute(select(TestRun))).scalars().all())

        assert repos_count == 0
        assert prs_count == 0
        assert reviews_count == 0
        assert findings_count == 0
        assert fixes_count == 0
        assert test_runs_count == 0

    await engine.dispose()
