from datetime import date

import pytest

import db.orders
import db.payment_methods
from db.errors import ConflictError, NotFoundError, ValidationError
from db.orders import record_order, update_order_status
from db.payment_methods import (
    add_payment_method,
    compute_expected_settlement_date,
    compute_fee,
    count_pending_orders,
    deactivate_payment_method,
    get_payment_method,
    list_payment_methods,
    preview_fee,
    reactivate_payment_method,
    update_payment_method,
)
from tests.helpers import stocked_product

TODAY = date(2026, 10, 6)


@pytest.fixture
def fixed_today(monkeypatch):
    monkeypatch.setattr(db.orders, "today_local", lambda conn=None: TODAY)
    return TODAY


def _paid_order(conn, product_id, method_id, order_date="2026-10-01", status="COMPLETED"):
    return record_order(
        conn,
        "WEBSITE",
        [{"product_id": product_id, "quantity": 1, "unit_price": 100000}],
        order_date=order_date,
        shipping_charge=0,
        packaging_kit_id=None,
        postage_cost=0,
        payment_method_id=method_id,
        status=status,
    )


def _method(fee_bps=0, fee_fixed=0, rule="IMMEDIATE", days=None):
    return {"fee_bps": fee_bps, "fee_fixed": fee_fixed, "settlement_rule": rule, "settlement_days": days}


# ---------------------------------------------------------------- CRUD


def test_add_and_get_payment_method(test_db):
    method_id = add_payment_method(
        test_db, "  Zarinpal  ", "DAYS_AFTER", settlement_days=1, fee_bps=150, fee_fixed=500
    )
    method = get_payment_method(test_db, method_id)
    assert method["name"] == "Zarinpal"
    assert method["settlement_rule"] == "DAYS_AFTER"
    assert method["settlement_days"] == 1
    assert method["fee_bps"] == 150
    assert method["fee_fixed"] == 500
    assert method["is_active"] == 1


def test_add_payment_method_defaults_to_no_fee(test_db):
    method = get_payment_method(test_db, add_payment_method(test_db, "Card to card", "IMMEDIATE"))
    assert (method["fee_bps"], method["fee_fixed"], method["settlement_days"]) == (0, 0, None)


def test_get_missing_payment_method_is_not_found(test_db):
    with pytest.raises(NotFoundError, match="Payment method with id 999 does not exist"):
        get_payment_method(test_db, 999)


def test_list_payment_methods_sorted_and_hides_inactive(test_db):
    zarinpal = add_payment_method(test_db, "Zarinpal", "DAYS_AFTER", 1)
    add_payment_method(test_db, "Card to card", "IMMEDIATE")
    deactivate_payment_method(test_db, zarinpal)

    assert [m["name"] for m in list_payment_methods(test_db)] == ["Card to card"]
    assert [m["name"] for m in list_payment_methods(test_db, include_inactive=True)] == [
        "Card to card",
        "Zarinpal",
    ]


@pytest.mark.parametrize("name", ["", "   ", None])
def test_add_payment_method_requires_name(test_db, name):
    with pytest.raises(ValidationError, match="name is required") as exc_info:
        add_payment_method(test_db, name, "IMMEDIATE")
    assert exc_info.value.field == "name"


def test_duplicate_name_is_conflict(test_db):
    add_payment_method(test_db, "Digipay", "DAY_OF_NEXT_MONTH", 7)
    with pytest.raises(ConflictError, match="A payment method named 'Digipay' already exists"):
        add_payment_method(test_db, "Digipay", "IMMEDIATE")


def test_rename_to_existing_name_is_conflict(test_db):
    add_payment_method(test_db, "Digipay", "DAY_OF_NEXT_MONTH", 7)
    other = add_payment_method(test_db, "Zarinpal", "DAYS_AFTER", 1)
    with pytest.raises(ConflictError, match="named 'Digipay' already exists"):
        update_payment_method(test_db, other, name="Digipay")


@pytest.mark.parametrize(
    "kwargs, field, message",
    [
        ({"fee_bps": -1}, "fee_bps", "fee_bps must be between 0 and 10000, got -1"),
        ({"fee_bps": 10001}, "fee_bps", "fee_bps must be between 0 and 10000, got 10001"),
        ({"fee_fixed": -1}, "fee_fixed", "fee_fixed must be >= 0, got -1"),
    ],
)
def test_add_payment_method_fee_validation(test_db, kwargs, field, message):
    with pytest.raises(ValidationError, match=message) as exc_info:
        add_payment_method(test_db, "Bad", "IMMEDIATE", **kwargs)
    assert exc_info.value.field == field


