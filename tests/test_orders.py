import pytest

from db.orders import (
    compute_order_profit,
    compute_order_total,
    get_order,
    list_orders,
    record_order,
    update_order_status,
)
from db.products import add_product, get_product


@pytest.fixture
def order_setup(test_db):
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


def test_record_order_single_item_happy_path(test_db, order_setup):
    product_id = order_setup["product_a_id"]

    order_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 2, "unit_price": 3000}],
        customer_name="Alice",
        shipping_charge=200,
        postage_cost=150,
        transaction_fee=50,
    )

    assert order_id == 1
    assert _product_stock(test_db, product_id) == 8

    detail = get_order(test_db, order_id)
    assert detail["order"]["channel"] == "INSTAGRAM"
    assert detail["order"]["customer_name"] == "Alice"
    assert len(detail["items"]) == 1

    item = detail["items"][0]
    assert item["product_name"] == "Product A"
    assert item["quantity"] == 2
    assert item["list_price"] == 6000
    assert item["discount_amount"] == 0
    assert item["unit_price"] == 3000
    assert item["unit_cost_at_time"] == 500

    movements = test_db.execute(
        "SELECT * FROM stock_movements WHERE reason = 'SALE'"
    ).fetchall()
    assert len(movements) == 1
    assert movements[0]["item_type"] == "PRODUCT"
    assert movements[0]["item_id"] == product_id
    assert movements[0]["quantity_change"] == -2
    assert movements[0]["reference_order_id"] == order_id


def test_record_order_multiple_items_happy_path(test_db, order_setup):
    product_a_id = order_setup["product_a_id"]
    product_b_id = order_setup["product_b_id"]

    order_id = record_order(
        test_db,
        "WEBSITE",
        [
            {"product_id": product_a_id, "quantity": 1, "unit_price": 3000},
            {
                "product_id": product_b_id,
                "quantity": 3,
                "unit_price": 1500,
                "discount_amount": 300,
            },
        ],
    )

    assert _product_stock(test_db, product_a_id) == 9
    assert _product_stock(test_db, product_b_id) == 17

    detail = get_order(test_db, order_id)
    assert len(detail["items"]) == 2

    by_product = {item["product_id"]: item for item in detail["items"]}
    assert by_product[product_b_id]["list_price"] == 4500
    assert by_product[product_b_id]["discount_amount"] == 300
    assert by_product[product_b_id]["unit_price"] == 1400

    movements = test_db.execute(
        "SELECT * FROM stock_movements WHERE reason = 'SALE' ORDER BY id"
    ).fetchall()
    assert len(movements) == 2
    assert {m["item_id"] for m in movements} == {product_a_id, product_b_id}
    assert all(m["reference_order_id"] == order_id for m in movements)


def test_insufficient_stock_rolls_back_entire_order(test_db, order_setup):
    product_a_id = order_setup["product_a_id"]
    product_b_id = order_setup["product_b_id"]

    stock_a_before = _product_stock(test_db, product_a_id)
    stock_b_before = _product_stock(test_db, product_b_id)
    orders_before = _count_rows(test_db, "orders")
    items_before = _count_rows(test_db, "order_items")
    movements_before = _count_rows(test_db, "stock_movements")

    with pytest.raises(ValueError, match="Product B.*insufficient stock"):
        record_order(
            test_db,
            "INSTAGRAM",
            [
                {"product_id": product_a_id, "quantity": 1, "unit_price": 3000},
                {"product_id": product_b_id, "quantity": 25, "unit_price": 1500},
            ],
        )

    assert _product_stock(test_db, product_a_id) == stock_a_before
    assert _product_stock(test_db, product_b_id) == stock_b_before
    assert _count_rows(test_db, "orders") == orders_before
    assert _count_rows(test_db, "order_items") == items_before
    assert _count_rows(test_db, "stock_movements") == movements_before


def test_invalid_channel_raises_value_error(test_db, order_setup):
    product_id = order_setup["product_a_id"]

    with pytest.raises(ValueError, match="Invalid channel"):
        record_order(
            test_db,
            "INVALID",
            [{"product_id": product_id, "quantity": 1, "unit_price": 1000}],
        )

    assert _count_rows(test_db, "orders") == 0


