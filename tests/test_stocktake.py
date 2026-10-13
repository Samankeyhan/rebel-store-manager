"""Stocktake (db/stocktake.py): a physical count becomes ADJUSTMENT movements, all or nothing."""

import json
from fractions import Fraction

import pytest

from db.adjustments import list_stock_adjustments, record_stock_adjustment
from db.audit import list_audit_log
from db.errors import ConflictError, ErrorCode, ValidationError
from db.materials import add_material, deactivate_material
from db.products import add_product, deactivate_product, get_product
from db.stocktake import MAX_ITEMS, apply_stocktake, difference, plan_stocktake, stocktake_note
from tests.helpers import cat


def _stock(conn, table, item_id):
    return conn.execute(f"SELECT current_stock, unit_cost FROM {table} WHERE id = ?", (item_id,)).fetchone()


def _counts(conn):
    return {
        "movements": conn.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0],
        "audit": conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0],
        "stock": [tuple(r) for r in conn.execute(
            "SELECT 'p', id, current_stock, unit_cost FROM products UNION ALL SELECT 'm', id, current_stock, unit_cost FROM materials ORDER BY 1, 2")],
    }


def _product(conn, name="Fictional LP", stock=0, unit_cost=None):
    product_id = add_product(conn, name, cat(conn, "VINYL"), 3_000_000, 2_000_000)
    conn.execute("UPDATE products SET current_stock = ?, unit_cost = ? WHERE id = ?", (stock, unit_cost, product_id))
    return product_id


def item(kind, item_id, counted, system, unit_cost=None):
    entry = {"item_type": kind, "item_id": item_id, "counted": counted, "system_quantity": system}
    if unit_cost is not None:
        entry["unit_cost"] = unit_cost
    return entry


# ------------------------------------------------------------------- the maths


def test_difference_is_exact_decimal_arithmetic_rounded_to_a_billionth():
    assert difference(0.3, 0.1 + 0.2) == 0  # 0.30000000000000004 is noise
    assert difference(5, 2) == 3
    assert difference(2.5, 5) == Fraction(-5, 2)
    assert difference(0.1, 0) == Fraction(1, 10)
    assert difference(1.0000000004, 1) == 0  # below 1e-9
    assert difference(1.000000001, 1) == Fraction(1, 10**9)


def test_the_note_has_the_jalali_date_in_persian_digits():
    from datetime import date

    assert stocktake_note(date(2026, 10, 13)) == "شمارش موجودی ۱۴۰۵/۰۷/۲۱"
    assert stocktake_note(date(2026, 10, 13), "انبار اصلی") == "شمارش موجودی ۱۴۰۵/۰۷/۲۱ — انبار اصلی"


# --------------------------------------------------------------------- gains


def test_a_gain_on_a_material_uses_its_current_cost_and_keeps_it(test_db):
    box = add_material(test_db, "Fictional Box", "STOCK", 12_000, initial_stock=10)
    result = apply_stocktake(test_db, [item("MATERIAL", box, 14.5, 10)], "2026-10-12")
    (c,) = result["corrections"]
    assert (c["old_quantity"], c["new_quantity"], c["difference"]) == (10, 14.5, 4.5)
    assert c["unit_cost"] == 12_000 and c["value"] == 54_000 and result["total_value"] == 54_000
    stock = _stock(test_db, "materials", box)
    assert (stock["current_stock"], stock["unit_cost"]) == (14.5, 12_000)
    movement = list_stock_adjustments(test_db)[0]
    assert (movement["reason"], movement["quantity_change"], movement["unit_cost_at_time"]) == ("ADJUSTMENT", 4.5, 12_000)
    assert movement["id"] == c["movement_id"]


def test_a_gain_with_a_unit_cost_blends_the_cost_by_weighted_average(test_db):
    box = add_material(test_db, "Fictional Box", "STOCK", 1_000, initial_stock=10)
    apply_stocktake(test_db, [item("MATERIAL", box, 20, 10, unit_cost=2_000)])
    # (10 x 1000 + 10 x 2000) / 20 = 1500
    assert _stock(test_db, "materials", box)["unit_cost"] == 1_500


def test_opening_stock_of_a_product_with_no_cost_needs_a_cost(test_db):
    product = _product(test_db)
    before = _counts(test_db)
    with pytest.raises(ValidationError) as exc_info:
        apply_stocktake(test_db, [item("PRODUCT", product, 12, 0)])
    exc = exc_info.value
    assert exc.code == ErrorCode.PRODUCT_NO_UNIT_COST and exc.field == "items.0.unit_cost"
    assert exc.details == {"product_id": product, "product_name": "Fictional LP"}
    assert _counts(test_db) == before

    result = apply_stocktake(test_db, [item("PRODUCT", product, 12, 0, unit_cost=1_500_000)])
    stock = _stock(test_db, "products", product)
    assert (stock["current_stock"], stock["unit_cost"]) == (12, 1_500_000)
    assert result["corrections"][0]["value"] == 18_000_000


