import pytest

from db import packaging, postage
from db.errors import ConflictError
from db.materials import add_material, get_material
from db.orders import (
    get_revenue_summary,
    record_order,
    update_order_status,
)
from db.products import add_product, get_product
from db.purchases import record_material_purchase, record_product_purchase
from db.returns import process_return
from db.settings import update_channel_settings


@pytest.fixture
def return_setup(test_db):
    product_a_id = add_product(test_db, "Product A", "VINYL", 3000, 2000)
    product_b_id = add_product(test_db, "Product B", "CASSETTE", 1500, 1000)
    test_db.execute(
        "UPDATE products SET current_stock = 10, unit_cost = 500 WHERE id = ?",
        (product_a_id,),
    )
    test_db.execute(
        "UPDATE products SET current_stock = 20, unit_cost = 300 WHERE id = ?",
        (product_b_id,),
    )
    test_db.commit()
    return {"product_a_id": product_a_id, "product_b_id": product_b_id}


@pytest.fixture
def canonical_setup(test_db):
    """Same canonical fixture as tests/test_orders.py: a product, three
    packaging materials, a kit set as WEBSITE's default, and a postage batch —
    built through the real db/ functions, never raw SQL.
    """
    vinyl_id = add_product(test_db, "Vinyl", "VINYL", 3_000_000, 2_500_000)
    record_product_purchase(test_db, vinyl_id, quantity_bought=10, total_paid=12_000_000)

    box_id = add_material(test_db, "Box", "STOCK", unit_cost=0)
    record_material_purchase(test_db, box_id, quantity_bought=100, total_paid=3_000_000)

    tape_id = add_material(test_db, "Tape", "STOCK", unit_cost=0, unit="m")
    record_material_purchase(test_db, tape_id, quantity_bought=100, total_paid=250_000)

    filler_id = add_material(test_db, "Filler", "STOCK", unit_cost=0)
    record_material_purchase(test_db, filler_id, quantity_bought=50, total_paid=500_000)

    kit_id = packaging.create_kit(test_db, "Standard box")
    packaging.add_kit_item(test_db, kit_id, box_id, 1)
    packaging.add_kit_item(test_db, kit_id, tape_id, 2)
    packaging.add_kit_item(test_db, kit_id, filler_id, 1)
    update_channel_settings(test_db, "WEBSITE", default_packaging_kit_id=kit_id)

    postage.record_postage_batch(test_db, total_paid=10_000_000, order_count=40)

    return {
        "vinyl_id": vinyl_id,
        "box_id": box_id,
        "tape_id": tape_id,
        "filler_id": filler_id,
        "kit_id": kit_id,
    }


