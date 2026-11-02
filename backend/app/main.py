"""FastAPI application entry point."""

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import init_db
from app.routers import chat, documents, health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize storage and report lazy model downloads."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    logger.info(
        "Local embedding and reranker models load on first use; "
        "the first startup may download model files."
    )
    yield


app = FastAPI(title="DocMind API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_timing(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Log the method, path, status, and duration for each HTTP request."""
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request error: %s %s", request.method, request.url.path)
        raise
    logger.info(
        "%s %s %s %.3fs",
        request.method,
        request.url.path,
        response.status_code,
        time.perf_counter() - started,
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return a consistent JSON shape for invalid requests."""
    return JSONResponse(
        status_code=422,
        content={"error": "Invalid request", "details": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Log database failures and return a non-sensitive error."""
    logger.exception("Database operation failed", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": "Database operation failed"})


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Log unexpected failures and return a stable JSON error response."""
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


app.include_router(health.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
