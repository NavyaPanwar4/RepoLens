"""Optional read-only GitHub pull-request integration."""

import json
import urllib.parse
import urllib.request
import time
import hmac
import hashlib
import jwt

from app.core.config import get_settings


def _github_request(path: str) -> dict | list:
    settings = get_settings()
    if not settings.github_token:
        raise ValueError("GITHUB_TOKEN is not configured.")
    request = urllib.request.Request(
        f"https://api.github.com/{path.lstrip('/')}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {settings.github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "RepoLens",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_github_repository(url: str) -> tuple[str, str] | None:
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname not in {"github.com", "www.github.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    return parts[0], parts[1].removesuffix(".git")


def list_pull_requests(repository_url: str, state: str = "open") -> list[dict]:
    parsed = parse_github_repository(repository_url)
    if not parsed:
        raise ValueError("A GitHub repository URL is required.")
    owner, repository = parsed
    items = _github_request(
        f"repos/{owner}/{repository}/pulls?"
        + urllib.parse.urlencode({"state": state, "per_page": 20})
    )
    if not isinstance(items, list):
        raise ValueError("GitHub returned an unexpected response.")
    return [
        {
            "number": item["number"],
            "title": item["title"],
            "state": item["state"],
            "author": item["user"]["login"],
            "draft": item.get("draft", False),
            "url": item["html_url"],
            "base": item["base"]["ref"],
            "head": item["head"]["ref"],
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
        }
        for item in items
    ]


def verify_webhook_signature(payload: bytes, signature: str | None) -> bool:
    settings = get_settings()
    secret = settings.github_webhook_secret
    if not secret:
        return False
    if not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def create_app_jwt() -> str:
    settings = get_settings()
    if not settings.github_app_id or not settings.github_app_private_key:
        raise ValueError("GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY are required.")
    private_key = settings.github_app_private_key
    private_key = private_key.replace("\\n", "\n")
    now = int(time.time())
    return jwt.encode(
        {"iat": now - 60, "exp": now + 540, "iss": settings.github_app_id},
        private_key,
        algorithm="RS256",
    )


def get_app_installation_token(installation_id: str | None = None) -> str:
    settings = get_settings()
    resolved_installation_id = installation_id or settings.github_app_installation_id
    if not resolved_installation_id:
        raise ValueError("A GitHub App installation ID is required.")
    app_jwt = create_app_jwt()
    request = urllib.request.Request(
        f"https://api.github.com/app/installations/{resolved_installation_id}/access_tokens",
        data=b"{}",
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {app_jwt}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "RepoLens",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = payload.get("token")
    if not token:
        raise ValueError("GitHub did not return an installation token.")
    return token


def github_app_request(path: str, method: str = "GET", body: dict | None = None,
                       installation_id: str | None = None) -> dict | list:
    token = get_app_installation_token(installation_id)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"https://api.github.com/{path.lstrip('/')}",
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "RepoLens",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        content = response.read()
    return json.loads(content.decode("utf-8")) if content else {}


def get_pull_request_diff(owner: str, repository: str, pull_number: int,
                          installation_id: str | None = None) -> dict:
    request_path = f"repos/{owner}/{repository}/pulls/{pull_number}"
    pull = github_app_request(request_path, installation_id=installation_id)
    files = github_app_request(
        f"{request_path}/files?per_page=100",
        installation_id=installation_id,
    )
    if not isinstance(pull, dict) or not isinstance(files, list):
        raise ValueError("GitHub returned an unexpected pull-request response.")
    return {
        "number": pull["number"],
        "title": pull["title"],
        "state": pull["state"],
        "draft": pull.get("draft", False),
        "base": pull["base"]["ref"],
        "head": pull["head"]["ref"],
        "author": pull["user"]["login"],
        "body": pull.get("body") or "",
        "html_url": pull["html_url"],
        "changed_files": [
            {
                "filename": file["filename"],
                "status": file["status"],
                "additions": file["additions"],
                "deletions": file["deletions"],
                "changes": file["changes"],
                "patch": file.get("patch"),
            }
            for file in files
        ],
    }


def post_pull_request_review(owner: str, repository: str, pull_number: int,
                             body: str, event: str = "COMMENT",
                             installation_id: str | None = None) -> dict:
    if event not in {"COMMENT", "APPROVE", "REQUEST_CHANGES"}:
        raise ValueError("Review event must be COMMENT, APPROVE, or REQUEST_CHANGES.")
    return github_app_request(
        f"repos/{owner}/{repository}/pulls/{pull_number}/reviews",
        method="POST",
        body={"body": body, "event": event},
        installation_id=installation_id,
    )
