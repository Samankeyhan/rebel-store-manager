"""Settlements: pending groups, recording payouts (chosen orders or whole
Jalali months), reading, listing and correcting them."""

from datetime import date

import pytest

import db.orders
import db.settlements
from db.errors import ConflictError, NotFoundError, ValidationError
from db.orders import get_order, record_order
from db.payment_methods import (
    add_payment_method,
    deactivate_payment_method,
    update_payment_method,
)
from db.returns import process_return
from db.settlements import (
    get_pending,
    get_settlement,
    list_settlements,
    record_settlement,
    update_settlement,
)
from tests.helpers import stocked_product

TODAY = date(2026, 10, 6)  # 14 Mehr 1405


@pytest.fixture
def set_today(monkeypatch):
    def _set(day: date) -> date:
        for module in (db.orders, db.settlements):
            monkeypatch.setattr(module, "today_local", lambda conn=None: day)
        return day

    _set(TODAY)
    return _set


@pytest.fixture
def setup(test_db, set_today):
    return {
        "product_id": stocked_product(test_db, stock=1000),
        "card": add_payment_method(test_db, "Card to card", "IMMEDIATE"),
        "zarinpal": add_payment_method(test_db, "Zarinpal", "DAYS_AFTER", 1, fee_bps=100),
        "digipay": add_payment_method(test_db, "Digipay", "DAY_OF_NEXT_MONTH", 7, fee_bps=300),
    }


def _order(conn, setup, method_key, paid, price=100000, status="COMPLETED", **kwargs):
    kwargs.setdefault("shipping_charge", 0)
    method_id = setup[method_key] if isinstance(method_key, str) else method_key
    return record_order(
        conn,
        "WEBSITE",
        [{"product_id": setup["product_id"], "quantity": 1, "unit_price": price}],
        order_date=paid,
        packaging_kit_id=None,
        postage_cost=0,
        payment_method_id=method_id,
        status=status,
        **kwargs,
    )


def _settlement_id_of(conn, order_id):
    return get_order(conn, order_id)["order"]["settlement_id"]


def _pending_for(conn, method_id):
    entries = [e for e in get_pending(conn) if e["payment_method_id"] == method_id]
    return entries[0] if entries else None


def _month_keys(entry):
    return [(g["jalali_year"], g["jalali_month"]) for g in entry["groups"]] if entry else []


def _settlement_count(conn):
    return conn.execute("SELECT COUNT(*) FROM settlements").fetchone()[0]


# ---------------------------------------------------------------- pending


def test_pending_shape_for_date_rules(test_db, setup):
    order_id = _order(test_db, setup, "zarinpal", "2026-10-01", customer_name="Test Buyer")
    entry = _pending_for(test_db, setup["zarinpal"])
    assert {k: entry[k] for k in entry if k != "groups"} == {
        "payment_method_id": setup["zarinpal"],
        "name": "Zarinpal",
        "settlement_rule": "DAYS_AFTER",
        "settlement_days": 1,
        "is_active": 1,
        "total_expected": 99000,
    }
    (group,) = entry["groups"]
    assert {k: group[k] for k in group if k != "orders"} == {
        "expected_date": "2026-10-02",
        "due": True,
        "overdue": True,
        "order_count": 1,
        "customer_total_sum": 100000,
        "fee_sum": 1000,
        "expected_amount": 99000,
    }
    assert group["orders"] == [
        {
            "id": order_id,
            "invoice_number": "INV-000001",
            "order_date": "2026-09-30 20:30:00",
            "paid_date": "2026-10-01",
            "customer_name": "Test Buyer",
            "channel": "WEBSITE",
            "customer_total": 100000,
            "transaction_fee": 1000,
            "expected_amount": 99000,
            "expected_settlement_date": "2026-10-02",
        }
    ]


def test_pending_shape_for_monthly_rule(test_db, setup):
    _order(test_db, setup, "digipay", "2026-09-01")
    _order(test_db, setup, "digipay", "2026-09-23")
    entry = _pending_for(test_db, setup["digipay"])
    shahrivar, mehr = entry["groups"]
    assert {k: shahrivar[k] for k in shahrivar if k != "orders"} == {
        "jalali_year": 1405,
        "jalali_month": 6,
        "month_first_day": "2026-08-23",
        "month_last_day": "2026-09-22",
        "expected_date": "2026-09-29",
        "month_ended": True,
        "can_settle": True,
        "due": True,
        "overdue": True,
        "order_count": 1,
        "customer_total_sum": 100000,
        "fee_sum": 3000,
        "expected_amount": 97000,
    }
    assert (mehr["month_first_day"], mehr["month_last_day"]) == ("2026-09-23", "2026-10-22")
    assert (mehr["expected_date"], mehr["month_ended"], mehr["can_settle"]) == (
        "2026-10-29", False, False,
    )
    assert (mehr["due"], mehr["overdue"]) == (False, False)
    assert entry["total_expected"] == 194000


