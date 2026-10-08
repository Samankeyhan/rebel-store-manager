"""Per-material minimum stock (migration 011) and the low-stock rule in db/materials.py."""

import math

import pytest

from db.errors import NotFoundError, ValidationError
from db.materials import (
    add_material,
    deactivate_material,
    get_low_stock_materials,
    get_material,
    list_materials,
    update_material,
)


def _low_ids(conn) -> list[int]:
    return [m["id"] for m in get_low_stock_materials(conn)]


def _set_stock(conn, material_id: int, stock: float) -> None:
    conn.execute("UPDATE materials SET current_stock = ? WHERE id = ?", (stock, material_id))
    conn.commit()


# ── the rule ──


@pytest.mark.parametrize(
    ("stock", "minimum", "low"),
    [
        (10, 10, True),  # at the minimum counts as low
        (11, 10, False),  # one above is not
        (9, 10, True),  # below is low
        (0, 0, True),  # minimum 0, stock 0
        (1, 0, False),  # minimum 0, stock 1
        (0, None, True),  # out of stock always warns, with no minimum
        (5, None, False),  # no minimum and stock left: no warning
        (2.5, 2.5, True),  # fractional, at the minimum
        (2.6, 2.5, False),
        (2.4, 2.5, True),
        (0.001, 0.001, True),
    ],
)
def test_low_stock_rule(test_db, stock, minimum, low):
    material_id = add_material(test_db, "Test Box", "STOCK", 1000, initial_stock=stock, min_stock=minimum)
    assert (material_id in _low_ids(test_db)) is low
    assert get_material(test_db, material_id)["is_low_stock"] == (1 if low else 0)


def test_service_never_low(test_db):
    service_id = add_material(test_db, "Test Print", "SERVICE", 5000)
    assert get_material(test_db, service_id)["min_stock"] is None
    assert get_material(test_db, service_id)["is_low_stock"] == 0
    assert service_id not in _low_ids(test_db)


@pytest.mark.parametrize(("stock", "minimum"), [(0, None), (3, 5), (0, 0)])
def test_inactive_never_low(test_db, stock, minimum):
    material_id = add_material(test_db, "Test Old Tape", "STOCK", 1000, initial_stock=stock, min_stock=minimum)
    deactivate_material(test_db, material_id)
    assert material_id not in _low_ids(test_db)
    assert get_material(test_db, material_id)["is_low_stock"] == 0


def test_flag_matches_query_for_every_material(test_db):
    specs = [(0, None), (4, 5), (5, 5), (6, 5), (0, 3), (7, None), (1, 0)]
    for i, (stock, minimum) in enumerate(specs):
        add_material(test_db, f"Test M{i}", "STOCK", 100, initial_stock=stock, min_stock=minimum)
    add_material(test_db, "Test Service", "SERVICE", 100)
    flagged = {m["id"] for m in list_materials(test_db, active_only=False) if m["is_low_stock"] == 1}
    assert flagged == set(_low_ids(test_db))
    assert len(flagged) == 4


def test_ordering_most_urgent_first(test_db):
    a = add_material(test_db, "B half", "STOCK", 100, initial_stock=5, min_stock=10)  # 0.5
    b = add_material(test_db, "A at min", "STOCK", 100, initial_stock=10, min_stock=10)  # 1.0
    c = add_material(test_db, "Z out no min", "STOCK", 100, initial_stock=0)  # 0
    d = add_material(test_db, "Y out with min", "STOCK", 100, initial_stock=0, min_stock=4)  # 0
    e = add_material(test_db, "C quarter", "STOCK", 100, initial_stock=1, min_stock=4)  # 0.25
    f = add_material(test_db, "A half", "STOCK", 100, initial_stock=1, min_stock=2)  # 0.5, name before "B half"
    g = add_material(test_db, "X zero min", "STOCK", 100, initial_stock=0, min_stock=0)  # 0
    # ratio first; ties by name, then id
    assert _low_ids(test_db) == [g, d, c, e, f, a, b]


def test_ordering_ties_by_id(test_db):
    first = add_material(test_db, "Same", "STOCK", 100, initial_stock=0)
    second = add_material(test_db, "Same", "STOCK", 100, initial_stock=0)
    assert _low_ids(test_db) == [first, second]


def test_empty_when_nothing_is_low(test_db):
    add_material(test_db, "Test Box", "STOCK", 100, initial_stock=20, min_stock=10)
    add_material(test_db, "Test Tape", "STOCK", 100, initial_stock=3)
    add_material(test_db, "Test Print", "SERVICE", 100)
    assert get_low_stock_materials(test_db) == []


