"""Orders with payment methods: fees, paid_date, the frozen settlement fields,
the closed-month guard, list filters and the channel default method."""

from datetime import date

import pytest

import db.orders
import db.settlements
from db.errors import ConflictError, NotFoundError, ValidationError
from db.orders import (
    get_order,
    list_orders,
    record_order,
    set_paid_date,
    update_order_status,
)
from db.payment_methods import add_payment_method, deactivate_payment_method
from db.returns import process_return
from db.settings import get_channel_settings, update_channel_settings
from db.settlements import record_settlement
from tests.helpers import stocked_product

TODAY = date(2026, 10, 6)  # 14 Mehr 1405


@pytest.fixture
def fixed_today(monkeypatch):
    for module in (db.orders, db.settlements):
        monkeypatch.setattr(module, "today_local", lambda conn=None: TODAY)
    return TODAY


@pytest.fixture
def setup(test_db, fixed_today):
    return {
        "product_id": stocked_product(test_db),
        "card": add_payment_method(test_db, "Card to card", "IMMEDIATE"),
        "zarinpal": add_payment_method(
            test_db, "Zarinpal", "DAYS_AFTER", 1, fee_bps=150, fee_fixed=500
        ),
        "digipay": add_payment_method(test_db, "Digipay", "DAY_OF_NEXT_MONTH", 7, fee_bps=300),
    }


def _order(conn, setup, method_id, **kwargs):
    kwargs.setdefault("order_date", "2026-10-01")
    kwargs.setdefault("shipping_charge", 0)
    kwargs.setdefault("packaging_kit_id", None)
    kwargs.setdefault("postage_cost", 0)
    items = kwargs.pop(
        "items", [{"product_id": setup["product_id"], "quantity": 1, "unit_price": 100000}]
    )
    return record_order(conn, "WEBSITE", items, payment_method_id=method_id, **kwargs)


def _row(conn, order_id):
    return get_order(conn, order_id)["order"]


def _paid_fields(order):
    return (
        order["paid_date"],
        order["expected_settlement_date"],
        order["paid_jalali_year"],
        order["paid_jalali_month"],
    )


# ---------------------------------------------------------------- fees


def test_fee_computed_from_method_on_customer_total(test_db, setup):
    order_id = _order(
        test_db,
        setup,
        setup["zarinpal"],
        items=[
            {
                "product_id": setup["product_id"],
                "quantity": 2,
                "unit_price": 100000,
                "discount_amount": 10000,
            }
        ],
        shipping_charge=50000,
    )
    # customer_total = 200000 - 10000 + 50000 = 240000; 1.5% = 3600; + 500 fixed.
    assert get_order(test_db, order_id)["customer_total"] == 240000
    assert _row(test_db, order_id)["transaction_fee"] == 4100


def test_fee_half_rounds_to_even(test_db, setup):
    method_id = add_payment_method(test_db, "Tiny", "IMMEDIATE", fee_bps=5)
    low = _order(test_db, setup, method_id, items=[
        {"product_id": setup["product_id"], "quantity": 1, "unit_price": 1000}])
    high = _order(test_db, setup, method_id, items=[
        {"product_id": setup["product_id"], "quantity": 1, "unit_price": 3000}])
    assert _row(test_db, low)["transaction_fee"] == 0
    assert _row(test_db, high)["transaction_fee"] == 2


def test_manual_fee_overrides_computed(test_db, setup):
    order_id = _order(test_db, setup, setup["zarinpal"], transaction_fee=777)
    assert _row(test_db, order_id)["transaction_fee"] == 777


def test_manual_zero_fee_is_a_real_zero(test_db, setup):
    order_id = _order(test_db, setup, setup["zarinpal"], transaction_fee=0)
    assert _row(test_db, order_id)["transaction_fee"] == 0


def test_negative_manual_fee_rejected(test_db, setup):
    with pytest.raises(ValidationError) as exc_info:
        _order(test_db, setup, setup["zarinpal"], transaction_fee=-1)
    assert exc_info.value.field == "transaction_fee"


