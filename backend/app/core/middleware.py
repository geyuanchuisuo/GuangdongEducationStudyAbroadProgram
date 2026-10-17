import json
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logger import logger


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start_time = time.time()
        response: Response = await call_next(request)
        duration = round((time.time() - start_time) * 1000, 2)

        logger.info(
            "[%s] %s %s %s %.2fms",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )

        response.headers["X-Request-ID"] = request_id

        if response.headers.get("content-type", "").startswith("application/json"):
            body_chunks = []
            async for chunk in response.body_iterator:
                body_chunks.append(chunk)
            body = b"".join(body_chunks)
            try:
                data = json.loads(body)
                if isinstance(data, dict) and "traceId" not in data:
                    data["traceId"] = request_id
                    new_body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                    return Response(
                        content=new_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type="application/json",
                    )
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            return Response(content=body, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)

        return response
