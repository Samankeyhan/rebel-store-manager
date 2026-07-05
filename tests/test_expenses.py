import pytest

from db.expenses import (
    add_expense,
    add_expense_category,
    deactivate_expense_category,
    get_total_expenses,
    list_expense_categories,
    list_expenses,
)


def test_add_expense_category_happy_path(test_db):
    category_id = add_expense_category(test_db, "Ads")
    categories = list_expense_categories(test_db)
    assert len(categories) == 1
    assert categories[0]["id"] == category_id
    assert categories[0]["name"] == "Ads"
    assert categories[0]["is_active"] == 1


def test_duplicate_expense_category_raises_value_error(test_db):
    add_expense_category(test_db, "Tools")

    with pytest.raises(ValueError, match="Expense category 'Tools' already exists"):
        add_expense_category(test_db, "Tools")


def test_deactivate_expense_category(test_db):
    category_id = add_expense_category(test_db, "Rent")

    deactivate_expense_category(test_db, category_id)

    assert list_expense_categories(test_db) == []
    inactive = list_expense_categories(test_db, active_only=False)
    assert len(inactive) == 1
    assert inactive[0]["is_active"] == 0


def test_add_expense_happy_path(test_db):
    category_id = add_expense_category(test_db, "Ads")

    expense_id = add_expense(
        test_db,
        category_id,
        5000,
        description="Instagram campaign",
        expense_date="2026-01-15",
    )

    expenses = list_expenses(test_db)
    assert len(expenses) == 1
    assert expenses[0]["id"] == expense_id
    assert expenses[0]["category_name"] == "Ads"
    assert expenses[0]["amount"] == 5000
    assert expenses[0]["description"] == "Instagram campaign"
    assert expenses[0]["expense_date"] == "2026-01-15"


def test_add_expense_nonexistent_category_raises(test_db):
    with pytest.raises(ValueError, match="Expense category with id 9999 does not exist"):
        add_expense(test_db, 9999, 100)


def test_add_expense_negative_amount_raises(test_db):
    category_id = add_expense_category(test_db, "Misc")

    with pytest.raises(ValueError, match="amount must be >= 0"):
        add_expense(test_db, category_id, -1)


def test_list_expenses_filters(test_db):
    ads_id = add_expense_category(test_db, "Ads")
    tools_id = add_expense_category(test_db, "Tools")

    add_expense(test_db, ads_id, 100, expense_date="2026-01-10")
    add_expense(test_db, tools_id, 200, expense_date="2026-02-10")
    add_expense(test_db, ads_id, 300, expense_date="2026-03-10")

    ads_only = list_expenses(test_db, category_id=ads_id)
    assert len(ads_only) == 2
    assert all(e["category_name"] == "Ads" for e in ads_only)

    feb_only = list_expenses(test_db, start_date="2026-02-01", end_date="2026-02-28")
    assert len(feb_only) == 1
    assert feb_only[0]["amount"] == 200

    q1 = list_expenses(test_db, start_date="2026-01-01", end_date="2026-03-31")
    assert len(q1) == 3


def test_get_total_expenses(test_db):
    ads_id = add_expense_category(test_db, "Ads")
    tools_id = add_expense_category(test_db, "Tools")

    add_expense(test_db, ads_id, 100, expense_date="2026-01-10")
    add_expense(test_db, tools_id, 250, expense_date="2026-02-10")
    add_expense(test_db, ads_id, 150, expense_date="2026-03-10")

    assert get_total_expenses(test_db) == 500
    assert get_total_expenses(test_db, start_date="2026-02-01", end_date="2026-03-31") == 400
    assert get_total_expenses(test_db, start_date="2099-01-01") == 0
