from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from app.core.config import settings
import logging
import traceback

logger = logging.getLogger(__name__)

class ErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            # Preserve CORS headers from original response
            if response.status_code >= 400:
                error_response = self.handle_error(response)
                # Copy CORS headers if they exist
                if hasattr(response, 'headers'):
                    for key, value in response.headers.items():
                        if key.lower().startswith('access-control'):
                            error_response.headers[key] = value
                # Ensure CORS headers are present
                self._add_cors_headers(error_response, request)
                return error_response
            return response
        except HTTPException as exc:
            response = self.handle_http_exception(exc)
            self._add_cors_headers(response, request)
            return response
        except Exception as exc:
            logger.error(f"Unhandled exception: {exc}")
            logger.error(traceback.format_exc())
            response = self.handle_unexpected_exception(exc)
            self._add_cors_headers(response, request)
            return response
    
    def _add_cors_headers(self, response: JSONResponse, request: Request):
        """Add CORS headers to response based on request origin."""
        origin = request.headers.get("origin")
        if origin and origin in settings.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"
        elif not origin:
            # If no origin header, allow all configured origins
            response.headers["Access-Control-Allow-Origin"] = settings.allowed_origins[0] if settings.allowed_origins else "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"

    def handle_error(self, response):
        return JSONResponse(
            status_code=response.status_code,
            content={"detail": getattr(response, 'body', b'').decode() if hasattr(response, 'body') else str(response)},
        )

    def handle_http_exception(self, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    def handle_unexpected_exception(self, exc):
        # Include more details in debug mode
        detail = "An unexpected error occurred."
        if hasattr(exc, '__class__'):
            detail = f"An unexpected error occurred: {exc.__class__.__name__}: {str(exc)}"
        return JSONResponse(
            status_code=500,
            content={"detail": detail},
        )