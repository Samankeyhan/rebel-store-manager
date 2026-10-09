"""Profit payouts to partners, split by ownership percentage at distribution time and snapshotted per share so later changes don't rewrite history.
May read `get_profit_and_loss` as a reference; never writes `orders`, `order_items` or `expenses`.
`_compute_share_amounts` is the pattern for integer rounding with leftover reconciliation.
`preview_profit_distribution` shares `_validate_distribution_request` and `_plan_distribution` with `record_profit_distribution`, so a preview is exactly what recording would store; it never writes."""

import sqlite3

from db.connection import transaction
from db.errors import ConflictError, ValidationError
from db.partners import list_partners
from db.reports import get_profit_and_loss
from db.timeutil import normalize_record_date, to_utc_range, validate_calendar_date

PERCENTAGE_SUM_TOLERANCE = 0.01


def _validate_non_negative(amount: int, field_name: str) -> None:
    if amount < 0:
        raise ValidationError(f"{field_name} must be >= 0, got {amount}", field=field_name)


def _validate_percentage_sum(partners: list[dict]) -> None:
    total = sum(partner["current_percentage"] for partner in partners)
    if abs(total - 100) > PERCENTAGE_SUM_TOLERANCE:
        breakdown = ", ".join(
            f"{partner['name']}: {partner['current_percentage']}%"
            for partner in partners
        )
        raise ValidationError(
            f"Active partner percentages must sum to 100% (tolerance "
            f"{PERCENTAGE_SUM_TOLERANCE}), but they sum to {total:.2f}%. "
            f"Current split: {breakdown}"
        )


def _compute_share_amounts(
    partners: list[dict], total_amount_distributed: int
) -> list[dict]:
    rounded_amounts: list[dict] = []
    for partner in partners:
        raw_amount = total_amount_distributed * (partner["current_percentage"] / 100)
        rounded_amounts.append(
            {
                "partner_id": partner["id"],
                "percentage_at_time": partner["current_percentage"],
                "amount": round(raw_amount),
            }
        )

    total_rounded = sum(share["amount"] for share in rounded_amounts)
    leftover = total_amount_distributed - total_rounded

    if leftover != 0:
        recipient = min(
            rounded_amounts,
            key=lambda share: (
                -share["percentage_at_time"],
                share["partner_id"],
            ),
        )
        recipient["amount"] += leftover

    return rounded_amounts


def get_undistributed_profit(conn: sqlite3.Connection, as_of_date: str) -> int:
    """Section 11: all-time net_profit through *as_of_date* minus whatever has
    already been distributed for periods ending on or before it.
    """
    as_of_date = validate_calendar_date(as_of_date)

    net_profit = get_profit_and_loss(conn, None, as_of_date)["net_profit"]

    row = conn.execute(
        """
        SELECT COALESCE(SUM(total_amount_distributed), 0) AS total
        FROM profit_distributions
        WHERE period_end <= ?
        """,
        (as_of_date,),
    ).fetchone()

    return net_profit - row["total"]


def _validate_distribution_request(
    conn: sqlite3.Connection,
    period_start: str,
    period_end: str,
    total_amount_distributed: int,
    distribution_date: str | None,
) -> tuple[str, str, str | None]:
    """Input checks shared by record and preview; returns the normalized
    (period_start, period_end, distribution_date)."""
    _validate_non_negative(total_amount_distributed, "total_amount_distributed")
    period_start = validate_calendar_date(period_start)
    period_end = validate_calendar_date(period_end)
    if period_end < period_start:
        raise ValidationError(
            f"period_end ({period_end}) cannot be before period_start ({period_start})",
            field="period_end",
        )
    if distribution_date is not None:
        distribution_date = normalize_record_date(distribution_date, conn)
    return period_start, period_end, distribution_date


def _plan_distribution(
    conn: sqlite3.Connection,
    period_start: str,
    period_end: str,
    total_amount_distributed: int,
) -> dict:
    """Read-only checks and figures shared by record and preview: period
    overlap (ConflictError), active partners summing to 100, the period's
    net_profit, the undistributed profit as of period_end and the shares."""
    overlap = conn.execute(
        """
        SELECT id, period_start, period_end
        FROM profit_distributions
        WHERE period_start <= ? AND period_end >= ?
        LIMIT 1
        """,
        (period_end, period_start),
    ).fetchone()
    if overlap is not None:
        raise ConflictError(
            f"Period {period_start}..{period_end} overlaps distribution "
            f"#{overlap['id']} ({overlap['period_start']}..{overlap['period_end']})"
        )

    active_partners = list_partners(conn, active_only=True)
    if not active_partners:
        raise ValidationError(
            "No active partners found — add partners before distributing"
        )

    _validate_percentage_sum(active_partners)

    pnl = get_profit_and_loss(conn, period_start, period_end)

    return {
        "active_partners": active_partners,
        "total_profit_available": pnl["net_profit"],
        "undistributed_profit": get_undistributed_profit(conn, period_end),
        "shares": _compute_share_amounts(active_partners, total_amount_distributed),
    }