@pytest.mark.parametrize(
    "rule, days, field, message",
    [
        ("WEEKLY", None, "settlement_rule", "Invalid settlement_rule 'WEEKLY'"),
        ("IMMEDIATE", 1, "settlement_days", "settlement_days must be empty for an IMMEDIATE method"),
        ("DAYS_AFTER", None, "settlement_days", "between 1 and 365 for DAYS_AFTER, got None"),
        ("DAYS_AFTER", 0, "settlement_days", "between 1 and 365 for DAYS_AFTER, got 0"),
        ("DAYS_AFTER", 366, "settlement_days", "between 1 and 365 for DAYS_AFTER, got 366"),
        ("DAY_OF_NEXT_MONTH", None, "settlement_days", "between 1 and 31 for DAY_OF_NEXT_MONTH, got None"),
        ("DAY_OF_NEXT_MONTH", 0, "settlement_days", "between 1 and 31 for DAY_OF_NEXT_MONTH, got 0"),
        ("DAY_OF_NEXT_MONTH", 32, "settlement_days", "between 1 and 31 for DAY_OF_NEXT_MONTH, got 32"),
    ],
)
def test_add_payment_method_rule_validation(test_db, rule, days, field, message):
    with pytest.raises(ValidationError, match=message) as exc_info:
        add_payment_method(test_db, "Bad", rule, days)
    assert exc_info.value.field == field
    assert list_payment_methods(test_db, include_inactive=True) == []


def test_update_unknown_field_is_validation_error(test_db):
    method_id = add_payment_method(test_db, "Card", "IMMEDIATE")
    with pytest.raises(ValidationError, match="Unknown field 'is_active'") as exc_info:
        update_payment_method(test_db, method_id, is_active=0)
    assert exc_info.value.field == "is_active"


def test_update_missing_method_is_not_found(test_db):
    with pytest.raises(NotFoundError):
        update_payment_method(test_db, 999, fee_bps=10)


def test_update_with_no_fields_changes_nothing(test_db, monkeypatch):
    method_id = add_payment_method(test_db, "Card", "IMMEDIATE")
    before = get_payment_method(test_db, method_id)
    monkeypatch.setattr(db.payment_methods, "now_utc", lambda: "2030-01-01 00:00:00")
    update_payment_method(test_db, method_id)
    assert get_payment_method(test_db, method_id) == before


def test_updated_at_changes_on_every_update(test_db, monkeypatch):
    method_id = add_payment_method(test_db, "Card", "IMMEDIATE")
    stamps = iter(["2026-10-01 10:00:00", "2026-10-02 10:00:00", "2026-10-03 10:00:00", "2026-10-04 10:00:00"])
    monkeypatch.setattr(db.payment_methods, "now_utc", lambda: next(stamps))

    update_payment_method(test_db, method_id, fee_bps=100)
    assert get_payment_method(test_db, method_id)["updated_at"] == "2026-10-01 10:00:00"
    update_payment_method(test_db, method_id, name="Card to card")
    assert get_payment_method(test_db, method_id)["updated_at"] == "2026-10-02 10:00:00"
    deactivate_payment_method(test_db, method_id)
    assert get_payment_method(test_db, method_id)["updated_at"] == "2026-10-03 10:00:00"
    reactivate_payment_method(test_db, method_id)
    assert get_payment_method(test_db, method_id)["updated_at"] == "2026-10-04 10:00:00"


def test_update_validates_merged_rule(test_db):
    method_id = add_payment_method(test_db, "Card", "IMMEDIATE")
    # Switching to DAYS_AFTER without days is refused against the merged row.
    with pytest.raises(ValidationError) as exc_info:
        update_payment_method(test_db, method_id, settlement_rule="DAYS_AFTER")
    assert exc_info.value.field == "settlement_days"
    update_payment_method(test_db, method_id, settlement_rule="DAYS_AFTER", settlement_days=3)
    method = get_payment_method(test_db, method_id)
    assert (method["settlement_rule"], method["settlement_days"]) == ("DAYS_AFTER", 3)


def test_deactivate_and_reactivate(test_db):
    method_id = add_payment_method(test_db, "Card", "IMMEDIATE")
    deactivate_payment_method(test_db, method_id)
    assert get_payment_method(test_db, method_id)["is_active"] == 0
    reactivate_payment_method(test_db, method_id)
    assert get_payment_method(test_db, method_id)["is_active"] == 1


