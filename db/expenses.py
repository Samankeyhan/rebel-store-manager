import sqlite3

from db.connection import transaction
from db.errors import ConflictError, NotFoundError, ValidationError
from db.timeutil import normalize_record_date, to_utc_range


def _get_expense_category(conn: sqlite3.Connection, category_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM expense_categories WHERE id = ?", (category_id,)
    ).fetchone()


def get_expense_category(conn: sqlite3.Connection, category_id: int) -> dict | None:
    row = _get_expense_category(conn, category_id)
    return dict(row) if row is not None else None


def add_expense_category(conn: sqlite3.Connection, name: str) -> int:
    stripped = name.strip()
    if not stripped:
        raise ValidationError("name is required and cannot be empty", field="name")

    try:
        with transaction(conn):
            cursor = conn.execute(
                "INSERT INTO expense_categories (name) VALUES (?)",
                (stripped,),
            )
    except sqlite3.IntegrityError:
        raise ConflictError(
            f"Expense category '{stripped}' already exists."
        ) from None
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


def deactivate_expense_category(conn: sqlite3.Connection, category_id: int) -> None:
    if _get_expense_category(conn, category_id) is None:
        raise NotFoundError(f"Expense category with id {category_id} does not exist")

    with transaction(conn):
        conn.execute(
            "UPDATE expense_categories SET is_active = 0 WHERE id = ?",
            (category_id,),
        )


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
    if amount < 0:
        raise ValidationError(f"amount must be >= 0, got {amount}", field="amount")
    if expense_date is not None:
        expense_date = normalize_record_date(expense_date, conn)

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