def test_pending_orders_include_every_method_sorted_by_name(test_db, setup):
    _order(test_db, setup, "zarinpal", "2026-10-01")
    _order(test_db, setup, "card", "2026-10-01")
    _order(test_db, setup, "digipay", "2026-10-01")
    assert [e["name"] for e in get_pending(test_db)] == ["Card to card", "Digipay", "Zarinpal"]


def test_pending_skips_methods_without_pending_orders_and_unpaid_orders(test_db, setup):
    _order(test_db, setup, "zarinpal", "2026-10-01", status="PENDING")
    _order(test_db, setup, None, "2026-10-01")
    assert get_pending(test_db) == []


def test_pending_filter_by_method(test_db, setup):
    _order(test_db, setup, "zarinpal", "2026-10-01")
    _order(test_db, setup, "card", "2026-10-01")
    assert [e["name"] for e in get_pending(test_db, payment_method_id=setup["card"])] == [
        "Card to card"
    ]
    assert get_pending(test_db, payment_method_id=setup["digipay"]) == []


def test_pending_filter_by_unknown_method_is_not_found(test_db, setup):
    with pytest.raises(NotFoundError):
        get_pending(test_db, payment_method_id=999)


def test_pending_today_parameter_overrides_today_local(test_db, setup):
    _order(test_db, setup, "zarinpal", "2026-10-01")
    (group,) = _pending_for(test_db, setup["zarinpal"])["groups"]
    assert group["overdue"] is True
    (group,) = get_pending(test_db, today=date(2026, 10, 2))[0]["groups"]
    assert (group["due"], group["overdue"]) == (True, False)
    (group,) = get_pending(test_db, today=date(2026, 10, 1))[0]["groups"]
    assert (group["due"], group["overdue"]) == (False, False)


@pytest.mark.parametrize("method_key", ["card", "zarinpal"])
def test_date_rule_orders_stay_pending_after_expected_date(test_db, setup, set_today, method_key):
    order_id = _order(test_db, setup, method_key, "2026-09-01")
    set_today(date(2026, 12, 1))
    (group,) = _pending_for(test_db, setup[method_key])["groups"]
    assert (group["due"], group["overdue"]) == (True, True)
    assert [o["id"] for o in group["orders"]] == [order_id]
    assert _settlement_id_of(test_db, order_id) is None


def test_date_groups_by_expected_date_oldest_first(test_db, setup):
    a = _order(test_db, setup, "zarinpal", "2026-10-01")
    b = _order(test_db, setup, "zarinpal", "2026-10-01", price=50000)
    c = _order(test_db, setup, "zarinpal", "2026-10-05")
    d = _order(test_db, setup, "zarinpal", "2026-10-06")
    groups = _pending_for(test_db, setup["zarinpal"])["groups"]
    assert [(g["expected_date"], [o["id"] for o in g["orders"]]) for g in groups] == [
        ("2026-10-02", [a, b]),
        ("2026-10-06", [c]),
        ("2026-10-07", [d]),
    ]
    assert [(g["due"], g["overdue"]) for g in groups] == [(True, True), (True, False), (False, False)]
    assert groups[0]["customer_total_sum"] == 150000
    assert groups[0]["fee_sum"] == 1500
    assert groups[0]["expected_amount"] == 148500


def test_negative_expected_amount_is_allowed(test_db, setup):
    order_id = _order(test_db, setup, "card", "2026-10-01", transaction_fee=150000)
    entry = _pending_for(test_db, setup["card"])
    assert entry["total_expected"] == -50000
    settlement_id = record_settlement(test_db, setup["card"], "2026-10-01", 0, order_ids=[order_id])
    settlement = get_settlement(test_db, settlement_id)
    assert (settlement["expected_amount"], settlement["difference"]) == (-50000, 50000)


# ---------------------------------------------------------------- Jalali month boundaries


@pytest.mark.parametrize(
    "last_day, next_day, month, next_month, length",
    [
        ("2026-09-22", "2026-09-23", (1405, 6), (1405, 7), 31),    # Shahrivar
        ("2026-10-22", "2026-10-23", (1405, 7), (1405, 8), 30),    # Mehr
        ("2026-03-20", "2026-03-21", (1404, 12), (1405, 1), 29),   # Esfand 1404
        ("2025-03-20", "2025-03-21", (1403, 12), (1404, 1), 30),   # Esfand 1403 (leap)
    ],
)
def test_last_day_of_month_belongs_to_its_month(
    test_db, setup, set_today, last_day, next_day, month, next_month, length
):
    set_today(date(2026, 11, 30))
    on_last = _order(test_db, setup, "digipay", last_day)
    on_next = _order(test_db, setup, "digipay", next_day)

    groups = _pending_for(test_db, setup["digipay"])["groups"]
    by_month = {(g["jalali_year"], g["jalali_month"]): g for g in groups}
    assert [o["id"] for o in by_month[month]["orders"]] == [on_last]
    assert [o["id"] for o in by_month[next_month]["orders"]] == [on_next]
    assert by_month[month]["month_last_day"] == last_day
    assert by_month[next_month]["month_first_day"] == next_day
    first = date.fromisoformat(by_month[month]["month_first_day"])
    assert (date.fromisoformat(last_day) - first).days + 1 == length