def test_invalid_status_raises_value_error(test_db, order_setup):
    product_id = order_setup["product_a_id"]

    with pytest.raises(ValueError, match="Invalid status"):
        record_order(
            test_db,
            "INSTAGRAM",
            [{"product_id": product_id, "quantity": 1, "unit_price": 1000}],
            status="INVALID",
        )

    assert _count_rows(test_db, "orders") == 0


def test_empty_items_raises_value_error(test_db):
    with pytest.raises(ValueError, match="at least one item"):
        record_order(test_db, "INSTAGRAM", [])


def test_discount_exceeds_line_total_raises_value_error(test_db, order_setup):
    product_id = order_setup["product_a_id"]

    with pytest.raises(ValueError, match="discount_amount"):
        record_order(
            test_db,
            "INSTAGRAM",
            [
                {
                    "product_id": product_id,
                    "quantity": 2,
                    "unit_price": 1000,
                    "discount_amount": 2500,
                }
            ],
        )

    assert _count_rows(test_db, "orders") == 0


def test_nonexistent_product_raises_value_error(test_db, order_setup):
    with pytest.raises(ValueError, match="product with id 9999 does not exist"):
        record_order(
            test_db,
            "INSTAGRAM",
            [{"product_id": 9999, "quantity": 1, "unit_price": 1000}],
        )

    assert _count_rows(test_db, "orders") == 0


def test_cost_snapshot_frozen_after_product_cost_change(test_db, order_setup):
    product_id = order_setup["product_a_id"]

    order_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 1, "unit_price": 3000}],
    )

    test_db.execute(
        "UPDATE products SET unit_cost = 999 WHERE id = ?", (product_id,)
    )
    test_db.commit()

    item = get_order(test_db, order_id)["items"][0]
    assert item["unit_cost_at_time"] == 500
    assert get_product(test_db, product_id)["unit_cost"] == 999


def test_get_order_computed_total_and_profit(test_db, order_setup):
    product_a_id = order_setup["product_a_id"]
    product_b_id = order_setup["product_b_id"]

    order_id = record_order(
        test_db,
        "WHOLESALE",
        [
            {
                "product_id": product_a_id,
                "quantity": 2,
                "unit_price": 1000,
                "discount_amount": 100,
            },
            {"product_id": product_b_id, "quantity": 1, "unit_price": 800},
        ],
        shipping_charge=200,
        postage_cost=150,
        transaction_fee=50,
    )

    detail = get_order(test_db, order_id)

    # Item A: list 2000 - discount 100 = 1900, COGS 2*500 = 1000
    # Item B: list 800, COGS 300
    # items revenue = 2700, COGS = 1300
    # total = 2700 + 200 + 150 - 50 = 3000
    # profit = 2700 - 1300 - 200 - 150 - 50 = 1000
    assert detail["total"] == 3000
    assert detail["profit"] == 1000

    order = detail["order"]
    items = detail["items"]
    assert compute_order_total(order, items) == 3000
    assert compute_order_profit(order, items) == 1000


def test_list_orders_filters_by_channel_and_status(test_db, order_setup):
    product_a_id = order_setup["product_a_id"]
    product_b_id = order_setup["product_b_id"]

    record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_a_id, "quantity": 1, "unit_price": 3000}],
        status="COMPLETED",
    )
    record_order(
        test_db,
        "WHOLESALE",
        [{"product_id": product_b_id, "quantity": 1, "unit_price": 1000}],
        status="PENDING",
    )

    instagram_orders = list_orders(test_db, channel="INSTAGRAM")
    assert len(instagram_orders) == 1
    assert instagram_orders[0]["channel"] == "INSTAGRAM"
    assert instagram_orders[0]["total"] == 3000

    pending_orders = list_orders(test_db, status="PENDING")
    assert len(pending_orders) == 1
    assert pending_orders[0]["status"] == "PENDING"
    assert pending_orders[0]["total"] == 1000


def test_update_order_status(test_db, order_setup):
    product_id = order_setup["product_a_id"]
    order_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 1, "unit_price": 3000}],
    )

    update_order_status(test_db, order_id, "PAID")
    assert get_order(test_db, order_id)["order"]["status"] == "PAID"

    with pytest.raises(ValueError, match="Use process_return"):
        update_order_status(test_db, order_id, "REFUNDED")

    with pytest.raises(ValueError, match="Order with id 9999 does not exist"):
        update_order_status(test_db, 9999, "CANCELLED")


