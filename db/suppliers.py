"""Supplier CRUD."""

import contextlib
import sqlite3

from db.audit import audited
from db.connection import transaction
from db.errors import ErrorCode, NotFoundError, ValidationError
from db.name_keys import duplicate_guard
from db.names import name_key, stored_form

UPDATABLE_FIELDS = ("name", "phone", "email", "website", "notes")


def _validate_name(name: str) -> str:
    stripped = stored_form(name)
    if not stripped:
        raise ValidationError("name is required and cannot be empty", field="name")
    return stripped


@audited()
def add_supplier(
    conn: sqlite3.Connection,
    name: str,
    phone: str | None = None,
    email: str | None = None,
    website: str | None = None,
    notes: str | None = None,
) -> int:
    validated_name = _validate_name(name)

    with duplicate_guard(conn, "suppliers", validated_name):
        with transaction(conn):
            cursor = conn.execute(
                """
                INSERT INTO suppliers (name, name_key, phone, email, website, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (validated_name, name_key(validated_name), phone, email, website, notes),
            )
    return cursor.lastrowid


def list_suppliers(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def get_supplier(conn: sqlite3.Connection, supplier_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM suppliers WHERE id = ?", (supplier_id,)
    ).fetchone()
    return dict(row) if row is not None else None


@audited()
def update_supplier(conn: sqlite3.Connection, supplier_id: int, **fields) -> None:
    if get_supplier(conn, supplier_id) is None:
        raise NotFoundError(
            f"Supplier with id {supplier_id} does not exist",
            code=ErrorCode.SUPPLIER_NOT_FOUND,
            details={"supplier_id": supplier_id},
        )

    updates: list[str] = []
    params: list = []
    new_name: str | None = None

    for field_name, value in fields.items():
        if field_name not in UPDATABLE_FIELDS:
            raise ValidationError(f"Unknown field '{field_name}'", field=field_name)
        if field_name == "name":
            value = _validate_name(value)
            new_name = value
            updates.append("name_key = ?")
            params.append(name_key(value))
        updates.append(f"{field_name} = ?")
        params.append(value)

    if not updates:
        return

    params.append(supplier_id)
    guard = (
        duplicate_guard(conn, "suppliers", new_name, exclude_id=supplier_id)
        if new_name is not None
        else contextlib.nullcontext()
    )
    with guard:
        with transaction(conn):
            conn.execute(
                f"UPDATE suppliers SET {', '.join(updates)} WHERE id = ?",
                params,
            )