def test_esfand_expected_date_rolls_into_farvardin(test_db, setup, set_today):
    set_today(date(2026, 4, 10))
    _order(test_db, setup, "digipay", "2026-03-20")
    (group,) = _pending_for(test_db, setup["digipay"])["groups"]
    assert (group["jalali_year"], group["jalali_month"]) == (1404, 12)
    assert group["month_first_day"] == "2026-02-20"
    assert group["expected_date"] == "2026-03-27"
    assert group["can_settle"] is True


def test_paid_on_2025_03_20_groups_into_esfand_1403(test_db, setup, set_today):
    set_today(date(2025, 4, 1))
    order_id = _order(test_db, setup, "digipay", "2025-03-20")
    assert _month_keys(_pending_for(test_db, setup["digipay"])) == [(1403, 12)]
    settlement_id = record_settlement(
        test_db, setup["digipay"], "2025-03-27", 97000, jalali_year=1403, jalali_month=12
    )
    assert _settlement_id_of(test_db, order_id) == settlement_id
    # Farvardin 1404 (2025-03-21..2025-04-20) has ended and holds nothing.
    set_today(date(2025, 5, 1))
    with pytest.raises(ConflictError, match="Nothing to settle"):
        record_settlement(
            test_db, setup["digipay"], "2025-04-25", 0, jalali_year=1404, jalali_month=1
        )


# ---------------------------------------------------------------- whole-month settlement


def test_whole_month_settlement(test_db, setup):
    a = _order(test_db, setup, "digipay", "2026-08-23")
    b = _order(test_db, setup, "digipay", "2026-09-10", price=200000, shipping_charge=50000)
    c = _order(test_db, setup, "digipay", "2026-09-22", price=50000)
    mehr = _order(test_db, setup, "digipay", "2026-09-23")
    # Fees at 3%: 3000, 7500, 1500. Expected 97000 + 242500 + 48500.
    settlement_id = record_settlement(
        test_db,
        setup["digipay"],
        "2026-09-29",
        385000,
        note="Shahrivar payout",
        jalali_year=1405,
        jalali_month=6,
    )

    settlement = get_settlement(test_db, settlement_id)
    assert settlement["expected_amount"] == 388000
    assert settlement["amount_received"] == 385000
    assert settlement["difference"] == -3000
    assert (settlement["jalali_year"], settlement["jalali_month"]) == (1405, 6)
    assert settlement["settled_date"] == "2026-09-29"
    assert settlement["note"] == "Shahrivar payout"
    assert settlement["payment_method_name"] == "Digipay"
    assert settlement["settlement_rule"] == "DAY_OF_NEXT_MONTH"
    assert [o["id"] for o in settlement["orders"]] == [a, b, c]
    assert [o["expected_amount"] for o in settlement["orders"]] == [97000, 242500, 48500]
    assert settlement["orders"][1] == {
        "id": b,
        "invoice_number": "INV-000002",
        "order_date": "2026-09-09 20:30:00",
        "paid_date": "2026-09-10",
        "customer_name": None,
        "channel": "WEBSITE",
        "status": "COMPLETED",
        "customer_total": 250000,
        "transaction_fee": 7500,
        "expected_amount": 242500,
    }
    for order_id in (a, b, c):
        assert _settlement_id_of(test_db, order_id) == settlement_id
    # 06 left pending; 07 (not ended) stays.
    assert _settlement_id_of(test_db, mehr) is None
    assert _month_keys(_pending_for(test_db, setup["digipay"])) == [(1405, 7)]


def test_difference_is_computed_not_stored(test_db, setup):
    _order(test_db, setup, "digipay", "2026-09-10")
    settlement_id = record_settlement(
        test_db, setup["digipay"], "2026-09-29", 98000, jalali_year=1405, jalali_month=6
    )
    columns = {r["name"] for r in test_db.execute("PRAGMA table_info(settlements)")}
    assert "difference" not in columns
    assert get_settlement(test_db, settlement_id)["difference"] == 1000


@pytest.mark.parametrize("order_ids", [[1], []])
def test_monthly_rule_refuses_order_ids_and_writes_nothing(test_db, setup, order_ids):
    _order(test_db, setup, "digipay", "2026-09-10")
    with pytest.raises(ValidationError, match="settles whole months only") as exc_info:
        record_settlement(
            test_db,
            setup["digipay"],
            "2026-09-29",
            97000,
            order_ids=order_ids,
            jalali_year=1405,
            jalali_month=6,
        )
    assert exc_info.value.field == "order_ids"
    assert _settlement_count(test_db) == 0
    assert _settlement_id_of(test_db, 1) is None


