import sqlite3

from db.connection import transaction
from db.errors import NotFoundError, ValidationError


def _validate_percentage(percentage: float, field_name: str = "percentage") -> None:
    if percentage <= 0 or percentage > 100:
        raise ValidationError(
            f"{field_name} must be > 0 and <= 100, got {percentage}", field=field_name
        )


def _validate_name(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        raise ValidationError("name is required and cannot be empty", field="name")
    return stripped


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def add_partner(
    conn: sqlite3.Connection,
    name: str,
    percentage: float,
    phone: str | None = None,
    email: str | None = None,
    notes: str | None = None,
) -> int:
    validated_name = _validate_name(name)
    _validate_percentage(percentage, "percentage")

    with transaction(conn):
        cursor = conn.execute(
            """
            INSERT INTO partners (name, current_percentage, phone, email, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (validated_name, percentage, phone, email, notes),
        )
    return cursor.lastrowid


def update_partner_percentage(
    conn: sqlite3.Connection, partner_id: int, new_percentage: float
) -> None:
    _validate_percentage(new_percentage, "new_percentage")

    partner = get_partner(conn, partner_id)
    if partner is None:
        raise NotFoundError(f"Partner with id {partner_id} does not exist")
    if not partner["is_active"]:
        raise ValidationError(f"Partner with id {partner_id} is not active")

    with transaction(conn):
        conn.execute(
            "UPDATE partners SET current_percentage = ? WHERE id = ?",
            (new_percentage, partner_id),
        )


def deactivate_partner(conn: sqlite3.Connection, partner_id: int) -> None:
    partner = get_partner(conn, partner_id)
    if partner is None:
        raise NotFoundError(f"Partner with id {partner_id} does not exist")

    with transaction(conn):
        conn.execute("UPDATE partners SET is_active = 0 WHERE id = ?", (partner_id,))


def list_partners(
    conn: sqlite3.Connection, active_only: bool = True
) -> list[dict]:
    if active_only:
        rows = conn.execute(
            "SELECT * FROM partners WHERE is_active = 1 ORDER BY name"
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM partners ORDER BY name").fetchall()
    return [_row_to_dict(row) for row in rows]


def get_partner(conn: sqlite3.Connection, partner_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM partners WHERE id = ?", (partner_id,)
    ).fetchone()
    return _row_to_dict(row) if row is not None else None


def get_active_percentage_total(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(current_percentage), 0) AS total
        FROM partners
        WHERE is_active = 1
        """
    ).fetchone()
    return float(row["total"])