def test_no_method_means_zero_fee_and_no_expected_date(test_db, setup):
    order_id = _order(test_db, setup, None, order_date="2026-09-22")
    order = _row(test_db, order_id)
    assert order["payment_method_id"] is None
    assert order["payment_method_name"] is None
    assert order["transaction_fee"] == 0
    # Still paid: the paid day and its Jalali month are recorded.
    assert _paid_fields(order) == ("2026-09-22", None, 1405, 6)


def test_no_method_manual_fee_kept(test_db, setup):
    order_id = _order(test_db, setup, None, transaction_fee=2500)
    assert _row(test_db, order_id)["transaction_fee"] == 2500


def test_method_name_and_reference_on_order(test_db, setup):
    order_id = _order(test_db, setup, setup["card"], payment_reference="TRX-123")
    order = _row(test_db, order_id)
    assert order["payment_method_id"] == setup["card"]
    assert order["payment_method_name"] == "Card to card"
    assert order["payment_reference"] == "TRX-123"


def test_missing_method_is_not_found_and_writes_nothing(test_db, setup):
    with pytest.raises(NotFoundError):
        _order(test_db, setup, 999)
    assert test_db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0


# ---------------------------------------------------------------- paid_date on creation


def test_paid_fields_frozen_for_each_rule(test_db, setup):
    card = _row(test_db, _order(test_db, setup, setup["card"], order_date="2026-09-22"))
    zarinpal = _row(test_db, _order(test_db, setup, setup["zarinpal"], order_date="2026-09-22"))
    digipay = _row(test_db, _order(test_db, setup, setup["digipay"], order_date="2026-09-22"))
    assert _paid_fields(card) == ("2026-09-22", "2026-09-22", 1405, 6)
    assert _paid_fields(zarinpal) == ("2026-09-22", "2026-09-23", 1405, 6)
    assert _paid_fields(digipay) == ("2026-09-22", "2026-09-29", 1405, 6)


def test_paid_date_defaults_to_today_without_order_date(test_db, setup):
    order_id = _order(test_db, setup, setup["card"], order_date=None)
    assert _row(test_db, order_id)["paid_date"] == "2026-10-06"


def test_paid_date_defaults_to_local_day_of_backdated_order(test_db, setup):
    # 01:00 Tehran on 23 Sep is still 22 Sep in UTC; the paid day is the local one.
    order_id = _order(test_db, setup, setup["digipay"], order_date="2026-09-23 01:00")
    order = _row(test_db, order_id)
    assert order["order_date"] == "2026-09-22 21:30:00"
    assert _paid_fields(order) == ("2026-09-23", "2026-10-29", 1405, 7)


def test_explicit_paid_date_on_creation(test_db, setup):
    order_id = _order(
        test_db, setup, setup["zarinpal"], order_date="2026-09-01", paid_date="2026-09-05"
    )
    assert _paid_fields(_row(test_db, order_id)) == ("2026-09-05", "2026-09-06", 1405, 6)


def test_future_paid_date_rejected(test_db, setup):
    with pytest.raises(ValidationError, match="is in the future") as exc_info:
        _order(test_db, setup, setup["card"], paid_date="2026-10-07")
    assert exc_info.value.field == "paid_date"


def test_today_paid_date_accepted(test_db, setup):
    order_id = _order(test_db, setup, setup["card"], paid_date="2026-10-06")
    assert _row(test_db, order_id)["paid_date"] == "2026-10-06"


def test_future_order_date_gives_future_paid_date_error(test_db, setup):
    with pytest.raises(ValidationError) as exc_info:
        _order(test_db, setup, setup["card"], order_date="2026-10-07")
    assert exc_info.value.field == "paid_date"


@pytest.mark.parametrize("bad", ["2026-13-01", "06/10/2026", "yesterday"])
def test_invalid_paid_date_rejected(test_db, setup, bad):
    with pytest.raises(ValidationError) as exc_info:
        _order(test_db, setup, setup["card"], paid_date=bad)
    assert exc_info.value.field == "paid_date"


