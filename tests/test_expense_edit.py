"""Editing and deleting expenses and postage payments (db/expenses.py, db/postage.py, db/period_lock.py)."""

from datetime import date

import pytest

from db import postage
from db.audit import list_audit_log
from db.distributions import record_profit_distribution
from db.errors import ConflictError, ErrorCode, NotFoundError, ValidationError
from db.expenses import (
    add_expense,
    add_expense_category,
    deactivate_expense_category,
    delete_expense,
    get_expense,
    get_total_expenses,
    update_expense,
)
from db.partners import add_partner
from db.period_lock import latest_distribution

TODAY = date(2026, 10, 23)


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr("db.timeutil.today_local", lambda conn=None: TODAY)


@pytest.fixture
def category(test_db):
    return add_expense_category(test_db, "Ads")


def _expense(conn, category_id, day="2026-09-10", amount=1000, description="x"):
    return add_expense(conn, category_id, amount, description=description, expense_date=day)


def _distribute(conn, period_end, period_start="2026-01-01"):
    add_partner(conn, "Solo", 100.0)
    return record_profit_distribution(conn, period_start, period_end, 0, allow_exceeding=True)


def _closed(exc_info):
    assert exc_info.value.code == ErrorCode.PERIOD_ALREADY_DISTRIBUTED
    return exc_info.value.details


# ------------------------------------------------------------------ expenses: edit


def test_update_expense_changes_each_field(test_db, category):
    other = add_expense_category(test_db, "Rent")
    expense_id = _expense(test_db, category)

    update_expense(
        test_db, expense_id,
        expense_category_id=other, amount=2500, description="y", expense_date="2026-09-12",
    )

    row = get_expense(test_db, expense_id)
    assert (row["expense_category_id"], row["amount"], row["description"]) == (other, 2500, "y")
    assert row["category_name"] == "Rent"
    assert row["expense_date"] == "2026-09-11 20:30:00"  # local midnight of 2026-09-12 (UTC+3:30)


def test_update_expense_is_partial_and_can_clear_the_description(test_db, category):
    expense_id = _expense(test_db, category)
    update_expense(test_db, expense_id, description=None)
    row = get_expense(test_db, expense_id)
    assert row["description"] is None and row["amount"] == 1000


def test_update_expense_moves_the_totals(test_db, category):
    expense_id = _expense(test_db, category, day="2026-09-10", amount=1000)
    update_expense(test_db, expense_id, amount=4000)
    assert get_total_expenses(test_db, "2026-09-01", "2026-09-30") == 4000
    update_expense(test_db, expense_id, expense_date="2026-08-20")
    assert get_total_expenses(test_db, "2026-09-01", "2026-09-30") == 0
    assert get_total_expenses(test_db, "2026-08-01", "2026-08-31") == 4000


def test_update_expense_same_day_keeps_the_stored_time(test_db, category):
    expense_id = add_expense(test_db, category, 1000, expense_date="2026-09-10 15:45")
    before = get_expense(test_db, expense_id)["expense_date"]
    update_expense(test_db, expense_id, expense_date="2026-09-10", amount=1)
    assert get_expense(test_db, expense_id)["expense_date"] == before


def test_update_expense_unknown_id_and_unknown_field(test_db, category):
    with pytest.raises(NotFoundError):
        update_expense(test_db, 999, amount=1)
    expense_id = _expense(test_db, category)
    with pytest.raises(ValidationError) as exc_info:
        update_expense(test_db, expense_id, id=5)
    assert exc_info.value.field == "id"


def test_update_expense_category_must_exist_and_be_active(test_db, category):
    expense_id = _expense(test_db, category)
    inactive = add_expense_category(test_db, "Old")
    deactivate_expense_category(test_db, inactive)
    with pytest.raises(NotFoundError):
        update_expense(test_db, expense_id, expense_category_id=999)
    with pytest.raises(ValidationError) as exc_info:
        update_expense(test_db, expense_id, expense_category_id=inactive)
    assert exc_info.value.field == "expense_category_id"


