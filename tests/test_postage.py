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
