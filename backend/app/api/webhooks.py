"""Webhook listener — receives and processes GitHub PR events.

POST /webhooks/github
- Validates HMAC-SHA256 signature against GITHUB_WEBHOOK_SECRET
- Parses pull_request events (opened, synchronize, reopened)
- Upserts Repo and PullRequest records
- Creates a Review record and enqueues the analysis pipeline
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal, get_db
from app.models.pull_request import PullRequest
from app.models.repo import Repo
from app.models.review import Review
from app.services.pipeline import run_ingestion_and_analysis

logger = logging.getLogger(__name__)

router = APIRouter()

# PR event actions we care about
_HANDLED_ACTIONS = {"opened", "synchronize", "reopened"}


def verify_github_signature(
    payload_body: bytes, signature_header: str, secret: str
) -> bool:
    """Validate the GitHub webhook signature using HMAC-SHA256.

    Args:
        payload_body: Raw request body bytes.
        signature_header: Value of the X-Hub-Signature-256 header.
        secret: The webhook secret configured in the GitHub App.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not signature_header.startswith("sha256="):
        return False

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    received_signature = signature_header[len("sha256="):]
    return hmac.compare_digest(expected_signature, received_signature)


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive and process GitHub webhook events.

    Only processes 'pull_request' events with actions:
    opened, synchronize, reopened.
    """
    # --- Signature validation ---
    if not settings.GITHUB_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Server misconfigured: GITHUB_WEBHOOK_SECRET not set",
        )

    signature = request.headers.get("X-Hub-Signature-256", "")
    body = await request.body()

    if not verify_github_signature(body, signature, settings.GITHUB_WEBHOOK_SECRET):
        logger.warning("Invalid webhook signature from %s", request.client)
        raise HTTPException(status_code=403, detail="Invalid signature")

    # --- Parse event ---
    event_type = request.headers.get("X-GitHub-Event", "")
    if event_type != "pull_request":
        # Acknowledge but ignore non-PR events (e.g. push, ping)
        return {"status": "ignored", "reason": f"event_type={event_type}"}

    payload = await request.json()
    action = payload.get("action", "")
    if action not in _HANDLED_ACTIONS:
        return {"status": "ignored", "reason": f"action={action}"}

    # --- Extract data ---
    pr_data = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})

    repo_full_name = repo_data.get("full_name", "")
    github_url = repo_data.get("html_url", "")
    pr_number = pr_data.get("number", 0)
    pr_title = pr_data.get("title", "")

    if not repo_full_name or not pr_number:
        raise HTTPException(status_code=400, detail="Missing repo or PR data")

    logger.info(
        "Webhook received: %s PR #%d (%s) — action=%s",
        repo_full_name, pr_number, pr_title, action,
    )

    # --- Upsert Repo ---
    result = await db.execute(
        select(Repo).where(Repo.github_url == github_url)
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        repo = Repo(github_url=github_url, webhook_status="active")
        db.add(repo)
        await db.flush()  # get repo.id
    else:
        repo.webhook_status = "active"

    # --- Upsert PullRequest ---
    result = await db.execute(
        select(PullRequest).where(
            PullRequest.repo_id == repo.id,
            PullRequest.pr_number == pr_number,
        )
    )
    pull_request = result.scalar_one_or_none()
    if pull_request is None:
        pull_request = PullRequest(
            repo_id=repo.id,
            pr_number=pr_number,
            title=pr_title,
            status="open",
        )
        db.add(pull_request)
        await db.flush()
    else:
        pull_request.title = pr_title
        pull_request.status = "open"

    # --- Create Review record ---
    review = Review(
        pr_id=pull_request.id,
        confidence_score=0.0,
        decision="pending",
    )
    db.add(review)
    await db.flush()

    await db.commit()

    # --- Enqueue background task ---
    background_tasks.add_task(
        run_ingestion_and_analysis,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        review_id=review.id,
        session_factory=SessionLocal,
    )

    logger.info(
        "Enqueued analysis pipeline for %s PR #%d (review_id=%d)",
        repo_full_name, pr_number, review.id,
    )

    return {
        "status": "accepted",
        "review_id": review.id,
        "repo": repo_full_name,
        "pr_number": pr_number,
    }