def test_settling_06_leaves_07_pending(test_db, setup, set_today):
    on_22 = _order(test_db, setup, "digipay", "2026-09-22")
    on_23 = _order(test_db, setup, "digipay", "2026-09-23")
    record_settlement(test_db, setup["digipay"], "2026-09-29", 97000, jalali_year=1405, jalali_month=6)
    assert _settlement_id_of(test_db, on_22) is not None
    assert _settlement_id_of(test_db, on_23) is None

    set_today(date(2026, 10, 30))
    (group,) = _pending_for(test_db, setup["digipay"])["groups"]
    assert (group["jalali_month"], group["can_settle"]) == (7, True)
    settlement_id = record_settlement(
        test_db, setup["digipay"], "2026-10-29", 97000, jalali_year=1405, jalali_month=7
    )
    assert _settlement_id_of(test_db, on_23) == settlement_id
    assert get_pending(test_db) == []


def test_month_not_ended_is_conflict(test_db, setup):
    _order(test_db, setup, "digipay", "2026-10-01")
    with pytest.raises(ConflictError, match="1405/07 has not ended yet"):
        record_settlement(test_db, setup["digipay"], "2026-10-06", 97000, jalali_year=1405, jalali_month=7)
    assert _settlement_count(test_db) == 0


def test_month_ending_today_has_not_ended(test_db, setup, set_today):
    set_today(date(2026, 10, 22))
    _order(test_db, setup, "digipay", "2026-10-01")
    with pytest.raises(ConflictError, match="has not ended yet"):
        record_settlement(test_db, setup["digipay"], "2026-10-22", 97000, jalali_year=1405, jalali_month=7)
    set_today(date(2026, 10, 23))
    record_settlement(test_db, setup["digipay"], "2026-10-23", 97000, jalali_year=1405, jalali_month=7)


def test_month_settled_twice_is_conflict(test_db, setup):
    _order(test_db, setup, "digipay", "2026-09-10")
    first = record_settlement(
        test_db, setup["digipay"], "2026-09-29", 97000, jalali_year=1405, jalali_month=6
    )
    with pytest.raises(ConflictError, match=f"already settled \\(settlement #{first}\\)"):
        record_settlement(test_db, setup["digipay"], "2026-09-30", 0, jalali_year=1405, jalali_month=6)
    assert _settlement_count(test_db) == 1


def test_empty_month_is_conflict(test_db, setup):
    _order(test_db, setup, "digipay", "2026-09-10")
    with pytest.raises(ConflictError, match="Nothing to settle: 'Digipay' has no pending paid orders in 1405/05"):
        record_settlement(test_db, setup["digipay"], "2026-09-29", 0, jalali_year=1405, jalali_month=5)
    assert _settlement_count(test_db) == 0


def test_month_with_only_unpaid_or_other_method_orders_is_empty(test_db, setup):
    _order(test_db, setup, "digipay", "2026-09-10", status="PENDING")
    _order(test_db, setup, "zarinpal", "2026-09-10")
    with pytest.raises(ConflictError, match="Nothing to settle"):
        record_settlement(test_db, setup["digipay"], "2026-09-29", 0, jalali_year=1405, jalali_month=6)


@pytest.mark.parametrize("settled_date", ["2026-09-22", "2026-09-01"])
def test_settled_date_inside_an_ended_month_is_validation_error(test_db, setup, settled_date):
    _order(test_db, setup, "digipay", "2026-09-10")
    with pytest.raises(ValidationError, match="must be after the end of month 1405/06 \\(2026-09-22\\)") as exc_info:
        record_settlement(test_db, setup["digipay"], settled_date, 97000, jalali_year=1405, jalali_month=6)
    assert exc_info.value.field == "settled_date"
    assert _settlement_count(test_db) == 0


def test_monthly_settled_day_after_month_end_accepted(test_db, setup):
    _order(test_db, setup, "digipay", "2026-09-10")
    settlement_id = record_settlement(
        test_db, setup["digipay"], "2026-09-23", 97000, jalali_year=1405, jalali_month=6
    )
    assert get_settlement(test_db, settlement_id)["settled_date"] == "2026-09-23"


@pytest.mark.parametrize(
    "year, month, field",
    [
        (None, 6, "jalali_year"),
        (1405, None, "jalali_month"),
        (None, None, "jalali_year"),
        (1405, 0, "jalali_month"),
        (1405, 13, "jalali_month"),
        (1405, "6", "jalali_month"),
        ("1405", 6, "jalali_year"),
        (9999, 6, "jalali_year"),
    ],
)
def test_monthly_rule_needs_a_valid_month(test_db, setup, year, month, field):
    _order(test_db, setup, "digipay", "2026-09-10")
    with pytest.raises(ValidationError) as exc_info:
        record_settlement(test_db, setup["digipay"], "2026-09-29", 0, jalali_year=year, jalali_month=month)
    assert exc_info.value.field == field
    assert _settlement_count(test_db) == 0


# ---------------------------------------------------------------- chosen-order settlement