def _count_rows(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _product_stock(conn, product_id: int) -> int:
    return get_product(conn, product_id)["current_stock"]


def _record_completed_order(test_db, return_setup, status="COMPLETED"):
    return record_order(
        test_db,
        "INSTAGRAM",
        [
            {"product_id": return_setup["product_a_id"], "quantity": 2, "unit_price": 3000},
            {"product_id": return_setup["product_b_id"], "quantity": 1, "unit_price": 1500},
        ],
        customer_name="Alice",
        status=status,
    )


def test_process_return_restores_stock_and_records_movements(test_db, return_setup):
    order_id = _record_completed_order(test_db, return_setup)
    product_a_id = return_setup["product_a_id"]
    product_b_id = return_setup["product_b_id"]

    assert _product_stock(test_db, product_a_id) == 8
    assert _product_stock(test_db, product_b_id) == 19

    process_return(test_db, order_id, "REFUNDED", reason="Customer changed mind")

    assert _product_stock(test_db, product_a_id) == 10
    assert _product_stock(test_db, product_b_id) == 20

    order = test_db.execute(
        "SELECT status FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    assert order["status"] == "REFUNDED"

    returns = test_db.execute(
        """
        SELECT * FROM stock_movements
        WHERE reason = 'RETURN' AND reference_order_id = ?
        ORDER BY id
        """,
        (order_id,),
    ).fetchall()
    assert len(returns) == 2
    assert returns[0]["item_type"] == "PRODUCT"
    assert returns[0]["quantity_change"] == 2
    assert returns[0]["notes"] == "Customer changed mind"
    assert {r["item_id"] for r in returns} == {product_a_id, product_b_id}


def test_process_return_cancelled_status(test_db, return_setup):
    order_id = _record_completed_order(test_db, return_setup, status="PAID")
    product_a_id = return_setup["product_a_id"]
    product_b_id = return_setup["product_b_id"]

    process_return(test_db, order_id, "CANCELLED")

    assert _product_stock(test_db, product_a_id) == 10
    assert _product_stock(test_db, product_b_id) == 20

    order = test_db.execute(
        "SELECT status FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    assert order["status"] == "CANCELLED"

    returns = test_db.execute(
        """
        SELECT * FROM stock_movements
        WHERE reason = 'RETURN' AND reference_order_id = ?
        """,
        (order_id,),
    ).fetchall()
    assert len(returns) == 2


def test_process_return_already_refunded_raises(test_db, return_setup):
    order_id = _record_completed_order(test_db, return_setup)
    process_return(test_db, order_id, "REFUNDED")

    with pytest.raises(ValueError, match="Order #1 is already REFUNDED"):
        process_return(test_db, order_id, "CANCELLED")


def test_process_return_already_cancelled_raises(test_db, return_setup):
    order_id = _record_completed_order(test_db, return_setup, status="PAID")
    process_return(test_db, order_id, "CANCELLED")

    with pytest.raises(ValueError, match="Order #1 is already CANCELLED"):
        process_return(test_db, order_id, "REFUNDED")


def test_process_return_invalid_status_raises(test_db, return_setup):
    order_id = _record_completed_order(test_db, return_setup)

    with pytest.raises(ValueError, match="new_status must be one of"):
        process_return(test_db, order_id, "COMPLETED")


def test_process_return_nonexistent_order_raises(test_db):
    with pytest.raises(ValueError, match="Order with id 9999 does not exist"):
        process_return(test_db, 9999, "REFUNDED")


def test_process_return_already_returned_leaves_state_unchanged(test_db, return_setup):
    order_id = _record_completed_order(test_db, return_setup)
    product_a_id = return_setup["product_a_id"]
    product_b_id = return_setup["product_b_id"]

    process_return(test_db, order_id, "REFUNDED")

    stock_a_after = _product_stock(test_db, product_a_id)
    stock_b_after = _product_stock(test_db, product_b_id)
    returns_after = test_db.execute(
        "SELECT COUNT(*) FROM stock_movements WHERE reason = 'RETURN'"
    ).fetchone()[0]

    with pytest.raises(ValueError, match="already REFUNDED"):
        process_return(test_db, order_id, "CANCELLED")

    assert _product_stock(test_db, product_a_id) == stock_a_after
    assert _product_stock(test_db, product_b_id) == stock_b_after
    assert test_db.execute(
        "SELECT COUNT(*) FROM stock_movements WHERE reason = 'RETURN'"
    ).fetchone()[0] == returns_after


def test_update_order_status_rejects_cancelled_and_refunded(test_db, return_setup):
    order_id = _record_completed_order(test_db, return_setup)

    with pytest.raises(ValueError, match="Use process_return"):
        update_order_status(test_db, order_id, "REFUNDED")

    with pytest.raises(ValueError, match="Use process_return"):
        update_order_status(test_db, order_id, "CANCELLED")


def test_get_revenue_summary_excludes_cancelled_and_refunded(test_db, return_setup):
    product_a_id = return_setup["product_a_id"]
    product_b_id = return_setup["product_b_id"]

    active_order = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_a_id, "quantity": 1, "unit_price": 3000}],
    )
    refunded_order = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": product_b_id, "quantity": 1, "unit_price": 1500}],
    )
    process_return(test_db, refunded_order, "REFUNDED")

    draft_order_id = test_db.execute(
        """
        INSERT INTO orders (status, channel)
        VALUES ('DRAFT', 'OTHER')
        """
    ).lastrowid
    test_db.execute(
        """
        INSERT INTO order_items
            (order_id, product_id, quantity, list_price, unit_price, unit_cost_at_time)
        VALUES (?, ?, 1, 9999, 9999, 100)
        """,
        (draft_order_id, product_a_id),
    )
    test_db.commit()

    # active_order: INSTAGRAM applies the default shipping charge (180,000)
    # since none was given: revenue = items_net(3000) + shipping(180,000) =
    # 183,000; profit = revenue - cogs(500) = 182,500 (no packaging/postage
    # batches recorded here, so postage estimate is the 0 default).
    summary = get_revenue_summary(test_db)
    assert summary["order_count"] == 1
    assert summary["total_revenue"] == 183_000
    assert summary["total_profit"] == 182_500

    assert active_order == 1