@pytest.mark.parametrize(
    "status",
    ["DRAFT", "PENDING", "PAID", "COMPLETED"],
)
def test_record_order_accepts_lifecycle_statuses(test_db, order_setup, status):
    product_id = order_setup["product_a_id"]

    order_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 1, "unit_price": 3000}],
        status=status,
    )

    assert get_order(test_db, order_id)["order"]["status"] == status


def test_record_order_rejects_cancelled_at_creation(test_db, order_setup):
    product_id = order_setup["product_a_id"]

    with pytest.raises(ValueError, match="Cannot create an order with status 'CANCELLED'"):
        record_order(
            test_db,
            "INSTAGRAM",
            [{"product_id": product_id, "quantity": 1, "unit_price": 3000}],
            status="CANCELLED",
        )

    assert _count_rows(test_db, "orders") == 0


def test_record_order_rejects_refunded_at_creation(test_db, order_setup):
    product_id = order_setup["product_a_id"]

    with pytest.raises(ValueError, match="Cannot create an order with status 'REFUNDED'"):
        record_order(
            test_db,
            "INSTAGRAM",
            [{"product_id": product_id, "quantity": 1, "unit_price": 3000}],
            status="REFUNDED",
        )

    assert _count_rows(test_db, "orders") == 0


def test_record_order_defaults_to_completed(test_db, order_setup):
    product_id = order_setup["product_a_id"]

    order_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 1, "unit_price": 3000}],
    )

    assert get_order(test_db, order_id)["order"]["status"] == "COMPLETED"


def test_forward_status_transitions_draft_to_completed(test_db, order_setup):
    product_id = order_setup["product_a_id"]

    order_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 1, "unit_price": 3000}],
        status="DRAFT",
    )

    update_order_status(test_db, order_id, "PENDING")
    assert get_order(test_db, order_id)["order"]["status"] == "PENDING"

    update_order_status(test_db, order_id, "PAID")
    assert get_order(test_db, order_id)["order"]["status"] == "PAID"

    update_order_status(test_db, order_id, "COMPLETED")
    assert get_order(test_db, order_id)["order"]["status"] == "COMPLETED"


def test_record_order_assigns_invoice_number(test_db, order_setup):
    product_id = order_setup["product_a_id"]

    order_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 1, "unit_price": 3000}],
    )

    invoice_number = get_order(test_db, order_id)["order"]["invoice_number"]
    assert invoice_number is not None
    assert invoice_number == "INV-000001"


def test_order_invoice_numbers_increment_sequentially(test_db, order_setup):
    product_id = order_setup["product_a_id"]
    item = [{"product_id": product_id, "quantity": 1, "unit_price": 3000}]

    first_id = record_order(test_db, "INSTAGRAM", item)
    second_id = record_order(test_db, "WEBSITE", item)
    third_id = record_order(test_db, "IN_PERSON", item)

    assert get_order(test_db, first_id)["order"]["invoice_number"] == "INV-000001"
    assert get_order(test_db, second_id)["order"]["invoice_number"] == "INV-000002"
    assert get_order(test_db, third_id)["order"]["invoice_number"] == "INV-000003"


def test_null_invoice_orders_do_not_break_numbering(test_db, order_setup):
    product_id = order_setup["product_a_id"]

    test_db.execute(
        """
        INSERT INTO orders
            (status, channel, customer_name, shipping_charge,
             postage_cost, transaction_fee, notes, invoice_number)
        VALUES ('COMPLETED', 'OTHER', NULL, 0, 0, 0, NULL, NULL)
        """
    )
    test_db.commit()

    order_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 1, "unit_price": 3000}],
    )

    assert get_order(test_db, order_id)["order"]["invoice_number"] == "INV-000001"


def test_invoice_number_shared_sequence_across_statuses(test_db, order_setup):
    product_id = order_setup["product_a_id"]
    item = [{"product_id": product_id, "quantity": 1, "unit_price": 3000}]

    statuses = ["DRAFT", "PENDING", "PAID", "COMPLETED"]
    expected_invoices = ["INV-000001", "INV-000002", "INV-000003", "INV-000004"]

    for status, expected_invoice in zip(statuses, expected_invoices):
        order_id = record_order(test_db, "INSTAGRAM", item, status=status)
        assert (
            get_order(test_db, order_id)["order"]["invoice_number"] == expected_invoice
        )
