"""Expense categories and entries: business overhead, not COGS.
`update_expense` / `delete_expense` fix a mistaken entry (hard delete: the audit log keeps the old row); a record date after today is refused (DATE_IN_FUTURE); changing amount or date, or deleting, on a closed day is refused (`db/period_lock.py`)."""

import sqlite3

from db.audit import audited
from db.connection import transaction
from db.costing import check_money
from db.errors import ConflictError, NotFoundError, ValidationError
from db.name_keys import duplicate_guard
from db.names import name_key, stored_form
from db.period_lock import refuse_closed_day
from db.timeutil import local_day, normalize_record_date, refuse_future_day, to_utc_range


def _get_expense_category(conn: sqlite3.Connection, category_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM expense_categories WHERE id = ?", (category_id,)
    ).fetchone()


def get_expense_category(conn: sqlite3.Connection, category_id: int) -> dict | None:
    row = _get_expense_category(conn, category_id)
    return dict(row) if row is not None else None


@audited()
def add_expense_category(conn: sqlite3.Connection, name: str) -> int:
    stripped = stored_form(name)
    if not stripped:
        raise ValidationError("name is required and cannot be empty", field="name")

    with duplicate_guard(conn, "expense_categories", stripped):
        with transaction(conn):
            cursor = conn.execute(
                "INSERT INTO expense_categories (name, name_key) VALUES (?, ?)",
                (stripped, name_key(stripped)),
            )
    return cursor.lastrowid


def list_expense_categories(
    conn: sqlite3.Connection, active_only: bool = True
) -> list[dict]:
    if active_only:
        rows = conn.execute(
            "SELECT * FROM expense_categories WHERE is_active = 1 ORDER BY name"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM expense_categories ORDER BY name"
        ).fetchall()
    return [dict(row) for row in rows]


@audited()
def deactivate_expense_category(conn: sqlite3.Connection, category_id: int) -> None:
    if _get_expense_category(conn, category_id) is None:
        raise NotFoundError(f"Expense category with id {category_id} does not exist")

    with transaction(conn):
        conn.execute(
            "UPDATE expense_categories SET is_active = 0 WHERE id = ?",
            (category_id,),
        )


