import os
from pathlib import Path
from unittest.mock import patch

import pdfplumber
import pytest
from PIL import Image

from db.currency import format_display_number
from db.orders import get_order, record_order
from db.products import add_product
from tests.helpers import cat
from pdf import invoice as invoice_module
from pdf.invoice import generate_invoice_pdf


def _write_test_png(path: Path, width: int = 20, height: int = 10) -> None:
    Image.new("RGB", (width, height), color=(180, 60, 60)).save(path, "PNG")


@pytest.fixture
def invoice_order_setup(test_db, tmp_path):
    product_id = add_product(test_db, "Test Vinyl", cat(test_db, "VINYL"), 3000, 2000)
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
    # in extracted text, but the digit run itself stays contiguous. Amounts are
    # stored in Rial and shown in the display currency (Toman by default).
    assert _shown(order["shipping_charge"]) in text
    assert _shown(detail["customer_total"]) in text
    for hidden in (order["postage_cost"], order["transaction_fee"]):
        assert _shown(hidden) not in text
        assert _shown(hidden, "RIAL") not in text


def _invoice_text(test_db, order_id, output_dir) -> str:
    path = generate_invoice_pdf(test_db, order_id, output_dir=output_dir)
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _shown(rial: int, currency: str = "TOMAN") -> str:
    """The number the invoice prints for a stored Rial amount (no unit), via
    the same exact conversion the invoice uses: Toman = Rial / 10 with «٫» and
    one digit only when needed, Rial = the stored integer."""
    return format_display_number(
        rial, currency, decimal_mark=invoice_module.PERSIAN_DECIMAL_MARK
    ).translate(invoice_module.PERSIAN_DIGIT_MAP)


def _discounted_order(test_db, product_id):
    return record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 2, "unit_price": 3000,
          "discount_amount": 700, "discount_reason": "promo"}],
        customer_name="Test Customer",
        shipping_charge=170_000,
        postage_cost=88_888,
        transaction_fee=77_777,
    )


@pytest.mark.parametrize("currency, unit, other_unit", [
    ("TOMAN", "تومان", "ریال"),
    ("RIAL", "ریال", "تومان"),
])
def test_invoice_amounts_follow_display_currency(
    invoice_order_setup, test_db, currency, unit, other_unit
):
    from db.settings import set_setting

    set_setting(test_db, "display_currency", currency)
    order_id = _discounted_order(test_db, invoice_order_setup["product_id"])
    detail = get_order(test_db, order_id)
    order = detail["order"]
    item = detail["items"][0]

    text = _invoice_text(test_db, order_id, invoice_order_setup["output_dir"])

    for rial in (
        item["unit_price"],
        item["list_price"] - item["discount_amount"],
        item["discount_amount"],
        order["shipping_charge"],
        detail["customer_total"],
    ):
        assert _shown(rial, currency) in text, rial
    # pdfplumber returns RTL words as visual glyph runs; check the reshaped unit.
    assert invoice_module.prepare_persian(unit) in text
    assert invoice_module.prepare_persian(other_unit) not in text
    # Still customer amounts only, in either currency.
    for hidden in (order["postage_cost"], order["transaction_fee"]):
        assert _shown(hidden, "TOMAN") not in text
        assert _shown(hidden, "RIAL") not in text


def test_invoice_rial_shows_the_stored_integer_and_toman_a_tenth(invoice_order_setup, test_db):
    from db.settings import set_setting

    order_id = invoice_order_setup["order_id"]
    total = get_order(test_db, order_id)["customer_total"]  # 176,000 Rial
    out = invoice_order_setup["output_dir"]

    toman_text = _invoice_text(test_db, order_id, out)
    set_setting(test_db, "display_currency", "RIAL")
    rial_text = _invoice_text(test_db, order_id, out)

    assert total == 176_000
    assert "۱۷,۶۰۰" in toman_text  # whole Toman: no decimal shown
    assert "۱۷۶,۰۰۰" in rial_text
    assert invoice_module.format_amount(total, "RIAL") == "۱۷۶,۰۰۰ ریال"
    assert invoice_module.format_amount(total, "TOMAN") == "۱۷,۶۰۰ تومان"