def test_rows_carry_unit_stock_and_minimum(test_db):
    material_id = add_material(test_db, "Test Filler", "STOCK", 100, unit="kg", initial_stock=1.5, min_stock=2)
    (row,) = get_low_stock_materials(test_db)
    assert row["id"] == material_id
    assert row["name"] == "Test Filler"
    assert row["unit"] == "kg"
    assert row["current_stock"] == 1.5
    assert row["min_stock"] == 2
    assert row["is_low_stock"] == 1


def test_low_after_stock_drops(test_db):
    material_id = add_material(test_db, "Test Box", "STOCK", 100, initial_stock=20, min_stock=10)
    assert _low_ids(test_db) == []
    _set_stock(test_db, material_id, 10)
    assert _low_ids(test_db) == [material_id]


# ── legacy threshold mode ──


def test_threshold_mode_ignores_min_stock_and_orders_by_name(test_db):
    high_min = add_material(test_db, "B high min", "STOCK", 100, initial_stock=50, min_stock=100)
    low_no_min = add_material(test_db, "A low", "STOCK", 100, initial_stock=5)
    out = add_material(test_db, "C out", "STOCK", 100, initial_stock=0)
    rows = get_low_stock_materials(test_db, threshold=10)
    assert [m["id"] for m in rows] == [low_no_min, out]
    assert high_min not in [m["id"] for m in rows]


# ── validation ──


@pytest.mark.parametrize("bad", [-1, -0.0001, True, False, "5", math.nan, math.inf, -math.inf, [1]])
def test_create_refuses_bad_min_stock(test_db, bad):
    with pytest.raises(ValidationError) as exc:
        add_material(test_db, "Test Box", "STOCK", 100, initial_stock=1, min_stock=bad)
    assert exc.value.field == "min_stock"
    assert list_materials(test_db, active_only=False) == []


@pytest.mark.parametrize("value", [0, 0.0, 2.5, 7])
def test_create_accepts_min_stock(test_db, value):
    material_id = add_material(test_db, "Test Box", "STOCK", 100, initial_stock=1, min_stock=value)
    assert get_material(test_db, material_id)["min_stock"] == value


@pytest.mark.parametrize("value", [0, 5])
def test_service_refuses_min_stock(test_db, value):
    with pytest.raises(ValidationError) as exc:
        add_material(test_db, "Test Print", "SERVICE", 100, min_stock=value)
    assert exc.value.field == "min_stock"
    service_id = add_material(test_db, "Test Print", "SERVICE", 100)
    with pytest.raises(ValidationError) as exc:
        update_material(test_db, service_id, min_stock=value)
    assert exc.value.field == "min_stock"
    # Clearing (None) is harmless on a SERVICE material.
    update_material(test_db, service_id, min_stock=None)
    assert get_material(test_db, service_id)["min_stock"] is None


@pytest.mark.parametrize("bad", [-1, True, "5", math.nan, math.inf])
def test_update_refuses_bad_min_stock(test_db, bad):
    material_id = add_material(test_db, "Test Box", "STOCK", 100, initial_stock=1, min_stock=3)
    with pytest.raises(ValidationError) as exc:
        update_material(test_db, material_id, min_stock=bad)
    assert exc.value.field == "min_stock"
    assert get_material(test_db, material_id)["min_stock"] == 3


# ── update: set, clear, omit ──


def test_update_set_clear_and_omit(test_db):
    material_id = add_material(test_db, "Test Box", "STOCK", 100, initial_stock=4)
    test_db.execute("UPDATE materials SET updated_at = '2025-01-02 03:04:05' WHERE id = ?", (material_id,))
    test_db.commit()
    before = get_material(test_db, material_id)

    update_material(test_db, material_id)  # omitted: nothing changes, not even updated_at
    assert get_material(test_db, material_id) == before

    update_material(test_db, material_id, min_stock=4.5)
    after_set = get_material(test_db, material_id)
    assert after_set["min_stock"] == 4.5
    assert after_set["is_low_stock"] == 1
    assert after_set["updated_at"] != "2025-01-02 03:04:05"
    unchanged = ("name", "type", "unit", "current_stock", "unit_cost", "is_active", "category_id", "created_at")
    assert {k: after_set[k] for k in unchanged} == {k: before[k] for k in unchanged}

    update_material(test_db, material_id, min_stock=None)
    after_clear = get_material(test_db, material_id)
    assert after_clear["min_stock"] is None
    assert after_clear["is_low_stock"] == 0


def test_update_refuses_unknown_field(test_db):
    material_id = add_material(test_db, "Test Box", "STOCK", 100, initial_stock=4)
    with pytest.raises(ValidationError) as exc:
        update_material(test_db, material_id, unit_cost=5)
    assert exc.value.field == "unit_cost"


def test_update_missing_material(test_db):
    with pytest.raises(NotFoundError):
        update_material(test_db, 9999, min_stock=1)