def test_a_gain_on_a_product_that_has_a_cost_may_leave_the_cost_blank(test_db):
    product = _product(test_db, stock=2, unit_cost=500_000)
    result = apply_stocktake(test_db, [item("PRODUCT", product, 5, 2)])
    assert _stock(test_db, "products", product)["unit_cost"] == 500_000
    assert result["corrections"][0]["value"] == 1_500_000


# ---------------------------------------------------------------------- losses


def test_a_loss_is_an_adjustment_not_waste_and_is_valued_at_the_current_cost(test_db):
    product = _product(test_db, stock=10, unit_cost=333)
    result = apply_stocktake(test_db, [item("PRODUCT", product, 7, 10)])
    (c,) = result["corrections"]
    assert c["difference"] == -3 and c["value"] == -999
    movement = list_stock_adjustments(test_db)[0]
    assert movement["reason"] == "ADJUSTMENT" and movement["quantity_change"] == -3
    assert get_product(test_db, product)["current_stock"] == 7
    assert not list_stock_adjustments(test_db, reason="WASTE")


def test_a_loss_on_an_item_with_unknown_cost_has_no_value(test_db):
    product = _product(test_db, stock=4, unit_cost=None)
    result = apply_stocktake(test_db, [item("PRODUCT", product, 1, 4)])
    assert result["corrections"][0]["value"] is None
    assert (result["total_value"], result["unvalued_count"]) == (0, 1)


def test_counting_everything_away_leaves_exactly_zero_even_with_float_residue(test_db):
    ink = add_material(test_db, "Fictional Ink", "STOCK", 700, initial_stock=0.1)
    test_db.execute("UPDATE materials SET current_stock = ? WHERE id = ?", (0.1 + 0.2 - 0.2, ink))  # 0.10000000000000003
    live = _stock(test_db, "materials", ink)["current_stock"]
    apply_stocktake(test_db, [item("MATERIAL", ink, 0, live)])
    assert _stock(test_db, "materials", ink)["current_stock"] == 0


def test_a_unit_cost_on_a_loss_is_refused(test_db):
    product = _product(test_db, stock=4, unit_cost=100)
    with pytest.raises(ValidationError) as exc_info:
        apply_stocktake(test_db, [item("PRODUCT", product, 1, 4, unit_cost=100)])
    assert exc_info.value.field == "items.0.unit_cost"


# ------------------------------------------------------- unchanged and mixed


def test_a_count_equal_to_the_system_changes_nothing_even_with_float_noise(test_db):
    ink = add_material(test_db, "Fictional Ink", "STOCK", 700, initial_stock=0.1)
    test_db.execute("UPDATE materials SET current_stock = ? WHERE id = ?", (0.1 + 0.2, ink))
    product = _product(test_db, stock=3, unit_cost=10)
    before = _counts(test_db)
    result = apply_stocktake(test_db, [item("MATERIAL", ink, 0.3, 0.1 + 0.2), item("PRODUCT", product, 3, 3)])
    assert result["corrections"] == [] and result["unchanged_count"] == 2 and result["total_value"] == 0
    assert _counts(test_db) == before


def test_a_mixed_count_corrects_only_what_differs(test_db):
    gain = _product(test_db, "Gain", stock=1, unit_cost=1_000)
    loss = _product(test_db, "Loss", stock=9, unit_cost=2_000)
    same = _product(test_db, "Same", stock=5, unit_cost=3_000)
    uncounted = _product(test_db, "Uncounted", stock=8, unit_cost=4_000)
    box = add_material(test_db, "Box", "STOCK", 50, initial_stock=2.5)
    result = apply_stocktake(test_db, [
        item("PRODUCT", gain, 4, 1), item("PRODUCT", loss, 6, 9), item("PRODUCT", same, 5, 5),
        item("MATERIAL", box, 2.25, 2.5),
    ])
    assert [(c["item_name"], c["difference"]) for c in result["corrections"]] == [("Gain", 3), ("Loss", -3), ("Box", -0.25)]
    # 3 x 1000 - 3 x 2000 + (-0.25 x 50 = -12.5, half-even -> -12)
    assert result["unchanged_count"] == 1 and result["total_value"] == 3_000 - 6_000 - 12
    assert _stock(test_db, "products", uncounted)["current_stock"] == 8
    assert sorted(m["quantity_change"] for m in list_stock_adjustments(test_db)) == [-3, -0.25, 3]