@pytest.mark.parametrize("status", ["PENDING", "DRAFT"])
def test_paid_date_on_unpaid_creation_rejected(test_db, setup, status):
    with pytest.raises(ValidationError, match=f"not {status}") as exc_info:
        _order(test_db, setup, setup["card"], status=status, paid_date="2026-10-01")
    assert exc_info.value.field == "paid_date"


@pytest.mark.parametrize("status", ["PENDING", "DRAFT"])
def test_unpaid_creation_has_no_paid_fields(test_db, setup, status):
    order = _row(test_db, _order(test_db, setup, setup["zarinpal"], status=status))
    assert _paid_fields(order) == (None, None, None, None)
    # The method and its fee are still recorded at creation.
    assert order["payment_method_id"] == setup["zarinpal"]
    assert order["transaction_fee"] == 2000


# ---------------------------------------------------------------- status changes


def test_pending_to_completed_sets_paid_fields_today(test_db, setup):
    order_id = _order(test_db, setup, setup["zarinpal"], status="PENDING")
    update_order_status(test_db, order_id, "COMPLETED")
    assert _paid_fields(_row(test_db, order_id)) == ("2026-10-06", "2026-10-07", 1405, 7)


def test_draft_to_paid_with_explicit_paid_date(test_db, setup):
    order_id = _order(test_db, setup, setup["digipay"], status="DRAFT")
    update_order_status(test_db, order_id, "PAID", paid_date="2026-09-22")
    order = _row(test_db, order_id)
    assert order["status"] == "PAID"
    assert order["stock_committed"] == 1
    assert _paid_fields(order) == ("2026-09-22", "2026-09-29", 1405, 6)


def test_paid_to_completed_keeps_paid_fields(test_db, setup):
    order_id = _order(test_db, setup, setup["zarinpal"], status="PAID", order_date="2026-09-22")
    update_order_status(test_db, order_id, "COMPLETED")
    assert _paid_fields(_row(test_db, order_id)) == ("2026-09-22", "2026-09-23", 1405, 6)


def test_paid_to_completed_with_paid_date_rejected(test_db, setup):
    order_id = _order(test_db, setup, setup["zarinpal"], status="PAID", order_date="2026-09-22")
    with pytest.raises(ValidationError, match="PAID to COMPLETED is not a payment") as exc_info:
        update_order_status(test_db, order_id, "COMPLETED", paid_date="2026-10-01")
    assert exc_info.value.field == "paid_date"
    order = _row(test_db, order_id)
    assert order["status"] == "PAID"
    assert order["paid_date"] == "2026-09-22"


def test_draft_to_pending_with_paid_date_rejected(test_db, setup):
    order_id = _order(test_db, setup, setup["card"], status="DRAFT")
    with pytest.raises(ValidationError) as exc_info:
        update_order_status(test_db, order_id, "PENDING", paid_date="2026-10-01")
    assert exc_info.value.field == "paid_date"


def test_status_change_future_paid_date_rejected(test_db, setup):
    order_id = _order(test_db, setup, setup["card"], status="PENDING")
    with pytest.raises(ValidationError) as exc_info:
        update_order_status(test_db, order_id, "PAID", paid_date="2026-10-07")
    assert exc_info.value.field == "paid_date"
    assert _row(test_db, order_id)["status"] == "PENDING"


def test_no_method_order_becoming_paid_gets_paid_day_only(test_db, setup):
    order_id = _order(test_db, setup, None, status="PENDING")
    update_order_status(test_db, order_id, "PAID")
    assert _paid_fields(_row(test_db, order_id)) == ("2026-10-06", None, 1405, 7)


# ---------------------------------------------------------------- set_paid_date


