import sqlite3

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.deps import get_db
from api.routers import (
    adjustments,
    catalog,
    distributions,
    expenses,
    materials,
    orders,
    packaging,
    partners,
    postage,
    production,
    products,
    purchases,
    recipes,
    reports,
    settings,
    suppliers,
)
from db.errors import AppError, ConflictError, InsufficientStockError, NotFoundError, ValidationError

app = FastAPI(title="Rebel Store Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_response(status_code: int, exc: AppError, details: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "field": getattr(exc, "field", None),
                "details": details or {},
            }
        },
    )


@app.exception_handler(InsufficientStockError)
def handle_insufficient_stock_error(request: Request, exc: InsufficientStockError) -> JSONResponse:
    return _error_response(
        409,
        exc,
        details={
            "item_name": exc.item_name,
            "needed": exc.needed,
            "available": exc.available,
        },
    )


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
