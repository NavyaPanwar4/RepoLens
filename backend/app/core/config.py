from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "RepoLens API"
    environment: str = "development"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    data_dir: Path = Path("./data")
    chroma_path: Path = Path("./data/chroma")
    max_upload_bytes: int = 100 * 1024 * 1024
    max_zip_members: int = 10_000
    max_zip_uncompressed_bytes: int = 500 * 1024 * 1024
    max_files_per_repo: int = 5_000
    max_file_bytes: int = 1_000_000
    allowed_git_hosts: str = "github.com,www.github.com"
    api_keys: str = ""
    redis_url: str = ""
    github_token: str = ""
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_app_installation_id: str = ""
    github_webhook_secret: str = ""
    enable_real_scanners: bool = False
    trusted_proxy_count: int = 0
    request_timeout_seconds: int = 300

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_git_host_list(self) -> set[str]:
        return {host.strip().lower() for host in self.allowed_git_hosts.split(",") if host.strip()}

    @property
    def api_key_list(self) -> set[str]:
        return {key.strip() for key in self.api_keys.split(",") if key.strip()}


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    return settings
