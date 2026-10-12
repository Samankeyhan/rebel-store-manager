"""User-editable categories: two trees by `kind` (PRODUCT / MATERIAL), two levels (top-level and an optional subcategory of the same kind).
Deactivate is refused while any product/material uses the category or it has active subcategories. Reactivate is refused under an inactive parent.
`validate_assignable`: an item's category must be the right kind, active, and have no active subcategories (once split, new items go in a subcategory)."""

import sqlite3

from db.audit import audited
from db.connection import transaction
from db.errors import ConflictError, ErrorCode, NotFoundError, ValidationError
from db.name_keys import duplicate_guard
from db.names import name_key, stored_form

VALID_KINDS = ("PRODUCT", "MATERIAL")

_SELECT = """
    SELECT c.*, p.name AS parent_name
    FROM categories c
    LEFT JOIN categories p ON p.id = c.parent_id
"""


def _validate_kind(kind: str) -> None:
    if kind not in VALID_KINDS:
        raise ValidationError(
            f"Invalid kind '{kind}'. Must be one of: {', '.join(VALID_KINDS)}",
            field="kind",
        )


def _clean_name(name: str) -> str:
    stripped = stored_form(name) if name is not None else ""
    if not stripped:
        raise ValidationError("Category name must not be empty", field="name")
    return stripped


def _require(conn: sqlite3.Connection, category_id: int) -> dict:
    category = get_category(conn, category_id)
    if category is None:
        raise NotFoundError(f"Category with id {category_id} does not exist")
    return category


def _has_active_children(conn: sqlite3.Connection, category_id: int) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM categories WHERE parent_id = ? AND is_active = 1 LIMIT 1",
            (category_id,),
        ).fetchone()
        is not None
    )


def get_category(conn: sqlite3.Connection, category_id: int) -> dict | None:
    row = conn.execute(f"{_SELECT} WHERE c.id = ?", (category_id,)).fetchone()
    return dict(row) if row is not None else None


def list_categories(
    conn: sqlite3.Connection,
    kind: str,
    parent_id: int | None = None,
    include_inactive: bool = False,
) -> list[dict]:
    """Top-level categories of *kind* when parent_id is None, else parent_id's children."""
    _validate_kind(kind)
    query = f"{_SELECT} WHERE c.kind = ?"
    params: list = [kind]
    if parent_id is None:
        query += " AND c.parent_id IS NULL"
    else:
        query += " AND c.parent_id = ?"
        params.append(parent_id)
    if not include_inactive:
        query += " AND c.is_active = 1"
    query += " ORDER BY c.name"
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def list_category_tree(
    conn: sqlite3.Connection, kind: str, include_inactive: bool = False
) -> list[dict]:
    """Top-level categories of *kind*, each with a `children` list."""
    tops = list_categories(conn, kind, include_inactive=include_inactive)
    for top in tops:
        top["children"] = list_categories(
            conn, kind, parent_id=top["id"], include_inactive=include_inactive
        )
    return tops


@audited()
def create_category(
    conn: sqlite3.Connection, kind: str, name: str, parent_id: int | None = None
) -> int:
    _validate_kind(kind)
    name = _clean_name(name)
    if parent_id is not None:
        parent = get_category(conn, parent_id)
        if parent is None:
            raise ValidationError(
                f"Parent category with id {parent_id} does not exist", field="parent_id"
            )
        if parent["parent_id"] is not None:
            raise ValidationError(
                f"'{parent['name']}' is already a subcategory; "
                f"subcategories cannot have subcategories.",
                field="parent_id",
            )
        if parent["kind"] != kind:
            raise ValidationError(
                f"Parent category '{parent['name']}' is a {parent['kind']} category, "
                f"not {kind}.",
                field="parent_id",
            )
        if not parent["is_active"]:
            raise ValidationError(
                f"Parent category '{parent['name']}' is inactive.",
                field="parent_id",
                code=ErrorCode.CATEGORY_PARENT_INACTIVE,
            )
    with duplicate_guard(
        conn, "categories", name, {"kind": kind, "parent_id": parent_id},
        code=ErrorCode.CATEGORY_DUPLICATE_NAME,
    ):
        with transaction(conn):
            cursor = conn.execute(
                "INSERT INTO categories (kind, name, name_key, parent_id) VALUES (?, ?, ?, ?)",
                (kind, name, name_key(name), parent_id),
            )
    return cursor.lastrowid