def test_update_expense_validates_amount_and_nulls(test_db, category):
    expense_id = _expense(test_db, category)
    with pytest.raises(ValidationError) as exc_info:
        update_expense(test_db, expense_id, amount=-1)
    assert exc_info.value.field == "amount"
    with pytest.raises(ValidationError) as exc_info:
        update_expense(test_db, expense_id, amount=2**60)
    assert exc_info.value.code == ErrorCode.AMOUNT_TOO_LARGE
    with pytest.raises(ValidationError) as exc_info:
        update_expense(test_db, expense_id, expense_date=None)
    assert exc_info.value.field == "expense_date"
    update_expense(test_db, expense_id, amount=0)  # the API allows zero
    assert get_expense(test_db, expense_id)["amount"] == 0


def test_update_expense_future_day_is_refused(test_db, category):
    expense_id = _expense(test_db, category)
    update_expense(test_db, expense_id, expense_date="2026-10-23")  # today is fine
    with pytest.raises(ValidationError) as exc_info:
        update_expense(test_db, expense_id, expense_date="2026-10-24")
    assert exc_info.value.code == ErrorCode.DATE_IN_FUTURE
    assert exc_info.value.field == "expense_date"
    assert exc_info.value.details == {"today": "2026-10-23"}


def test_add_expense_future_day_is_refused(test_db, category):
    with pytest.raises(ValidationError) as exc_info:
        add_expense(test_db, category, 10, expense_date="2026-10-24")
    assert exc_info.value.code == ErrorCode.DATE_IN_FUTURE
    assert test_db.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 0


# ------------------------------------------------------------------ expenses: delete and audit


def test_delete_expense(test_db, category):
    expense_id = _expense(test_db, category)
    delete_expense(test_db, expense_id)
    assert get_expense(test_db, expense_id) is None
    with pytest.raises(NotFoundError):
        delete_expense(test_db, expense_id)


def test_update_and_delete_are_audited_as_one_operation_each(test_db, category):
    expense_id = _expense(test_db, category, amount=1000)
    update_expense(test_db, expense_id, amount=2000, description="z")
    delete_expense(test_db, expense_id)

    entries = list_audit_log(test_db, entity_type="expenses", entity_id=expense_id)["items"]
    delete_entry, update_entry, _insert = entries
    assert update_entry["operation"] == "update_expense"
    assert update_entry["before"] == {"amount": 1000, "description": "x"}
    assert update_entry["after"] == {"amount": 2000, "description": "z"}
    assert delete_entry["operation"] == "delete_expense" and delete_entry["action"] == "DELETE"
    assert delete_entry["before"]["amount"] == 2000
    assert len({delete_entry["op_id"], update_entry["op_id"]}) == 2


def test_a_refused_update_leaves_no_audit_row(test_db, category):
    expense_id = _expense(test_db, category)
    before = list_audit_log(test_db)["total"]
    with pytest.raises(ValidationError):
        update_expense(test_db, expense_id, amount=1, expense_date="2026-10-24")
    assert list_audit_log(test_db)["total"] == before
    assert get_expense(test_db, expense_id)["amount"] == 1000


# ------------------------------------------------------------------ closed days (expenses)


def test_no_distribution_means_nothing_is_closed(test_db, category):
    assert latest_distribution(test_db) is None
    expense_id = _expense(test_db, category, day="2020-01-01")
    update_expense(test_db, expense_id, amount=5)
    delete_expense(test_db, expense_id)


def test_closed_day_boundary_period_end_blocked_next_day_allowed(test_db, category):
    distribution_id = _distribute(test_db, "2026-09-30")
    on_end = _expense(test_db, category, day="2026-09-30")
    after = _expense(test_db, category, day="2026-10-01")

    with pytest.raises(ConflictError) as exc_info:
        update_expense(test_db, on_end, amount=1)
    assert _closed(exc_info) == {
        "distribution_id": distribution_id, "period_end": "2026-09-30", "date": "2026-09-30",
    }
    with pytest.raises(ConflictError):
        delete_expense(test_db, on_end)

    update_expense(test_db, after, amount=1)
    delete_expense(test_db, after)


