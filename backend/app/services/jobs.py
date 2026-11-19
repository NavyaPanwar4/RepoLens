"""Thread-safe, file-backed analysis job tracking."""

from datetime import UTC, datetime
import json
from threading import Lock
from uuid import uuid4
from app.core.config import get_settings

_lock = Lock()


def _jobs_file():
    return get_settings().data_dir / "jobs.json"


def _redis():
    url = get_settings().redis_url
    if not url:
        return None
    try:
        import redis
        return redis.Redis.from_url(url, decode_responses=True)
    except Exception:
        return None


def _load_jobs() -> dict[str, dict]:
    path = _jobs_file()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_jobs(jobs: dict[str, dict]) -> None:
    path = _jobs_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(jobs, indent=2), encoding="utf-8")
    temporary.replace(path)


def create_job() -> dict:
    job = {
        "job_id": uuid4().hex,
        "status": "queued",
        "phase": "Queued for analysis",
        "created_at": datetime.now(UTC).isoformat(),
        "result": None,
        "error": None,
    }
    redis_client = _redis()
    if redis_client:
        redis_client.hset("repolens:job", job["job_id"], json.dumps(job))
        redis_client.expire("repolens:job", 30 * 24 * 60 * 60)
    else:
        with _lock:
            jobs = _load_jobs()
            jobs[job["job_id"]] = job
            _save_jobs(jobs)
    return job.copy()


def update_job(job_id: str, *, status: str, phase: str, result: dict | None = None, error: str | None = None) -> None:
    redis_client = _redis()
    if redis_client:
        raw = redis_client.hget("repolens:job", job_id)
        if not raw:
            return
        job = json.loads(raw)
        job.update({"status": status, "phase": phase, "result": result, "error": error})
        if status in {"completed", "failed"}:
            job["finished_at"] = datetime.now(UTC).isoformat()
        redis_client.hset("repolens:job", job_id, json.dumps(job))
        redis_client.expire("repolens:job", 30 * 24 * 60 * 60)
        return
    with _lock:
        jobs = _load_jobs()
        job = jobs.get(job_id)
        if not job:
            return
        job.update({"status": status, "phase": phase, "result": result, "error": error})
        if status in {"completed", "failed"}:
            job["finished_at"] = datetime.now(UTC).isoformat()
        _save_jobs(jobs)


def get_job(job_id: str) -> dict | None:
    redis_client = _redis()
    if redis_client:
        raw = redis_client.hget("repolens:job", job_id)
        return json.loads(raw) if raw else None
    with _lock:
        job = _load_jobs().get(job_id)
        return job.copy() if job else None
