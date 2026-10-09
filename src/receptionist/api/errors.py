
import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger()


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    error_id = id(exc)
    logger.error(
        "unhandled_exception",
        error_id=error_id,
        error=str(exc),
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "error_id": error_id,
        },
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.warning(
        "validation error",
        error=str(exc),
        path=request.url.path,
    )
    return JSONResponse(
        status_code=422,
        content={"error": "Validation error", "detail": str(exc)},
    )
