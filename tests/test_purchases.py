import pytest

from db.materials import add_material, get_material
from db.products import add_product, get_product
from db.purchases import (
    _compute_unit_cost,
    get_material_purchase,
    get_product_purchase,
    list_material_purchases,
    list_product_purchases,
    record_material_purchase,
    record_product_purchase,
)
from db.suppliers import add_supplier


@pytest.fixture
def purchase_setup(test_db):
    material_id = add_material(
        test_db, "Purchase Stock Material", "STOCK", 100, initial_stock=10
    )
    service_id = add_material(test_db, "Purchase Service", "SERVICE", 50)
    product_id = add_product(test_db, "Resale Vinyl", "VINYL", 3000, 2000)
    test_db.execute(
        "UPDATE products SET current_stock = 5, unit_cost = 400 WHERE id = ?",
        (product_id,),
    )
    test_db.commit()
    supplier_id = add_supplier(test_db, "Purchase Supplier")
    return {
        "material_id": material_id,
        "service_id": service_id,
        "product_id": product_id,
        "supplier_id": supplier_id,
    }


def _count_rows(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_compute_unit_cost_rounding():
    assert _compute_unit_cost(1000, 3) == 333
    assert _compute_unit_cost(1000, 4) == 250


def test_record_material_purchase_happy_path(purchase_setup, test_db):
    material_id = purchase_setup["material_id"]
    supplier_id = purchase_setup["supplier_id"]

    purchase_id = record_material_purchase(
        test_db,
        material_id,
        quantity_bought=7.5,
        total_paid=1500,
        supplier_id=supplier_id,
        purchase_date="2026-04-01",
        notes="Bulk order",
    )

    purchase = get_material_purchase(test_db, purchase_id)
    assert purchase is not None
    assert purchase["invoice_number"] == "PUR-000001"
    assert purchase["material_name"] == "Purchase Stock Material"
    assert purchase["supplier_name"] == "Purchase Supplier"
    assert purchase["quantity_bought"] == 7.5
    assert purchase["total_paid"] == 1500
    assert purchase["unit_cost"] == 200
    assert purchase["notes"] == "Bulk order"

    material = get_material(test_db, material_id)
    assert material["current_stock"] == 17.5
    assert material["unit_cost"] == 200

    movement = test_db.execute(
        """
        SELECT * FROM stock_movements
        WHERE reason = 'PURCHASE' AND item_type = 'MATERIAL' AND item_id = ?
        """,
        (material_id,),
    ).fetchone()
    assert movement is not None
    assert movement["quantity_change"] == 7.5
    assert movement["movement_date"] == "2026-04-01"
    assert movement["notes"] == "Material purchase #1 (invoice PUR-000001)"


def test_record_product_purchase_happy_path(purchase_setup, test_db):
    product_id = purchase_setup["product_id"]

    purchase_id = record_product_purchase(
        test_db,
        product_id,
        quantity_bought=4,
        total_paid=2000,
        purchase_date="2026-04-02",
    )

    purchase = get_product_purchase(test_db, purchase_id)
    assert purchase is not None
    assert purchase["invoice_number"] == "PUR-000001"
    assert purchase["product_name"] == "Resale Vinyl"
    assert purchase["supplier_name"] is None
    assert purchase["quantity_bought"] == 4
    assert purchase["total_paid"] == 2000
    assert purchase["unit_cost"] == 500

    product = get_product(test_db, product_id)
    assert product["current_stock"] == 9
    assert product["unit_cost"] == 500

    movement = test_db.execute(
        """
        SELECT * FROM stock_movements
        WHERE reason = 'PURCHASE' AND item_type = 'PRODUCT' AND item_id = ?
        """,
        (product_id,),
    ).fetchone()
    assert movement is not None
    assert movement["quantity_change"] == 4
    assert movement["notes"] == "Product purchase #1 (invoice PUR-000001)"


def test_invoice_numbers_shared_across_material_and_product(purchase_setup, test_db):
    material_id = purchase_setup["material_id"]
    product_id = purchase_setup["product_id"]

    first_id = record_material_purchase(
        test_db, material_id, quantity_bought=1, total_paid=100
    )
    second_id = record_product_purchase(
        test_db, product_id, quantity_bought=2, total_paid=400
    )
    third_id = record_material_purchase(
        test_db, material_id, quantity_bought=3, total_paid=300
    )

    assert get_material_purchase(test_db, first_id)["invoice_number"] == "PUR-000001"
    assert get_product_purchase(test_db, second_id)["invoice_number"] == "PUR-000002"
    assert get_material_purchase(test_db, third_id)["invoice_number"] == "PUR-000003"


def test_service_material_purchase_raises_and_rolls_back(purchase_setup, test_db):
    service_id = purchase_setup["service_id"]
    purchases_before = _count_rows(test_db, "material_purchases")
    movements_before = _count_rows(test_db, "stock_movements")

    with pytest.raises(ValueError, match="SERVICE"):
        record_material_purchase(
            test_db, service_id, quantity_bought=1, total_paid=100
        )

    assert _count_rows(test_db, "material_purchases") == purchases_before
    assert _count_rows(test_db, "stock_movements") == movements_before


def test_nonexistent_material_raises(purchase_setup, test_db):
    with pytest.raises(ValueError, match="does not exist"):
        record_material_purchase(test_db, 99999, quantity_bought=1, total_paid=100)


def test_nonexistent_product_raises(purchase_setup, test_db):
    with pytest.raises(ValueError, match="does not exist"):
        record_product_purchase(test_db, 99999, quantity_bought=1, total_paid=100)


def test_nonexistent_supplier_raises(purchase_setup, test_db):
    material_id = purchase_setup["material_id"]
    product_id = purchase_setup["product_id"]

    with pytest.raises(ValueError, match="Supplier with id 99999"):
        record_material_purchase(
            test_db, material_id, quantity_bought=1, total_paid=100, supplier_id=99999
        )

    with pytest.raises(ValueError, match="Supplier with id 99999"):
        record_product_purchase(
            test_db, product_id, quantity_bought=1, total_paid=100, supplier_id=99999
        )


@pytest.mark.parametrize(
    "record_fn,item_id_key",
    [
        (record_material_purchase, "material_id"),
        (record_product_purchase, "product_id"),
    ],
)
def test_invalid_quantity_raises(
    purchase_setup, test_db, record_fn, item_id_key
):
    item_id = purchase_setup[item_id_key]
    with pytest.raises(ValueError, match="quantity_bought must be > 0"):
        record_fn(test_db, item_id, quantity_bought=0, total_paid=100)


@pytest.mark.parametrize(
    "record_fn,item_id_key,quantity",
    [
        (record_material_purchase, "material_id", 1),
        (record_product_purchase, "product_id", 1),
    ],
)
def test_negative_total_paid_raises(
    purchase_setup, test_db, record_fn, item_id_key, quantity
):
    item_id = purchase_setup[item_id_key]
    with pytest.raises(ValueError, match="total_paid must be >= 0"):
        record_fn(test_db, item_id, quantity_bought=quantity, total_paid=-1)


def test_material_purchase_without_supplier(purchase_setup, test_db):
    purchase_id = record_material_purchase(
        test_db,
        purchase_setup["material_id"],
        quantity_bought=2,
        total_paid=600,
        supplier_id=None,
    )
    purchase = get_material_purchase(test_db, purchase_id)
    assert purchase["supplier_id"] is None
    assert purchase["supplier_name"] is None


def test_list_material_purchases_filters(purchase_setup, test_db):
    material_id = purchase_setup["material_id"]
    supplier_id = purchase_setup["supplier_id"]
    other_supplier_id = add_supplier(test_db, "Other Supplier")

    first_id = record_material_purchase(
        test_db,
        material_id,
        quantity_bought=1,
        total_paid=100,
        supplier_id=supplier_id,
        purchase_date="2026-03-01",
    )
    record_material_purchase(
        test_db,
        material_id,
        quantity_bought=2,
        total_paid=200,
        supplier_id=other_supplier_id,
        purchase_date="2026-03-15",
    )
    record_material_purchase(
        test_db,
        material_id,
        quantity_bought=3,
        total_paid=300,
        supplier_id=supplier_id,
        purchase_date="2026-04-01",
    )

    by_material = list_material_purchases(test_db, material_id=material_id)
    assert len(by_material) == 3

    by_supplier = list_material_purchases(test_db, supplier_id=supplier_id)
    assert len(by_supplier) == 2

    in_march = list_material_purchases(
        test_db, start_date="2026-03-01", end_date="2026-03-31"
    )
    assert len(in_march) == 2

    assert list_material_purchases(test_db, start_date="2099-01-01") == []

    latest = list_material_purchases(test_db)[0]
    assert latest["id"] == first_id or latest["purchase_date"] >= "2026-04-01"


def test_list_product_purchases_filters(purchase_setup, test_db):
    product_id = purchase_setup["product_id"]
    supplier_id = purchase_setup["supplier_id"]

    record_product_purchase(
        test_db,
        product_id,
        quantity_bought=1,
        total_paid=100,
        supplier_id=supplier_id,
        purchase_date="2026-02-10",
    )
    second_id = record_product_purchase(
        test_db,
        product_id,
        quantity_bought=2,
        total_paid=200,
        purchase_date="2026-03-10",
    )

    by_product = list_product_purchases(test_db, product_id=product_id)
    assert len(by_product) == 2
    assert by_product[0]["id"] == second_id

    by_supplier = list_product_purchases(test_db, supplier_id=supplier_id)
    assert len(by_supplier) == 1

    in_feb = list_product_purchases(
        test_db, start_date="2026-02-01", end_date="2026-02-28"
    )
    assert len(in_feb) == 1


def test_get_purchase_returns_none_for_missing(purchase_setup, test_db):
    assert get_material_purchase(test_db, 99999) is None
    assert get_product_purchase(test_db, 99999) is None
