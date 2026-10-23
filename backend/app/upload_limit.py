from fastapi import HTTPException
from starlette.responses import JSONResponse

from app.config import get_settings


class UploadLimitMiddleware:
    """Bound multipart request consumption as well as file storage writes."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].endswith("/materials/upload"):
            return await self.app(scope, receive, send)
        limit = get_settings().max_upload_size_bytes + 64 * 1024
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = 0
        if length > limit:
            return await JSONResponse({"detail": "Upload exceeds request limit"}, status_code=413)(
                scope, receive, send
            )
        consumed = 0

        async def limited_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get("body", b""))
            if consumed > limit:
                raise HTTPException(413, "Upload exceeds request limit")
            return message

        return await self.app(scope, limited_receive, send)
