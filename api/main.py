"""FastAPI app: lifespan runs `init_db` on the served DB (refuses to start if migrations can't apply), CORS, `db/errors.py` → HTTP handlers, `/health`, routers."""

import sqlite3
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from pydantic import TypeAdapter
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.deps import db_path, get_db
from api.schemas.errors import ErrorEnvelope
from api.validation import validation_envelope
from api.routers import (
    adjustments,
    audit,
    catalog,
    categories,
    distributions,
    expenses,
    materials,
    orders,
    packaging,
    partners,
    payment_methods,
    postage,
    production,
    products,
    purchases,
    recipes,
    reports,
    settings,
    settlements,
    suppliers,
)
from db.connection import init_db
from db.errors import AppError, ConflictError, ErrorCode, InsufficientStockError, NotFoundError, ValidationError


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bring the database up to date before serving any request.

    Pending migrations are applied (init_db backs the file up first). If that
    fails — a broken migration, or an applied file whose content changed — the
    server refuses to start rather than run against a half-migrated schema
    and 500 on every request.
    """
    path = db_path()
    try:
        init_db(path)
    except Exception as exc:
        raise RuntimeError(
            f"Could not apply database migrations to {path}; refusing to start: {exc}"
        ) from exc
    yield


# App errors (db/errors.py) share one body. Declared for 400/404/409/422 so the
# ErrorEnvelope / ErrorCode schemas reach the OpenAPI spec (and api-types.ts);
# 422 is declared too: db/ ValidationErrors and request-shape errors (api/validation.py) both answer it with an ErrorEnvelope.
_APP_ERROR_RESPONSES = {
    status: {"model": ErrorEnvelope, "description": "App error (see ErrorBody.code)"}
    for status in (400, 404, 409, 422)
}

app = FastAPI(title="Rebel Store Manager API", lifespan=lifespan, responses=_APP_ERROR_RESPONSES)


def _openapi_with_error_code() -> dict:
    """The default schema plus the ErrorCode enum as a named component: the per-code error bodies
    (api/schemas/errors.py) use Literals, so nothing references the enum, but clients type `code` with it."""
    if app.openapi_schema is None:
        schema = FastAPI.openapi(app)
        schema["components"]["schemas"]["ErrorCode"] = TypeAdapter(ErrorCode).json_schema()
        app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _openapi_with_error_code

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_response(status_code: int, exc: AppError) -> JSONResponse:
    """The ErrorEnvelope body: `code` and `details` are what clients act on."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "type": type(exc).__name__,
                "code": str(exc.code),
                "message": str(exc),
                "field": getattr(exc, "field", None),
                "details": exc.details,
            }
        },
    )


@app.exception_handler(RequestValidationError)
def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content=validation_envelope(exc.errors()))


@app.exception_handler(InsufficientStockError)
def handle_insufficient_stock_error(request: Request, exc: InsufficientStockError) -> JSONResponse:
    return _error_response(409, exc)


@app.exception_handler(ValidationError)
def handle_validation_error(request: Request, exc: ValidationError) -> JSONResponse:
    return _error_response(422, exc)


@app.exception_handler(NotFoundError)
def handle_not_found_error(request: Request, exc: NotFoundError) -> JSONResponse:
    return _error_response(404, exc)


@app.exception_handler(ConflictError)
def handle_conflict_error(request: Request, exc: ConflictError) -> JSONResponse:
    return _error_response(409, exc)


@app.exception_handler(AppError)
def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return _error_response(400, exc)


@app.get("/health")
def health(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    conn.execute("SELECT 1")
    return {"status": "ok", "db": "ok"}


app.include_router(products.router)
app.include_router(recipes.router)
app.include_router(materials.router)
app.include_router(production.router)
app.include_router(orders.router)
app.include_router(suppliers.router)
app.include_router(purchases.router)
app.include_router(adjustments.router)
app.include_router(expenses.router)
app.include_router(packaging.router)
app.include_router(postage.router)
app.include_router(partners.router)
app.include_router(distributions.router)
app.include_router(settings.router)
app.include_router(reports.router)
app.include_router(catalog.router)
app.include_router(categories.router)
app.include_router(payment_methods.router)
app.include_router(settlements.router)
app.include_router(audit.router)
