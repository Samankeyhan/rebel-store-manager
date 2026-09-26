from pydantic import BaseModel, ConfigDict

from api.schemas.common import DateStr, Money


class ExpenseOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    expense_category_id: int
    expense_date: str
    amount: int
    description: str | None
    category_name: str


class ExpenseCategoryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    is_active: int
    created_at: str
    updated_at: str | None


class ExpenseCategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expense_category_id: int
    amount: Money
    expense_date: DateStr | None = None
    description: str | None = None
