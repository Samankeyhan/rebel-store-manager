import pytest

from db.distributions import (
    get_partner_payout_history,
    get_partner_totals,
    get_profit_distribution,
    list_profit_distributions,
    record_profit_distribution,
)
from db.expenses import add_expense, add_expense_category
from db.orders import record_order
from db.partners import add_partner, deactivate_partner, update_partner_percentage
from db.products import add_product
from db.reports import get_profit_and_loss


@pytest.fixture
def distribution_setup(test_db):
    product_id = add_product(test_db, "Dist Vinyl", "VINYL", 3000, 2000)
    test_db.execute(
        "UPDATE products SET current_stock = 100, unit_cost = 500 WHERE id = ?",
        (product_id,),
    )
    test_db.commit()

    ads_id = add_expense_category(test_db, "Ads")
    add_expense(test_db, ads_id, 500, expense_date="2026-03-01")

    order_id = record_order(
        test_db,
        "INSTAGRAM",
        [{"product_id": product_id, "quantity": 2, "unit_price": 3000}],
        shipping_charge=100,
        postage_cost=50,
        transaction_fee=20,
    )
    test_db.execute(
        "UPDATE orders SET order_date = ? WHERE id = ?",
        ("2026-03-10 08:00:00", order_id),
    )
    test_db.commit()

    alice_id = add_partner(test_db, "Alice", 50.0)
    bob_id = add_partner(test_db, "Bob", 30.0)
    carol_id = add_partner(test_db, "Carol", 20.0)

    return {
        "product_id": product_id,
        "alice_id": alice_id,
        "bob_id": bob_id,
        "carol_id": carol_id,
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
    }


def test_record_profit_distribution_happy_path(distribution_setup, test_db):
    distribution_id = record_profit_distribution(
        test_db,
        distribution_setup["period_start"],
        distribution_setup["period_end"],
        1000,
        distribution_date="2026-04-01",
    )

    distribution = get_profit_distribution(test_db, distribution_id)
    assert distribution is not None
    assert distribution["total_amount_distributed"] == 1000
    assert len(distribution["shares"]) == 3

    shares_by_name = {s["partner_name"]: s for s in distribution["shares"]}
    assert shares_by_name["Alice"]["amount"] == 500
    assert shares_by_name["Alice"]["percentage_at_time"] == 50.0
    assert shares_by_name["Bob"]["amount"] == 300
    assert shares_by_name["Bob"]["percentage_at_time"] == 30.0
    assert shares_by_name["Carol"]["amount"] == 200
    assert shares_by_name["Carol"]["percentage_at_time"] == 20.0

    total_shares = sum(s["amount"] for s in distribution["shares"])
    assert total_shares == 1000


def test_rounding_reconciliation(test_db):
    p1 = add_partner(test_db, "Partner A", 33.33)
    p2 = add_partner(test_db, "Partner B", 33.33)
    p3 = add_partner(test_db, "Partner C", 33.34)

    distribution_id = record_profit_distribution(
        test_db,
        "2026-01-01",
        "2026-01-31",
        1000,
        distribution_date="2026-02-01",
    )

    distribution = get_profit_distribution(test_db, distribution_id)
    shares_by_id = {s["partner_id"]: s for s in distribution["shares"]}

    assert shares_by_id[p1]["amount"] == 333
    assert shares_by_id[p2]["amount"] == 333
    assert shares_by_id[p3]["amount"] == 334

    total_shares = sum(s["amount"] for s in distribution["shares"])
    assert total_shares == 1000


def test_percentage_sum_not_100_raises_and_rolls_back(test_db):
    add_partner(test_db, "Alice", 50.0)
    add_partner(test_db, "Bob", 30.0)

    with pytest.raises(ValueError, match="sum to 80.00%"):
        record_profit_distribution(
            test_db, "2026-01-01", "2026-01-31", 1000
        )

    assert test_db.execute("SELECT COUNT(*) FROM profit_distributions").fetchone()[0] == 0
    assert test_db.execute("SELECT COUNT(*) FROM distribution_shares").fetchone()[0] == 0

    add_partner(test_db, "Carol", 30.0)

    with pytest.raises(ValueError, match="sum to 110.00%"):
        record_profit_distribution(
            test_db, "2026-01-01", "2026-01-31", 1000
        )

    assert test_db.execute("SELECT COUNT(*) FROM profit_distributions").fetchone()[0] == 0
    assert test_db.execute("SELECT COUNT(*) FROM distribution_shares").fetchone()[0] == 0


def test_total_profit_available_from_pnl(distribution_setup, test_db):
    expected_pnl = get_profit_and_loss(
        test_db,
        distribution_setup["period_start"],
        distribution_setup["period_end"],
    )

    distribution_id = record_profit_distribution(
        test_db,
        distribution_setup["period_start"],
        distribution_setup["period_end"],
        1000,
        distribution_date="2026-04-01",
    )

    distribution = get_profit_distribution(test_db, distribution_id)
    assert distribution["total_profit_available"] == expected_pnl["net_profit"]
    assert distribution["total_profit_available"] == 4330


