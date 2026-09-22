import sqlite3

from db.partners import list_partners
from db.reports import get_profit_and_loss

PERCENTAGE_SUM_TOLERANCE = 0.01


def _validate_non_negative(amount: int, field_name: str) -> None:
    if amount < 0:
        raise ValueError(f"{field_name} must be >= 0, got {amount}")


def _validate_percentage_sum(partners: list[dict]) -> None:
    total = sum(partner["current_percentage"] for partner in partners)
    if abs(total - 100) > PERCENTAGE_SUM_TOLERANCE:
        breakdown = ", ".join(
            f"{partner['name']}: {partner['current_percentage']}%"
            for partner in partners
        )
        raise ValueError(
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


def record_profit_distribution(
    conn: sqlite3.Connection,
    period_start: str,
    period_end: str,
    total_amount_distributed: int,
    distribution_date: str | None = None,
    notes: str | None = None,
) -> int:
    _validate_non_negative(total_amount_distributed, "total_amount_distributed")

    conn.execute("BEGIN")
    try:
        active_partners = list_partners(conn, active_only=True)
        if not active_partners:
            raise ValueError("No active partners found — add partners before distributing")

        _validate_percentage_sum(active_partners)

        pnl = get_profit_and_loss(conn, period_start, period_end)
        total_profit_available = pnl["net_profit"]

        share_amounts = _compute_share_amounts(
            active_partners, total_amount_distributed
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

        conn.commit()
        return distribution_id
    except Exception:
        conn.rollback()
        raise


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
    query: str,
    params: list,
    start_date: str | None,
    end_date: str | None,
) -> tuple[str, list]:
    if start_date is not None:
        query += " AND profit_distributions.distribution_date >= ?"
        params.append(start_date)
    if end_date is not None:
        query += " AND profit_distributions.distribution_date <= ?"
        params.append(end_date)
    return query, params


def list_profit_distributions(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM profit_distributions WHERE 1=1"
    params: list = []
    query, params = _append_distribution_date_filters(
        query, params, start_date, end_date
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
        query, params, start_date, end_date
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
        query, params, start_date, end_date
    )
    query += """
        GROUP BY partners.id, partners.name
        ORDER BY total_received DESC
    """

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
