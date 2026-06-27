"""GitHub App authentication — installation token generation.

Uses the GitHub App's private key to create a JWT, then exchanges it for
a short-lived installation access token scoped to a specific repository.
This token is used by the ingestion service and for posting draft PR reviews.
"""

from __future__ import annotations

import logging
import time

import jwt
import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

_GITHUB_API_BASE = "https://api.github.com"


def _build_jwt(app_id: str, private_key: str) -> str:
    """Build a short-lived JWT (10 min expiry) signed with the App's RSA private key.

    This JWT authenticates as the GitHub App itself (not as an installation).
    """
    now = int(time.time())
    payload = {
        "iat": now - 60,  # issued at (60s in the past to account for clock drift)
        "exp": now + (10 * 60),  # expires in 10 minutes
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def _get_installation_id(jwt_token: str, repo_full_name: str) -> int:
    """Find the installation ID for a given repository.

    GET /repos/{owner}/{repo}/installation
    """
    url = f"{_GITHUB_API_BASE}/repos/{repo_full_name}/installation"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()["id"]


def get_installation_token(repo_full_name: str) -> str:
    """Full flow: build JWT → find installation → create installation access token.

    Returns the token string, valid for ~1 hour.
    Raises ValueError if GitHub App credentials are not configured.
    """
    if not settings.GITHUB_APP_ID or not settings.GITHUB_APP_PRIVATE_KEY:
        raise ValueError(
            "GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY must be set in .env "
            "to authenticate as a GitHub App."
        )

    # Step 1: Build JWT to authenticate as the App
    app_jwt = _build_jwt(settings.GITHUB_APP_ID, settings.GITHUB_APP_PRIVATE_KEY)

    # Step 2: Find the installation ID for this repo
    installation_id = _get_installation_id(app_jwt, repo_full_name)
    logger.info(
        "Found GitHub App installation %d for %s",
        installation_id,
        repo_full_name,
    )

    # Step 3: Create an installation access token
    url = f"{_GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.post(url, headers=headers, timeout=15)
    resp.raise_for_status()
    token = resp.json()["token"]

    logger.info("Installation token created for %s", repo_full_name)
    return token