def test_deactivate_missing_method_is_not_found(test_db):
    with pytest.raises(NotFoundError):
        deactivate_payment_method(test_db, 999)
    with pytest.raises(NotFoundError):
        reactivate_payment_method(test_db, 999)


# ---------------------------------------------------------------- rule edits


def test_rule_edit_refused_while_orders_pending(test_db, fixed_today):
    product_id = stocked_product(test_db)
    method_id = add_payment_method(test_db, "Zarinpal", "DAYS_AFTER", 1)
    _paid_order(test_db, product_id, method_id)

    with pytest.raises(ConflictError) as exc_info:
        update_payment_method(test_db, method_id, settlement_days=2)
    assert str(exc_info.value) == (
        "Cannot change the settlement rule of 'Zarinpal': 1 paid order is still "
        "pending settlement. Deactivate this method and create a new one with the new rule."
    )
    assert get_payment_method(test_db, method_id)["settlement_days"] == 1


def test_rule_edit_message_counts_plural_and_rule_change(test_db, fixed_today):
    product_id = stocked_product(test_db)
    method_id = add_payment_method(test_db, "Zarinpal", "DAYS_AFTER", 1)
    _paid_order(test_db, product_id, method_id)
    _paid_order(test_db, product_id, method_id, status="PAID")

    with pytest.raises(ConflictError, match="2 paid orders are still pending settlement"):
        update_payment_method(test_db, method_id, settlement_rule="IMMEDIATE", settlement_days=None)


def test_saving_an_unchanged_rule_never_conflicts(test_db, fixed_today):
    product_id = stocked_product(test_db)
    method_id = add_payment_method(test_db, "Zarinpal", "DAYS_AFTER", 1)
    _paid_order(test_db, product_id, method_id)

    update_payment_method(
        test_db, method_id, name="Zarinpal", settlement_rule="DAYS_AFTER", settlement_days=1
    )
    assert get_payment_method(test_db, method_id)["settlement_days"] == 1


def test_fee_edits_always_allowed_while_pending(test_db, fixed_today):
    product_id = stocked_product(test_db)
    method_id = add_payment_method(test_db, "Zarinpal", "DAYS_AFTER", 1, fee_bps=100)
    order_id = _paid_order(test_db, product_id, method_id)

    update_payment_method(test_db, method_id, fee_bps=200, fee_fixed=1000)
    method = get_payment_method(test_db, method_id)
    assert (method["fee_bps"], method["fee_fixed"]) == (200, 1000)
    # The fee is frozen on the existing order.
    fee = test_db.execute("SELECT transaction_fee FROM orders WHERE id = ?", (order_id,)).fetchone()[0]
    assert fee == 1000


def test_rule_edit_allowed_when_only_unpaid_orders_exist(test_db, fixed_today):
    product_id = stocked_product(test_db)
    method_id = add_payment_method(test_db, "Zarinpal", "DAYS_AFTER", 1)
    _paid_order(test_db, product_id, method_id, status="PENDING")
    assert count_pending_orders(test_db, method_id) == 0

    update_payment_method(test_db, method_id, settlement_days=5)
    assert get_payment_method(test_db, method_id)["settlement_days"] == 5


def test_count_pending_orders_counts_paid_unsettled_of_this_method(test_db, fixed_today):
    product_id = stocked_product(test_db)
    method_id = add_payment_method(test_db, "Zarinpal", "DAYS_AFTER", 1)
    other_id = add_payment_method(test_db, "Card", "IMMEDIATE")
    _paid_order(test_db, product_id, method_id)
    _paid_order(test_db, product_id, method_id, status="PAID")
    pending_order = _paid_order(test_db, product_id, method_id, status="PENDING")
    _paid_order(test_db, product_id, other_id)

    assert count_pending_orders(test_db, method_id) == 2
    update_order_status(test_db, pending_order, "PAID")
    assert count_pending_orders(test_db, method_id) == 3


# ---------------------------------------------------------------- compute_fee


@pytest.mark.parametrize(
    "total, fee_bps, fee_fixed, expected",
    [
        (100000, 150, 0, 1500),        # percentage only
        (100000, 0, 2500, 2500),       # fixed only
        (100000, 150, 2500, 4000),     # both
        (1000, 5, 0, 0),               # exact .5 -> even (0)
        (3000, 5, 0, 2),               # exact .5 -> even (2)
        (5000, 3, 0, 2),               # 1.5 -> 2
        (2500, 10, 0, 2),              # 2.5 -> 2
        (1001, 5, 0, 1),               # 0.5005 -> 1 (above half)
        (999, 5, 0, 0),                # 0.4995 -> 0 (below half)
        (123456, 0, 0, 0),             # bps 0
        (123456, 10000, 0, 123456),    # bps 10000 = the whole total
        (123456, 10000, 100, 123556),
        (0, 300, 500, 500),            # zero total still pays the fixed fee
    ],
)
def test_compute_fee(total, fee_bps, fee_fixed, expected):
    assert compute_fee(total, _method(fee_bps, fee_fixed)) == expected


