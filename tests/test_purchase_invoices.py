"""db/purchases.py `record_purchase` (accounting rules section 22): one supplier invoice with several lines, mixed
STOCK materials / services / products, the same item twice refused, a service line has no stock and no movement and sets
the service's price (total ÷ quantity), a service line of total 0 is refused, everything is checked before anything is
written, one audit operation, one PUR number; the invoice reads and the summary."""

import pytest

from db.adjustments import record_service_waste
from db.constants import MAX_MONEY
from db.errors import ErrorCode, NotFoundError, ValidationError
from db.materials import add_material, deactivate_material, get_material
from db.products import add_product, get_product
from db.production import run_production_batch
from db.purchases import (
    get_purchase,
    list_purchases,
    purchase_lines,
    record_purchase,
    require_purchase,
)
from db.recipes import add_recipe_item
from db.reports import get_profit_and_loss, get_purchases_summary
from db.suppliers import add_supplier
from tests.helpers import cat


@pytest.fixture
def shop(test_db):
    ids = {
        "paper": add_material(test_db, "Invoice Paper", "STOCK", 100, initial_stock=10),
        "ink": add_material(test_db, "Invoice Ink", "STOCK", 0),
        "print": add_material(test_db, "Invoice Printing", "SERVICE", 50),
        "tee": add_product(test_db, "Invoice Tee", cat(test_db, "TSHIRT"), 3000, 2000),
        "acme": add_supplier(test_db, "Invoice Acme"),
    }
    return test_db, ids


def line(kind, item_id, quantity, total):
    return {"kind": kind, "item_id": item_id, "quantity_bought": quantity, "total_paid": total}


def _counts(conn):
    return {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("purchase_invoices", "material_purchases", "product_purchases", "stock_movements", "supplier_payments")
    }


def test_one_invoice_with_a_stock_material_a_service_and_a_product(shop):
    conn, ids = shop
    purchase_id = record_purchase(
        conn,
        [line("MATERIAL", ids["paper"], 5, 1000), line("MATERIAL", ids["print"], 4, 600), line("PRODUCT", ids["tee"], 3, 900)],
        supplier_id=ids["acme"], purchase_date="2026-05-02", notes="one bill",
    )
    purchase = get_purchase(conn, purchase_id)
    assert purchase["invoice_number"] == "PUR-000001"
    assert (purchase["supplier_name"], purchase["notes"], purchase["status"]) == ("Invoice Acme", "one bill", "ACTIVE")
    assert purchase["total"] == 2500 and purchase["paid"] == 2500 and purchase["payment_status"] == "PAID"
    assert [(l["kind"], l["item_type"], l["item_name"], l["quantity_bought"], l["total_paid"], l["unit_cost"]) for l in purchase["lines"]] == [
        ("MATERIAL", "STOCK", "Invoice Paper", 5, 1000, 200),
        ("MATERIAL", "SERVICE", "Invoice Printing", 4, 600, 150),
        ("PRODUCT", "PRODUCT", "Invoice Tee", 3, 900, 300),
    ]
    # the stock material blends, the product has no cost yet, the service takes the price
    paper, printing, tee = get_material(conn, ids["paper"]), get_material(conn, ids["print"]), get_product(conn, ids["tee"])
    assert (paper["current_stock"], paper["unit_cost"]) == (15, 133)  # (10 x 100 + 1000) / 15 = 133.3
    assert (printing["current_stock"], printing["unit_cost"]) == (None, 150)
    assert (tee["current_stock"], tee["unit_cost"]) == (3, 300)
    # a movement for the stock material and the product only, each linked to its own line
    moved = conn.execute("SELECT item_type, item_id, quantity_change, notes FROM stock_movements WHERE reason = 'PURCHASE' ORDER BY id").fetchall()
    assert [(m["item_type"], m["item_id"], m["quantity_change"]) for m in moved] == [("MATERIAL", ids["paper"], 5), ("PRODUCT", ids["tee"], 3)]
    assert all("(invoice PUR-000001)" in m["notes"] for m in moved)
    links = [r[0] for r in conn.execute("SELECT stock_movement_id FROM material_purchases ORDER BY id")]
    assert links[0] is not None and links[1] is None
    assert conn.execute("SELECT stock_movement_id FROM product_purchases").fetchone()[0] is not None


