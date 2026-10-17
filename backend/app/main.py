"""FastAPI Application entrypoint, middleware, exception handlers, and routing."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.core.errors import AppException, app_exception_handler, create_error_response
from backend.app.db.init_db import create_tables
from backend.app.api.v1.api import api_router

logger = logging.getLogger("matrix_intel")
logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown hooks."""
    logger.info("Initializing MATRIX Intel database schema...")
    try:
        create_tables()
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.error(f"Failed to initialize database tables: {exc}")

    yield

    logger.info("Shutting down MATRIX Intel API.")


def create_application() -> FastAPI:
    """Application factory initializing FastAPI with configurations and routers."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "MATRIX Intel API: Predictive cybercrime analytics and cash-withdrawal location forecasting. "
            "Built for investigative prioritization on IBM LinuxONE Community Cloud."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 1. CORS Middleware configuration with explicit allowed origins
    allowed_origins = settings.cors_origins_list
    logger.info(f"Configuring CORS with allowed origins: {allowed_origins}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
    )

    # 2. Custom Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Format 422 Request Validation errors into consistent error payload."""
        return create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            detail="Request validation failed. Check request body, path, or query parameters.",
            path=str(request.url.path),
            meta={"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch unhandled internal errors without leaking internals in production."""
        logger.exception(f"Unhandled error processing request: {exc}")
        detail_msg = str(exc) if settings.DEBUG else "An unexpected internal server error occurred."
        return create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INTERNAL_SERVER_ERROR",
            detail=detail_msg,
            path=str(request.url.path),
        )

    # 3. Root informational endpoint
    @app.get(
        "/",
        tags=["Root"],
        summary="API Root Information",
        description="Provides API metadata and links to OpenAPI documentation.",
    )
    def root() -> dict:
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "docs": "/docs",
            "redoc": "/redoc",
            "api_v1": settings.API_V1_PREFIX,
            "health": f"{settings.API_V1_PREFIX}/health",
        }

    # 4. Include Version 1 API routers
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
