"""Global exception handlers for consistent API error responses."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import logger
from app.exceptions.custom_exceptions import GeospatialAPIException


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI application instance."""

    @app.exception_handler(GeospatialAPIException)
    async def handle_geospatial_api_exception(
        request: Request, exc: GeospatialAPIException
    ) -> JSONResponse:
        logger.warning(
            "Domain error [%s]: %s (path=%s)",
            exc.code,
            exc.message,
            request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_starlette_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code_map = {
            400: "INVALID_REQUEST",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            413: "FILE_TOO_LARGE",
            422: "UNPROCESSABLE_ENTITY",
            500: "INTERNAL_SERVER_ERROR",
        }
        code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
        logger.warning("HTTP error [%d]: %s (path=%s)", exc.status_code, exc.detail, request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": str(exc.detail),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first_error = exc.errors()[0] if exc.errors() else {"msg": "Validation failed"}
        msg = f"Invalid request parameters: {first_error.get('msg', 'Validation failed')}"
        logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": msg,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # Crucial security requirement: Log the full traceback internally, never return it to client.
        logger.exception("Unhandled server exception on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred while processing the request.",
                }
            },
        )