def test_set_paid_date_recomputes_frozen_fields(test_db, setup):
    order_id = _order(test_db, setup, setup["digipay"], order_date="2026-09-23")
    assert _paid_fields(_row(test_db, order_id)) == ("2026-09-23", "2026-10-29", 1405, 7)
    set_paid_date(test_db, order_id, "2026-09-22")
    assert _paid_fields(_row(test_db, order_id)) == ("2026-09-22", "2026-09-29", 1405, 6)


def test_set_paid_date_does_not_change_the_fee(test_db, setup):
    order_id = _order(test_db, setup, setup["zarinpal"], transaction_fee=123)
    set_paid_date(test_db, order_id, "2026-09-30")
    order = _row(test_db, order_id)
    assert order["transaction_fee"] == 123
    assert order["expected_settlement_date"] == "2026-10-01"


def test_set_paid_date_on_unpaid_order_is_conflict(test_db, setup):
    order_id = _order(test_db, setup, setup["card"], status="PENDING")
    with pytest.raises(ConflictError, match="not paid"):
        set_paid_date(test_db, order_id, "2026-10-01")


def test_set_paid_date_on_cancelled_order_is_conflict(test_db, setup):
    order_id = _order(test_db, setup, setup["card"], status="PAID")
    process_return(test_db, order_id, "CANCELLED")
    with pytest.raises(ConflictError, match="CANCELLED, not paid"):
        set_paid_date(test_db, order_id, "2026-10-01")


def test_set_paid_date_on_settled_order_is_conflict(test_db, setup):
    order_id = _order(test_db, setup, setup["card"], order_date="2026-10-01")
    settlement_id = record_settlement(
        test_db, setup["card"], "2026-10-02", 100000, order_ids=[order_id]
    )
    with pytest.raises(ConflictError, match=f"settlement #{settlement_id}"):
        set_paid_date(test_db, order_id, "2026-09-30")
    assert _row(test_db, order_id)["paid_date"] == "2026-10-01"


def test_set_paid_date_future_rejected(test_db, setup):
    order_id = _order(test_db, setup, setup["card"])
    with pytest.raises(ValidationError) as exc_info:
        set_paid_date(test_db, order_id, "2026-10-07")
    assert exc_info.value.field == "paid_date"


def test_set_paid_date_missing_order_is_not_found(test_db, setup):
    with pytest.raises(NotFoundError):
        set_paid_date(test_db, 999, "2026-10-01")


# ---------------------------------------------------------------- inactive methods


def test_inactive_method_refused_for_new_order(test_db, setup):
    deactivate_payment_method(test_db, setup["zarinpal"])
    with pytest.raises(ValidationError, match="Payment method 'Zarinpal' is not active") as exc_info:
        _order(test_db, setup, setup["zarinpal"])
    assert exc_info.value.field == "payment_method_id"


def test_existing_pending_order_with_inactive_method_can_be_marked_paid(test_db, setup):
    order_id = _order(test_db, setup, setup["zarinpal"], status="PENDING")
    deactivate_payment_method(test_db, setup["zarinpal"])
    update_order_status(test_db, order_id, "PAID", paid_date="2026-10-02")
    order = _row(test_db, order_id)
    assert order["status"] == "PAID"
    assert _paid_fields(order) == ("2026-10-02", "2026-10-03", 1405, 7)


def test_inactive_method_does_not_block_set_paid_date(test_db, setup):
    order_id = _order(test_db, setup, setup["zarinpal"])
    deactivate_payment_method(test_db, setup["zarinpal"])
    set_paid_date(test_db, order_id, "2026-09-30")
    assert _row(test_db, order_id)["expected_settlement_date"] == "2026-10-01"


# ---------------------------------------------------------------- closed-month guard


def _settle_shahrivar(conn, setup):
    """Settle Digipay's 1405/06 (one order paid 2026-09-10)."""
    _order(conn, setup, setup["digipay"], order_date="2026-09-10")
    return record_settlement(
        conn, setup["digipay"], "2026-09-29", 97000, jalali_year=1405, jalali_month=6
    )


