import sqlite3

import pytest

from db import packaging, postage
from db.errors import ConflictError, InsufficientStockError, ValidationError
from db.materials import add_material, get_material
from db.orders import (
    compute_order_profit,
    compute_order_revenue,
    get_order,
    list_orders,
    record_order,
    update_order_status,
)
from db.products import add_product, get_product
from db.purchases import record_material_purchase, record_product_purchase
from db.settings import get_setting, set_setting, update_channel_settings


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


@pytest.fixture
def canonical_setup(test_db):
    """The canonical fixture from the task: a product, three packaging
    materials, a packaging kit set as WEBSITE's default, and a postage batch —
    all built through the real db/ functions, never raw SQL.
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


def test_stock_check_aggregates_needed_quantity_across_multiple_lines(test_db, order_setup):
    product_id = order_setup["product_a_id"]
    test_db.execute("UPDATE products SET current_stock = 5 WHERE id = ?", (product_id,))
    test_db.commit()

    orders_before = _count_rows(test_db, "orders")

    with pytest.raises(InsufficientStockError) as exc_info:
        record_order(
            test_db,
            "IN_PERSON",
            [
                {"product_id": product_id, "quantity": 3, "unit_price": 3000},
                {"product_id": product_id, "quantity": 3, "unit_price": 3000},
            ],
        )

    assert exc_info.value.needed == 6
    assert exc_info.value.available == 5
    assert _count_rows(test_db, "orders") == orders_before
    assert _product_stock(test_db, product_id) == 5


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


def test_selling_product_with_null_cost_raises_validation_error(test_db):
    product_id = add_product(test_db, "No Cost Product", "POSTER", 1000, 500)
    test_db.execute(
        "UPDATE products SET current_stock = 5 WHERE id = ?", (product_id,)
    )
    test_db.commit()

    with pytest.raises(ValidationError, match="unit_cost"):
        record_order(
            test_db,
            "IN_PERSON",
            [{"product_id": product_id, "quantity": 1, "unit_price": 1000}],
        )

    assert _product_stock(test_db, product_id) == 5


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
    # items_net = 2700, COGS = 1300, no packaging kit on WHOLESALE
    # revenue = 2700 + shipping(200) = 2900
    # profit = 2900 - 1300 - packaging(0) - postage(150) - fee(50) = 1400
    assert detail["customer_total"] == 2900
    assert detail["profit"] == 1400
    assert "total" not in detail

    order = detail["order"]
    items = detail["items"]
    assert compute_order_revenue(order, items) == 2900
    assert compute_order_profit(order, items) == 1400


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

    # INSTAGRAM applies the default shipping charge (180,000) since none was
    # given: customer_total = items_net (3000) + shipping (180,000).
    instagram_orders = list_orders(test_db, channel="INSTAGRAM")
    assert len(instagram_orders) == 1
    assert instagram_orders[0]["channel"] == "INSTAGRAM"
    assert instagram_orders[0]["customer_total"] == 183_000

    # WHOLESALE does not apply a shipping charge by default.
    pending_orders = list_orders(test_db, status="PENDING")
    assert len(pending_orders) == 1
    assert pending_orders[0]["status"] == "PENDING"
    assert pending_orders[0]["customer_total"] == 1000


def test_list_orders_includes_profit(test_db, canonical_setup):
    vinyl_id = canonical_setup["vinyl_id"]

    order_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": vinyl_id, "quantity": 2, "unit_price": 2_500_000}],
        transaction_fee=50_000,
    )

    rows = list_orders(test_db, channel="WEBSITE")
    assert len(rows) == 1
    row = rows[0]
    assert row["customer_total"] == 5_180_000
    assert row["profit"] == 2_435_000

    detail = get_order(test_db, order_id)
    assert row["customer_total"] == detail["customer_total"]
    assert row["profit"] == detail["profit"]

    draft_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_500_000}],
        status="DRAFT",
    )
    draft_row = next(
        r for r in list_orders(test_db, status="DRAFT") if r["id"] == draft_id
    )
    assert draft_row["profit"] is None


def test_update_order_status(test_db, order_setup):
    product_id = order_setup["product_a_id"]
    order_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 1, "unit_price": 3000}],
        status="PENDING",
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


def test_duplicate_order_invoice_number_rejected_by_unique_index(test_db, order_setup):
    product_id = order_setup["product_a_id"]
    order_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 1, "unit_price": 3000}],
    )
    invoice_number = get_order(test_db, order_id)["order"]["invoice_number"]

    with pytest.raises(sqlite3.IntegrityError):
        test_db.execute(
            """
            INSERT INTO orders (status, channel, invoice_number)
            VALUES ('COMPLETED', 'OTHER', ?)
            """,
            (invoice_number,),
        )


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


# ---------------------------------------------------------------------------
# Packaging kits, postage, and the DRAFT/commit lifecycle (canonical fixture)
# ---------------------------------------------------------------------------


def test_canonical_website_order(test_db, canonical_setup):
    vinyl_id = canonical_setup["vinyl_id"]
    box_id = canonical_setup["box_id"]
    tape_id = canonical_setup["tape_id"]
    filler_id = canonical_setup["filler_id"]

    order_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": vinyl_id, "quantity": 2, "unit_price": 2_500_000}],
        transaction_fee=50_000,
    )

    detail = get_order(test_db, order_id)
    order = detail["order"]

    assert order["shipping_charge"] == 180_000
    assert order["packaging_cost"] == 45_000
    assert order["postage_cost"] == 250_000
    assert detail["customer_total"] == 5_180_000
    assert detail["profit"] == 2_435_000
    assert "total" not in detail

    assert detail["items"][0]["unit_cost_at_time"] == 1_200_000

    assert get_product(test_db, vinyl_id)["current_stock"] == 8
    assert get_material(test_db, box_id)["current_stock"] == 99
    assert get_material(test_db, tape_id)["current_stock"] == 98
    assert get_material(test_db, filler_id)["current_stock"] == 49

    packaging_movements = test_db.execute(
        """
        SELECT * FROM stock_movements
        WHERE reason = 'PACKAGING' AND reference_order_id = ?
        """,
        (order_id,),
    ).fetchall()
    assert len(packaging_movements) == 3
    assert all(m["item_type"] == "MATERIAL" for m in packaging_movements)


def test_in_person_order_has_no_shipping_postage_or_packaging_by_default(
    test_db, canonical_setup
):
    vinyl_id = canonical_setup["vinyl_id"]

    order_id = record_order(
        test_db,
        "IN_PERSON",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_500_000}],
    )

    order = get_order(test_db, order_id)["order"]
    assert order["shipping_charge"] == 0
    assert order["postage_cost"] == 0
    assert order["packaging_cost"] == 0
    assert order["packaging_kit_id"] is None


def test_wholesale_order_no_shipping_but_postage_estimate_applies(
    test_db, canonical_setup
):
    vinyl_id = canonical_setup["vinyl_id"]

    order_id = record_order(
        test_db,
        "WHOLESALE",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_000_000}],
    )

    order = get_order(test_db, order_id)["order"]
    assert order["shipping_charge"] == 0
    assert order["postage_cost"] == 250_000


def test_overrides_shipping_charge_zero_and_no_packaging(test_db, canonical_setup):
    vinyl_id = canonical_setup["vinyl_id"]

    order_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_500_000}],
        shipping_charge=0,
        packaging_kit_id=None,
    )

    order = get_order(test_db, order_id)["order"]
    assert order["shipping_charge"] == 0
    assert order["packaging_kit_id"] is None
    assert order["packaging_cost"] == 0


def test_explicit_postage_override_wins_even_when_channel_does_not_apply_postage(
    test_db, canonical_setup
):
    vinyl_id = canonical_setup["vinyl_id"]

    order_id = record_order(
        test_db,
        "IN_PERSON",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_500_000}],
        postage_cost=99_999,
    )

    order = get_order(test_db, order_id)["order"]
    assert order["postage_cost"] == 99_999


def test_draft_commit_uses_postage_estimate_live_at_commit_time(
    test_db, canonical_setup
):
    vinyl_id = canonical_setup["vinyl_id"]

    order_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_500_000}],
        status="DRAFT",
    )

    order = get_order(test_db, order_id)["order"]
    assert order["status"] == "DRAFT"
    assert order["stock_committed"] == 0
    assert get_product(test_db, vinyl_id)["current_stock"] == 10

    postage.record_postage_batch(test_db, total_paid=600_000, order_count=2)
    # window = 3; batches so far: 10,000,000/40 and 600,000/2
    # estimate = round(10,600,000 / 42) = 252,381
    assert postage.get_current_postage_estimate(test_db) == 252_381

    update_order_status(test_db, order_id, "PAID")

    order = get_order(test_db, order_id)["order"]
    assert order["status"] == "PAID"
    assert order["stock_committed"] == 1
    assert order["postage_cost"] == 252_381
    assert get_product(test_db, vinyl_id)["current_stock"] == 9


def test_draft_to_paid_fails_when_stock_ran_out_in_the_meantime(
    test_db, canonical_setup
):
    vinyl_id = canonical_setup["vinyl_id"]

    draft_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": vinyl_id, "quantity": 10, "unit_price": 2_500_000}],
        status="DRAFT",
    )

    record_order(
        test_db,
        "IN_PERSON",
        [{"product_id": vinyl_id, "quantity": 10, "unit_price": 2_500_000}],
    )
    assert get_product(test_db, vinyl_id)["current_stock"] == 0

    with pytest.raises(InsufficientStockError):
        update_order_status(test_db, draft_id, "PAID")

    order = get_order(test_db, draft_id)["order"]
    assert order["status"] == "DRAFT"
    assert order["stock_committed"] == 0


@pytest.mark.parametrize(
    "from_status, to_status",
    [("COMPLETED", "DRAFT"), ("PAID", "PENDING"), ("PAID", "PAID")],
)
def test_illegal_transitions_raise_conflict_error(
    test_db, canonical_setup, from_status, to_status
):
    vinyl_id = canonical_setup["vinyl_id"]

    order_id = record_order(
        test_db,
        "IN_PERSON",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_500_000}],
        status=from_status,
    )

    with pytest.raises(ConflictError):
        update_order_status(test_db, order_id, to_status)


def test_changing_default_shipping_charge_does_not_affect_existing_order(
    test_db, canonical_setup
):
    vinyl_id = canonical_setup["vinyl_id"]

    order_id = record_order(
        test_db,
        "WEBSITE",
        [{"product_id": vinyl_id, "quantity": 1, "unit_price": 2_500_000}],
    )
    assert get_order(test_db, order_id)["order"]["shipping_charge"] == 180_000

    set_setting(test_db, "default_shipping_charge", 999_999)

    assert get_order(test_db, order_id)["order"]["shipping_charge"] == 180_000
