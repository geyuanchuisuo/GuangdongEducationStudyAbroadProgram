import time
from typing import Any

from pydantic import BaseModel


class ResponseModel(BaseModel):
    code: int
    message: str
    data: Any = None
    timestamp: int


def success_response(data: Any = None, message: str = "success") -> dict:
    return {
        "code": 200,
        "message": message,
        "data": data,
        "timestamp": int(time.time()),
    }


def error_response(code: int, message: str, data: Any = None) -> dict:
    return {
        "code": code,
        "message": message,
        "data": data,
        "timestamp": int(time.time()),
    }
