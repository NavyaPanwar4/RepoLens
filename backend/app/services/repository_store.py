"""Persistent metadata and source snapshots for an analysis workspace."""

import json
import shutil
from pathlib import Path

from app.core.config import get_settings


def _workspace_dir(repo_id: str) -> Path:
    return get_settings().data_dir / "workspaces" / repo_id


def persist_sources(repo_id: str, parsed_files: list[dict], repo_root: str) -> None:
    """Keep the supported source files so citations remain valid after cleanup."""
    root = Path(repo_root).resolve()
    source_dir = _workspace_dir(repo_id) / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)

    for parsed in parsed_files:
        absolute_path = Path(parsed["file"]).resolve()
        relative_path = absolute_path.relative_to(root)
        destination = source_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(parsed.get("raw", ""), encoding="utf-8")
        parsed["file"] = relative_path.as_posix()


def persist_analysis(repo_id: str, analysis: dict) -> None:
    workspace = _workspace_dir(repo_id)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "analysis.json").write_text(
        json.dumps(analysis, indent=2), encoding="utf-8"
    )


def get_analysis(repo_id: str) -> dict | None:
    analysis_file = _workspace_dir(repo_id) / "analysis.json"
    if not analysis_file.is_file():
        return None
    return json.loads(analysis_file.read_text(encoding="utf-8"))


def get_source(repo_id: str, relative_path: str) -> str | None:
    source_root = (_workspace_dir(repo_id) / "sources").resolve()
    requested = (source_root / relative_path).resolve()
    if requested != source_root and source_root not in requested.parents:
        return None
    if not requested.is_file():
        return None
    return requested.read_text(encoding="utf-8")


def list_analyses(limit: int = 20, offset: int = 0) -> list[dict]:
    """Return lightweight summaries for the most recently updated workspaces."""
    workspace_root = get_settings().data_dir / "workspaces"
    if not workspace_root.is_dir():
        return []

    analyses = []
    for analysis_file in workspace_root.glob("*/analysis.json"):
        try:
            analysis = json.loads(analysis_file.read_text(encoding="utf-8"))
            analyses.append({
                "repo_id": analysis.get("repo_id") or analysis_file.parent.name,
                "summary": analysis.get("summary", {}),
                "bugs": analysis.get("bugs", {}),
                "overview": analysis.get("overview", {}),
                "updated_at": analysis_file.stat().st_mtime,
            })
        except (json.JSONDecodeError, OSError):
            continue
    analyses.sort(key=lambda item: item["updated_at"], reverse=True)
    return analyses[offset:offset + limit]


def delete_analysis(repo_id: str) -> bool:
    workspace = _workspace_dir(repo_id)
    if not workspace.is_dir():
        return False
    shutil.rmtree(workspace)
    return True


def count_analyses() -> int:
    workspace_root = get_settings().data_dir / "workspaces"
    if not workspace_root.is_dir():
        return 0
    return sum(1 for path in workspace_root.glob("*/analysis.json") if path.is_file())


def create_share(repo_id: str) -> str | None:
    analysis_file = _workspace_dir(repo_id) / "analysis.json"
    if not analysis_file.is_file():
        return None
    import secrets
    analysis = json.loads(analysis_file.read_text(encoding="utf-8"))
    token = secrets.token_urlsafe(24)
    analysis["share"] = {"token": token, "enabled": True}
    analysis_file.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    return token


def revoke_share(repo_id: str) -> bool:
    analysis_file = _workspace_dir(repo_id) / "analysis.json"
    if not analysis_file.is_file():
        return False
    analysis = json.loads(analysis_file.read_text(encoding="utf-8"))
    if "share" in analysis:
        analysis["share"]["enabled"] = False
        analysis_file.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    return True


def get_shared_analysis(token: str) -> dict | None:
    workspace_root = get_settings().data_dir / "workspaces"
    if not workspace_root.is_dir():
        return None
    for analysis_file in workspace_root.glob("*/analysis.json"):
        try:
            analysis = json.loads(analysis_file.read_text(encoding="utf-8"))
            share = analysis.get("share", {})
            if share.get("enabled") and share.get("token") == token:
                return analysis
        except (json.JSONDecodeError, OSError):
            continue
    return None