# ---------------------------------------------------------------------------
# CANCELLED/REFUNDED transition rules and packaging restoration
# ---------------------------------------------------------------------------


def test_cancelled_from_paid_restores_products_and_packaging(test_db, canonical_setup):
    vinyl_id = canonical_setup["vinyl_id"]
    box_id = canonical_setup["box_id"]
    tape_id = canonical_setup["tape_id"]
    filler_id = canonical_setup["filler_id"]

    order_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": vinyl_id, "quantity": 2, "unit_price": 2_500_000}],
        status="PAID",
    )
    assert get_product(test_db, vinyl_id)["current_stock"] == 8
    assert get_material(test_db, box_id)["current_stock"] == 99

    process_return(test_db, order_id, "CANCELLED")

    assert get_product(test_db, vinyl_id)["current_stock"] == 10
    assert get_material(test_db, box_id)["current_stock"] == 100
    assert get_material(test_db, tape_id)["current_stock"] == 100
    assert get_material(test_db, filler_id)["current_stock"] == 50


def test_refunded_from_completed_restores_products_only(test_db, canonical_setup):
    vinyl_id = canonical_setup["vinyl_id"]
    box_id = canonical_setup["box_id"]
    tape_id = canonical_setup["tape_id"]
    filler_id = canonical_setup["filler_id"]

    order_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": vinyl_id, "quantity": 2, "unit_price": 2_500_000}],
        status="COMPLETED",
    )
    assert get_material(test_db, box_id)["current_stock"] == 99

    process_return(test_db, order_id, "REFUNDED")

    assert get_product(test_db, vinyl_id)["current_stock"] == 10
    # Packaging was used up — not restored on a refund.
    assert get_material(test_db, box_id)["current_stock"] == 99
    assert get_material(test_db, tape_id)["current_stock"] == 98
    assert get_material(test_db, filler_id)["current_stock"] == 49


@pytest.mark.parametrize("status", ["DRAFT", "PENDING"])
def test_refunded_from_draft_or_pending_raises_conflict(
    test_db, canonical_setup, status
):
    vinyl_id = canonical_setup["vinyl_id"]
    order_id = record_order(
        test_db,
        "IN_PERSON",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_500_000}],
        status=status,
    )

    with pytest.raises(ConflictError):
        process_return(test_db, order_id, "REFUNDED")


def test_cancelling_draft_restores_nothing_and_does_not_fail(test_db, canonical_setup):
    vinyl_id = canonical_setup["vinyl_id"]
    order_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_500_000}],
        status="DRAFT",
    )
    assert get_product(test_db, vinyl_id)["current_stock"] == 10

    process_return(test_db, order_id, "CANCELLED")

    assert test_db.execute(
        "SELECT status FROM orders WHERE id = ?", (order_id,)
    ).fetchone()["status"] == "CANCELLED"
    assert get_product(test_db, vinyl_id)["current_stock"] == 10


def test_cancel_restores_packaging_from_actual_movements_not_current_kit(
    test_db, canonical_setup
):
    vinyl_id = canonical_setup["vinyl_id"]
    filler_id = canonical_setup["filler_id"]
    kit_id = canonical_setup["kit_id"]

    order_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_500_000}],
        status="PAID",
    )
    assert get_material(test_db, filler_id)["current_stock"] == 49

    packaging.update_kit_item(test_db, kit_id, filler_id, 2)

    process_return(test_db, order_id, "CANCELLED")

    # Restored by exactly what was deducted (1), not the kit's new quantity (2).
    assert get_material(test_db, filler_id)["current_stock"] == 50