def test_closed_month_guard_on_record_order(test_db, setup):
    settlement_id = _settle_shahrivar(test_db, setup)
    count_before = test_db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    with pytest.raises(ConflictError) as exc_info:
        _order(test_db, setup, setup["digipay"], order_date="2026-09-22")
    assert str(exc_info.value) == (
        f"Digipay's month 1405/06 is already settled (settlement #{settlement_id}); "
        f"choose a paid date in an open month."
    )
    assert test_db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == count_before
    # The next day is Mehr, which is open.
    _order(test_db, setup, setup["digipay"], order_date="2026-09-23")


def test_closed_month_guard_on_explicit_paid_date(test_db, setup):
    _settle_shahrivar(test_db, setup)
    with pytest.raises(ConflictError, match="1405/06 is already settled"):
        _order(test_db, setup, setup["digipay"], order_date="2026-10-01", paid_date="2026-09-20")


def test_closed_month_guard_on_status_change(test_db, setup):
    order_id = _order(test_db, setup, setup["digipay"], status="PENDING", order_date="2026-09-15")
    _settle_shahrivar(test_db, setup)
    with pytest.raises(ConflictError, match="1405/06 is already settled"):
        update_order_status(test_db, order_id, "PAID", paid_date="2026-09-20")
    order = _row(test_db, order_id)
    assert order["status"] == "PENDING"
    assert order["paid_date"] is None
    # Paying it in an open month works.
    update_order_status(test_db, order_id, "PAID", paid_date="2026-10-01")
    assert _row(test_db, order_id)["paid_jalali_month"] == 7


def test_closed_month_guard_on_set_paid_date(test_db, setup):
    order_id = _order(test_db, setup, setup["digipay"], order_date="2026-10-01")
    _settle_shahrivar(test_db, setup)
    with pytest.raises(ConflictError, match="1405/06 is already settled"):
        set_paid_date(test_db, order_id, "2026-09-22")
    assert _row(test_db, order_id)["paid_date"] == "2026-10-01"


def test_closed_month_guard_is_per_method(test_db, setup):
    _settle_shahrivar(test_db, setup)
    other = add_payment_method(test_db, "Other monthly", "DAY_OF_NEXT_MONTH", 5)
    _order(test_db, setup, other, order_date="2026-09-22")
    _order(test_db, setup, setup["zarinpal"], order_date="2026-09-22")
    _order(test_db, setup, None, order_date="2026-09-22")


# ---------------------------------------------------------------- list_orders filters


def test_list_orders_filters_by_method_and_settlement_state(test_db, setup):
    card_paid = _order(test_db, setup, setup["card"], order_date="2026-10-01")
    card_settled = _order(test_db, setup, setup["card"], order_date="2026-10-02")
    card_pending_status = _order(test_db, setup, setup["card"], status="PENDING")
    zarinpal_paid = _order(test_db, setup, setup["zarinpal"], order_date="2026-10-03")
    no_method = _order(test_db, setup, None, order_date="2026-10-04")
    record_settlement(test_db, setup["card"], "2026-10-05", 100000, order_ids=[card_settled])

    def ids(**filters):
        return sorted(o["id"] for o in list_orders(test_db, **filters))

    assert ids(payment_method_id=setup["card"]) == sorted(
        [card_paid, card_settled, card_pending_status]
    )
    assert ids(settlement_state="pending") == sorted([card_paid, zarinpal_paid])
    assert ids(settlement_state="settled") == [card_settled]
    assert ids(payment_method_id=setup["card"], settlement_state="pending") == [card_paid]
    assert no_method in ids()

    listed = {o["id"]: o for o in list_orders(test_db)}
    assert listed[zarinpal_paid]["payment_method_name"] == "Zarinpal"
    assert listed[no_method]["payment_method_name"] is None


def test_list_orders_pending_drops_cancelled_and_refunded(test_db, setup):
    cancelled = _order(test_db, setup, setup["card"], status="PAID")
    refunded = _order(test_db, setup, setup["card"])
    kept = _order(test_db, setup, setup["card"])
    process_return(test_db, cancelled, "CANCELLED")
    process_return(test_db, refunded, "REFUNDED")
    assert [o["id"] for o in list_orders(test_db, settlement_state="pending")] == [kept]


