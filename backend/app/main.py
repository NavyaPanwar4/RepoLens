from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import ingest, ask
from app.core.config import get_settings
from fastapi import Request
from fastapi.responses import JSONResponse
from app.services.deployment import validate_deployment

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router, prefix="/api")
app.include_router(ask.router,    prefix="/api")


@app.middleware("http")
async def optional_api_key(request: Request, call_next):
    expected = settings.api_key_list
    if expected:
        public_paths = {"/health", "/docs", "/openapi.json", "/redoc"}
        is_public_share = request.url.path.startswith("/api/shared/")
        is_public_webhook = request.url.path == "/api/github/webhooks/github"
        if request.url.path not in public_paths and not is_public_share and not is_public_webhook:
            supplied = request.headers.get("x-api-key")
            if supplied not in expected:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "A valid X-API-Key header is required."},
                )
    return await call_next(request)

@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
def readiness():
    data_ready = settings.data_dir.is_dir()
    chroma_ready = settings.chroma_path.is_dir()
    redis_ready = True
    if settings.redis_url:
        try:
            import redis
            client = redis.Redis.from_url(settings.redis_url, socket_timeout=1)
            redis_ready = client.ping()
        except Exception:
            redis_ready = False
    ready = data_ready and chroma_ready and redis_ready
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "data": data_ready,
            "chroma": chroma_ready,
            "redis": redis_ready,
        },
    )


@app.get("/deployment")
def deployment_status():
    return validate_deployment()
