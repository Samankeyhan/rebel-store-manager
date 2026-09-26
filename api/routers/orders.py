import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.common import DateStr
from api.schemas.orders import OrderDetailOut, OrderListItemOut
from db.orders import get_order, list_orders

router = APIRouter(tags=["orders"])


@router.get("/orders", response_model=list[OrderListItemOut])
def read_orders(
    channel: str | None = None,
    status: str | None = None,
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[OrderListItemOut]:
    orders = list_orders(
        conn, channel=channel, status=status, start_date=start_date, end_date=end_date
    )
    return [OrderListItemOut.model_validate(o) for o in orders]


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
def read_order(order_id: int, conn: sqlite3.Connection = Depends(get_db)) -> OrderDetailOut:
    # get_order raises NotFoundError itself.
    return OrderDetailOut.model_validate(get_order(conn, order_id))
