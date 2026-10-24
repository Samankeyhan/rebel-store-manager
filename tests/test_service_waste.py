"""Waste of a service (accounting rules section 8): a WASTE movement with no stock change, valued at the price per unit it stores."""

from datetime import date

import pytest

import db.timeutil
from db.adjustments import get_stock_movement, list_stock_adjustments, record_service_waste, record_stock_adjustment
from db.audit import list_audit_log
from db.constants import MAX_MONEY, MAX_QUANTITY
from db.distributions import record_profit_distribution
from db.errors import ErrorCode, NotFoundError, ValidationError
from db.materials import add_material, deactivate_material, get_material, update_material
from db.partners import add_partner
from db.reports import get_profit_and_loss, get_waste_report

TODAY = date(2026, 10, 20)


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(db.timeutil, "today_local", lambda conn=None: TODAY)


@pytest.fixture
def printing(test_db):
    return add_material(test_db, "Fictional Printing", "SERVICE", 90_000, unit="sheet")


def _movements(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0]


def test_stores_a_waste_movement_at_the_current_cost(test_db, printing):
    movement_id = record_service_waste(test_db, printing, 2, notes="failed job", movement_date="2026-10-18")
    row = get_stock_movement(test_db, movement_id)
    assert (row["item_type"], row["item_id"], row["quantity_change"], row["reason"]) == ("MATERIAL", printing, -2, "WASTE")
    assert row["unit_cost_at_time"] == 90_000
    assert row["notes"] == "failed job"
    assert row["reference_order_id"] is None and row["reference_production_batch_id"] is None
    assert row["item_name"] == "Fictional Printing"


def test_no_stock_change(test_db, printing):
    before = get_material(test_db, printing)
    record_service_waste(test_db, printing, 3)
    after = get_material(test_db, printing)
    assert before["current_stock"] is None and after["current_stock"] is None
    assert after["unit_cost"] == before["unit_cost"] == 90_000


def test_a_fractional_quantity_is_allowed(test_db, printing):
    movement_id = record_service_waste(test_db, printing, 0.5)
    assert get_stock_movement(test_db, movement_id)["quantity_change"] == -0.5


def test_the_price_override_is_what_is_stored(test_db, printing):
    movement_id = record_service_waste(test_db, printing, 3, unit_cost=333)
    assert get_stock_movement(test_db, movement_id)["unit_cost_at_time"] == 333
    assert get_material(test_db, printing)["unit_cost"] == 90_000  # the material's own cost is untouched


def test_the_cost_is_frozen_at_the_time(test_db, printing):
    movement_id = record_service_waste(test_db, printing, 1)
    test_db.execute("UPDATE materials SET unit_cost = 1 WHERE id = ?", (printing,))
    assert get_stock_movement(test_db, movement_id)["unit_cost_at_time"] == 90_000


def test_a_service_without_a_cost_is_refused_with_its_code(test_db):
    free = add_material(test_db, "Fictional Free Service", "SERVICE", 0)
    with pytest.raises(ValidationError) as caught:
        record_service_waste(test_db, free, 1)
    assert caught.value.code == ErrorCode.MATERIAL_NO_UNIT_COST
    assert caught.value.details == {"material_id": free, "material_name": "Fictional Free Service"}
    assert _movements(test_db) == 0


def test_an_override_does_not_get_around_a_missing_cost(test_db):
    free = add_material(test_db, "Fictional Free Service", "SERVICE", 0)
    with pytest.raises(ValidationError) as caught:
        record_service_waste(test_db, free, 1, unit_cost=500)
    assert caught.value.code == ErrorCode.MATERIAL_NO_UNIT_COST


@pytest.mark.parametrize("bad", [0, -5, True, 1.5, "10"])
def test_the_price_must_be_a_whole_rial_of_at_least_one(test_db, printing, bad):
    with pytest.raises(ValidationError) as caught:
        record_service_waste(test_db, printing, 1, unit_cost=bad)
    assert caught.value.field == "unit_cost"
    assert _movements(test_db) == 0


@pytest.mark.parametrize("bad", [0, -1, True, "2", None])
def test_the_quantity_must_be_a_positive_number(test_db, printing, bad):
    with pytest.raises(ValidationError) as caught:
        record_service_waste(test_db, printing, bad)
    assert caught.value.field == "quantity"
    assert _movements(test_db) == 0


def test_a_quantity_over_the_limit_is_refused(test_db, printing):
    with pytest.raises(ValidationError) as caught:
        record_service_waste(test_db, printing, MAX_QUANTITY + 1)
    assert caught.value.code == ErrorCode.QUANTITY_OUT_OF_RANGE


