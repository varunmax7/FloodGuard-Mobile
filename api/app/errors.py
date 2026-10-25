"""Error envelope per §6.4: { "error": { "code", "message", "retryable" } }."""
from fastapi import Request
from fastapi.responses import JSONResponse


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str, retryable: bool = False):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable}},
    )