# ------------------------------------------- all or nothing, audit, date, note


def _invalid_last(test_db):
    good1 = _product(test_db, "Good one", stock=1, unit_cost=100)
    good2 = _product(test_db, "Good two", stock=2, unit_cost=100)
    return [item("PRODUCT", good1, 5, 1), item("PRODUCT", good2, 0, 2), item("PRODUCT", good1 + 1000, 1, 0)]


def test_a_failure_on_the_last_item_leaves_no_movement_no_stock_change_and_no_audit_row(test_db):
    items = _invalid_last(test_db)
    test_db.commit()
    before = _counts(test_db)
    with pytest.raises(Exception) as exc_info:
        apply_stocktake(test_db, items)
    assert "does not exist" in str(exc_info.value)
    assert _counts(test_db) == before
    assert not test_db.in_transaction


def test_a_failure_inside_the_writing_phase_also_undoes_the_earlier_corrections(test_db, monkeypatch):
    first = _product(test_db, "First", stock=1, unit_cost=100)
    second = _product(test_db, "Second", stock=1, unit_cost=100)
    test_db.commit()
    import db.stocktake as module

    real = module.record_stock_adjustment
    calls = []

    def fail_on_second(*args, **kwargs):
        calls.append(args[2])
        if len(calls) == 2:
            raise RuntimeError("boom")
        return real(*args, **kwargs)

    monkeypatch.setattr(module, "record_stock_adjustment", fail_on_second)
    before = _counts(test_db)
    with pytest.raises(RuntimeError):
        apply_stocktake(test_db, [item("PRODUCT", first, 4, 1), item("PRODUCT", second, 4, 1)])
    assert len(calls) == 2
    assert _counts(test_db) == before


def test_every_correction_shares_one_op_id_with_the_operation_apply_stocktake(test_db):
    a = _product(test_db, "A", stock=1, unit_cost=100)
    b = _product(test_db, "B", stock=1, unit_cost=100)
    box = add_material(test_db, "Box", "STOCK", 50, initial_stock=1)
    start = test_db.execute("SELECT COALESCE(MAX(id), 0) FROM audit_log").fetchone()[0]
    apply_stocktake(test_db, [item("PRODUCT", a, 3, 1), item("PRODUCT", b, 0, 1), item("MATERIAL", box, 2, 1)])
    rows = test_db.execute("SELECT entity_type, operation, op_id FROM audit_log WHERE id > ?", (start,)).fetchall()
    assert {r["operation"] for r in rows} == {"apply_stocktake"}
    assert len({r["op_id"] for r in rows}) == 1 and rows[0]["op_id"]
    assert sum(r["entity_type"] == "stock_movements" for r in rows) == 3
    assert {r["entity_type"] for r in rows} == {"stock_movements", "products", "materials"}
    assert list_audit_log(test_db, op_id=rows[0]["op_id"])["total"] == len(rows)


def test_the_movement_date_and_note_are_on_every_correction(test_db):
    a = _product(test_db, "A", stock=1, unit_cost=100)
    b = _product(test_db, "B", stock=1, unit_cost=100)
    apply_stocktake(test_db, [item("PRODUCT", a, 3, 1), item("PRODUCT", b, 0, 1)], "2026-10-01", "انبار")
    movements = list_stock_adjustments(test_db)
    assert len(movements) == 2
    for movement in movements:
        assert movement["notes"] == "شمارش موجودی ۱۴۰۵/۰۷/۰۹ — انبار"
        assert movement["movement_date"] == "2026-09-30 20:30:00"  # local midnight of 1 Oct in Asia/Tehran, as UTC
    audit = test_db.execute("SELECT after_json FROM audit_log WHERE entity_type = 'stock_movements' ORDER BY id DESC LIMIT 1").fetchone()
    assert json.loads(audit["after_json"])["notes"].startswith("شمارش موجودی")


def test_record_stock_adjustment_takes_a_movement_date_on_its_own(test_db):
    product = _product(test_db, stock=1, unit_cost=100)
    movement_id = record_stock_adjustment(test_db, "PRODUCT", product, 2, "ADJUSTMENT", movement_date="2026-10-01")
    assert test_db.execute("SELECT movement_date FROM stock_movements WHERE id = ?", (movement_id,)).fetchone()[0] == "2026-09-30 20:30:00"