def test_subset_settlement_removes_only_chosen_orders(test_db, setup):
    a = _order(test_db, setup, "zarinpal", "2026-10-01")
    b = _order(test_db, setup, "zarinpal", "2026-10-01", price=50000)
    c = _order(test_db, setup, "zarinpal", "2026-10-02")
    settlement_id = record_settlement(
        test_db, setup["zarinpal"], "2026-10-03", 148000, order_ids=[c, a]
    )
    settlement = get_settlement(test_db, settlement_id)
    assert settlement["expected_amount"] == 99000 + 99000
    assert settlement["difference"] == 148000 - 198000
    assert (settlement["jalali_year"], settlement["jalali_month"]) == (None, None)
    assert sorted(o["id"] for o in settlement["orders"]) == [a, c]

    (group,) = _pending_for(test_db, setup["zarinpal"])["groups"]
    assert [o["id"] for o in group["orders"]] == [b]
    assert _pending_for(test_db, setup["zarinpal"])["total_expected"] == 49500


def test_settling_before_expected_date_is_allowed(test_db, setup):
    order_id = _order(test_db, setup, "zarinpal", "2026-10-06")  # expected 2026-10-07
    settlement_id = record_settlement(test_db, setup["zarinpal"], "2026-10-06", 99000, order_ids=[order_id])
    assert _settlement_id_of(test_db, order_id) == settlement_id


def test_settled_date_before_latest_paid_date_rejected(test_db, setup):
    a = _order(test_db, setup, "card", "2026-10-01")
    b = _order(test_db, setup, "card", "2026-10-04")
    with pytest.raises(ValidationError, match="before the latest paid date of its orders \\(2026-10-04\\)") as exc_info:
        record_settlement(test_db, setup["card"], "2026-10-03", 200000, order_ids=[a, b])
    assert exc_info.value.field == "settled_date"
    record_settlement(test_db, setup["card"], "2026-10-04", 200000, order_ids=[a, b])


def test_subset_rule_refuses_month_fields(test_db, setup):
    order_id = _order(test_db, setup, "card", "2026-10-01")
    with pytest.raises(ValidationError) as exc_info:
        record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[order_id], jalali_year=1405)
    assert exc_info.value.field == "jalali_year"
    with pytest.raises(ValidationError) as exc_info:
        record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[order_id], jalali_month=7)
    assert exc_info.value.field == "jalali_month"


@pytest.mark.parametrize("order_ids", [None, [], ()])
def test_subset_rule_requires_order_ids(test_db, setup, order_ids):
    with pytest.raises(ValidationError) as exc_info:
        record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=order_ids)
    assert exc_info.value.field == "order_ids"


def test_duplicate_order_ids_rejected(test_db, setup):
    order_id = _order(test_db, setup, "card", "2026-10-01")
    with pytest.raises(ValidationError, match="duplicates") as exc_info:
        record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[order_id, order_id])
    assert exc_info.value.field == "order_ids"
    assert _settlement_count(test_db) == 0


def test_foreign_method_order_rejected(test_db, setup):
    mine = _order(test_db, setup, "card", "2026-10-01")
    foreign = _order(test_db, setup, "zarinpal", "2026-10-01")
    no_method = _order(test_db, setup, None, "2026-10-01")
    for bad in (foreign, no_method):
        with pytest.raises(ValidationError, match=f"Order #{bad} was not paid with 'Card to card'") as exc_info:
            record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[mine, bad])
        assert exc_info.value.field == "order_ids"
    assert _settlement_count(test_db) == 0
    assert _settlement_id_of(test_db, mine) is None


def test_missing_order_rejected(test_db, setup):
    with pytest.raises(ValidationError, match="Order #999 does not exist") as exc_info:
        record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[999])
    assert exc_info.value.field == "order_ids"


def test_already_settled_order_is_conflict(test_db, setup):
    a = _order(test_db, setup, "card", "2026-10-01")
    b = _order(test_db, setup, "card", "2026-10-01")
    first = record_settlement(test_db, setup["card"], "2026-10-02", 100000, order_ids=[a])
    with pytest.raises(ConflictError, match=f"Order #{a} is already in settlement #{first}"):
        record_settlement(test_db, setup["card"], "2026-10-02", 200000, order_ids=[b, a])
    assert _settlement_count(test_db) == 1
    assert _settlement_id_of(test_db, b) is None


@pytest.mark.parametrize(
    "create_status, action, expected_status",
    [
        ("PAID", "CANCELLED", "CANCELLED"),
        ("COMPLETED", "REFUNDED", "REFUNDED"),
        ("PENDING", None, "PENDING"),
    ],
)
def test_unpaid_order_is_conflict(test_db, setup, create_status, action, expected_status):
    good = _order(test_db, setup, "card", "2026-10-01")
    bad = _order(test_db, setup, "card", "2026-10-01", status=create_status)
    if action:
        process_return(test_db, bad, action)
    with pytest.raises(ConflictError, match=f"Order #{bad} is {expected_status}, not paid"):
        record_settlement(test_db, setup["card"], "2026-10-02", 1, order_ids=[good, bad])
    assert _settlement_count(test_db) == 0
    assert _settlement_id_of(test_db, good) is None


