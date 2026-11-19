"""Deployment environment validation."""

from app.core.config import get_settings
import os


def validate_deployment() -> dict:
    settings = get_settings()
    errors = []
    warnings = []

    if settings.environment.lower() == "production" and not settings.api_keys:
        errors.append("API_KEYS must be configured in production.")
    if settings.environment.lower() == "production" and not settings.cors_origins:
        errors.append("CORS_ORIGINS must be configured in production.")
    if settings.environment.lower() == "production" and settings.cors_origins == "*":
        errors.append("Wildcard CORS origins are not allowed in production.")
    if settings.enable_real_scanners:
        warnings.append("Real scanners are enabled; ensure scanner binaries are available.")
    if not os.getenv("GROQ_API_KEY"):
        warnings.append("GROQ_API_KEY is not configured.")
    if settings.redis_url:
        warnings.append("Redis workers are enabled.")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "environment": settings.environment,
    }