def test_compute_fee_returns_int():
    assert isinstance(compute_fee(3000, _method(5)), int)


# ---------------------------------------------------------------- expected settlement date


def test_expected_date_immediate_is_paid_day():
    assert compute_expected_settlement_date(date(2026, 9, 22), _method()) == date(2026, 9, 22)


@pytest.mark.parametrize(
    "paid, days, expected",
    [
        (date(2026, 9, 22), 1, date(2026, 9, 23)),
        (date(2026, 12, 31), 1, date(2027, 1, 1)),
        (date(2026, 1, 1), 365, date(2027, 1, 1)),
    ],
)
def test_expected_date_days_after(paid, days, expected):
    assert compute_expected_settlement_date(paid, _method(rule="DAYS_AFTER", days=days)) == expected


@pytest.mark.parametrize(
    "paid, days, expected",
    [
        # Paid in Shahrivar 1405 (2026-08-23..2026-09-22): day 7 of Mehr.
        (date(2026, 8, 23), 7, date(2026, 9, 29)),
        (date(2026, 9, 22), 7, date(2026, 9, 29)),
        # Paid on 1 Mehr: day 7 of Aban.
        (date(2026, 9, 23), 7, date(2026, 10, 29)),
        # Day 31 clamps to 30 Mehr (a 30-day month).
        (date(2026, 9, 1), 31, date(2026, 10, 22)),
        # Day 31 in a 31-day month (Shahrivar) is not clamped: paid in Mordad 1405.
        (date(2026, 8, 1), 31, date(2026, 9, 22)),
        # Esfand rolls into Farvardin of the next year: paid in Esfand 1404.
        (date(2026, 3, 10), 7, date(2026, 3, 27)),
        (date(2026, 3, 20), 1, date(2026, 3, 21)),
        # Paid in Bahman 1404, day 31 -> Esfand 1404 has 29 days.
        (date(2026, 2, 10), 31, date(2026, 3, 20)),
        # Paid in Bahman 1403, day 31 -> Esfand 1403 (leap) has 30 days.
        (date(2025, 2, 10), 31, date(2025, 3, 20)),
    ],
)
def test_expected_date_day_of_next_month(paid, days, expected):
    method = _method(rule="DAY_OF_NEXT_MONTH", days=days)
    assert compute_expected_settlement_date(paid, method) == expected


def test_expected_date_unknown_rule_is_validation_error():
    with pytest.raises(ValidationError) as exc_info:
        compute_expected_settlement_date(date(2026, 9, 22), _method(rule="WEEKLY"))
    assert exc_info.value.field == "settlement_rule"


# ---------------------------------------------------------------- preview_fee


def test_preview_fee(test_db):
    method_id = add_payment_method(test_db, "Zarinpal", "DAYS_AFTER", 1, fee_bps=150, fee_fixed=500)
    assert preview_fee(test_db, method_id, 240000) == {
        "payment_method_id": method_id,
        "amount": 240000,
        "transaction_fee": 4100,
        "expected_amount": 235900,
    }


def test_preview_fee_can_exceed_amount(test_db):
    method_id = add_payment_method(test_db, "Fixed", "IMMEDIATE", fee_fixed=500)
    assert preview_fee(test_db, method_id, 0)["expected_amount"] == -500


def test_preview_fee_inactive_method_allowed(test_db):
    method_id = add_payment_method(test_db, "Old", "IMMEDIATE", fee_bps=100)
    deactivate_payment_method(test_db, method_id)
    assert preview_fee(test_db, method_id, 10000)["transaction_fee"] == 100


def test_preview_fee_missing_method(test_db):
    with pytest.raises(NotFoundError):
        preview_fee(test_db, 999, 1000)


@pytest.mark.parametrize("amount", [-1, 1.5, "1000", True, None])
def test_preview_fee_rejects_bad_amount(test_db, amount):
    method_id = add_payment_method(test_db, "Card", "IMMEDIATE")
    with pytest.raises(ValidationError) as exc_info:
        preview_fee(test_db, method_id, amount)
    assert exc_info.value.field == "amount"
