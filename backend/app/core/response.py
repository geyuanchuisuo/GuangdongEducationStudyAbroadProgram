import time
from typing import Any

from pydantic import BaseModel


class ResponseModel(BaseModel):
    code: int
    message: str
    data: Any = None
    traceId: str = ""
    timestamp: int


def success_response(data: Any = None, message: str = "success", trace_id: str = "") -> dict:
    return {
        "code": 200,
        "message": message,
        "data": data,
        "traceId": trace_id,
        "timestamp": int(time.time()),
    }


def error_response(code: int, message: str, data: Any = None, trace_id: str = "") -> dict:
    return {
        "code": code,
        "message": message,
        "data": data,
        "traceId": trace_id,
        "timestamp": int(time.time()),
    }
