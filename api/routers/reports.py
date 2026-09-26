import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.common import DateStr
from api.schemas.reports import (
    ChannelBreakdownOut,
    ExpenseBreakdownOut,
    ProductPerformanceOut,
    ProfitAndLossOut,
    RevenueSummaryOut,
    ShippingByChannelOut,
    ShippingSummaryOut,
    WasteReportOut,
)
from db.orders import get_revenue_summary
from db.reports import (
    get_channel_breakdown,
    get_expense_breakdown,
    get_product_performance,
    get_profit_and_loss,
    get_shipping_by_channel,
    get_shipping_summary,
    get_waste_report,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/profit-and-loss", response_model=ProfitAndLossOut)
def read_profit_and_loss(
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> ProfitAndLossOut:
    return ProfitAndLossOut.model_validate(
        get_profit_and_loss(conn, start_date=start_date, end_date=end_date)
    )


@router.get("/products", response_model=list[ProductPerformanceOut])
def read_product_performance(
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[ProductPerformanceOut]:
    rows = get_product_performance(conn, start_date=start_date, end_date=end_date)
    return [ProductPerformanceOut.model_validate(r) for r in rows]


@router.get("/channels", response_model=list[ChannelBreakdownOut])
def read_channel_breakdown(
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[ChannelBreakdownOut]:
    rows = get_channel_breakdown(conn, start_date=start_date, end_date=end_date)
    return [ChannelBreakdownOut.model_validate(r) for r in rows]


@router.get("/shipping", response_model=ShippingSummaryOut)
def read_shipping_summary(
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> ShippingSummaryOut:
    return ShippingSummaryOut.model_validate(
        get_shipping_summary(conn, start_date=start_date, end_date=end_date)
    )


@router.get("/shipping-by-channel", response_model=list[ShippingByChannelOut])
def read_shipping_by_channel(
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[ShippingByChannelOut]:
    rows = get_shipping_by_channel(conn, start_date=start_date, end_date=end_date)
    return [ShippingByChannelOut.model_validate(r) for r in rows]


@router.get("/waste", response_model=list[WasteReportOut])
def read_waste_report(
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[WasteReportOut]:
    rows = get_waste_report(conn, start_date=start_date, end_date=end_date)
    return [WasteReportOut.model_validate(r) for r in rows]


@router.get("/expenses", response_model=list[ExpenseBreakdownOut])
def read_expense_breakdown(
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[ExpenseBreakdownOut]:
    rows = get_expense_breakdown(conn, start_date=start_date, end_date=end_date)
    return [ExpenseBreakdownOut.model_validate(r) for r in rows]


@router.get("/revenue-summary", response_model=RevenueSummaryOut)
def read_revenue_summary(
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> RevenueSummaryOut:
    return RevenueSummaryOut.model_validate(
        get_revenue_summary(conn, start_date=start_date, end_date=end_date)
    )
