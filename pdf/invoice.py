import sqlite3
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from config.store_info import (
    FOOTER_PATH,
    LOGO_PATH,
    STORE_ADDRESS,
    STORE_NAME,
    STORE_PHONE,
)
from db.orders import get_order

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = PROJECT_ROOT / "fonts"

PAGE_MARGIN = 50
LINE_HEIGHT = 16
TABLE_ROW_HEIGHT = 18
LOGO_MAX_HEIGHT = 48
FOOTER_MAX_HEIGHT = 70
FOOTER_ABOVE_MARGIN = 14
HEADER_LOGO_TO_NAME_GAP = 22
HEADER_TEXT_GAP = 20
HEADER_BOTTOM_GAP = 28

THANK_YOU_TEXT = "با تشکر از خرید شما"
THANK_YOU_HEART = "\u2764"  # ❤ (U+2764); ❤️+VS16 leaves a tofu box in Helvetica
THANK_YOU_HEART_FONT = "Helvetica"
THANK_YOU_HEART_GAP = 5
THANK_YOU_HEART_COLOR = colors.HexColor("#E53935")

PERSIAN_DIGIT_MAP = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

CHANNEL_LABELS = {
    "INSTAGRAM": "اینستاگرام",
    "WEBSITE": "وبسایت",
    "WHOLESALE": "عمده‌فروشی",
    "IN_PERSON": "حضوری",
    "OTHER": "سایر",
}

# Column right edges (points from left origin).
# Physical left-to-right on page: جمع | قیمت واحد | تعداد | نام محصول
COL_LINE_TOTAL = 112
COL_UNIT_PRICE = 205
COL_QUANTITY = 268
COL_PRODUCT = 545
PRODUCT_NAME_GAP = 55
PRODUCT_NAME_MAX_WIDTH = COL_PRODUCT - COL_QUANTITY - PRODUCT_NAME_GAP

_fonts_registered = False


def _register_fonts() -> None:
    global _fonts_registered
    if _fonts_registered:
        return
    pdfmetrics.registerFont(
        TTFont("Vazir", str(FONTS_DIR / "Vazirmatn-Regular.ttf"))
    )
    pdfmetrics.registerFont(
        TTFont("Vazir-Bold", str(FONTS_DIR / "Vazirmatn-Bold.ttf"))
    )
    _fonts_registered = True


def prepare_persian(text: str) -> str:
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def to_persian_digits(number: int) -> str:
    formatted = f"{number:,}"
    persian = formatted.translate(PERSIAN_DIGIT_MAP)
    return persian + " تومان"


def _channel_label(channel: str) -> str:
    return CHANNEL_LABELS.get(channel, channel)


def _line_total(item) -> int:
    return item["list_price"] - item["discount_amount"]


def _resolve_output_dir(output_dir: str) -> Path:
    path = Path(output_dir)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _truncate_to_width(
    text: str,
    font: str,
    size: int,
    max_width: float,
) -> str:
    if pdfmetrics.stringWidth(text, font, size) <= max_width:
        return text
    ellipsis = "…"
    trimmed = text
    while trimmed and pdfmetrics.stringWidth(
        trimmed + ellipsis, font, size
    ) > max_width:
        trimmed = trimmed[:-1]
    return trimmed + ellipsis if trimmed else ellipsis


def _draw_persian_right(
    c: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    *,
    font: str = "Vazir",
    size: int = 11,
) -> None:
    c.setFont(font, size)
    c.drawRightString(x, y, prepare_persian(text))


def _draw_thank_you_line(
    c: canvas.Canvas,
    right: float,
    y: float,
    *,
    size: int = 11,
) -> None:
    """Draw the thank-you phrase in Vazir and a heart in Helvetica (separate fonts)."""
    persian = prepare_persian(THANK_YOU_TEXT)
    c.setFont("Vazir", size)
    c.drawRightString(right, y, persian)

    persian_width = pdfmetrics.stringWidth(persian, "Vazir", size)
    heart_x = right - persian_width - THANK_YOU_HEART_GAP
    c.setFont(THANK_YOU_HEART_FONT, size)
    c.setFillColor(THANK_YOU_HEART_COLOR)
    c.drawRightString(heart_x, y, THANK_YOU_HEART)
    c.setFillColor(colors.black)


