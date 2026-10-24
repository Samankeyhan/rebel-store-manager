"""Integrity check i (voided orders and corrections, accounting-rules sections 18 and 20): a shop with a void and
a correction passes every check, the stock replay includes the reversal movements, and each corruption is named."""

from db.order_voids import correct_order, void_order
from tests.test_integrity_check import fails, run, shop, writable  # noqa: F401 (shop is a fixture)


def _voided_shop(shop, test_db):
    void_order(test_db, shop["pending_order"], "entered twice")
    shop["replacement"] = correct_order(
        test_db, shop["zarinpal_order"], "wrong price", "WEBSITE",
        [{"product_id": shop["product"], "quantity": 1, "unit_price": 9_000_000}],
        order_date="2026-09-30", shipping_charge=30_000, packaging_kit_id=None, postage_cost=0,
        payment_method_id=shop["zarinpal"],
    )
    test_db.commit()
    return shop


def test_a_shop_with_a_void_and_a_correction_passes_every_check(shop, test_db):
    _voided_shop(shop, test_db)
    results = run(test_db)
    assert {key: r.status for key, r in results.items() if key != "d3"} == {
        key: "PASS" for key in ("a", "b", "c", "d1", "d2", "d4", "e", "f", "g", "h", "i")}
    assert results["i"].summary == "2 voided orders, 1 corrections checked"


def test_a_voided_order_whose_stock_did_not_come_back_fails(shop, test_db):
    _voided_shop(shop, test_db)
    raw = writable(test_db)
    movement = raw.execute(
        "SELECT id, item_id, quantity_change FROM stock_movements WHERE reason = 'RETURN' AND reference_order_id = ?",
        (shop["pending_order"],),
    ).fetchone()
    raw.execute("DELETE FROM stock_movements WHERE id = ?", (movement["id"],))
    raw.execute("UPDATE products SET current_stock = current_stock - ? WHERE id = ?",
                (movement["quantity_change"], movement["item_id"]))
    raw.close()
    rows = fails(run(test_db), "i")
    assert len(rows) == 1 and f"order {shop['pending_order']}" in rows[0] and "net to zero" in rows[0]


def test_a_voided_order_in_a_settlement_or_never_committed_fails(shop, test_db):
    _voided_shop(shop, test_db)
    raw = writable(test_db)
    raw.execute("UPDATE orders SET settlement_id = ?, stock_committed = 0 WHERE id = ?",
                (shop["s_card"], shop["pending_order"]))
    raw.close()
    rows = fails(run(test_db), "i")
    assert any("settlement_id" in row for row in rows) and any("stock_committed" in row for row in rows)


def test_a_voided_order_without_reason_or_moment_fails(shop, test_db):
    _voided_shop(shop, test_db)
    raw = writable(test_db)
    raw.execute("UPDATE orders SET void_reason = '  ', voided_at = NULL WHERE id = ?", (shop["pending_order"],))
    raw.close()
    rows = fails(run(test_db), "i")
    assert any("void_reason" in row for row in rows) and any("voided_at" in row for row in rows)


def test_a_correction_pointing_at_an_order_that_is_not_voided_fails(shop, test_db):
    _voided_shop(shop, test_db)
    raw = writable(test_db)
    raw.execute("UPDATE orders SET replaces_order_id = ? WHERE id = ?", (shop["card_order"], shop["replacement"]))
    raw.close()
    rows = fails(run(test_db), "i")
    assert rows and all("replaces_order_id" in row for row in rows)
