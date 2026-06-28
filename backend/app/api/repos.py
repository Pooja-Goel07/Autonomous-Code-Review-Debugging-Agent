"""Repos API — CRUD operations for connected repositories.

All endpoints require JWT authentication via get_current_user.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import RepoCreate, RepoListResponse, RepoResponse, UserResponse
from app.db.session import get_db
from app.models.pull_request import PullRequest
from app.models.repo import Repo

router = APIRouter()


@router.get("", response_model=RepoListResponse)
async def list_repos(
    db: AsyncSession = Depends(get_db),
    _user: UserResponse = Depends(get_current_user),
) -> RepoListResponse:
    """List all connected repos with their webhook_status and PR count."""
    # Subquery for PR count per repo
    pr_count_subq = (
        select(
            PullRequest.repo_id,
            func.count(PullRequest.id).label("pr_count"),
        )
        .group_by(PullRequest.repo_id)
        .subquery()
    )

    result = await db.execute(
        select(Repo, pr_count_subq.c.pr_count)
        .outerjoin(pr_count_subq, Repo.id == pr_count_subq.c.repo_id)
        .order_by(Repo.created_at.desc())
    )

    repos = []
    for row in result.all():
        repo = row[0]
        pr_count = row[1] or 0
        repos.append(
            RepoResponse(
                id=repo.id,
                github_url=repo.github_url,
                webhook_status=repo.webhook_status,
                created_at=repo.created_at,
                pr_count=pr_count,
            )
        )

    return RepoListResponse(repos=repos, total=len(repos))


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repo(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    _user: UserResponse = Depends(get_current_user),
) -> RepoResponse:
    """Get a single repo by ID."""
    result = await db.execute(select(Repo).where(Repo.id == repo_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repo not found")

    # Count PRs
    pr_result = await db.execute(
        select(func.count(PullRequest.id)).where(PullRequest.repo_id == repo_id)
    )
    pr_count = pr_result.scalar() or 0

    return RepoResponse(
        id=repo.id,
        github_url=repo.github_url,
        webhook_status=repo.webhook_status,
        created_at=repo.created_at,
        pr_count=pr_count,
    )


@router.post("", response_model=RepoResponse, status_code=status.HTTP_201_CREATED)
async def create_repo(
    body: RepoCreate,
    db: AsyncSession = Depends(get_db),
    _user: UserResponse = Depends(get_current_user),
) -> RepoResponse:
    """Create a new repo record (Connect Repo flow)."""
    # Check for duplicate
    result = await db.execute(select(Repo).where(Repo.github_url == body.github_url))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repo already connected",
        )

    repo = Repo(github_url=body.github_url, webhook_status="pending")
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    return RepoResponse(
        id=repo.id,
        github_url=repo.github_url,
        webhook_status=repo.webhook_status,
        created_at=repo.created_at,
        pr_count=0,
    )
