"""FastAPI app: the lifespan (api/startup.py) runs `init_db` on the served DB (refuses to start if migrations can't apply) and makes the daily backup, CORS, `db/errors.py` → HTTP handlers, `/health`, routers."""

import logging
import sqlite3

from fastapi import Depends, FastAPI, Request
from pydantic import TypeAdapter
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.deps import get_db
from api.logsetup import sanitized_traceback
from api.startup import service_lifespan
from api.schemas.errors import ErrorEnvelope
from api.validation import validation_envelope
from api.routers import (
    adjustments,
    audit,
    backups,
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
    stocktake,
    supplier_payments,
    suppliers,
)
from db.errors import AppError, BackupError, ConflictError, ErrorCode, InsufficientStockError, NotFoundError, ValidationError


# App errors (db/errors.py) share one body. Declared for 400/404/409/422 so the
# ErrorEnvelope / ErrorCode schemas reach the OpenAPI spec (and api-types.ts);
# 422 is declared too: db/ ValidationErrors and request-shape errors (api/validation.py) both answer it with an ErrorEnvelope.
_APP_ERROR_RESPONSES = {
    status: {"model": ErrorEnvelope, "description": "App error (see ErrorBody.code)"}
    for status in (400, 404, 409, 422)
}

app_log = logging.getLogger("rebel.app")

app = FastAPI(title="Rebel Store Manager API", lifespan=service_lifespan, responses=_APP_ERROR_RESPONSES)


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


def _log_error(request: Request | None, status_code: int, code: str) -> None:
    """One log line per handled error: code, status and path. Never the message, the query string or the body."""
    where = request.url.path if request is not None else "-"
    level = logging.ERROR if status_code >= 500 else logging.INFO
    app_log.log(level, "handled error code=%s status=%s path=%s", code, status_code, where)


def _error_response(status_code: int, exc: AppError, request: Request | None = None) -> JSONResponse:
    """The ErrorEnvelope body: `code` and `details` are what clients act on."""
    _log_error(request, status_code, str(exc.code))
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
    body = validation_envelope(exc.errors())
    _log_error(request, 422, body["error"]["code"])
    return JSONResponse(status_code=422, content=body)


@app.exception_handler(InsufficientStockError)
def handle_insufficient_stock_error(request: Request, exc: InsufficientStockError) -> JSONResponse:
    return _error_response(409, exc, request)


@app.exception_handler(ValidationError)
def handle_validation_error(request: Request, exc: ValidationError) -> JSONResponse:
    return _error_response(422, exc, request)


@app.exception_handler(NotFoundError)
def handle_not_found_error(request: Request, exc: NotFoundError) -> JSONResponse:
    return _error_response(404, exc, request)


@app.exception_handler(BackupError)
def handle_backup_error(request: Request, exc: BackupError) -> JSONResponse:
    # a server-side failure (disk full, locked database …), not bad input: 500 with the usual envelope
    return _error_response(500, exc, request)


@app.exception_handler(ConflictError)
def handle_conflict_error(request: Request, exc: ConflictError) -> JSONResponse:
    return _error_response(409, exc, request)


@app.exception_handler(AppError)
def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return _error_response(400, exc, request)


@app.middleware("http")
async def catch_unexpected_errors(request: Request, call_next):
    """Anything no handler claimed becomes a plain 500 envelope, logged with a sanitised traceback (class and frames, never the
    exception's message: it can hold a name or an amount). Nothing is re-raised, so the server prints no traceback either."""
    try:
        return await call_next(request)
    except Exception as exc:
        app_log.error("unexpected error status=500 path=%s\n%s", request.url.path, sanitized_traceback(exc))
        return JSONResponse(
            status_code=500,
            content={"error": {"type": "InternalError", "code": "APP_ERROR", "message": "Internal error", "field": None, "details": {}}},
        )


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
app.include_router(supplier_payments.router)
app.include_router(adjustments.router)
app.include_router(stocktake.router)
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
app.include_router(backups.router)