def test_list_orders_invalid_settlement_state(test_db, setup):
    with pytest.raises(ValidationError) as exc_info:
        list_orders(test_db, settlement_state="open")
    assert exc_info.value.field == "settlement_state"


# ---------------------------------------------------------------- channel default method


def test_channel_default_method_starts_empty(test_db):
    assert get_channel_settings(test_db, "WEBSITE")["default_payment_method_id"] is None


def test_channel_default_method_set_used_and_cleared(test_db, setup):
    update_channel_settings(test_db, "WEBSITE", default_payment_method_id=setup["zarinpal"])
    assert get_channel_settings(test_db, "WEBSITE")["default_payment_method_id"] == setup["zarinpal"]

    order_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": setup["product_id"], "quantity": 1, "unit_price": 100000}],
        shipping_charge=0,
        packaging_kit_id=None,
        postage_cost=0,
    )
    order = _row(test_db, order_id)
    assert order["payment_method_id"] == setup["zarinpal"]
    assert order["transaction_fee"] == 2000

    update_channel_settings(test_db, "WEBSITE", default_payment_method_id=None)
    assert get_channel_settings(test_db, "WEBSITE")["default_payment_method_id"] is None


def test_channel_default_unset_leaves_it_unchanged(test_db, setup):
    update_channel_settings(test_db, "WEBSITE", default_payment_method_id=setup["card"])
    update_channel_settings(test_db, "WEBSITE", applies_postage=0)
    settings = get_channel_settings(test_db, "WEBSITE")
    assert settings["default_payment_method_id"] == setup["card"]
    assert settings["applies_postage"] == 0


def test_channel_default_is_per_channel(test_db, setup):
    update_channel_settings(test_db, "WEBSITE", default_payment_method_id=setup["card"])
    assert get_channel_settings(test_db, "INSTAGRAM")["default_payment_method_id"] is None


def test_explicit_none_overrides_channel_default(test_db, setup):
    update_channel_settings(test_db, "WEBSITE", default_payment_method_id=setup["zarinpal"])
    order = _row(test_db, _order(test_db, setup, None))
    assert order["payment_method_id"] is None
    assert order["transaction_fee"] == 0


def test_channel_default_missing_method_is_not_found(test_db, setup):
    with pytest.raises(NotFoundError):
        update_channel_settings(test_db, "WEBSITE", default_payment_method_id=999)
    assert get_channel_settings(test_db, "WEBSITE")["default_payment_method_id"] is None


def test_channel_default_inactive_method_rejected(test_db, setup):
    deactivate_payment_method(test_db, setup["card"])
    with pytest.raises(ValidationError, match="'Card to card' is not active") as exc_info:
        update_channel_settings(test_db, "WEBSITE", default_payment_method_id=setup["card"])
    assert exc_info.value.field == "default_payment_method_id"
    assert get_channel_settings(test_db, "WEBSITE")["default_payment_method_id"] is None


def test_deactivating_a_channel_default_is_allowed_but_new_orders_refuse_it(test_db, setup):
    update_channel_settings(test_db, "WEBSITE", default_payment_method_id=setup["digipay"])
    deactivate_payment_method(test_db, setup["digipay"])
    assert get_channel_settings(test_db, "WEBSITE")["default_payment_method_id"] == setup["digipay"]

    with pytest.raises(ValidationError, match="Payment method 'Digipay' is not active") as exc_info:
        record_order(
            test_db,
            "WEBSITE",
            [{"product_id": setup["product_id"], "quantity": 1, "unit_price": 100000}],
            shipping_charge=0,
            packaging_kit_id=None,
            postage_cost=0,
        )
    assert exc_info.value.field == "payment_method_id"
    # Clearing the default (None) is always allowed.
    update_channel_settings(test_db, "WEBSITE", default_payment_method_id=None)
