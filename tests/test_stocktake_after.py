"""db/stocktake.py `stocktake_after`: the shared read-only helper an order void and a purchase cancel use to find a
stocktake that counted an item after a given movement."""

from db.adjustments import record_stock_adjustment
from db.materials import add_material
from db.stocktake import NOTE_PREFIX, apply_stocktake, stocktake_after


def _last_movement(conn) -> int:
    return conn.execute("SELECT MAX(id) FROM stock_movements").fetchone()[0] or 0


def test_finds_the_first_stocktake_on_one_of_the_items_after_the_movement(test_db):
    box = add_material(test_db, "Helper Box", "STOCK", 100, initial_stock=10)
    tape = add_material(test_db, "Helper Tape", "STOCK", 100, initial_stock=10)
    start = _last_movement(test_db)
    record_stock_adjustment(test_db, "MATERIAL", box, -1, "ADJUSTMENT")  # a manual adjustment is not a count
    apply_stocktake(test_db, [{"item_type": "MATERIAL", "item_id": tape, "counted": 8, "system_quantity": 10}])
    apply_stocktake(test_db, [{"item_type": "MATERIAL", "item_id": box, "counted": 7, "system_quantity": 9}])
    found = stocktake_after(test_db, start, {("MATERIAL", box)})
    assert (found["item_type"], found["item_id"]) == ("MATERIAL", box)
    assert stocktake_after(test_db, start, {("MATERIAL", tape)})["item_id"] == tape
    assert stocktake_after(test_db, found["id"], {("MATERIAL", box)}) is None  # nothing after it
    assert stocktake_after(test_db, start, {("PRODUCT", box)}) is None  # same id, other kind


def test_a_movement_with_the_stocktake_note_counts_and_no_items_is_none(test_db):
    box = add_material(test_db, "Helper Crate", "STOCK", 100, initial_stock=10)
    start = _last_movement(test_db)
    record_stock_adjustment(test_db, "MATERIAL", box, -2, "ADJUSTMENT", notes=f"{NOTE_PREFIX} 1405/08/01")
    assert stocktake_after(test_db, start, {("MATERIAL", box)}) is not None
    assert stocktake_after(test_db, start, set()) is None
