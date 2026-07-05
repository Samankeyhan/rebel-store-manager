import pytest

from db.orders import (
    get_revenue_summary,
    record_order,
    update_order_status,
)
from db.products import add_product, get_product
from db.returns import process_return


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


def _count_rows(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _product_stock(conn, product_id: int) -> int:
    return get_product(conn, product_id)["current_stock"]


def _record_completed_order(test_db, return_setup):
    return record_order(
        test_db,
        "INSTAGRAM",
        [
            {"product_id": return_setup["product_a_id"], "quantity": 2, "unit_price": 3000},
            {"product_id": return_setup["product_b_id"], "quantity": 1, "unit_price": 1500},
        ],
        customer_name="Alice",
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
    order_id = _record_completed_order(test_db, return_setup)
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
    order_id = _record_completed_order(test_db, return_setup)
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

    summary = get_revenue_summary(test_db)
    assert summary["order_count"] == 1
    assert summary["total_revenue"] == 3000
    # revenue 3000 - COGS 500 = 2500 profit
    assert summary["total_profit"] == 2500

    assert active_order == 1