def test_every_line_stores_the_item_cost_before_and_after(shop):
    conn, ids = shop
    record_purchase(conn, [line("MATERIAL", ids["paper"], 5, 1000), line("MATERIAL", ids["print"], 4, 600), line("PRODUCT", ids["tee"], 3, 900)])
    rows = conn.execute("SELECT item_cost_before, item_cost_after FROM material_purchases ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [(100, 133), (50, 150)]
    assert tuple(conn.execute("SELECT item_cost_before, item_cost_after FROM product_purchases").fetchone()) == (None, 300)


def test_a_service_price_is_the_last_purchase_not_an_average(shop):
    conn, ids = shop
    record_purchase(conn, [line("MATERIAL", ids["print"], 3, 100)])
    assert get_material(conn, ids["print"])["unit_cost"] == 33  # 33.33 -> 33, from a price of 50
    record_purchase(conn, [line("MATERIAL", ids["print"], 2.5, 1000)])
    service = get_material(conn, ids["print"])
    assert service["unit_cost"] == 400 and service["current_stock"] is None
    # a service at cost 0 ("not entered") gets its price the same way
    free = add_material(conn, "Invoice Unpriced Service", "SERVICE", 0)
    record_purchase(conn, [line("MATERIAL", free, 10, 5000)])
    assert get_material(conn, free)["unit_cost"] == 500


def test_a_service_purchase_writes_no_movement_and_never_gives_it_stock(shop):
    conn, ids = shop
    before = _counts(conn)
    record_purchase(conn, [line("MATERIAL", ids["print"], 2, 300)])
    after = _counts(conn)
    assert after["stock_movements"] == before["stock_movements"]
    assert (after["purchase_invoices"], after["material_purchases"]) == (before["purchase_invoices"] + 1, before["material_purchases"] + 1)
    assert conn.execute("SELECT stock_movement_id FROM material_purchases").fetchone()[0] is None
    assert get_material(conn, ids["print"])["current_stock"] is None


def test_a_service_line_of_total_0_is_refused_and_nothing_is_written(shop):
    conn, ids = shop
    before = _counts(conn)
    with pytest.raises(ValidationError) as exc:
        record_purchase(conn, [line("MATERIAL", ids["paper"], 1, 100), line("MATERIAL", ids["print"], 2, 0)])
    assert exc.value.code == ErrorCode.SERVICE_PURCHASE_NEEDS_TOTAL and exc.value.field == "lines.1.total_paid"
    assert exc.value.details == {"index": 1, "material_id": ids["print"], "material_name": "Invoice Printing"}
    assert _counts(conn) == before
    assert get_material(conn, ids["print"])["unit_cost"] == 50
    record_purchase(conn, [line("MATERIAL", ids["paper"], 1, 0)])  # a stock material may be bought at total 0


def test_the_same_item_twice_is_refused_but_a_material_and_a_product_may_share_an_id(shop):
    conn, ids = shop
    before = _counts(conn)
    with pytest.raises(ValidationError) as exc:
        record_purchase(conn, [line("MATERIAL", ids["paper"], 1, 100), line("PRODUCT", ids["tee"], 1, 100), line("MATERIAL", ids["paper"], 2, 300)])
    assert exc.value.code == ErrorCode.PURCHASE_DUPLICATE_ITEM and exc.value.field == "lines.2.item_id"
    assert exc.value.details == {"index": 2, "item_type": "MATERIAL", "item_id": ids["paper"]}
    assert _counts(conn) == before
    # the same id in the two tables is two different items
    other = add_product(conn, "Invoice Other Tee", cat(conn, "TSHIRT"), 3000, 2000)
    record_purchase(conn, [line("MATERIAL", ids["paper"], 1, 100), line("PRODUCT", other, 1, 100)])


@pytest.mark.parametrize("bad, field, code", [
    (line("MATERIAL", 1, 0, 100), "lines.1.quantity_bought", ErrorCode.QUANTITY_OUT_OF_RANGE),
    (line("MATERIAL", 1, 1, -1), "lines.1.total_paid", ErrorCode.VALIDATION_FAILED),
    (line("MATERIAL", 1, 1, MAX_MONEY + 1), "lines.1.total_paid", ErrorCode.AMOUNT_TOO_LARGE),
    (line("MATERIAL", 1, 1, 10.5), "lines.1.total_paid", ErrorCode.VALIDATION_FAILED),
    (line("BOGUS", 1, 1, 100), "lines.1.kind", ErrorCode.VALIDATION_FAILED),
])
def test_a_bad_line_names_its_field_and_nothing_is_written(shop, bad, field, code):
    conn, ids = shop
    before = _counts(conn)
    good = line("MATERIAL", ids["paper"], 1, 100)
    bad = {**bad, "item_id": ids["ink"] if bad["kind"] == "MATERIAL" else bad["item_id"]}
    with pytest.raises(ValidationError) as exc:
        record_purchase(conn, [good, bad])
    assert exc.value.field == field and exc.value.code == code
    assert _counts(conn) == before


def test_a_product_quantity_must_be_whole(shop):
    conn, ids = shop
    with pytest.raises(ValidationError) as exc:
        record_purchase(conn, [line("PRODUCT", ids["tee"], 1.5, 100)])
    assert exc.value.code == ErrorCode.QUANTITY_NOT_WHOLE and exc.value.field == "lines.0.quantity_bought"


def test_missing_inactive_and_unknown_things(shop):
    conn, ids = shop
    with pytest.raises(ValidationError) as exc:
        record_purchase(conn, [])
    assert exc.value.field == "lines"
    with pytest.raises(NotFoundError):
        record_purchase(conn, [line("MATERIAL", 99999, 1, 100)])
    with pytest.raises(NotFoundError):
        record_purchase(conn, [line("PRODUCT", 99999, 1, 100)])
    with pytest.raises(NotFoundError) as exc:
        record_purchase(conn, [line("MATERIAL", ids["paper"], 1, 100)], supplier_id=99999)
    assert exc.value.code == ErrorCode.SUPPLIER_NOT_FOUND
    deactivate_material(conn, ids["ink"])
    with pytest.raises(ValidationError) as exc:
        record_purchase(conn, [line("MATERIAL", ids["paper"], 1, 100), line("MATERIAL", ids["ink"], 1, 100)])
    assert exc.value.field == "lines.1.item_id"


def test_the_invoice_total_is_bounded(shop):
    conn, ids = shop
    big = MAX_MONEY // 2 + 1
    with pytest.raises(ValidationError) as exc:
        record_purchase(conn, [line("MATERIAL", ids["paper"], 1, big), line("MATERIAL", ids["ink"], 1, big)])
    assert exc.value.code == ErrorCode.AMOUNT_TOO_LARGE and exc.value.field == "lines"


def test_payment_terms_apply_to_the_invoice_total(shop):
    conn, ids = shop
    lines = [line("MATERIAL", ids["paper"], 1, 1000), line("MATERIAL", ids["print"], 1, 500)]
    on_credit = get_purchase(conn, record_purchase(conn, lines, supplier_id=ids["acme"], payment={"mode": "NONE"}))
    assert (on_credit["total"], on_credit["paid"], on_credit["payment_status"]) == (1500, 0, "UNPAID")
    partial = get_purchase(conn, record_purchase(conn, [line("MATERIAL", ids["ink"], 1, 900)], supplier_id=ids["acme"],
                                                  payment={"mode": "PARTIAL", "amount": 400, "method": "CASH"}))
    assert (partial["paid"], partial["outstanding"]) == (400, 500)


def test_one_pur_number_and_one_operation_for_the_whole_invoice(shop):
    conn, ids = shop
    first = record_purchase(conn, [line("MATERIAL", ids["paper"], 1, 100), line("PRODUCT", ids["tee"], 1, 100)])
    second = record_purchase(conn, [line("MATERIAL", ids["ink"], 1, 100)])
    assert [get_purchase(conn, p)["invoice_number"] for p in (first, second)] == ["PUR-000001", "PUR-000002"]
    rows = conn.execute(
        "SELECT entity_type, operation, op_id FROM audit_log WHERE entity_type IN "
        "('purchase_invoices', 'material_purchases', 'product_purchases', 'supplier_payments', 'supplier_payment_allocations') "
        "AND entity_id IN (?, '1', '2') ORDER BY id",
        (str(first),),
    ).fetchall()
    first_ops = {r["op_id"] for r in conn.execute(
        "SELECT op_id FROM audit_log WHERE entity_type = 'purchase_invoices' AND entity_id = ?", (str(first),))}
    assert len(first_ops) == 1
    op = first_ops.pop()
    kinds = {r[0] for r in conn.execute("SELECT entity_type FROM audit_log WHERE op_id = ?", (op,))}
    assert {"purchase_invoices", "material_purchases", "product_purchases", "stock_movements", "materials", "products"} <= kinds
    assert {r["operation"] for r in rows if r["op_id"] == op} == {"record_purchase"}


def test_list_purchases_filters_by_supplier_day_and_item_type(shop):
    conn, ids = shop
    mixed = record_purchase(conn, [line("MATERIAL", ids["paper"], 1, 100), line("MATERIAL", ids["print"], 1, 100)],
                            supplier_id=ids["acme"], purchase_date="2026-03-01")
    service = record_purchase(conn, [line("MATERIAL", ids["print"], 1, 200)], purchase_date="2026-04-01")
    product = record_purchase(conn, [line("PRODUCT", ids["tee"], 1, 300)], purchase_date="2026-05-01")
    assert [p["id"] for p in list_purchases(conn)] == [product, service, mixed]  # newest first
    assert [p["id"] for p in list_purchases(conn, supplier_id=ids["acme"])] == [mixed]
    assert [p["id"] for p in list_purchases(conn, start_date="2026-03-15", end_date="2026-04-30")] == [service]
    assert [p["id"] for p in list_purchases(conn, item_type="SERVICE")] == [service, mixed]
    assert [p["id"] for p in list_purchases(conn, item_type="MATERIAL")] == [mixed]  # STOCK materials
    assert [p["id"] for p in list_purchases(conn, item_type="PRODUCT")] == [product]
    assert [p["id"] for p in list_purchases(conn, item_type="SERVICE", item_id=ids["print"])] == [service, mixed]
    assert list_purchases(conn, item_type="PRODUCT", item_id=ids["tee"] + 99) == []
    with pytest.raises(ValidationError):
        list_purchases(conn, item_type="GADGET")
    with pytest.raises(ValidationError):
        list_purchases(conn, item_id=1)


def test_get_and_require_purchase(shop):
    conn, ids = shop
    purchase_id = record_purchase(conn, [line("MATERIAL", ids["paper"], 1, 100)])
    assert get_purchase(conn, 99999) is None
    assert require_purchase(conn, purchase_id)["id"] == purchase_id
    with pytest.raises(NotFoundError) as exc:
        require_purchase(conn, 99999)
    assert exc.value.code == ErrorCode.PURCHASE_NOT_FOUND and exc.value.details == {"purchase_id": 99999}
    assert [l["item_name"] for l in purchase_lines(conn, purchase_id)] == ["Invoice Paper"]


# ---------------------------------------------------------------- reports and the P&L


def test_the_summary_keeps_stock_services_and_products_apart(shop):
    conn, ids = shop
    record_purchase(conn, [line("MATERIAL", ids["paper"], 1, 1000), line("MATERIAL", ids["print"], 1, 400), line("PRODUCT", ids["tee"], 2, 600)],
                    purchase_date="2026-05-02")
    record_purchase(conn, [line("MATERIAL", ids["print"], 1, 200)], purchase_date="2026-06-02")
    summary = get_purchases_summary(conn)
    assert (summary["material_purchases_total"], summary["material_purchases_count"]) == (1000, 1)
    assert (summary["service_purchases_total"], summary["service_purchases_count"]) == (600, 2)
    assert (summary["product_purchases_total"], summary["product_purchases_count"]) == (600, 1)
    assert summary["purchase_invoices_count"] == 2
    in_may = get_purchases_summary(conn, "2026-05-01", "2026-05-31")
    assert (in_may["service_purchases_total"], in_may["purchase_invoices_count"]) == (400, 1)


def test_a_service_purchase_is_not_an_expense_and_its_cost_reaches_the_pnl_only_by_use(shop):
    conn, ids = shop
    before = get_profit_and_loss(conn)
    record_purchase(conn, [line("MATERIAL", ids["print"], 10, 5000)], supplier_id=ids["acme"], payment={"mode": "NONE"})
    assert get_profit_and_loss(conn) == before  # a purchase is neither revenue nor expense
    # used in production at the new price (500)
    product = add_product(conn, "Invoice Printed Tee", cat(conn, "TSHIRT"), 3000, 2000)
    add_recipe_item(conn, product, ids["print"], 1)
    batch_id = run_production_batch(conn, product, 2)
    assert conn.execute("SELECT unit_cost FROM production_batches WHERE id = ?", (batch_id,)).fetchone()[0] == 500
    assert conn.execute("SELECT unit_cost_at_time FROM production_batch_materials WHERE production_batch_id = ?", (batch_id,)).fetchone()[0] == 500
    # and wasted at it
    record_service_waste(conn, ids["print"], 2)
    assert get_profit_and_loss(conn)["waste_cost"] == 1000