@audited()
def add_expense(
    conn: sqlite3.Connection,
    expense_category_id: int,
    amount: int,
    description: str | None = None,
    expense_date: str | None = None,
) -> int:
    if _get_expense_category(conn, expense_category_id) is None:
        raise NotFoundError(
            f"Expense category with id {expense_category_id} does not exist"
        )
    check_money(amount, "amount")
    if amount < 0:
        raise ValidationError(f"amount must be >= 0, got {amount}", field="amount")
    if expense_date is not None:
        expense_date = normalize_record_date(expense_date, conn)
        refuse_future_day(conn, local_day(expense_date, conn), "expense_date")

    with transaction(conn):
        if expense_date is not None:
            cursor = conn.execute(
                """
                INSERT INTO expenses (expense_category_id, amount, description, expense_date)
                VALUES (?, ?, ?, ?)
                """,
                (expense_category_id, amount, description, expense_date),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO expenses (expense_category_id, amount, description)
                VALUES (?, ?, ?)
                """,
                (expense_category_id, amount, description),
            )

    return cursor.lastrowid


_EDITABLE = ("expense_category_id", "amount", "description", "expense_date")


@audited()
def update_expense(conn: sqlite3.Connection, expense_id: int, **fields) -> None:
    """Partial update: only the keys given change (`description=None` clears it; the others cannot be None).
    A new `expense_date` may not be after today (DATE_IN_FUTURE). A change of `amount` or `expense_date` is refused
    on a day on or before the latest profit distribution's period_end, old or new (PERIOD_ALREADY_DISTRIBUTED);
    category and description changes are always allowed."""
    unknown = sorted(set(fields) - set(_EDITABLE))
    if unknown:
        raise ValidationError(f"Cannot update: {', '.join(unknown)}", field=unknown[0])
    old = get_expense(conn, expense_id)
    if old is None:
        raise NotFoundError(f"Expense with id {expense_id} does not exist")
    for name in ("expense_category_id", "amount", "expense_date"):
        if name in fields and fields[name] is None:
            raise ValidationError(f"{name} cannot be empty", field=name)

    changes: dict = {}
    if "expense_category_id" in fields and fields["expense_category_id"] != old["expense_category_id"]:
        category = _get_expense_category(conn, fields["expense_category_id"])
        if category is None:
            raise NotFoundError(f"Expense category with id {fields['expense_category_id']} does not exist")
        if not category["is_active"]:
            raise ValidationError(
                f"Expense category {category['name']!r} is inactive", field="expense_category_id"
            )
        changes["expense_category_id"] = category["id"]
    if "amount" in fields:
        check_money(fields["amount"], "amount")
        if fields["amount"] < 0:
            raise ValidationError(f"amount must be >= 0, got {fields['amount']}", field="amount")
        if fields["amount"] != old["amount"]:
            changes["amount"] = fields["amount"]
    if "description" in fields and fields["description"] != old["description"]:
        changes["description"] = fields["description"]

    old_day = local_day(old["expense_date"], conn)
    new_day = old_day
    if "expense_date" in fields:
        moment = normalize_record_date(fields["expense_date"], conn)
        new_day = local_day(moment, conn)
        if new_day != old_day:  # the same day keeps the stored time of day
            refuse_future_day(conn, new_day, "expense_date")
            changes["expense_date"] = moment

    if "amount" in changes or "expense_date" in changes:
        refuse_closed_day(conn, old_day)
        refuse_closed_day(conn, new_day)

    if not changes:
        return
    with transaction(conn):
        assignments = ", ".join(f"{name} = ?" for name in changes)
        conn.execute(f"UPDATE expenses SET {assignments} WHERE id = ?", (*changes.values(), expense_id))


@audited()
def delete_expense(conn: sqlite3.Connection, expense_id: int) -> None:
    """Hard delete; the audit log keeps the whole old row. Refused on a day on or before the latest profit
    distribution's period_end (PERIOD_ALREADY_DISTRIBUTED)."""
    old = get_expense(conn, expense_id)
    if old is None:
        raise NotFoundError(f"Expense with id {expense_id} does not exist")
    refuse_closed_day(conn, local_day(old["expense_date"], conn))
    with transaction(conn):
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))


def get_expense(conn: sqlite3.Connection, expense_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT
            expenses.*,
            expense_categories.name AS category_name
        FROM expenses
        JOIN expense_categories ON expense_categories.id = expenses.expense_category_id
        WHERE expenses.id = ?
        """,
        (expense_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def list_expenses(
    conn: sqlite3.Connection,
    category_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    query = """
        SELECT
            expenses.*,
            expense_categories.name AS category_name
        FROM expenses
        JOIN expense_categories ON expense_categories.id = expenses.expense_category_id
        WHERE 1=1
    """
    params: list = []

    if category_id is not None:
        query += " AND expenses.expense_category_id = ?"
        params.append(category_id)
    start_utc, end_exclusive_utc = to_utc_range(start_date, end_date, conn)
    if start_utc is not None:
        query += " AND expenses.expense_date >= ?"
        params.append(start_utc)
    if end_exclusive_utc is not None:
        query += " AND expenses.expense_date < ?"
        params.append(end_exclusive_utc)

    query += " ORDER BY expenses.expense_date DESC, expenses.id DESC"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_total_expenses(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> int:
    query = "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE 1=1"
    params: list = []

    start_utc, end_exclusive_utc = to_utc_range(start_date, end_date, conn)
    if start_utc is not None:
        query += " AND expense_date >= ?"
        params.append(start_utc)
    if end_exclusive_utc is not None:
        query += " AND expense_date < ?"
        params.append(end_exclusive_utc)

    row = conn.execute(query, params).fetchone()
    return int(row[0])
