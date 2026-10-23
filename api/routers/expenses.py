import sqlite3

from fastapi import APIRouter, Depends, Response

from api.deps import get_db
from api.schemas.common import DateStr
from api.schemas.expenses import (
    ExpenseCategoryCreate,
    ExpenseCategoryOut,
    ExpenseCreate,
    ExpenseOut,
    ExpenseUpdate,
)
from db.expenses import (
    add_expense,
    add_expense_category,
    delete_expense,
    get_expense,
    get_expense_category,
    list_expense_categories,
    list_expenses,
    update_expense,
)

router = APIRouter(tags=["expenses"])


@router.get("/expenses", response_model=list[ExpenseOut])
def read_expenses(
    category_id: int | None = None,
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[ExpenseOut]:
    expenses = list_expenses(
        conn, category_id=category_id, start_date=start_date, end_date=end_date
    )
    return [ExpenseOut.model_validate(e) for e in expenses]


@router.get("/expense-categories", response_model=list[ExpenseCategoryOut])
def read_expense_categories(
    active_only: bool = True, conn: sqlite3.Connection = Depends(get_db)
) -> list[ExpenseCategoryOut]:
    return [
        ExpenseCategoryOut.model_validate(c)
        for c in list_expense_categories(conn, active_only)
    ]


@router.post("/expense-categories", response_model=ExpenseCategoryOut, status_code=201)
def create_expense_category(
    body: ExpenseCategoryCreate, conn: sqlite3.Connection = Depends(get_db)
) -> ExpenseCategoryOut:
    category_id = add_expense_category(conn, body.name)
    return ExpenseCategoryOut.model_validate(get_expense_category(conn, category_id))


@router.post("/expenses", response_model=ExpenseOut, status_code=201)
def create_expense(
    body: ExpenseCreate, conn: sqlite3.Connection = Depends(get_db)
) -> ExpenseOut:
    expense_id = add_expense(
        conn,
        body.expense_category_id,
        body.amount,
        description=body.description,
        expense_date=body.expense_date,
    )
    return ExpenseOut.model_validate(get_expense(conn, expense_id))


@router.patch("/expenses/{expense_id}", response_model=ExpenseOut)
def patch_expense(
    expense_id: int, body: ExpenseUpdate, conn: sqlite3.Connection = Depends(get_db)
) -> ExpenseOut:
    """Only the fields present in the body change. 404 unknown expense or category."""
    update_expense(conn, expense_id, **body.model_dump(exclude_unset=True))
    return ExpenseOut.model_validate(get_expense(conn, expense_id))


@router.delete("/expenses/{expense_id}", status_code=204)
def remove_expense(expense_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Response:
    """Hard delete (the audit log keeps the old row). 409 PERIOD_ALREADY_DISTRIBUTED on a closed day."""
    delete_expense(conn, expense_id)
    return Response(status_code=204)