def preview_profit_distribution(
    conn: sqlite3.Connection,
    period_start: str,
    period_end: str,
    total_amount_distributed: int,
    distribution_date: str | None = None,
) -> dict:
    """What record_profit_distribution would store for the same arguments,
    without writing. Raises the same errors, except that exceeding the
    undistributed profit is not an error here: it is reported as
    exceeds_undistributed (allow_exceeding has no role in a preview)."""
    period_start, period_end, _ = _validate_distribution_request(
        conn, period_start, period_end, total_amount_distributed, distribution_date
    )
    plan = _plan_distribution(conn, period_start, period_end, total_amount_distributed)
    names = {partner["id"]: partner["name"] for partner in plan["active_partners"]}

    return {
        "period_start": period_start,
        "period_end": period_end,
        "total_amount_distributed": total_amount_distributed,
        "total_profit_available": plan["total_profit_available"],
        "undistributed_profit": plan["undistributed_profit"],
        "exceeds_undistributed": total_amount_distributed > plan["undistributed_profit"],
        "shares": [
            {**share, "partner_name": names[share["partner_id"]]}
            for share in plan["shares"]
        ],
    }


def record_profit_distribution(
    conn: sqlite3.Connection,
    period_start: str,
    period_end: str,
    total_amount_distributed: int,
    distribution_date: str | None = None,
    notes: str | None = None,
    allow_exceeding: bool = False,
) -> int:
    period_start, period_end, distribution_date = _validate_distribution_request(
        conn, period_start, period_end, total_amount_distributed, distribution_date
    )

    with transaction(conn):
        plan = _plan_distribution(
            conn, period_start, period_end, total_amount_distributed
        )
        total_profit_available = plan["total_profit_available"]
        share_amounts = plan["shares"]

        if not allow_exceeding:
            undistributed = plan["undistributed_profit"]
            if total_amount_distributed > undistributed:
                raise ValidationError(
                    f"total_amount_distributed ({total_amount_distributed}) exceeds "
                    f"undistributed profit as of {period_end} ({undistributed}). "
                    f"Pass allow_exceeding=True to distribute anyway.",
                    field="total_amount_distributed",
                )

        if distribution_date is not None:
            cursor = conn.execute(
                """
                INSERT INTO profit_distributions
                    (distribution_date, period_start, period_end,
                     total_profit_available, total_amount_distributed, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    distribution_date,
                    period_start,
                    period_end,
                    total_profit_available,
                    total_amount_distributed,
                    notes,
                ),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO profit_distributions
                    (period_start, period_end, total_profit_available,
                     total_amount_distributed, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    period_start,
                    period_end,
                    total_profit_available,
                    total_amount_distributed,
                    notes,
                ),
            )
        distribution_id = cursor.lastrowid

        for share in share_amounts:
            conn.execute(
                """
                INSERT INTO distribution_shares
                    (distribution_id, partner_id, percentage_at_time, amount)
                VALUES (?, ?, ?, ?)
                """,
                (
                    distribution_id,
                    share["partner_id"],
                    share["percentage_at_time"],
                    share["amount"],
                ),
            )

    return distribution_id


def get_profit_distribution(
    conn: sqlite3.Connection, distribution_id: int
) -> dict | None:
    distribution = conn.execute(
        "SELECT * FROM profit_distributions WHERE id = ?",
        (distribution_id,),
    ).fetchone()
    if distribution is None:
        return None

    share_rows = conn.execute(
        """
        SELECT
            distribution_shares.*,
            partners.name AS partner_name
        FROM distribution_shares
        JOIN partners ON partners.id = distribution_shares.partner_id
        WHERE distribution_shares.distribution_id = ?
        ORDER BY partners.name
        """,
        (distribution_id,),
    ).fetchall()

    return {
        **dict(distribution),
        "shares": [dict(row) for row in share_rows],
    }


def _append_distribution_date_filters(
    conn: sqlite3.Connection,
    query: str,
    params: list,
    start_date: str | None,
    end_date: str | None,
) -> tuple[str, list]:
    start_utc, end_exclusive_utc = to_utc_range(start_date, end_date, conn)
    if start_utc is not None:
        query += " AND profit_distributions.distribution_date >= ?"
        params.append(start_utc)
    if end_exclusive_utc is not None:
        query += " AND profit_distributions.distribution_date < ?"
        params.append(end_exclusive_utc)
    return query, params


def list_profit_distributions(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM profit_distributions WHERE 1=1"
    params: list = []
    query, params = _append_distribution_date_filters(
        conn, query, params, start_date, end_date
    )
    query += " ORDER BY distribution_date DESC"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_partner_payout_history(
    conn: sqlite3.Connection,
    partner_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    query = """
        SELECT
            distribution_shares.percentage_at_time,
            distribution_shares.amount,
            profit_distributions.period_start,
            profit_distributions.period_end,
            profit_distributions.distribution_date
        FROM distribution_shares
        JOIN profit_distributions
            ON profit_distributions.id = distribution_shares.distribution_id
        WHERE distribution_shares.partner_id = ?
    """
    params: list = [partner_id]
    query, params = _append_distribution_date_filters(
        conn, query, params, start_date, end_date
    )
    query += " ORDER BY profit_distributions.distribution_date DESC"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_partner_totals(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    query = """
        SELECT
            partners.name AS partner_name,
            SUM(distribution_shares.amount) AS total_received,
            COUNT(distribution_shares.id) AS distribution_count
        FROM distribution_shares
        JOIN profit_distributions
            ON profit_distributions.id = distribution_shares.distribution_id
        JOIN partners ON partners.id = distribution_shares.partner_id
        WHERE 1=1
    """
    params: list = []
    query, params = _append_distribution_date_filters(
        conn, query, params, start_date, end_date
    )
    query += """
        GROUP BY partners.id, partners.name
        ORDER BY total_received DESC
    """

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