# ---------------------------------------------------------------- common validation


def test_unknown_method_is_not_found(test_db, setup):
    with pytest.raises(NotFoundError):
        record_settlement(test_db, 999, "2026-10-02", 1, order_ids=[1])


@pytest.mark.parametrize("amount", [-1, 1.5, "100", True, None])
def test_amount_received_must_be_non_negative_int(test_db, setup, amount):
    order_id = _order(test_db, setup, "card", "2026-10-01")
    with pytest.raises(ValidationError) as exc_info:
        record_settlement(test_db, setup["card"], "2026-10-02", amount, order_ids=[order_id])
    assert exc_info.value.field == "amount_received"
    assert _settlement_count(test_db) == 0


def test_amount_received_zero_accepted(test_db, setup):
    order_id = _order(test_db, setup, "card", "2026-10-01")
    settlement_id = record_settlement(test_db, setup["card"], "2026-10-02", 0, order_ids=[order_id])
    assert get_settlement(test_db, settlement_id)["difference"] == -100000


@pytest.mark.parametrize("settled_date", ["2026-10-07", "2026-02-30", "06/10/2026", "", None])
def test_settled_date_must_be_valid_and_not_future(test_db, setup, settled_date):
    order_id = _order(test_db, setup, "card", "2026-10-01")
    with pytest.raises(ValidationError) as exc_info:
        record_settlement(test_db, setup["card"], settled_date, 1, order_ids=[order_id])
    assert exc_info.value.field == "settled_date"


def test_settled_today_accepted(test_db, setup):
    order_id = _order(test_db, setup, "card", "2026-10-01")
    settlement_id = record_settlement(test_db, setup["card"], "2026-10-06", 1, order_ids=[order_id])
    assert get_settlement(test_db, settlement_id)["settled_date"] == "2026-10-06"


# ---------------------------------------------------------------- cancel / refund interplay


def test_cancelling_an_unsettled_order_drops_it_from_its_group(test_db, setup):
    a = _order(test_db, setup, "zarinpal", "2026-10-01", status="PAID")
    b = _order(test_db, setup, "zarinpal", "2026-10-01", price=50000)
    process_return(test_db, a, "CANCELLED")
    entry = _pending_for(test_db, setup["zarinpal"])
    (group,) = entry["groups"]
    assert [o["id"] for o in group["orders"]] == [b]
    assert (group["order_count"], group["expected_amount"], entry["total_expected"]) == (1, 49500, 49500)


def test_refunding_an_unsettled_monthly_order_drops_it_from_the_month(test_db, setup):
    a = _order(test_db, setup, "digipay", "2026-09-10")
    b = _order(test_db, setup, "digipay", "2026-09-11")
    process_return(test_db, a, "REFUNDED")
    (group,) = _pending_for(test_db, setup["digipay"])["groups"]
    assert [o["id"] for o in group["orders"]] == [b]
    settlement_id = record_settlement(
        test_db, setup["digipay"], "2026-09-29", 97000, jalali_year=1405, jalali_month=6
    )
    assert get_settlement(test_db, settlement_id)["expected_amount"] == 97000
    assert _settlement_id_of(test_db, a) is None


def test_refunding_a_settled_order_leaves_the_settlement_untouched(test_db, setup):
    a = _order(test_db, setup, "card", "2026-10-01")
    b = _order(test_db, setup, "card", "2026-10-01")
    settlement_id = record_settlement(test_db, setup["card"], "2026-10-02", 200000, order_ids=[a, b])
    process_return(test_db, a, "REFUNDED")

    settlement = get_settlement(test_db, settlement_id)
    assert settlement["expected_amount"] == 200000
    assert settlement["difference"] == 0
    assert [(o["id"], o["status"]) for o in settlement["orders"]] == [(a, "REFUNDED"), (b, "COMPLETED")]
    assert _settlement_id_of(test_db, a) == settlement_id
    assert get_pending(test_db) == []


# ---------------------------------------------------------------- read and list


def test_get_missing_settlement_is_not_found(test_db, setup):
    with pytest.raises(NotFoundError, match="Settlement with id 999 does not exist"):
        get_settlement(test_db, 999)


