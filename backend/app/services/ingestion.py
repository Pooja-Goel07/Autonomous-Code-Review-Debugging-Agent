"""Ingestion service — fetches PR diff, changed files, and clones the repo.

Uses PyGithub with a GitHub App installation token to fetch PR metadata
and diff content. Performs a shallow git clone of the PR's head branch
for lint/test execution in an isolated temp directory.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from github import Github

from app.services.analysis.models import ChangedFile, PRIngestionResult
from app.services.github_auth import get_installation_token

logger = logging.getLogger(__name__)


def ingest_pr(repo_full_name: str, pr_number: int) -> PRIngestionResult:
    """Fetch PR metadata, diff, and changed file contents via GitHub API.

    Args:
        repo_full_name: "owner/repo" format.
        pr_number: Pull request number.

    Returns:
        PRIngestionResult with all PR data needed for analysis.
    """
    token = get_installation_token(repo_full_name)
    gh = Github(token)
    repo = gh.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    changed_files: list[ChangedFile] = []
    diff_parts: list[str] = []

    for f in pr.get_files():
        patch = f.patch or ""
        diff_parts.append(f"--- a/{f.filename}\n+++ b/{f.filename}\n{patch}")

        # Fetch full file content for non-deleted files
        content: str | None = None
        if f.status != "removed":
            try:
                content_file = repo.get_contents(f.filename, ref=pr.head.sha)
                # get_contents can return a list for directories; we only want files
                if not isinstance(content_file, list):
                    content = content_file.decoded_content.decode("utf-8", errors="replace")
            except Exception:
                logger.warning("Could not fetch content for %s", f.filename)
                content = None

        changed_files.append(
            ChangedFile(
                filename=f.filename,
                status=f.status,
                patch=patch,
                content=content,
            )
        )

    return PRIngestionResult(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        pr_title=pr.title,
        base_branch=pr.base.ref,
        head_branch=pr.head.ref,
        head_sha=pr.head.sha,
        diff_text="\n".join(diff_parts),
        changed_files=changed_files,
    )


async def clone_pr_head(
    repo_full_name: str,
    head_branch: str,
    work_dir: Path,
    token: str,
) -> None:
    """Shallow-clone the repository at the PR's head branch into work_dir.

    Uses the installation token for HTTPS auth. The clone is depth-1
    to minimize disk/network usage.

    Args:
        repo_full_name: "owner/repo" format.
        head_branch: The PR's head branch name.
        work_dir: Target directory for the clone.
        token: GitHub installation access token.
    """
    # Clean up if work_dir already exists
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    clone_url = f"https://x-access-token:{token}@github.com/{repo_full_name}.git"
    cmd = [
        "git", "clone",
        "--depth", "1",
        "--branch", head_branch,
        clone_url,
        str(work_dir),
    ]

    logger.info("Cloning %s@%s into %s", repo_full_name, head_branch, work_dir)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

    if proc.returncode != 0:
        err_msg = stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"git clone failed (exit {proc.returncode}): {err_msg}")

    logger.info("Clone complete: %s", work_dir)