def test_a_future_date_is_refused(test_db):
    product = _product(test_db, stock=1, unit_cost=100)
    with pytest.raises(ValidationError) as exc_info:
        apply_stocktake(test_db, [item("PRODUCT", product, 2, 1)], "2999-01-01")
    assert exc_info.value.code == ErrorCode.DATE_IN_FUTURE and exc_info.value.field == "stocktake_date"
    with pytest.raises(ValidationError):
        apply_stocktake(test_db, [item("PRODUCT", product, 2, 1)], "not-a-date")


# ---------------------------------------------------------------- validation


def test_products_must_be_counted_in_whole_numbers_and_materials_may_be_fractional(test_db):
    product = _product(test_db, stock=1, unit_cost=100)
    box = add_material(test_db, "Box", "STOCK", 50, initial_stock=1)
    with pytest.raises(ValidationError) as exc_info:
        apply_stocktake(test_db, [item("PRODUCT", product, 2.5, 1)])
    assert exc_info.value.code == ErrorCode.QUANTITY_NOT_WHOLE and exc_info.value.field == "items.0.counted"
    apply_stocktake(test_db, [item("MATERIAL", box, 2.5, 1)])
    assert _stock(test_db, "materials", box)["current_stock"] == 2.5


@pytest.mark.parametrize("counted, code", [(-1, ErrorCode.QUANTITY_OUT_OF_RANGE), (10**9 + 1, ErrorCode.QUANTITY_OUT_OF_RANGE)])
def test_counts_outside_the_limits_are_out_of_range(test_db, counted, code):
    box = add_material(test_db, "Box", "STOCK", 50, initial_stock=1)
    with pytest.raises(ValidationError) as exc_info:
        apply_stocktake(test_db, [item("MATERIAL", box, counted, 1)])
    assert exc_info.value.code == code and exc_info.value.field == "items.0.counted"


def test_non_numbers_are_refused(test_db):
    box = add_material(test_db, "Box", "STOCK", 50, initial_stock=1)
    for bad in ("3", True, None, float("nan")):
        with pytest.raises(ValidationError):
            apply_stocktake(test_db, [item("MATERIAL", box, bad, 1)])


def test_services_unknown_items_duplicates_and_bad_types_are_refused(test_db):
    service = add_material(test_db, "Printing", "SERVICE", 90_000)
    box = add_material(test_db, "Box", "STOCK", 50, initial_stock=1)
    with pytest.raises(ValidationError) as exc_info:
        apply_stocktake(test_db, [item("MATERIAL", service, 1, 0)])
    assert exc_info.value.field == "items.0.item_id"
    with pytest.raises(Exception, match="does not exist"):
        apply_stocktake(test_db, [item("MATERIAL", 9999, 1, 0)])
    with pytest.raises(ValidationError) as exc_info:
        apply_stocktake(test_db, [item("MATERIAL", box, 2, 1), item("MATERIAL", box, 3, 1)])
    assert exc_info.value.field == "items.1.item_id"
    with pytest.raises(ValidationError) as exc_info:
        apply_stocktake(test_db, [item("THING", 1, 2, 1)])
    assert exc_info.value.field == "items.0.item_type"


def test_an_empty_or_oversized_item_list_is_refused(test_db):
    for items in ([], [item("MATERIAL", 1, 1, 0)] * (MAX_ITEMS + 1)):
        with pytest.raises(ValidationError) as exc_info:
            apply_stocktake(test_db, items)
        assert exc_info.value.field == "items"


def test_a_money_amount_beyond_the_limit_is_refused(test_db):
    product = _product(test_db)
    with pytest.raises(ValidationError) as exc_info:
        apply_stocktake(test_db, [item("PRODUCT", product, 2, 0, unit_cost=2**53)])
    assert exc_info.value.code == ErrorCode.AMOUNT_TOO_LARGE and exc_info.value.field == "items.0.unit_cost"
    big = _product(test_db, "Big")
    with pytest.raises(ValidationError) as exc_info:
        apply_stocktake(test_db, [item("PRODUCT", big, 900_000, 0, unit_cost=2**53 - 1)])
    assert exc_info.value.code == ErrorCode.AMOUNT_TOO_LARGE  # the value of the line leaves the bound


# ------------------------------------------------------------ inactive items


def test_inactive_items_can_be_counted_but_other_adjustments_still_refuse_them(test_db):
    product = _product(test_db, stock=1, unit_cost=100)
    box = add_material(test_db, "Box", "STOCK", 50, initial_stock=1)
    deactivate_product(test_db, product)
    deactivate_material(test_db, box)
    apply_stocktake(test_db, [item("PRODUCT", product, 4, 1), item("MATERIAL", box, 0.5, 1)])
    assert get_product(test_db, product)["current_stock"] == 4
    assert _stock(test_db, "materials", box)["current_stock"] == 0.5
    with pytest.raises(ValidationError, match="not active"):
        record_stock_adjustment(test_db, "PRODUCT", product, 1, "ADJUSTMENT")


