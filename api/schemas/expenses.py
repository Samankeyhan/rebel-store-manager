from pydantic import BaseModel, ConfigDict, StrictInt

from api.schemas.common import DateStr, Money, NamedOut, Rial


class ExpenseOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    expense_category_id: int
    expense_date: str
    amount: Rial
    description: str | None
    category_name: str


class ExpenseCategoryOut(NamedOut):
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


class ExpenseUpdate(BaseModel):
    """Only the fields present in the body change. `description: null` clears it; null on any other field is a 422.
    A new `expense_date` after today is a 422 DATE_IN_FUTURE; a change of `amount` or `expense_date` on a closed day
    (on or before the latest profit distribution's period_end) is a 409 PERIOD_ALREADY_DISTRIBUTED."""

    model_config = ConfigDict(extra="forbid")

    expense_category_id: StrictInt | None = None
    amount: Money | None = None
    expense_date: DateStr | None = None
    description: str | None = None
