import pytest

from db import postage
from db.errors import ValidationError
from db.settings import set_setting


def test_record_and_list_postage_batches(test_db):
    batch_id = postage.record_postage_batch(
        test_db, total_paid=1_000_000, order_count=10, notes="Jan"
    )

    batches = postage.list_postage_batches(test_db)
    assert len(batches) == 1
    assert batches[0]["id"] == batch_id
    assert batches[0]["total_paid"] == 1_000_000
    assert batches[0]["order_count"] == 10
    assert batches[0]["notes"] == "Jan"


def test_record_postage_batch_validates_total_paid(test_db):
    with pytest.raises(ValidationError):
        postage.record_postage_batch(test_db, total_paid=-1, order_count=1)


def test_record_postage_batch_validates_order_count(test_db):
    with pytest.raises(ValidationError):
        postage.record_postage_batch(test_db, total_paid=1000, order_count=0)


def test_estimate_with_no_batches_uses_default_setting(test_db):
    set_setting(test_db, "default_postage_estimate", 12345)

    assert postage.get_current_postage_estimate(test_db) == 12345


def test_estimate_uses_most_recent_batches_within_window(test_db):
    postage.record_postage_batch(
        test_db, total_paid=10_000_000, order_count=40, paid_date="2026-01-01"
    )
    postage.record_postage_batch(
        test_db, total_paid=600_000, order_count=2, paid_date="2026-01-02"
    )
    postage.record_postage_batch(
        test_db, total_paid=900_000, order_count=3, paid_date="2026-01-03"
    )

    # postage_estimate_window = 3 (seeded default): sum = 11,500,000 / 45
    # = 255,555.55... -> 255,556
    assert postage.get_current_postage_estimate(test_db) == 255_556

    postage.record_postage_batch(
        test_db, total_paid=2_000_000, order_count=10, paid_date="2026-01-04"
    )

    # Oldest batch (10,000,000/40) drops out of the 3-batch window:
    # sum = 3,500,000 / 15 = 233,333.33... -> 233,333
    assert postage.get_current_postage_estimate(test_db) == 233_333


def test_get_postage_batch(test_db):
    batch_id = postage.record_postage_batch(
        test_db, total_paid=500_000, order_count=4, paid_date="2026-01-15", notes="Feb"
    )

    batch = postage.get_postage_batch(test_db, batch_id)
    assert batch["id"] == batch_id
    assert batch["total_paid"] == 500_000
    assert batch["order_count"] == 4
    assert batch["paid_date"] == "2026-01-14 20:30:00"
    assert batch["notes"] == "Feb"

    assert postage.get_postage_batch(test_db, 999) is None


@pytest.mark.parametrize("total_paid, order_count, expected", [
    (5, 2, 2),      # 2.5 -> 2, the even neighbour
    (7, 2, 4),      # 3.5 -> 4
    (1_000, 3, 333),
])
def test_estimate_ties_go_to_the_even_neighbour(test_db, total_paid, order_count, expected):
    postage.record_postage_batch(test_db, total_paid=total_paid, order_count=order_count)
    assert postage.get_current_postage_estimate(test_db) == expected


def test_estimate_is_exact_above_float_precision(test_db):
    # 2^53 + 1 = 9,007,199,254,740,993: a float quotient lands on ...994, the exact one is ...993.
    # Only differs above 2^53 Rial; a cleanup, not a real-world bug.
    postage.record_postage_batch(test_db, total_paid=3 * 9_007_199_254_740_993 + 1, order_count=3)
    assert postage.get_current_postage_estimate(test_db) == 9_007_199_254_740_993


def test_estimate_sums_the_window_before_dividing(test_db):
    postage.record_postage_batch(test_db, total_paid=3, order_count=2, paid_date="2026-01-01")
    postage.record_postage_batch(test_db, total_paid=2, order_count=2, paid_date="2026-01-02")
    # (3 + 2) / (2 + 2) = 1.25 -> 1 (not the mean of 1.5 and 1)
    assert postage.get_current_postage_estimate(test_db) == 1