# --------------------------------------------------------------------- stale


def test_stale_items_are_all_listed_and_nothing_is_written(test_db):
    a = _product(test_db, "A", stock=5, unit_cost=100)
    b = _product(test_db, "B", stock=5, unit_cost=100)
    c = _product(test_db, "C", stock=5, unit_cost=100)
    test_db.commit()
    before = _counts(test_db)
    with pytest.raises(ConflictError) as exc_info:
        apply_stocktake(test_db, [item("PRODUCT", a, 9, 4), item("PRODUCT", b, 9, 5), item("PRODUCT", c, 1, 7)])
    exc = exc_info.value
    assert exc.code == ErrorCode.STOCKTAKE_STALE
    assert exc.details["items"] == [
        {"item_type": "PRODUCT", "item_id": a, "item_name": "A", "expected": 4, "actual": 5},
        {"item_type": "PRODUCT", "item_id": c, "item_name": "C", "expected": 7, "actual": 5},
    ]
    assert _counts(test_db) == before


def test_applying_the_same_count_twice_is_stale_the_second_time(test_db):
    product = _product(test_db, stock=1, unit_cost=100)
    payload = [item("PRODUCT", product, 4, 1)]
    apply_stocktake(test_db, payload)
    with pytest.raises(ConflictError) as exc_info:
        apply_stocktake(test_db, payload)
    assert exc_info.value.code == ErrorCode.STOCKTAKE_STALE
    assert get_product(test_db, product)["current_stock"] == 4


# ------------------------------------------------------ plan, opening stock, scale


def test_the_plan_writes_nothing_and_matches_what_apply_returns(test_db):
    product = _product(test_db, stock=2, unit_cost=250)
    test_db.commit()
    before = _counts(test_db)
    plan = plan_stocktake(test_db, [item("PRODUCT", product, 6, 2)], "2026-10-12")
    assert _counts(test_db) == before and plan["corrections"][0]["movement_id"] is None
    applied = apply_stocktake(test_db, [item("PRODUCT", product, 6, 2)], "2026-10-12")
    assert {k: v for k, v in applied.items() if k != "corrections"} == {k: v for k, v in plan.items() if k != "corrections"}
    assert {k: v for k, v in applied["corrections"][0].items() if k != "movement_id"} == \
        {k: v for k, v in plan["corrections"][0].items() if k != "movement_id"}


def test_loading_opening_stock_for_150_items_in_one_call(test_db):
    products = [_product(test_db, f"Opening {n}") for n in range(100)]
    materials = [add_material(test_db, f"Opening material {n}", "STOCK", 100 + n) for n in range(50)]
    items = [item("PRODUCT", p, n + 1, 0, unit_cost=1_000 * (n + 1)) for n, p in enumerate(products)]
    items += [item("MATERIAL", m, n + 0.5, 0) for n, m in enumerate(materials)]
    result = apply_stocktake(test_db, items, "2026-10-12", "موجودی اول دوره")
    assert len(result["corrections"]) == 150 and result["unchanged_count"] == 0
    assert test_db.execute("SELECT COUNT(*) FROM stock_movements WHERE reason = 'ADJUSTMENT'").fetchone()[0] == 150
    assert _stock(test_db, "products", products[9]) ["current_stock"] == 10
    assert _stock(test_db, "products", products[9])["unit_cost"] == 10_000
    expected = sum((n + 1) * 1_000 * (n + 1) for n in range(100)) + sum(round(Fraction(n * 2 + 1, 2) * (100 + n)) for n in range(50))
    assert result["total_value"] == expected


def test_the_integrity_check_still_prints_ok_after_a_stocktake(test_db, capsys):
    from tools.integrity_check import __main__ as cli

    product = _product(test_db, stock=0, unit_cost=None)
    box = add_material(test_db, "Box", "STOCK", 50, initial_stock=5)
    apply_stocktake(test_db, [item("PRODUCT", product, 12, 0, unit_cost=1_500_000), item("MATERIAL", box, 3.5, 5)])
    apply_stocktake(test_db, [item("PRODUCT", product, 10, 12), item("MATERIAL", box, 6, 3.5)])
    test_db.commit()
    path = next(r["file"] for r in test_db.execute("PRAGMA database_list") if r["name"] == "main")
    code = cli.main(["--db", path])
    out = capsys.readouterr().out
    assert code == 0 and out.strip().splitlines()[-1] == "OK", out
