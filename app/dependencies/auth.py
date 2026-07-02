from fastapi import HTTPException, Request
from app.core.config import get_settings
from app.core.cache import redis_client
from axiom.auth import (
    AuthConfig,
    JWTService,
    RefreshTokenStore,
    TokenBlacklist,
    get_current_user as get_current_user_payload,
)
from axiom.cache.rate_limiter import RateLimiter


settings = get_settings()

auth_config = AuthConfig(secret=settings.secret_key)
jwt_service = JWTService(auth_config)

_blacklist: TokenBlacklist | None = None
_refresh_store: RefreshTokenStore | None = None

if redis_client:
    _blacklist = TokenBlacklist(redis_client)
    _refresh_store = RefreshTokenStore(redis_client)

def make_auth_rate_limit_dep(scope: str, max_requests: int, window_seconds: int = 60):
    """Returns a FastAPI dependency that rate-limits public auth endpoints by client IP."""
    async def _dep(request: Request) -> None:
        # Rate limiting requires Redis and is disabled in the test env so the
        # suite can drive the auth endpoints freely from a single client IP.
        if redis_client is None or settings.env.lower() == "test":
            return
        limiter = RateLimiter(redis_client, max_requests=max_requests, window_seconds=window_seconds)
        ip = request.client.host if request.client else "unknown"
        result = await limiter.check(ip, scope=scope)
        if not result.allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(result.retry_after)},
            )
    return _dep

async def get_jwt_service() -> JWTService:
    return jwt_service

def get_blacklist() -> TokenBlacklist | None:
    return _blacklist

def get_refresh_store() -> RefreshTokenStore | None:
    return _refresh_store

__all__ = [
    "auth_config",
    "jwt_service",
    "_blacklist",
    "_refresh_store",
    "get_jwt_service",
    "get_blacklist",
    "get_refresh_store",
    "get_current_user_payload",
    "make_auth_rate_limit_dep",
]