"""preview_profit_distribution: same shares and errors as recording, no writes."""

import pytest

from db.distributions import (
    get_profit_distribution,
    preview_profit_distribution,
    record_profit_distribution,
)
from db.errors import ConflictError, ValidationError
from db.partners import add_partner, deactivate_partner

PERIOD = ("2026-03-01", "2026-03-31")


def _add_partners(conn, percentages):
    names = ["Alice", "Bob", "Carol", "Dave"]
    return [add_partner(conn, names[i], pct) for i, pct in enumerate(percentages)]


def _share_key(shares):
    return sorted(
        (s["partner_id"], s["percentage_at_time"], s["amount"]) for s in shares
    )


def _row_counts(conn):
    return (
        conn.execute("SELECT COUNT(*) FROM profit_distributions").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM distribution_shares").fetchone()[0],
    )


@pytest.mark.parametrize(
    "percentages, amount",
    [
        ([33.33, 33.33, 33.34], 1_000_000),
        ([33.33, 33.33, 33.34], 2),  # fewer Rial than partners
        ([33.33, 33.33, 33.34], 1_000_001),  # odd amount
        ([45.0, 45.0, 10.0], 1),  # leftover on a tie for the highest percentage
        ([50.0, 50.0], 1),  # 0.5 rounds half-even to 0, leftover 1
        ([60.0, 40.0], 12_345),
    ],
)
def test_preview_shares_equal_recorded_shares(test_db, percentages, amount):
    _add_partners(test_db, percentages)

    preview = preview_profit_distribution(test_db, *PERIOD, amount)
    distribution_id = record_profit_distribution(
        test_db, *PERIOD, amount, allow_exceeding=True
    )
    recorded = get_profit_distribution(test_db, distribution_id)

    assert _share_key(preview["shares"]) == _share_key(recorded["shares"])
    assert sum(s["amount"] for s in preview["shares"]) == amount
    assert preview["total_profit_available"] == recorded["total_profit_available"]
    assert {s["partner_id"]: s["partner_name"] for s in preview["shares"]} == {
        s["partner_id"]: s["partner_name"] for s in recorded["shares"]
    }


def test_negative_leftover_goes_to_highest_percentage(test_db):
    # 2 × 33.33% and 2 × 33.34% all round up to 1 (sum 3), so the
    # highest-percentage partner gives one back and ends at 0.
    alice, bob, carol = _add_partners(test_db, [33.33, 33.33, 33.34])

    shares = preview_profit_distribution(test_db, *PERIOD, 2)["shares"]

    assert {s["partner_id"]: s["amount"] for s in shares} == {alice: 1, bob: 1, carol: 0}


def test_tie_on_highest_percentage_gives_leftover_to_lowest_id(test_db):
    alice, bob, carol = _add_partners(test_db, [45.0, 45.0, 10.0])

    shares = preview_profit_distribution(test_db, *PERIOD, 1)["shares"]

    assert {s["partner_id"]: s["amount"] for s in shares} == {alice: 1, bob: 0, carol: 0}


def test_preview_writes_nothing(test_db):
    _add_partners(test_db, [60.0, 40.0])
    record_profit_distribution(test_db, "2026-02-01", "2026-02-28", 0)
    before_counts = _row_counts(test_db)
    before_changes = test_db.total_changes

    preview_profit_distribution(
        test_db, *PERIOD, 5_000, distribution_date="2026-04-01"
    )

    assert _row_counts(test_db) == before_counts
    assert test_db.total_changes == before_changes
    assert not test_db.in_transaction


def test_over_cap_is_a_flag_not_an_error(test_db):
    _add_partners(test_db, [60.0, 40.0])

    over = preview_profit_distribution(test_db, *PERIOD, 1_000)
    assert over["exceeds_undistributed"] is True
    assert over["undistributed_profit"] == 0
    assert over["total_profit_available"] == 0
    assert sorted(s["amount"] for s in over["shares"]) == [400, 600]

    within = preview_profit_distribution(test_db, *PERIOD, 0)
    assert within["exceeds_undistributed"] is False

    with pytest.raises(ValidationError) as exc_info:
        record_profit_distribution(test_db, *PERIOD, 1_000)
    assert exc_info.value.field == "total_amount_distributed"


def _same_error(conn, args, kwargs, error_type):
    with pytest.raises(error_type) as previewed:
        preview_profit_distribution(conn, *args, **kwargs)
    with pytest.raises(error_type) as recorded:
        record_profit_distribution(conn, *args, allow_exceeding=True, **kwargs)
    assert str(previewed.value) == str(recorded.value)
    assert getattr(previewed.value, "field", None) == getattr(
        recorded.value, "field", None
    )


def test_no_active_partners_is_the_same_error(test_db):
    (alice,) = _add_partners(test_db, [100.0])
    deactivate_partner(test_db, alice)
    _same_error(test_db, (*PERIOD, 100), {}, ValidationError)


def test_percentages_not_summing_to_100_is_the_same_error(test_db):
    _add_partners(test_db, [60.0, 30.0])
    _same_error(test_db, (*PERIOD, 100), {}, ValidationError)


@pytest.mark.parametrize(
    "args, kwargs",
    [
        (("2026-03-31", "2026-03-01", 100), {}),
        (("2026-02-30", "2026-03-01", 100), {}),
        ((*PERIOD, -1), {}),
        ((*PERIOD, 100), {"distribution_date": "not-a-date"}),
    ],
)
def test_bad_input_is_the_same_error(test_db, args, kwargs):
    _add_partners(test_db, [60.0, 40.0])
    _same_error(test_db, args, kwargs, ValidationError)


def test_overlap_is_the_same_conflict(test_db):
    _add_partners(test_db, [60.0, 40.0])
    record_profit_distribution(test_db, *PERIOD, 0)
    _same_error(test_db, ("2026-03-15", "2026-04-15", 0), {}, ConflictError)