@audited()
def update_category(
    conn: sqlite3.Connection,
    category_id: int,
    name: str | None = None,
    is_active: bool | None = None,
) -> None:
    """Rename and/or (de)activate. Kind and parent never change.

    is_active goes through deactivate_category / reactivate_category, so the
    same refusals apply. Both changes happen in one transaction.
    """
    category = _require(conn, category_id)
    with transaction(conn):
        if name is not None:
            name = _clean_name(name)
            with duplicate_guard(
                conn, "categories", name,
                {"kind": category["kind"], "parent_id": category["parent_id"]},
                exclude_id=category_id, code=ErrorCode.CATEGORY_DUPLICATE_NAME,
            ):
                conn.execute(
                    "UPDATE categories SET name = ?, name_key = ? WHERE id = ?",
                    (name, name_key(name), category_id),
                )
        if is_active is True:
            reactivate_category(conn, category_id)
        elif is_active is False:
            deactivate_category(conn, category_id)


@audited()
def deactivate_category(conn: sqlite3.Connection, category_id: int) -> None:
    """Refuses while any product/material (active or not) uses it, or it has active children."""
    category = _require(conn, category_id)
    products = conn.execute(
        "SELECT COUNT(*) FROM products WHERE category_id = ?", (category_id,)
    ).fetchone()[0]
    materials = conn.execute(
        "SELECT COUNT(*) FROM materials WHERE category_id = ?", (category_id,)
    ).fetchone()[0]
    if products or materials:
        used_by = products if category["kind"] == "PRODUCT" else materials
        noun = "product(s)" if category["kind"] == "PRODUCT" else "material(s)"
        raise ConflictError(
            f"Category '{category['name']}' is used by {used_by} {noun}; "
            f"move them to another category before deactivating it.",
            code=ErrorCode.CATEGORY_IN_USE,
            details={"item_count": used_by},
        )
    if _has_active_children(conn, category_id):
        raise ConflictError(
            f"Category '{category['name']}' has active subcategories; "
            f"deactivate them first.",
            code=ErrorCode.CATEGORY_HAS_SUBCATEGORIES,
        )
    with transaction(conn):
        conn.execute("UPDATE categories SET is_active = 0 WHERE id = ?", (category_id,))


@audited()
def reactivate_category(conn: sqlite3.Connection, category_id: int) -> None:
    """Refuses for a subcategory whose parent is inactive."""
    category = _require(conn, category_id)
    if category["parent_id"] is not None:
        parent = _require(conn, category["parent_id"])
        if not parent["is_active"]:
            raise ConflictError(
                f"Parent category '{parent['name']}' is inactive; reactivate it first.",
                code=ErrorCode.CATEGORY_PARENT_INACTIVE,
            )
    with transaction(conn):
        conn.execute("UPDATE categories SET is_active = 1 WHERE id = ?", (category_id,))


def validate_assignable(conn: sqlite3.Connection, category_id: int, kind: str) -> None:
    """Raise ValidationError(field="category_id") unless an item of *kind* may use it."""
    category = get_category(conn, category_id)
    if category is None:
        raise ValidationError(
            f"Category with id {category_id} does not exist", field="category_id"
        )
    if category["kind"] != kind:
        raise ValidationError(
            f"Category '{category['name']}' is a {category['kind']} category, not {kind}.",
            field="category_id",
        )
    if not category["is_active"]:
        raise ValidationError(
            f"Category '{category['name']}' is inactive.", field="category_id"
        )
    if _has_active_children(conn, category_id):
        raise ValidationError(
            f"Category '{category['name']}' has subcategories; choose one of them.",
            field="category_id",
            code=ErrorCode.CATEGORY_HAS_SUBCATEGORIES,
        )
