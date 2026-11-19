"""Redis-backed worker entry point."""

import json
import os
import shutil
import time

import redis

from app.core.config import get_settings
from app.routes.ingest import _run_url_job, _run_zip_job


def run_worker() -> None:
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required to run the worker.")
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    for raw in client.lrange("repolens:processing", 0, -1):
        client.lrem("repolens:processing", 1, raw)
        client.rpush("repolens:queue", raw)

    while True:
        raw = client.brpoplpush(
            "repolens:queue",
            "repolens:processing",
            timeout=5,
        )
        if not raw:
            continue
        item = json.loads(raw)
        job_id = item["job_id"]
        try:
            if item["task"] == "url":
                _run_url_job(job_id, item["payload"]["url"])
            elif item["task"] == "zip":
                _run_zip_job(
                    job_id,
                    item["payload"]["zip_path"],
                    item["payload"]["upload_dir"],
                )
            else:
                raise ValueError(f"Unknown task: {item['task']}")
            client.lrem("repolens:processing", 1, raw)
        except Exception as exc:
            attempt = item.get("attempt", 0) + 1
            client.lrem("repolens:processing", 1, raw)
            if attempt < 3:
                item["attempt"] = attempt
                time.sleep(2 ** attempt)
                client.rpush("repolens:queue", json.dumps(item))
            else:
                from app.services.jobs import update_job
                update_job(
                    job_id,
                    status="failed",
                    phase="Analysis failed",
                    error=str(exc),
                )


if __name__ == "__main__":
    run_worker()
