"""Material/product purchases from suppliers: increase stock, compute unit cost, log PURCHASE stock movements.
`total_paid` is the purchase's invoice total (it sets the weighted-average cost); what was actually paid for it is in
db/supplier_payments.py: a new purchase is paid in FULL (the default), NONE (on credit) or PARTIAL, and NONE / PARTIAL
need a supplier. Each purchase stores its own PURCHASE movement (`stock_movement_id`) and the item's unit cost just
before and just after it (`item_cost_before` / `item_cost_after`), for a later cancel or correction (section 22).
Reads give `paid`, `outstanding` and `payment_status` (section 21)."""

import sqlite3

from db.audit import audited
from db.connection import next_counter, transaction
from db.costing import blend_unit_cost, check_money, check_quantity, per_unit_cost
from db.errors import ErrorCode, NotFoundError, ValidationError
from db.materials import get_material
from db.products import get_product
from db.supplier_payments import (
    check_purchase_payment,
    paid_sql,
    purchase_payments,
    record_purchase_payment,
    with_payment_figures,
)
from db.suppliers import get_supplier
from db.timeutil import normalize_record_date, to_utc_range


def _validate_total_paid(total_paid: int) -> None:
    check_money(total_paid, "total_paid")
    if total_paid < 0:
        raise ValidationError(f"total_paid must be >= 0, got {total_paid}", field="total_paid")


def _validate_supplier(conn: sqlite3.Connection, supplier_id: int | None) -> None:
    if supplier_id is None:
        return
    if get_supplier(conn, supplier_id) is None:
        raise NotFoundError(
            f"Supplier with id {supplier_id} does not exist",
            code=ErrorCode.SUPPLIER_NOT_FOUND,
            details={"supplier_id": supplier_id},
        )


def _compute_unit_cost(total_paid: int, quantity_bought: float) -> int:
    """Per-unit cost from total paid and quantity: exact, rounded half-even to the Rial
    (a REAL quantity counts as the decimal it was entered as)."""
    try:
        return per_unit_cost(total_paid, quantity_bought)
    except ValidationError as exc:
        if exc.code != ErrorCode.AMOUNT_TOO_LARGE:
            raise
        # A tiny quantity makes the per-unit cost too large: the amount to change is total_paid.
        raise ValidationError(
            f"The unit cost (total_paid / quantity_bought) must be at most {exc.details['max']} Rial",
            field="total_paid", code=exc.code, details=exc.details,
        ) from None


# purchase kind -> (table, item table, item column, item_type of its movement, note label)
_KINDS = {
    "MATERIAL": ("material_purchases", "materials", "material_id", "MATERIAL", "Material"),
    "PRODUCT": ("product_purchases", "products", "product_id", "PRODUCT", "Product"),
}


def _write_purchase(
    conn: sqlite3.Connection,
    kind: str,
    item_id: int,
    quantity_bought,
    total_paid: int,
    unit_cost: int,
    cost_before: int | None,
    cost_after: int,
    supplier_id: int | None,
    purchase_date: str | None,
    notes: str | None,
    payment: dict | None,
) -> int:
    """The purchase row, the item's stock and cost, its PURCHASE movement and the payment made with it, in one
    transaction. `purchase_date` None = now."""
    table, item_table, item_column, item_type, label = _KINDS[kind]
    with transaction(conn):
        invoice_number = f"PUR-{next_counter(conn, 'PUR'):06d}"
        cursor = conn.execute(
            f"""
            INSERT INTO {table}
                ({item_column}, supplier_id, invoice_number, purchase_date,
                 quantity_bought, total_paid, unit_cost, notes, item_cost_before, item_cost_after)
            VALUES (?, ?, ?, COALESCE(?, datetime('now')), ?, ?, ?, ?, ?, ?)
            """,
            (item_id, supplier_id, invoice_number, purchase_date, quantity_bought, total_paid, unit_cost, notes,
             cost_before, cost_after),
        )
        purchase_id = cursor.lastrowid
        stored_date = conn.execute(f"SELECT purchase_date FROM {table} WHERE id = ?", (purchase_id,)).fetchone()[0]

        conn.execute(
            f"UPDATE {item_table} SET current_stock = current_stock + ?, unit_cost = ? WHERE id = ?",
            (quantity_bought, cost_after, item_id),
        )
        movement = conn.execute(
            """
            INSERT INTO stock_movements
                (item_type, item_id, quantity_change, reason, movement_date, notes)
            VALUES (?, ?, ?, 'PURCHASE', ?, ?)
            """,
            (item_type, item_id, quantity_bought, stored_date,
             f"{label} purchase #{purchase_id} (invoice {invoice_number})"),
        )
        conn.execute(f"UPDATE {table} SET stock_movement_id = ? WHERE id = ?", (movement.lastrowid, purchase_id))
        record_purchase_payment(conn, kind, purchase_id, payment)
    return purchase_id