def test_closed_day_blocks_the_new_day_too_and_reports_which_day_hit(test_db, category):
    _distribute(test_db, "2026-09-30")
    open_id = _expense(test_db, category, day="2026-10-05")
    closed_id = _expense(test_db, category, day="2026-09-10")

    with pytest.raises(ConflictError) as exc_info:  # moving into the closed range
        update_expense(test_db, open_id, expense_date="2026-09-29")
    assert _closed(exc_info)["date"] == "2026-09-29"
    with pytest.raises(ConflictError) as exc_info:  # moving out of it
        update_expense(test_db, closed_id, expense_date="2026-10-02")
    assert _closed(exc_info)["date"] == "2026-09-10"
    assert get_expense(test_db, closed_id)["amount"] == 1000


def test_closed_day_covers_gaps_before_the_latest_period_end(test_db, category):
    _distribute(test_db, "2026-03-31", period_start="2026-03-01")  # nothing recorded before March
    gap_id = _expense(test_db, category, day="2026-01-15")
    with pytest.raises(ConflictError):
        update_expense(test_db, gap_id, amount=1)


def test_the_latest_period_end_decides(test_db, category):
    add_partner(test_db, "Solo", 100.0)
    record_profit_distribution(test_db, "2026-06-01", "2026-06-30", 0, allow_exceeding=True)
    record_profit_distribution(test_db, "2026-08-01", "2026-08-31", 0, allow_exceeding=True)
    july = _expense(test_db, category, day="2026-07-10")  # between the two periods
    with pytest.raises(ConflictError) as exc_info:
        delete_expense(test_db, july)
    assert _closed(exc_info)["period_end"] == "2026-08-31"


def test_category_and_description_edits_are_allowed_on_a_closed_day(test_db, category):
    other = add_expense_category(test_db, "Rent")
    _distribute(test_db, "2026-09-30")
    expense_id = _expense(test_db, category, day="2026-09-10")
    update_expense(test_db, expense_id, expense_category_id=other, description="fixed")
    update_expense(test_db, expense_id, amount=1000, expense_date="2026-09-10")  # nothing actually changes
    row = get_expense(test_db, expense_id)
    assert (row["expense_category_id"], row["description"]) == (other, "fixed")


def test_recording_a_new_expense_on_a_closed_day_is_not_blocked(test_db, category):
    """Known difference (docs/accounting-rules.md section 11), to revisit with a reopen-payout feature."""
    _distribute(test_db, "2026-09-30")
    expense_id = _expense(test_db, category, day="2026-09-10")
    assert get_expense(test_db, expense_id) is not None
    batch_id = postage.record_postage_batch(test_db, 100, 1, paid_date="2026-09-10")
    assert postage.get_postage_batch(test_db, batch_id) is not None


# ------------------------------------------------------------------ postage


def _batch(conn, day="2026-09-10", total=900, count=3, notes="n"):
    return postage.record_postage_batch(conn, total, count, paid_date=day, notes=notes)


def test_update_postage_batch_changes_each_field(test_db):
    batch_id = _batch(test_db)
    postage.update_postage_batch(
        test_db, batch_id, total_paid=1200, order_count=4, paid_date="2026-09-12", notes="m"
    )
    row = postage.get_postage_batch(test_db, batch_id)
    assert (row["total_paid"], row["order_count"], row["notes"]) == (1200, 4, "m")
    assert row["paid_date"] == "2026-09-11 20:30:00"


def test_update_postage_batch_partial_and_clear_notes(test_db):
    batch_id = _batch(test_db)
    postage.update_postage_batch(test_db, batch_id, notes=None)
    row = postage.get_postage_batch(test_db, batch_id)
    assert row["notes"] is None and row["total_paid"] == 900


