"""
app/main.py
FastAPI application entrypoint for the Remote Patient Health Monitoring System.

DISCLAIMER:
Educational research prototype only. Not a certified medical device.
Its readings and automated outputs are not intended for clinical diagnosis,
emergency monitoring, or treatment decisions.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.database.session import init_db

# Configure structured JSON logging
configure_logging()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle handler."""
    logger.info("Initializing database schemas...")
    await init_db()
    logger.info("Database initialization complete.")
    logger.info(
        "Remote Health Monitoring Server v%s ready on port 8000.", settings.APP_VERSION
    )
    yield
    logger.info("Server shutting down.")


app = FastAPI(
    title="Remote Patient Health Monitoring API",
    description="""
# Remote Patient Health Monitoring API

Professional REST API for remote patient health monitoring in rural areas.

### Modalities:
- **ECG (AD8232)**: Single-lead numerical sample batches in ADC counts.
- **Heart Rate & SpO₂ (MAX30102)**: Pulse oximetry.
- **Body Temperature (DS18B20)**: Digital temperature sensing.
- **Cellular Ingestion (SIM800L 2G/GPRS)**: Duplicate-safe, retry-compatible JSON ingestion.

### Authentication:
- **Doctor Endpoints**: JWT Bearer token via `POST /api/v1/auth/login`.
- **Device Telemetry**: API Key via `X-Device-API-Key` header on `POST /api/v1/ingest`.

---
*Notice: Educational research prototype. Not certified for clinical medical use.*
    """,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration (supports local dev and cloud deployments)
_cors_origins = [settings.CORS_ORIGINS] if isinstance(settings.CORS_ORIGINS, str) else list(settings.CORS_ORIGINS)
if "*" in _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

MAX_BODY_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB request-body limit


@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    """Enforce a strict 2 MB payload size limit to prevent resource exhaustion."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_SIZE_BYTES:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": "Request body exceeds maximum allowed limit of 2 MB."},
                )
        except ValueError:
            pass
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Format Pydantic validation errors clearly."""
    formatted_errors = []
    for err in exc.errors():
        field_path = " -> ".join(str(loc) for loc in err.get("loc", []))
        formatted_errors.append(
            {
                "field": field_path,
                "message": err.get("msg", "Validation error"),
                "type": err.get("type", "value_error"),
            }
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": formatted_errors},
    )


# Register v1 router
app.include_router(api_router)


# Health check endpoints
@app.get("/health", tags=["System"])
@app.get("/api/v1/health", tags=["System"])
async def health_check() -> dict:
    """Public health-check endpoint for cloud monitoring probes (Render, UptimeRobot, etc.)."""
    db_type = "sqlite" if settings.DATABASE_URL.startswith("sqlite") else "postgresql"
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "database": db_type,
        "service": "remote-patient-health-monitor",
        "disclaimer": "Educational research prototype only.",
    }


@app.get("/", include_in_schema=False)
async def root_redirect() -> dict:
    """Root redirect pointer."""
    return {
        "name": "Remote Patient Health Monitoring Server",
        "docs": "/docs",
        "version": settings.APP_VERSION,
    }