@audited()
def record_material_purchase(
    conn: sqlite3.Connection,
    material_id: int,
    quantity_bought: float,
    total_paid: int,
    supplier_id: int | None = None,
    purchase_date: str | None = None,
    notes: str | None = None,
    payment: dict | None = None,
) -> int:
    """`payment`: {mode FULL | NONE | PARTIAL, amount (PARTIAL only), method, reference}; None = paid in full."""
    material = get_material(conn, material_id)
    if material is None:
        raise NotFoundError(f"Material with id {material_id} does not exist")
    if not material["is_active"]:
        raise ValidationError(f"Material '{material['name']}' is not active")
    if material["type"] == "SERVICE":
        raise ValidationError(
            f"Material '{material['name']}' is a SERVICE and cannot be purchased "
            f"into stock"
        )
    check_quantity(quantity_bought, "quantity_bought")

    _validate_total_paid(total_paid)
    _validate_supplier(conn, supplier_id)
    paid_now = check_purchase_payment(payment, supplier_id, total_paid)

    unit_cost = _compute_unit_cost(total_paid, quantity_bought)
    new_material_unit_cost = blend_unit_cost(
        material["current_stock"], material["unit_cost"], quantity_bought, total_paid,
        zero_is_unknown=True,
    )
    if purchase_date is not None:
        purchase_date = normalize_record_date(purchase_date, conn)

    return _write_purchase(
        conn, "MATERIAL", material_id, quantity_bought, total_paid, unit_cost,
        material["unit_cost"], new_material_unit_cost, supplier_id, purchase_date, notes, paid_now,
    )


@audited()
def record_product_purchase(
    conn: sqlite3.Connection,
    product_id: int,
    quantity_bought: int,
    total_paid: int,
    supplier_id: int | None = None,
    purchase_date: str | None = None,
    notes: str | None = None,
    payment: dict | None = None,
) -> int:
    """`payment`: as for `record_material_purchase`."""
    product = get_product(conn, product_id)
    if product is None:
        raise NotFoundError(f"Product with id {product_id} does not exist")
    if not product["is_active"]:
        raise ValidationError(f"Product '{product['name']}' is not active")
    check_quantity(quantity_bought, "quantity_bought", whole=True)

    _validate_total_paid(total_paid)
    _validate_supplier(conn, supplier_id)
    paid_now = check_purchase_payment(payment, supplier_id, total_paid)

    unit_cost = _compute_unit_cost(total_paid, quantity_bought)
    new_product_unit_cost = blend_unit_cost(
        product["current_stock"], product["unit_cost"], quantity_bought, total_paid
    )
    if purchase_date is not None:
        purchase_date = normalize_record_date(purchase_date, conn)

    return _write_purchase(
        conn, "PRODUCT", product_id, quantity_bought, total_paid, unit_cost,
        product["unit_cost"], new_product_unit_cost, supplier_id, purchase_date, notes, paid_now,
    )


# ---------------------------------------------------------------- reads


def _select(kind: str) -> str:
    """The public columns of a purchase (not its movement links or cost snapshot), the item and supplier names, the
    purchase that replaced it, and `paid`."""
    table, item_table, item_column, _, _ = _KINDS[kind]
    item_name = "material_name" if kind == "MATERIAL" else "product_name"
    return f"""
        SELECT
            {table}.id, {table}.{item_column}, {table}.supplier_id, {table}.invoice_number, {table}.purchase_date,
            {table}.quantity_bought, {table}.total_paid, {table}.unit_cost, {table}.notes,
            {table}.status, {table}.cancel_reason, {table}.cancelled_at, {table}.replaces_purchase_id,
            (SELECT r.id FROM {table} AS r WHERE r.replaces_purchase_id = {table}.id) AS replaced_by_purchase_id,
            {item_table}.name AS {item_name},
            suppliers.name AS supplier_name,
            {paid_sql(kind)} AS paid
        FROM {table}
        JOIN {item_table} ON {item_table}.id = {table}.{item_column}
        LEFT JOIN suppliers ON suppliers.id = {table}.supplier_id
    """


def _get(conn: sqlite3.Connection, kind: str, purchase_id: int) -> dict | None:
    table = _KINDS[kind][0]
    row = conn.execute(f"{_select(kind)} WHERE {table}.id = ?", (purchase_id,)).fetchone()
    if row is None:
        return None
    purchase = with_payment_figures(dict(row))
    purchase["payments"] = purchase_payments(conn, kind, purchase_id)
    return purchase


def get_material_purchase(conn: sqlite3.Connection, purchase_id: int) -> dict | None:
    """One purchase with its payment figures and `payments` (the payments that paid it)."""
    return _get(conn, "MATERIAL", purchase_id)


def get_product_purchase(conn: sqlite3.Connection, purchase_id: int) -> dict | None:
    """One purchase with its payment figures and `payments` (the payments that paid it)."""
    return _get(conn, "PRODUCT", purchase_id)


def _list(
    conn: sqlite3.Connection,
    kind: str,
    item_id: int | None,
    supplier_id: int | None,
    start_date: str | None,
    end_date: str | None,
) -> list[dict]:
    table, _, item_column, _, _ = _KINDS[kind]
    query = f"{_select(kind)} WHERE 1=1"
    params: list = []

    if item_id is not None:
        query += f" AND {table}.{item_column} = ?"
        params.append(item_id)
    if supplier_id is not None:
        query += f" AND {table}.supplier_id = ?"
        params.append(supplier_id)
    start_utc, end_exclusive_utc = to_utc_range(start_date, end_date, conn)
    if start_utc is not None:
        query += f" AND {table}.purchase_date >= ?"
        params.append(start_utc)
    if end_exclusive_utc is not None:
        query += f" AND {table}.purchase_date < ?"
        params.append(end_exclusive_utc)

    query += f" ORDER BY {table}.purchase_date DESC, {table}.id DESC"

    rows = conn.execute(query, params).fetchall()
    return [with_payment_figures(dict(row)) for row in rows]


def list_material_purchases(
    conn: sqlite3.Connection,
    material_id: int | None = None,
    supplier_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    return _list(conn, "MATERIAL", material_id, supplier_id, start_date, end_date)


def list_product_purchases(
    conn: sqlite3.Connection,
    product_id: int | None = None,
    supplier_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    return _list(conn, "PRODUCT", product_id, supplier_id, start_date, end_date)