def test_update_postage_batch_validation(test_db):
    batch_id = _batch(test_db)
    with pytest.raises(NotFoundError):
        postage.update_postage_batch(test_db, 999, notes="x")
    for kwargs, field in (({"order_count": 0}, "order_count"), ({"total_paid": -1}, "total_paid"),
                          ({"paid_date": None}, "paid_date"), ({"created_at": "x"}, "created_at")):
        with pytest.raises(ValidationError) as exc_info:
            postage.update_postage_batch(test_db, batch_id, **kwargs)
        assert exc_info.value.field == field
    with pytest.raises(ValidationError) as exc_info:
        postage.update_postage_batch(test_db, batch_id, total_paid=2**60)
    assert exc_info.value.code == ErrorCode.AMOUNT_TOO_LARGE


def test_update_postage_batch_future_day_is_refused(test_db):
    batch_id = _batch(test_db)
    with pytest.raises(ValidationError) as exc_info:
        postage.update_postage_batch(test_db, batch_id, paid_date="2026-10-24")
    assert (exc_info.value.code, exc_info.value.field) == (ErrorCode.DATE_IN_FUTURE, "paid_date")
    with pytest.raises(ValidationError) as exc_info:
        postage.record_postage_batch(test_db, 1, 1, paid_date="2026-10-24")
    assert exc_info.value.code == ErrorCode.DATE_IN_FUTURE


def test_postage_edit_and_delete_move_the_estimate(test_db):
    set_window = test_db.execute("UPDATE settings SET value = '3' WHERE key = 'postage_estimate_window'")
    assert set_window is not None
    first = _batch(test_db, day="2026-09-01", total=1000, count=10)
    second = _batch(test_db, day="2026-09-02", total=3000, count=10)
    assert postage.get_current_postage_estimate(test_db) == 200
    postage.update_postage_batch(test_db, second, total_paid=2000)
    assert postage.get_current_postage_estimate(test_db) == 150
    postage.delete_postage_batch(test_db, first)
    assert postage.get_current_postage_estimate(test_db) == 200
    postage.delete_postage_batch(test_db, second)
    assert postage.get_current_postage_estimate(test_db) == int(
        test_db.execute("SELECT value FROM settings WHERE key = 'default_postage_estimate'").fetchone()[0]
    )
    with pytest.raises(NotFoundError):
        postage.delete_postage_batch(test_db, second)


def test_postage_update_and_delete_are_audited(test_db):
    batch_id = _batch(test_db)
    postage.update_postage_batch(test_db, batch_id, total_paid=901)
    postage.delete_postage_batch(test_db, batch_id)
    delete_entry, update_entry, _insert = list_audit_log(
        test_db, entity_type="postage_batches", entity_id=batch_id
    )["items"]
    assert update_entry["operation"] == "update_postage_batch"
    assert update_entry["before"] == {"total_paid": 900} and update_entry["after"] == {"total_paid": 901}
    assert delete_entry["operation"] == "delete_postage_batch"
    assert delete_entry["before"]["total_paid"] == 901


def test_postage_closed_day_rules(test_db):
    distribution_id = _distribute(test_db, "2026-09-30")
    on_end = _batch(test_db, day="2026-09-30")
    after = _batch(test_db, day="2026-10-01")

    with pytest.raises(ConflictError) as exc_info:
        postage.update_postage_batch(test_db, on_end, total_paid=1)
    assert _closed(exc_info) == {
        "distribution_id": distribution_id, "period_end": "2026-09-30", "date": "2026-09-30",
    }
    with pytest.raises(ConflictError):
        postage.update_postage_batch(test_db, after, paid_date="2026-09-30")
    with pytest.raises(ConflictError):
        postage.delete_postage_batch(test_db, on_end)

    postage.update_postage_batch(test_db, on_end, order_count=5, notes="ok")  # estimate only, not the P&L
    postage.update_postage_batch(test_db, after, total_paid=1)
    postage.delete_postage_batch(test_db, after)