def _draw_amount_right(
    c: canvas.Canvas,
    x: float,
    y: float,
    amount: int,
    *,
    font: str = "Vazir",
    size: int = 11,
) -> None:
    _draw_persian_right(c, x, y, to_persian_digits(amount), font=font, size=size)


def _draw_store_header(c: canvas.Canvas, right: float, y: float) -> float:
    logo_path = PROJECT_ROOT / LOGO_PATH
    if logo_path.is_file():
        img = ImageReader(str(logo_path))
        img_w, img_h = img.getSize()
        scale = LOGO_MAX_HEIGHT / img_h
        draw_w = img_w * scale
        draw_h = img_h * scale
        c.drawImage(
            img,
            right - draw_w,
            y - draw_h,
            width=draw_w,
            height=draw_h,
            mask="auto",
        )
        y -= draw_h + HEADER_LOGO_TO_NAME_GAP

    _draw_persian_right(c, right, y, STORE_NAME, font="Vazir-Bold", size=14)
    y -= HEADER_TEXT_GAP

    if STORE_ADDRESS:
        _draw_persian_right(c, right, y, STORE_ADDRESS)
        y -= HEADER_TEXT_GAP

    if STORE_PHONE:
        _draw_persian_right(c, right, y, STORE_PHONE)

    return y - HEADER_BOTTOM_GAP


def _draw_footer(c: canvas.Canvas, page_width: float) -> None:
    footer_path = PROJECT_ROOT / FOOTER_PATH
    if not footer_path.is_file():
        return

    usable_width = page_width - 2 * PAGE_MARGIN
    img = ImageReader(str(footer_path))
    img_w, img_h = img.getSize()
    scale = min(FOOTER_MAX_HEIGHT / img_h, usable_width / img_w)
    draw_w = img_w * scale
    draw_h = img_h * scale
    x = (page_width - draw_w) / 2
    y = PAGE_MARGIN + FOOTER_ABOVE_MARGIN
    c.drawImage(
        img,
        x,
        y,
        width=draw_w,
        height=draw_h,
        mask="auto",
    )


def _draw_table_header(c: canvas.Canvas, y: float) -> float:
    c.setFont("Vazir-Bold", 10)
    c.drawRightString(COL_PRODUCT, y, prepare_persian("نام محصول"))
    c.drawRightString(COL_QUANTITY, y, prepare_persian("تعداد"))
    c.drawRightString(COL_UNIT_PRICE, y, prepare_persian("قیمت واحد"))
    c.drawRightString(COL_LINE_TOTAL, y, prepare_persian("جمع"))
    y -= 6
    c.line(PAGE_MARGIN, y, COL_PRODUCT + 10, y)
    return y - TABLE_ROW_HEIGHT


def _draw_line_item(c: canvas.Canvas, item, y: float) -> float:
    c.setFont("Vazir", 10)
    product_name = _truncate_to_width(
        item["product_name"], "Vazir", 10, PRODUCT_NAME_MAX_WIDTH
    )
    c.drawRightString(COL_PRODUCT, y, prepare_persian(product_name))

    qty_text = prepare_persian(str(item["quantity"]))
    c.drawRightString(COL_QUANTITY, y, qty_text)

    _draw_amount_right(c, COL_UNIT_PRICE, y, item["unit_price"], size=10)
    _draw_amount_right(c, COL_LINE_TOTAL, y, _line_total(item), size=10)

    y -= TABLE_ROW_HEIGHT

    if item["discount_amount"] > 0:
        reason = item["discount_reason"] or ""
        discount_label = f"تخفیف: {to_persian_digits(item['discount_amount'])}"
        if reason:
            discount_label += f" ({reason})"
        _draw_persian_right(c, COL_PRODUCT, y, discount_label, size=9)
        y -= LINE_HEIGHT

    return y


