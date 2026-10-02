import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.categories import (
    CategoryCreate,
    CategoryKind,
    CategoryOut,
    CategoryTreeOut,
    CategoryUpdate,
)
from db.categories import (
    create_category,
    deactivate_category,
    get_category,
    list_categories,
    list_category_tree,
    reactivate_category,
    update_category,
)
from db.errors import NotFoundError

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=list[CategoryOut])
def read_categories(
    kind: CategoryKind,
    parent_id: int | None = None,
    active_only: bool = True,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[CategoryOut]:
    """Top-level categories of *kind*, or parent_id's subcategories when given."""
    rows = list_categories(conn, kind, parent_id=parent_id, include_inactive=not active_only)
    return [CategoryOut.model_validate(c) for c in rows]


@router.get("/categories/tree", response_model=list[CategoryTreeOut])
def read_category_tree(
    kind: CategoryKind,
    active_only: bool = True,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[CategoryTreeOut]:
    rows = list_category_tree(conn, kind, include_inactive=not active_only)
    return [CategoryTreeOut.model_validate(c) for c in rows]


@router.get("/categories/{category_id}", response_model=CategoryOut)
def read_category(
    category_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> CategoryOut:
    return build_category(conn, category_id)


def build_category(conn: sqlite3.Connection, category_id: int) -> CategoryOut:
    category = get_category(conn, category_id)
    if category is None:
        raise NotFoundError(f"Category with id {category_id} does not exist")
    return CategoryOut.model_validate(category)


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create(body: CategoryCreate, conn: sqlite3.Connection = Depends(get_db)) -> CategoryOut:
    category_id = create_category(conn, body.kind, body.name, parent_id=body.parent_id)
    return build_category(conn, category_id)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update(
    category_id: int,
    body: CategoryUpdate,
    conn: sqlite3.Connection = Depends(get_db),
) -> CategoryOut:
    """Only fields present in the body change."""
    update_category(conn, category_id, **body.model_dump(exclude_unset=True))
    return build_category(conn, category_id)


@router.post("/categories/{category_id}/deactivate", response_model=CategoryOut)
def deactivate(category_id: int, conn: sqlite3.Connection = Depends(get_db)) -> CategoryOut:
    deactivate_category(conn, category_id)
    return build_category(conn, category_id)


@router.post("/categories/{category_id}/reactivate", response_model=CategoryOut)
def reactivate(category_id: int, conn: sqlite3.Connection = Depends(get_db)) -> CategoryOut:
    reactivate_category(conn, category_id)
    return build_category(conn, category_id)