def test_list_settlements_newest_first_with_filters(test_db, setup):
    a = _order(test_db, setup, "card", "2026-10-01")
    b = _order(test_db, setup, "card", "2026-10-01")
    c = _order(test_db, setup, "zarinpal", "2026-10-01")
    d = _order(test_db, setup, "zarinpal", "2026-10-01")
    s1 = record_settlement(test_db, setup["card"], "2026-10-03", 100000, order_ids=[a])
    s2 = record_settlement(test_db, setup["zarinpal"], "2026-10-02", 99500, order_ids=[c])
    s3 = record_settlement(test_db, setup["card"], "2026-10-03", 99000, order_ids=[b])
    s4 = record_settlement(test_db, setup["zarinpal"], "2026-10-05", 99000, order_ids=[d])

    listed = list_settlements(test_db)
    assert [s["id"] for s in listed] == [s4, s3, s1, s2]
    by_id = {s["id"]: s for s in listed}
    assert by_id[s2]["difference"] == 500
    assert by_id[s3]["difference"] == -1000
    assert by_id[s1]["order_count"] == 1
    assert by_id[s4]["payment_method_name"] == "Zarinpal"

    assert [s["id"] for s in list_settlements(test_db, payment_method_id=setup["card"])] == [s3, s1]
    # Inclusive calendar-day bounds.
    assert [s["id"] for s in list_settlements(test_db, start_date="2026-10-03")] == [s4, s3, s1]
    assert [s["id"] for s in list_settlements(test_db, end_date="2026-10-03")] == [s3, s1, s2]
    assert [
        s["id"] for s in list_settlements(test_db, start_date="2026-10-03", end_date="2026-10-03")
    ] == [s3, s1]
    assert list_settlements(test_db, start_date="2026-10-06") == []


def test_list_settlements_order_count_for_a_month(test_db, setup):
    for paid in ("2026-09-01", "2026-09-02", "2026-09-03"):
        _order(test_db, setup, "digipay", paid)
    record_settlement(test_db, setup["digipay"], "2026-09-29", 291000, jalali_year=1405, jalali_month=6)
    (listed,) = list_settlements(test_db)
    assert (listed["order_count"], listed["expected_amount"], listed["difference"]) == (3, 291000, 0)


@pytest.mark.parametrize("field", ["start_date", "end_date"])
def test_list_settlements_invalid_date(test_db, setup, field):
    with pytest.raises(ValidationError) as exc_info:
        list_settlements(test_db, **{field: "2026-13-01"})
    assert exc_info.value.field == field


# ---------------------------------------------------------------- update


@pytest.fixture
def two_settlements(test_db, setup):
    a = _order(test_db, setup, "card", "2026-10-01")
    b = _order(test_db, setup, "card", "2026-10-03")
    subset_id = record_settlement(
        test_db, setup["card"], "2026-10-04", 200000, note="first", order_ids=[a, b]
    )
    _order(test_db, setup, "digipay", "2026-09-10")
    month_id = record_settlement(
        test_db, setup["digipay"], "2026-09-29", 97000, jalali_year=1405, jalali_month=6
    )
    return {"subset": subset_id, "month": month_id, "orders": [a, b]}


def _snapshot(conn, settlement_id):
    settlement = get_settlement(conn, settlement_id)
    return settlement["expected_amount"], [o["id"] for o in settlement["orders"]]


def test_update_amount_received(test_db, two_settlements):
    sid = two_settlements["subset"]
    before = _snapshot(test_db, sid)
    update_settlement(test_db, sid, amount_received=195000)
    settlement = get_settlement(test_db, sid)
    assert (settlement["amount_received"], settlement["difference"]) == (195000, -5000)
    assert _snapshot(test_db, sid) == before


def test_update_settled_date(test_db, two_settlements):
    update_settlement(test_db, two_settlements["subset"], settled_date="2026-10-03")
    update_settlement(test_db, two_settlements["month"], settled_date=" 2026-09-23 ")
    assert get_settlement(test_db, two_settlements["subset"])["settled_date"] == "2026-10-03"
    assert get_settlement(test_db, two_settlements["month"])["settled_date"] == "2026-09-23"


def test_update_note_set_and_cleared(test_db, two_settlements):
    sid = two_settlements["subset"]
    update_settlement(test_db, sid, note="bank ref 42")
    assert get_settlement(test_db, sid)["note"] == "bank ref 42"
    update_settlement(test_db, sid, note=None)
    assert get_settlement(test_db, sid)["note"] is None


def test_update_several_fields_at_once(test_db, two_settlements):
    sid = two_settlements["month"]
    before = _snapshot(test_db, sid)
    update_settlement(test_db, sid, amount_received=90000, settled_date="2026-10-01", note="late")
    settlement = get_settlement(test_db, sid)
    assert (settlement["amount_received"], settlement["settled_date"], settlement["note"]) == (
        90000, "2026-10-01", "late",
    )
    assert _snapshot(test_db, sid) == before


def test_update_with_no_fields_changes_nothing(test_db, two_settlements):
    before = get_settlement(test_db, two_settlements["subset"])
    update_settlement(test_db, two_settlements["subset"])
    assert get_settlement(test_db, two_settlements["subset"]) == before


@pytest.mark.parametrize("field", ["expected_amount", "order_ids", "payment_method_id", "jalali_month"])
def test_update_unknown_field_is_validation_error(test_db, two_settlements, field):
    before = get_settlement(test_db, two_settlements["subset"])
    with pytest.raises(ValidationError, match=f"Unknown field '{field}'") as exc_info:
        update_settlement(test_db, two_settlements["subset"], **{field: 1}, note="x")
    assert exc_info.value.field == field
    assert get_settlement(test_db, two_settlements["subset"]) == before