def _draw_totals_section(
    c: canvas.Canvas,
    order,
    items: list,
    final_total: int,
    y: float,
) -> float:
    y -= LINE_HEIGHT
    c.line(PAGE_MARGIN, y, COL_PRODUCT + 10, y)
    y -= TABLE_ROW_HEIGHT

    subtotal = sum(_line_total(item) for item in items)
    _draw_persian_right(c, COL_PRODUCT, y, "جمع اقلام:", font="Vazir-Bold", size=10)
    _draw_amount_right(c, COL_PRODUCT - 80, y, subtotal, size=10)
    y -= TABLE_ROW_HEIGHT

    if order["shipping_charge"] > 0:
        _draw_persian_right(
            c, COL_PRODUCT, y, "هزینه ارسال:", font="Vazir-Bold", size=10
        )
        _draw_amount_right(
            c, COL_PRODUCT - 80, y, order["shipping_charge"], size=10
        )
        y -= TABLE_ROW_HEIGHT

    if order["postage_cost"] > 0:
        _draw_persian_right(
            c, COL_PRODUCT, y, "هزینه پست:", font="Vazir-Bold", size=10
        )
        _draw_amount_right(
            c, COL_PRODUCT - 80, y, order["postage_cost"], size=10
        )
        y -= TABLE_ROW_HEIGHT

    if order["transaction_fee"] > 0:
        _draw_persian_right(
            c, COL_PRODUCT, y, "کارمزد تراکنش (کسر):", font="Vazir-Bold", size=10
        )
        _draw_amount_right(
            c, COL_PRODUCT - 80, y, order["transaction_fee"], size=10
        )
        y -= TABLE_ROW_HEIGHT

    y -= 4
    _draw_persian_right(
        c, COL_PRODUCT, y, "مبلغ نهایی:", font="Vazir-Bold", size=13
    )
    _draw_amount_right(
        c, COL_PRODUCT - 80, y, final_total, font="Vazir-Bold", size=13
    )
    return y - LINE_HEIGHT * 2


def generate_invoice_pdf(
    conn: sqlite3.Connection,
    order_id: int,
    output_dir: str = "invoices",
) -> str:
    """Generate a Persian RTL invoice PDF for an order. Returns the file path."""
    _register_fonts()

    try:
        order_data = get_order(conn, order_id)
    except ValueError:
        raise ValueError(f"Order with id {order_id} does not exist")

    order = order_data["order"]
    items = order_data["items"]
    final_total = order_data["total"]

    out_dir = _resolve_output_dir(output_dir)
    invoice_number = order["invoice_number"]
    if invoice_number:
        filename = f"invoice_{invoice_number}.pdf"
    else:
        filename = f"invoice_order_{order_id}.pdf"
    filepath = out_dir / filename

    page_width, page_height = A4
    right = page_width - PAGE_MARGIN
    c = canvas.Canvas(str(filepath), pagesize=A4)

    y = page_height - PAGE_MARGIN
    y = _draw_store_header(c, right, y)

    invoice_num = invoice_number or "-"
    _draw_persian_right(
        c, right, y, f"شماره فاکتور: {invoice_num}", font="Vazir-Bold", size=11
    )
    y -= LINE_HEIGHT

    order_date = order["order_date"]
    if " " in order_date:
        order_date = order_date.split(" ")[0]
    _draw_persian_right(c, right, y, f"تاریخ: {order_date}")
    y -= LINE_HEIGHT * 1.5

    customer_name = order["customer_name"]
    if customer_name:
        _draw_persian_right(c, right, y, f"مشتری: {customer_name}")
        y -= LINE_HEIGHT

    channel = _channel_label(order["channel"])
    _draw_persian_right(c, right, y, f"کانال فروش: {channel}")
    y -= LINE_HEIGHT * 2

    y = _draw_table_header(c, y)
    for item in items:
        y = _draw_line_item(c, item, y)

    y = _draw_totals_section(c, order, items, final_total, y)

    _draw_thank_you_line(c, right, y)

    _draw_footer(c, page_width)

    c.save()
    return str(filepath)
