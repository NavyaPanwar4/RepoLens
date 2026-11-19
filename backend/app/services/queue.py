"""Redis queue dispatch with an in-process FastAPI fallback."""

import json
from app.core.config import get_settings


def enqueue(job_id: str, task: str, payload: dict) -> bool:
    settings = get_settings()
    if not settings.redis_url:
        return False
    try:
        import redis
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        client.rpush(
            "repolens:queue",
            json.dumps({
                "job_id": job_id,
                "task": task,
                "payload": payload,
                "attempt": 0,
            }),
        )
        return True
    except Exception:
        return False
