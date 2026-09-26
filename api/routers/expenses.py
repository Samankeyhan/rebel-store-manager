import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.common import DateStr
from api.schemas.expenses import ExpenseCategoryOut, ExpenseOut
from db.expenses import list_expense_categories, list_expenses

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