def test_update_missing_settlement_is_not_found(test_db, setup):
    with pytest.raises(NotFoundError):
        update_settlement(test_db, 999, note="x")


@pytest.mark.parametrize("amount", [-1, 1.5, True])
def test_update_amount_received_validated(test_db, two_settlements, amount):
    with pytest.raises(ValidationError) as exc_info:
        update_settlement(test_db, two_settlements["subset"], amount_received=amount)
    assert exc_info.value.field == "amount_received"
    assert get_settlement(test_db, two_settlements["subset"])["amount_received"] == 200000


@pytest.mark.parametrize(
    "key, settled_date, message",
    [
        ("subset", "2026-10-07", "is in the future"),
        ("subset", "2026-31-01", "Invalid date"),
        ("subset", "2026-10-02", "before the latest paid date of its orders \\(2026-10-03\\)"),
        ("month", "2026-10-07", "is in the future"),
        ("month", "2026-09-22", "must be after the end of month 1405/06"),
        ("month", "2026-09-01", "must be after the end of month 1405/06"),
    ],
)
def test_update_settled_date_refusals(test_db, two_settlements, key, settled_date, message):
    sid = two_settlements[key]
    before = get_settlement(test_db, sid)
    with pytest.raises(ValidationError, match=message) as exc_info:
        update_settlement(test_db, sid, settled_date=settled_date, note="changed")
    assert exc_info.value.field == "settled_date"
    assert get_settlement(test_db, sid) == before


def test_update_monthly_settlement_uses_its_month_after_a_rule_change(test_db, setup, two_settlements):
    # Nothing is pending for Digipay, so its rule may change; the old monthly
    # settlement still follows its own month.
    update_payment_method(test_db, setup["digipay"], settlement_rule="IMMEDIATE", settlement_days=None)
    with pytest.raises(ValidationError, match="must be after the end of month 1405/06"):
        update_settlement(test_db, two_settlements["month"], settled_date="2026-09-15")


# ---------------------------------------------------------------- deactivated methods


def test_deactivated_method_still_lists_settles_and_updates(test_db, setup, set_today):
    card_order = _order(test_db, setup, "card", "2026-10-01")
    digipay_order = _order(test_db, setup, "digipay", "2026-09-10")
    deactivate_payment_method(test_db, setup["card"])
    deactivate_payment_method(test_db, setup["digipay"])

    entries = {e["name"]: e for e in get_pending(test_db)}
    assert entries["Card to card"]["is_active"] == 0
    assert entries["Digipay"]["is_active"] == 0
    assert [o["id"] for o in entries["Card to card"]["groups"][0]["orders"]] == [card_order]

    card_settlement = record_settlement(test_db, setup["card"], "2026-10-02", 100000, order_ids=[card_order])
    month_settlement = record_settlement(
        test_db, setup["digipay"], "2026-09-29", 97000, jalali_year=1405, jalali_month=6
    )
    assert _settlement_id_of(test_db, card_order) == card_settlement
    assert _settlement_id_of(test_db, digipay_order) == month_settlement

    update_settlement(test_db, card_settlement, amount_received=99000)
    update_settlement(test_db, month_settlement, note="corrected")
    assert get_settlement(test_db, card_settlement)["difference"] == -1000
    assert get_settlement(test_db, month_settlement)["note"] == "corrected"
    assert get_pending(test_db) == []


# ---------------------------------------------------------------- fee cap


def test_settlement_over_orders_before_and_after_a_cap_change(test_db, setup):
    method_id = add_payment_method(
        test_db, "Zarinpal capped", "DAYS_AFTER", 1, fee_bps=50, fee_cap=160_000, fee_fixed=5_000
    )
    old_big = _order(test_db, setup, method_id, "2026-10-01", price=94_900_000)      # fee 165,000
    old_small = _order(test_db, setup, method_id, "2026-10-01", price=18_300_000)    # fee 96,500
    update_payment_method(test_db, method_id, fee_cap=100_000)
    new_big = _order(test_db, setup, method_id, "2026-10-02", price=94_900_000)      # fee 105,000
    new_tie = _order(test_db, setup, method_id, "2026-10-02", price=19_999_900)      # 99,999.5 -> 100,000 = cap

    fees = {
        oid: get_order(test_db, oid)["order"]["transaction_fee"]
        for oid in (old_big, old_small, new_big, new_tie)
    }
    assert fees == {old_big: 165_000, old_small: 96_500, new_big: 105_000, new_tie: 105_000}

    customer_total = 94_900_000 + 18_300_000 + 94_900_000 + 19_999_900
    expected = customer_total - sum(fees.values())
    settlement_id = record_settlement(
        test_db, method_id, "2026-10-03", expected, order_ids=[old_big, old_small, new_big, new_tie]
    )
    settlement = get_settlement(test_db, settlement_id)
    assert settlement["expected_amount"] == expected
    assert settlement["difference"] == 0
