"""Stocktake: a physical count turned into stock corrections, all or nothing (docs/accounting-rules.md section 19).
`plan_stocktake` (read-only) validates every counted item, compares the count with the system stock and values each difference; `apply_stocktake` applies the plan in ONE transaction by calling `record_stock_adjustment` (reason ADJUSTMENT) for every differing item, so movements, the weighted-average blend (section 2) and the audit log are the existing ones. Any invalid item undoes everything.
Quantities are compared as exact decimals (`exact_quantity`) rounded half-even to 1e-9, never as floats; a difference of 0 after that rounding is "no change". A gain on an item with no unit cost needs one in the request (PRODUCT_NO_UNIT_COST). Each movement's note is «شمارش موجودی <Jalali date>» (+ the caller's note); one op_id and the operation `apply_stocktake` tie a count's audit rows together."""

import sqlite3
from fractions import Fraction

from db import jalali
from db.adjustments import VALID_ITEM_TYPES, record_stock_adjustment
from db.audit import audited
from db.connection import transaction
from db.constants import MAX_QUANTITY
from db.costing import check_money, exact_quantity, round_half_even
from db.errors import ConflictError, ErrorCode, NotFoundError, ValidationError
from db.materials import get_material
from db.products import get_product
from db.timeutil import parse_calendar_date, today_local

MAX_ITEMS = 2000
MAX_NOTE_LENGTH = 200
NOTE_PREFIX = "شمارش موجودی"
_SCALE = 1_000_000_000  # quantities are compared to 1e-9
_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _round9(value: Fraction) -> Fraction:
    """Half-even to 1e-9: removes the binary-float noise REAL stock carries."""
    return Fraction(round(value * _SCALE), _SCALE)


def difference(counted, system) -> Fraction:
    """counted − system as an exact decimal rounded half-even to 1e-9."""
    return _round9(exact_quantity(counted) - exact_quantity(system))


def stocktake_note(day, extra: str | None = None) -> str:
    jy, jm, jd = jalali.to_jalali(day)
    text = f"{NOTE_PREFIX} {jy}/{jm:02d}/{jd:02d}".translate(_PERSIAN_DIGITS)
    return f"{text} — {extra}" if extra else text


def stocktake_after(conn: sqlite3.Connection, movement_id: int, items: set[tuple[str, int]]) -> sqlite3.Row | None:
    """Read-only: the first stocktake movement recorded after movement `movement_id` on one of `items` ({(item_type,
    item_id)}), or None. A stocktake movement is an ADJUSTMENT the audit log labels `apply_stocktake`, or one carrying the
    stocktake note. A void or a purchase cancel that would move such an item's stock again would count it twice."""
    if not items:
        return None
    rows = conn.execute(
        """
        SELECT stock_movements.id, item_type, item_id, movement_date
        FROM stock_movements
        WHERE reason = 'ADJUSTMENT' AND stock_movements.id > ?
          AND (notes LIKE ? || '%' OR EXISTS (
                SELECT 1 FROM audit_log
                WHERE audit_log.entity_type = 'stock_movements'
                  AND audit_log.entity_id = CAST(stock_movements.id AS TEXT)
                  AND audit_log.action = 'INSERT'
                  AND audit_log.operation = 'apply_stocktake'))
        ORDER BY stock_movements.id
        """,
        (movement_id, NOTE_PREFIX),
    ).fetchall()
    for row in rows:
        if (row["item_type"], row["item_id"]) in items:
            return row
    return None


def _field(index: int, name: str) -> str:
    return f"items.{index}.{name}"


def _resolve_date(conn: sqlite3.Connection, stocktake_date: str | None):
    today = today_local(conn)
    if stocktake_date is None:
        return today
    try:
        day = parse_calendar_date(stocktake_date)
    except ValidationError as exc:
        raise ValidationError(str(exc), field="stocktake_date") from None
    if day > today:
        raise ValidationError(
            f"stocktake_date {day.isoformat()} is in the future (today is {today.isoformat()})",
            field="stocktake_date",
            code=ErrorCode.DATE_IN_FUTURE,
            details={"today": today.isoformat()},
        )
    return day


