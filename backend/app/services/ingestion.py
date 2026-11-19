import git
import zipfile
import tempfile
import shutil
import os
import stat
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings

# Files we can parse with tree-sitter (structured extraction)
PARSEABLE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".rs", ".cpp", ".cc", ".cxx", ".c",
    ".go", ".rb", ".php", ".swift", ".kt",
}

# Files we index as raw text (no AST, just content)
RAW_TEXT_EXTENSIONS = {
    ".html", ".css", ".scss", ".sass", ".less",
    ".md", ".txt", ".json", ".yaml", ".yml",
    ".toml", ".env.example", ".xml", ".svg",
    ".sh", ".bash", ".zsh", ".dockerfile",
    ".lcov",
}

ALL_SUPPORTED = PARSEABLE_EXTENSIONS | RAW_TEXT_EXTENSIONS

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "dist", "build",
    ".venv", "venv", ".next", "target", "out", "coverage",
    ".idea", ".vscode", "vendor", "third_party",
}

SKIP_FILES = {
    "package-lock.json", "yarn.lock", "poetry.lock",
    "Pipfile.lock", "Cargo.lock",
}


def _validate_git_url(git_url: str) -> None:
    parsed = urlparse(git_url)
    settings = get_settings()
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Provide an HTTPS GitHub repository URL.")
    if parsed.username or parsed.password or parsed.hostname.lower() not in settings.allowed_git_host_list:
        raise ValueError("Only configured public Git hosts are allowed.")


def ingest_from_url(github_url: str) -> str:
    _validate_git_url(github_url)
    tmp = tempfile.mkdtemp()
    try:
        git.Repo.clone_from(github_url, tmp, depth=1, multi_options=["--no-tags"])
    except Exception as e:
        shutil.rmtree(tmp)
        raise ValueError(f"Failed to clone repo: {e}")
    return tmp


def ingest_from_zip(zip_path: str) -> str:
    tmp = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            settings = get_settings()
            members = z.infolist()
            total_uncompressed = sum(member.file_size for member in members)
            if len(members) > settings.max_zip_members:
                raise ValueError("ZIP contains too many files.")
            if total_uncompressed > settings.max_zip_uncompressed_bytes:
                raise ValueError("ZIP expands beyond the allowed size.")

            destination_root = Path(tmp).resolve()
            for member in members:
                member_path = (destination_root / member.filename).resolve()
                if member_path != destination_root and destination_root not in member_path.parents:
                    raise ValueError("ZIP contains an unsafe path.")
                if stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError("ZIP symbolic links are not allowed.")
            z.extractall(tmp)
    except Exception as e:
        shutil.rmtree(tmp)
        raise ValueError(f"Failed to extract ZIP: {e}")
    return tmp


def walk_repo(root: str) -> list:
    settings = get_settings()
    files = []
    for path in Path(root).rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in ALL_SUPPORTED and path.name not in {"Dockerfile", "Makefile"}:
            continue
        if path.name in SKIP_FILES:
            continue
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if ".min." in path.name:
            continue
        if path.stat().st_size > settings.max_file_bytes:
            continue
        files.append(path)
        if len(files) > settings.max_files_per_repo:
            raise ValueError("Repository contains too many supported files.")
    return files


def cleanup(path: str):
    shutil.rmtree(path, ignore_errors=True)