def test_distribute_less_than_profit_available(distribution_setup, test_db):
    distribution_id = record_profit_distribution(
        test_db,
        distribution_setup["period_start"],
        distribution_setup["period_end"],
        3000,
        distribution_date="2026-04-01",
    )

    distribution = get_profit_distribution(test_db, distribution_id)
    assert distribution["total_profit_available"] > distribution["total_amount_distributed"]
    assert distribution["total_amount_distributed"] == 3000

    total_shares = sum(s["amount"] for s in distribution["shares"])
    assert total_shares == 3000


def test_get_partner_payout_history(distribution_setup, test_db):
    record_profit_distribution(
        test_db,
        distribution_setup["period_start"],
        distribution_setup["period_end"],
        1000,
        distribution_date="2026-04-01",
    )
    record_profit_distribution(
        test_db,
        "2026-04-01",
        "2026-04-30",
        2000,
        distribution_date="2026-05-01",
    )

    alice_history = get_partner_payout_history(
        test_db, distribution_setup["alice_id"]
    )
    assert len(alice_history) == 2
    assert alice_history[0]["amount"] == 1000
    assert alice_history[1]["amount"] == 500

    bob_history = get_partner_payout_history(
        test_db, distribution_setup["bob_id"]
    )
    assert len(bob_history) == 2
    assert bob_history[0]["amount"] == 600
    assert bob_history[1]["amount"] == 300


def test_get_partner_totals(distribution_setup, test_db):
    record_profit_distribution(
        test_db,
        distribution_setup["period_start"],
        distribution_setup["period_end"],
        1000,
        distribution_date="2026-04-01",
    )
    record_profit_distribution(
        test_db,
        "2026-04-01",
        "2026-04-30",
        2000,
        distribution_date="2026-05-01",
    )

    totals = get_partner_totals(test_db)
    totals_by_name = {row["partner_name"]: row for row in totals}

    assert totals_by_name["Alice"]["total_received"] == 1500
    assert totals_by_name["Alice"]["distribution_count"] == 2
    assert totals_by_name["Bob"]["total_received"] == 900
    assert totals_by_name["Carol"]["total_received"] == 600

    filtered = get_partner_totals(test_db, start_date="2026-05-01")
    assert len(filtered) == 3
    filtered_by_name = {row["partner_name"]: row for row in filtered}
    assert filtered_by_name["Alice"]["total_received"] == 1000
    assert filtered_by_name["Bob"]["total_received"] == 600
    assert filtered_by_name["Carol"]["total_received"] == 400


def test_list_profit_distributions_date_filtering(distribution_setup, test_db):
    record_profit_distribution(
        test_db,
        distribution_setup["period_start"],
        distribution_setup["period_end"],
        1000,
        distribution_date="2026-04-01",
    )
    record_profit_distribution(
        test_db,
        "2026-04-01",
        "2026-04-30",
        2000,
        distribution_date="2026-05-01",
    )

    all_distributions = list_profit_distributions(test_db)
    assert len(all_distributions) == 2
    assert all_distributions[0]["distribution_date"] == "2026-04-30 20:30:00"
    assert all_distributions[1]["distribution_date"] == "2026-03-31 20:30:00"

    april_only = list_profit_distributions(
        test_db, start_date="2026-04-01", end_date="2026-04-30"
    )
    assert len(april_only) == 1
    assert april_only[0]["distribution_date"] == "2026-03-31 20:30:00"


def test_deactivated_partner_excluded_from_later_distribution(
    distribution_setup, test_db
):
    first_id = record_profit_distribution(
        test_db,
        distribution_setup["period_start"],
        distribution_setup["period_end"],
        1000,
        distribution_date="2026-04-01",
    )

    first = get_profit_distribution(test_db, first_id)
    assert len(first["shares"]) == 3

    deactivate_partner(test_db, distribution_setup["carol_id"])
    update_partner_percentage(test_db, distribution_setup["alice_id"], 62.5)
    update_partner_percentage(test_db, distribution_setup["bob_id"], 37.5)

    second_id = record_profit_distribution(
        test_db,
        "2026-04-01",
        "2026-04-30",
        800,
        distribution_date="2026-05-01",
    )

    second = get_profit_distribution(test_db, second_id)
    assert len(second["shares"]) == 2
    partner_names = {s["partner_name"] for s in second["shares"]}
    assert "Carol" not in partner_names

    first_again = get_profit_distribution(test_db, first_id)
    carol_share = next(
        s for s in first_again["shares"] if s["partner_name"] == "Carol"
    )
    assert carol_share["percentage_at_time"] == 20.0
    assert carol_share["amount"] == 200

    alice_second = next(
        s for s in second["shares"] if s["partner_name"] == "Alice"
    )
    assert alice_second["percentage_at_time"] == 62.5
