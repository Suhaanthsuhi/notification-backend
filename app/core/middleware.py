import json
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

_NORMALIZE_STATUSES = {401, 403, 429}
_PRESERVE_HEADERS = {"retry-after", "www-authenticate"}


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Outermost middleware: stamps X-Request-ID on every response and
    normalizes bare {"detail": ...} auth-middleware error bodies into the
    standard ApiResponse envelope so clients always see a consistent shape."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        if (
            response.status_code in _NORMALIZE_STATUSES
            and "application/json" in response.headers.get("content-type", "")
        ):
            raw = b""
            async for chunk in response.body_iterator:
                raw += chunk
            try:
                data = json.loads(raw)
                if "success" not in data and "detail" in data:
                    detail = data["detail"]
                    extra = {
                        k: response.headers[k]
                        for k in _PRESERVE_HEADERS
                        if k in response.headers
                    }
                    extra["X-Request-ID"] = request_id
                    return JSONResponse(
                        status_code=response.status_code,
                        content={
                            "success": False,
                            "detail": detail,
                            "error": {
                                "code": f"HTTP_{response.status_code}",
                                "message": detail if isinstance(detail, str) else "Request failed",
                            },
                        },
                        headers=extra,
                    )
            except (json.JSONDecodeError, KeyError):
                pass
            return Response(
                content=raw,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response