def test_an_amount_over_the_money_limit_is_refused(test_db, printing):
    with pytest.raises(ValidationError) as caught:
        record_service_waste(test_db, printing, 2, unit_cost=MAX_MONEY)
    assert caught.value.code == ErrorCode.AMOUNT_TOO_LARGE
    assert _movements(test_db) == 0


def test_a_missing_inactive_or_stock_material_is_refused(test_db, printing):
    with pytest.raises(NotFoundError):
        record_service_waste(test_db, 99999, 1)
    deactivate_material(test_db, printing)
    with pytest.raises(ValidationError, match="not active"):
        record_service_waste(test_db, printing, 1)
    stock = add_material(test_db, "Fictional Ink", "STOCK", 100, initial_stock=10)
    with pytest.raises(ValidationError, match="not a SERVICE"):
        record_service_waste(test_db, stock, 1)
    assert _movements(test_db) == 0


def test_the_stock_adjustment_still_refuses_a_service(test_db, printing):
    with pytest.raises(ValidationError, match="SERVICE"):
        record_stock_adjustment(test_db, "MATERIAL", printing, -1, "WASTE")


def test_a_future_date_is_refused(test_db, printing):
    with pytest.raises(ValidationError) as caught:
        record_service_waste(test_db, printing, 1, movement_date="2026-10-21")
    assert caught.value.code == ErrorCode.DATE_IN_FUTURE
    assert caught.value.field == "movement_date"
    assert caught.value.details == {"today": "2026-10-20"}
    assert _movements(test_db) == 0


def test_today_and_a_past_day_are_accepted(test_db, printing):
    record_service_waste(test_db, printing, 1, movement_date="2026-10-20")
    record_service_waste(test_db, printing, 1, movement_date="2026-09-01")
    record_service_waste(test_db, printing, 1)
    assert _movements(test_db) == 3


def test_a_bad_date_is_a_validation_error(test_db, printing):
    with pytest.raises(ValidationError):
        record_service_waste(test_db, printing, 1, movement_date="not a date")


def test_a_closed_day_does_not_refuse_a_new_record(test_db, printing):
    add_partner(test_db, "Fictional Partner", 100.0)
    record_profit_distribution(
        test_db, "2026-01-01", "2026-01-31", 1000, distribution_date="2026-02-01", allow_exceeding=True
    )
    record_service_waste(test_db, printing, 1, movement_date="2026-01-15")
    assert _movements(test_db) == 1


def test_the_waste_report_and_the_profit_and_loss_include_it(test_db, printing):
    record_service_waste(test_db, printing, 2, movement_date="2026-10-10")
    record_service_waste(test_db, printing, 0.5, movement_date="2026-10-11", unit_cost=333)
    rows = get_waste_report(test_db, "2026-10-01", "2026-10-31")
    assert len(rows) == 1
    row = rows[0]
    assert (row["item_type"], row["item_id"], row["unit"]) == ("MATERIAL", printing, "sheet")
    assert (row["total_wasted"], row["waste_event_count"], row["unknown_cost_count"]) == (2.5, 2, 0)
    # The item's exact sum, rounded once, half-even: 2 x 90000 + 0.5 x 333 = 180166.5 -> 180166.
    assert row["cost"] == 180_166
    assert get_profit_and_loss(test_db, "2026-10-01", "2026-10-31")["waste_cost"] == 180_166


def test_it_is_outside_the_range_of_another_month(test_db, printing):
    record_service_waste(test_db, printing, 1, movement_date="2026-09-10")
    assert get_waste_report(test_db, "2026-10-01", "2026-10-31") == []
    assert get_profit_and_loss(test_db, "2026-10-01", "2026-10-31")["waste_cost"] == 0


def test_the_history_lists_it(test_db, printing):
    movement_id = record_service_waste(test_db, printing, 1)
    rows = list_stock_adjustments(test_db, item_type="MATERIAL", reason="WASTE")
    assert [r["id"] for r in rows] == [movement_id]


def test_one_audit_operation(test_db, printing):
    record_service_waste(test_db, printing, 1)
    page = list_audit_log(test_db, operation="record_service_waste", limit=50)
    assert page["total"] > 0
    assert {e["entity_type"] for e in page["items"]} == {"stock_movements"}
    assert len({e["op_id"] for e in page["items"]}) == 1


def test_a_material_type_cannot_be_changed(test_db, printing):
    """`type` is fixed at creation: the only updatable field is min_stock, so a service can never turn into a STOCK
    material (whose stock replay would then see a service waste)."""
    with pytest.raises(ValidationError) as caught:
        update_material(test_db, printing, type="STOCK")
    assert caught.value.field == "type"
    assert get_material(test_db, printing)["type"] == "SERVICE"