def _plan(conn, items, stocktake_date, note):
    if not isinstance(items, (list, tuple)) or not 1 <= len(items) <= MAX_ITEMS:
        raise ValidationError(f"items must hold 1 to {MAX_ITEMS} entries", field="items")
    day = _resolve_date(conn, stocktake_date)
    extra = note.strip() if isinstance(note, str) and note.strip() else None
    if extra is not None and len(extra) > MAX_NOTE_LENGTH:
        raise ValidationError(f"note must be at most {MAX_NOTE_LENGTH} characters", field="note")
    text = stocktake_note(day, extra)

    seen: set[tuple] = set()
    stale: list[dict] = []
    corrections: list[dict] = []
    cost_args: list[int | None] = []
    unchanged = 0

    for index, entry in enumerate(items):
        item_type = entry["item_type"]
        item_id = entry["item_id"]
        if item_type not in VALID_ITEM_TYPES:
            raise ValidationError(
                f"Invalid item_type '{item_type}'. Must be one of: {', '.join(VALID_ITEM_TYPES)}",
                field=_field(index, "item_type"),
            )
        if (item_type, item_id) in seen:
            raise ValidationError(
                f"{item_type.lower()} {item_id} is counted twice", field=_field(index, "item_id")
            )
        seen.add((item_type, item_id))

        item = get_material(conn, item_id) if item_type == "MATERIAL" else get_product(conn, item_id)
        if item is None:
            raise NotFoundError(f"items.{index}: {item_type.lower()} with id {item_id} does not exist")
        if item_type == "MATERIAL" and item["type"] == "SERVICE":
            raise ValidationError(
                f"Material '{item['name']}' is a SERVICE and has no stock to count", field=_field(index, "item_id")
            )

        counted = entry["counted"]
        if isinstance(counted, bool) or not isinstance(counted, (int, float)) or counted != counted:
            raise ValidationError(f"counted must be a number, got {counted!r}", field=_field(index, "counted"))
        if counted < 0 or counted > MAX_QUANTITY:
            raise ValidationError(
                f"counted must be between 0 and {MAX_QUANTITY}, got {counted}",
                field=_field(index, "counted"),
                code=ErrorCode.QUANTITY_OUT_OF_RANGE,
                details={"min": 0 if counted < 0 else None, "max": None if counted < 0 else MAX_QUANTITY},
            )
        if item_type == "PRODUCT" and counted != int(counted):
            raise ValidationError(
                f"counted must be a whole number for products, got {counted}",
                field=_field(index, "counted"),
                code=ErrorCode.QUANTITY_NOT_WHOLE,
            )

        live = item["current_stock"]
        if difference(live, entry["system_quantity"]) != 0:
            stale.append({
                "item_type": item_type, "item_id": item_id, "item_name": item["name"],
                "expected": entry["system_quantity"], "actual": live,
            })
            continue

        change = difference(counted, live)
        if change == 0:
            unchanged += 1
            continue

        unit_cost = entry.get("unit_cost")
        if unit_cost is not None:
            check_money(unit_cost, _field(index, "unit_cost"))
            if unit_cost < 0:
                raise ValidationError(f"unit_cost must be >= 0, got {unit_cost}", field=_field(index, "unit_cost"))
            if change < 0:
                raise ValidationError(
                    "unit_cost is only for a gain (counted above the system quantity)", field=_field(index, "unit_cost")
                )
        cost_used = unit_cost if unit_cost is not None else item["unit_cost"]
        if change > 0 and cost_used is None:
            raise ValidationError(
                f"Product '{item['name']}' has no unit_cost: enter the cost of the units found",
                field=_field(index, "unit_cost"),
                code=ErrorCode.PRODUCT_NO_UNIT_COST,
                details={"product_id": item_id, "product_name": item["name"]},
            )

        # Counting everything away takes exactly what the system holds (no float residue below zero).
        quantity_change = -float(live) if counted == 0 else float(change)
        if item_type == "PRODUCT":
            quantity_change = int(quantity_change)
        corrections.append({
            "item_type": item_type,
            "item_id": item_id,
            "item_name": item["name"],
            "unit": item["unit"] if item_type == "MATERIAL" else "piece",
            "old_quantity": live,
            "new_quantity": counted,
            "difference": quantity_change,
            "unit_cost": cost_used,
            "value": round_half_even(exact_quantity(quantity_change) * cost_used) if cost_used is not None else None,
            "movement_id": None,
        })
        cost_args.append(unit_cost if change > 0 else None)

    if stale:
        raise ConflictError(
            f"{len(stale)} item(s) changed since the screen was loaded; reload and check them again",
            code=ErrorCode.STOCKTAKE_STALE,
            details={"items": stale},
        )

    values = [c["value"] for c in corrections if c["value"] is not None]
    result = {
        "stocktake_date": day.isoformat(),
        "note": text,
        "corrections": corrections,
        "unchanged_count": unchanged,
        "total_value": sum(values),
        "unvalued_count": len(corrections) - len(values),
    }
    return result, cost_args


def plan_stocktake(
    conn: sqlite3.Connection, items: list[dict], stocktake_date: str | None = None, note: str | None = None
) -> dict:
    """What `apply_stocktake` would do, without writing. Each item: item_type, item_id, counted, system_quantity
    (the stock the count was made against) and optionally unit_cost (a gain only)."""
    return _plan(conn, items, stocktake_date, note)[0]


@audited()
def apply_stocktake(
    conn: sqlite3.Connection, items: list[dict], stocktake_date: str | None = None, note: str | None = None
) -> dict:
    with transaction(conn):
        result, cost_args = _plan(conn, items, stocktake_date, note)
        for correction, cost in zip(result["corrections"], cost_args):
            correction["movement_id"] = record_stock_adjustment(
                conn,
                correction["item_type"],
                correction["item_id"],
                correction["difference"],
                "ADJUSTMENT",
                unit_cost=cost,
                notes=result["note"],
                movement_date=result["stocktake_date"],
                allow_inactive=True,
            )
    return result
