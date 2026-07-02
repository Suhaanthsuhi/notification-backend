import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import sqlalchemy as sa

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.cache import redis_client
from app.core.middleware import RequestIDMiddleware
from app.core.logger import configure_logging, get_logger
from app.core.db import engine
from app.dependencies.auth import jwt_service, _blacklist

from axiom.db.base import BaseSchema
from axiom.auth.middleware import AuthMiddleware
from axiom.cache.rate_limiter import RateLimiter

settings = get_settings()
logger = get_logger(__name__)

_PUBLIC_PATHS = [
    "/health",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/request-otp",
    "/api/v1/auth/verify-otp",
]

_rate_limiter: RateLimiter | None = None
if redis_client and settings.env.lower() != "test":
    _rate_limiter = RateLimiter(redis_client, max_requests=100, window_seconds=60)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()

    # Tables are auto-created on every startup. create_all creates MISSING tables
    # only — it NEVER alters an existing one — so adding a new domain is friction
    # free (just add the model and restart), while ALTERing an existing table
    # (e.g. a new column on a populated table) is handled by an Alembic migration.
    # See README → Schema Migrations.
    async with engine.connect() as conn:
        async with conn.begin():
            if settings.db_supports_schema and settings.db_schema:
                await conn.execute(
                    sa.text(f'CREATE SCHEMA IF NOT EXISTS "{settings.db_schema}"')
                )
            await conn.run_sync(BaseSchema.metadata.create_all)

    yield

    await engine.dispose()
    if redis_client:
        await redis_client.close()

app = FastAPI(
    title=settings.service_name, 
    version="0.1.0"
)

@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    AuthMiddleware,
    jwt_secret=jwt_service,
    required=False,
    blacklist=_blacklist,
    rate_limiter=_rate_limiter,
    exclude_paths=_PUBLIC_PATHS,
)

# Must be added last so it is outermost — runs before AuthMiddleware and stamps
# X-Request-ID on every response including ones short-circuited by auth.
app.add_middleware(RequestIDMiddleware)

@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "online",
        "service": settings.service_name,
        "environment": settings.env,
    }