@pytest.mark.parametrize(
    "rial, toman, rial_text",
    [
        (1_800_005, "۱۸۰,۰۰۰٫۵ تومان", "۱,۸۰۰,۰۰۵ ریال"),
        (1_800_000, "۱۸۰,۰۰۰ تومان", "۱,۸۰۰,۰۰۰ ریال"),
        (7, "۰٫۷ تومان", "۷ ریال"),
        (12_345_671, "۱,۲۳۴,۵۶۷٫۱ تومان", "۱۲,۳۴۵,۶۷۱ ریال"),
    ],
)
def test_format_amount_toman_decimal_only_when_needed(rial, toman, rial_text):
    assert invoice_module.format_amount(rial, "TOMAN") == toman
    assert invoice_module.format_amount(rial, "RIAL") == rial_text


@pytest.mark.parametrize("currency", ["TOMAN", "RIAL"])
def test_invoice_with_odd_rial_amounts(test_db, tmp_path, currency):
    """Odd Rial amounts (not whole Toman) print exactly in both currencies."""
    from db.settings import set_setting

    product_id = add_product(test_db, "Odd Rial LP", cat(test_db, "VINYL"), 12_345, 10_001)
    test_db.execute("UPDATE products SET current_stock = 10, unit_cost = 5003 WHERE id = ?", (product_id,))
    test_db.commit()
    set_setting(test_db, "display_currency", currency)
    order_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 3, "unit_price": 12_345, "discount_amount": 7}],
        customer_name="Test Customer",
        shipping_charge=1_800_005,
        postage_cost=3_333,
        transaction_fee=4_567,
    )
    detail = get_order(test_db, order_id)
    item = detail["items"][0]
    assert item["list_price"] == 37_035
    assert detail["customer_total"] == 37_035 - 7 + 1_800_005 == 1_837_033

    text = _invoice_text(test_db, order_id, str(tmp_path / "invoices"))
    for rial in (37_035 - 7, 7, 1_800_005, 1_837_033):
        assert _shown(rial, currency) in text, (rial, _shown(rial, currency))
    if currency == "TOMAN":
        assert "۱۸۳,۷۰۳٫۳" in text and "۱۸۰,۰۰۰٫۵" in text and "۰٫۷" in text
    else:
        assert "۱,۸۳۷,۰۳۳" in text and "۱,۸۰۰,۰۰۵" in text
    for hidden in (3_333, 4_567):
        assert _shown(hidden, "TOMAN") not in text
        assert _shown(hidden, "RIAL") not in text


# The widest realistic amount, 999,999,995 Rial (99,999,999.5 Toman), in both
# display currencies, measured as drawn: line items use 10pt Vazir and
# _draw_amount_right right-aligns the reshaped text at the column edge.
WIDEST_REALISTIC_RIAL = 999_999_995
AMOUNT_FONT = "Vazir"
AMOUNT_SIZE = 10
MIN_GAP_UNIT_PRICE_TO_LINE_TOTAL = 9


def _drawn_amount_width(rial: int, currency: str) -> float:
    from reportlab.pdfbase import pdfmetrics

    invoice_module._register_fonts()
    text = invoice_module.prepare_persian(invoice_module.format_amount(rial, currency))
    return pdfmetrics.stringWidth(text, AMOUNT_FONT, AMOUNT_SIZE)


@pytest.mark.parametrize(
    "currency, expected",
    [("TOMAN", "۹۹,۹۹۹,۹۹۹٫۵ تومان"), ("RIAL", "۹۹۹,۹۹۹,۹۹۵ ریال")],
)
def test_widest_amount_fits_the_amount_columns(currency, expected):
    assert invoice_module.format_amount(WIDEST_REALISTIC_RIAL, currency) == expected
    width = _drawn_amount_width(WIDEST_REALISTIC_RIAL, currency)

    # The line total ends at COL_LINE_TOTAL and must start inside the page margin.
    line_total_left = invoice_module.COL_LINE_TOTAL - width
    assert line_total_left >= invoice_module.PAGE_MARGIN, (currency, width)

    # The unit price ends at COL_UNIT_PRICE and must keep the gap before the
    # line-total column's right edge.
    unit_price_left = invoice_module.COL_UNIT_PRICE - width
    gap = unit_price_left - invoice_module.COL_LINE_TOTAL
    assert gap >= MIN_GAP_UNIT_PRICE_TO_LINE_TOTAL, (currency, width, gap)
