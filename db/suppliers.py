import sqlite3

from db.connection import transaction
from db.errors import NotFoundError, ValidationError

UPDATABLE_FIELDS = ("name", "phone", "email", "website", "notes")


def _validate_name(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        raise ValidationError("name is required and cannot be empty", field="name")
    return stripped


def add_supplier(
    conn: sqlite3.Connection,
    name: str,
    phone: str | None = None,
    email: str | None = None,
    website: str | None = None,
    notes: str | None = None,
) -> int:
    validated_name = _validate_name(name)

    with transaction(conn):
        cursor = conn.execute(
            """
            INSERT INTO suppliers (name, phone, email, website, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (validated_name, phone, email, website, notes),
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


def update_supplier(conn: sqlite3.Connection, supplier_id: int, **fields) -> None:
    if get_supplier(conn, supplier_id) is None:
        raise NotFoundError(f"Supplier with id {supplier_id} does not exist")

    updates: list[str] = []
    params: list = []

    for field_name, value in fields.items():
        if field_name not in UPDATABLE_FIELDS:
            raise ValidationError(f"Unknown field '{field_name}'", field=field_name)
        if field_name == "name":
            value = _validate_name(value)
        updates.append(f"{field_name} = ?")
        params.append(value)

    if not updates:
        return

    params.append(supplier_id)
    with transaction(conn):
        conn.execute(
            f"UPDATE suppliers SET {', '.join(updates)} WHERE id = ?",
            params,
        )
