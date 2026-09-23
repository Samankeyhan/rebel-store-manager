import os
from pathlib import Path
from unittest.mock import patch

import pdfplumber
import pytest
from PIL import Image

from db.orders import get_order, record_order
from db.products import add_product
from pdf import invoice as invoice_module
from pdf.invoice import generate_invoice_pdf


def _write_test_png(path: Path, width: int = 20, height: int = 10) -> None:
    Image.new("RGB", (width, height), color=(180, 60, 60)).save(path, "PNG")


@pytest.fixture
def invoice_order_setup(test_db, tmp_path):
    product_id = add_product(test_db, "Test Vinyl", "VINYL", 3000, 2000)
    test_db.execute(
        "UPDATE products SET current_stock = 10, unit_cost = 500 WHERE id = ?",
        (product_id,),
    )
    test_db.commit()

    order_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 2, "unit_price": 3000}],
        customer_name="Test Customer",
        shipping_charge=170_000,
        postage_cost=88_888,
        transaction_fee=77_777,
    )
    return {
        "order_id": order_id,
        "output_dir": str(tmp_path / "invoices"),
        "product_id": product_id,
    }


def test_generate_invoice_pdf_creates_nonempty_file(invoice_order_setup, test_db):
    order_id = invoice_order_setup["order_id"]
    output_dir = invoice_order_setup["output_dir"]

    path = generate_invoice_pdf(test_db, order_id, output_dir=output_dir)

    assert os.path.isfile(path)
    assert os.path.getsize(path) > 0


def test_generate_invoice_pdf_raises_for_missing_order(test_db, tmp_path):
    output_dir = str(tmp_path / "invoices")

    with pytest.raises(ValueError, match="does not exist"):
        generate_invoice_pdf(test_db, 99999, output_dir=output_dir)

    assert not os.path.exists(output_dir) or not list(Path(output_dir).glob("*.pdf"))


def test_invoice_number_present_in_pdf_text(invoice_order_setup, test_db):
    order_id = invoice_order_setup["order_id"]
    output_dir = invoice_order_setup["output_dir"]
    invoice_number = get_order(test_db, order_id)["order"]["invoice_number"]

    path = generate_invoice_pdf(test_db, order_id, output_dir=output_dir)

    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert invoice_number in text


def test_filename_uses_invoice_number(invoice_order_setup, test_db):
    order_id = invoice_order_setup["order_id"]
    output_dir = invoice_order_setup["output_dir"]
    invoice_number = get_order(test_db, order_id)["order"]["invoice_number"]

    path = generate_invoice_pdf(test_db, order_id, output_dir=output_dir)

    assert path.endswith(f"invoice_{invoice_number}.pdf")


def test_filename_fallback_when_invoice_number_null(invoice_order_setup, test_db):
    product_id = invoice_order_setup["product_id"]
    output_dir = invoice_order_setup["output_dir"]

    cursor = test_db.execute(
        """
        INSERT INTO orders
            (status, channel, customer_name, shipping_charge,
             postage_cost, transaction_fee, notes, invoice_number)
        VALUES ('COMPLETED', 'OTHER', NULL, 0, 0, 0, NULL, NULL)
        """
    )
    legacy_order_id = cursor.lastrowid
    test_db.execute(
        """
        INSERT INTO order_items
            (order_id, product_id, quantity, list_price, discount_amount,
             discount_reason, unit_price, unit_cost_at_time)
        VALUES (?, ?, 1, 3000, 0, NULL, 3000, 500)
        """,
        (legacy_order_id, product_id),
    )
    test_db.commit()

    path = generate_invoice_pdf(test_db, legacy_order_id, output_dir=output_dir)

    assert path.endswith(f"invoice_order_{legacy_order_id}.pdf")


def test_missing_logo_does_not_crash(invoice_order_setup, test_db):
    order_id = invoice_order_setup["order_id"]
    output_dir = invoice_order_setup["output_dir"]

    path = generate_invoice_pdf(test_db, order_id, output_dir=output_dir)

    assert os.path.isfile(path)
    assert os.path.getsize(path) > 0


def test_missing_footer_does_not_crash(invoice_order_setup, test_db):
    order_id = invoice_order_setup["order_id"]
    output_dir = invoice_order_setup["output_dir"]

    with patch.object(invoice_module, "FOOTER_PATH", "assets/nonexistent_footer.png"):
        path = generate_invoice_pdf(test_db, order_id, output_dir=output_dir)

    assert os.path.isfile(path)
    assert os.path.getsize(path) > 0


def test_footer_image_does_not_crash(invoice_order_setup, test_db, tmp_path):
    order_id = invoice_order_setup["order_id"]
    output_dir = invoice_order_setup["output_dir"]
    footer_file = tmp_path / "test_footer.png"
    _write_test_png(footer_file)

    with patch.object(invoice_module, "FOOTER_PATH", str(footer_file)):
        path = generate_invoice_pdf(test_db, order_id, output_dir=output_dir)

    assert os.path.isfile(path)
    assert os.path.getsize(path) > 0


def test_invoice_shows_shipping_and_total_not_postage_or_fee(invoice_order_setup, test_db):
    order_id = invoice_order_setup["order_id"]
    output_dir = invoice_order_setup["output_dir"]
    detail = get_order(test_db, order_id)
    order = detail["order"]

    path = generate_invoice_pdf(test_db, order_id, output_dir=output_dir)

    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    # Match just the Persian-digit number (not the " تومان" suffix): RTL/bidi
    # reshaping can reorder the number relative to surrounding Persian words
    # in extracted text, but the digit run itself stays contiguous.
    def _persian_number(amount: int) -> str:
        return f"{amount:,}".translate(invoice_module.PERSIAN_DIGIT_MAP)

    shipping_text = _persian_number(order["shipping_charge"])
    total_text = _persian_number(detail["customer_total"])
    postage_text = _persian_number(order["postage_cost"])
    fee_text = _persian_number(order["transaction_fee"])

    assert shipping_text in text
    assert total_text in text
    assert postage_text not in text
    assert fee_text not in text
