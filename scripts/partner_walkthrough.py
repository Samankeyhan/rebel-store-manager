"""Manual walkthrough script for partner profit distribution."""
import os
import tempfile
from pathlib import Path

from db.connection import get_connection, init_db
from db.distributions import (
    get_partner_payout_history,
    get_profit_distribution,
    record_profit_distribution,
)
from db.expenses import add_expense, add_expense_category
from db.orders import record_order
from db.partners import (
    add_partner,
    get_active_percentage_total,
    list_partners,
    update_partner_percentage,
)
from db.products import add_product
from db.reports import get_profit_and_loss

DB_PATH = Path(tempfile.gettempdir()) / "rebel_partner_walkthrough.db"
if DB_PATH.exists():
    os.unlink(DB_PATH)

init_db(str(DB_PATH))
conn = get_connection(str(DB_PATH))

print("=" * 60)
print("STEP 1: Add 3 partners (50/30/20)")
print("=" * 60)
p1 = add_partner(conn, "Alex", 50.0, phone="555-0001")
p2 = add_partner(conn, "Blake", 30.0, phone="555-0002")
p3 = add_partner(conn, "Casey", 20.0, phone="555-0003")
print(f"Added partners: Alex (50%), Blake (30%), Casey (20%)")
print(f"Active percentage total: {get_active_percentage_total(conn):.2f}%")

print("\n" + "=" * 60)
print("STEP 2: Set up order/expense test data and record distribution")
print("=" * 60)
product_id = add_product(conn, "Walkthrough Vinyl", "VINYL", 3000, 2000)
conn.execute(
    "UPDATE products SET current_stock = 100, unit_cost = 500 WHERE id = ?",
    (product_id,),
)
conn.commit()

ads_id = add_expense_category(conn, "Marketing")
add_expense(conn, ads_id, 500, expense_date="2026-03-01")

order_id = record_order(
    conn,
    "INSTAGRAM",
    [{"product_id": product_id, "quantity": 2, "unit_price": 3000}],
    shipping_charge=100,
    postage_cost=50,
    transaction_fee=20,
)
conn.execute(
    "UPDATE orders SET order_date = ? WHERE id = ?",
    ("2026-03-10", order_id),
)
conn.commit()

period_start = "2026-03-01"
period_end = "2026-03-31"
pnl = get_profit_and_loss(conn, period_start, period_end)
net_profit = pnl["net_profit"]
amount_to_distribute = 4000

print(f"Period: {period_start} to {period_end}")
print(f"Net profit (from get_profit_and_loss): {net_profit}")
print(f"Amount chosen to distribute: {amount_to_distribute}")

dist1_id = record_profit_distribution(
    conn,
    period_start,
    period_end,
    amount_to_distribute,
    distribution_date="2026-04-01",
)
dist1 = get_profit_distribution(conn, dist1_id)
print("\nDistribution #1 per-partner breakdown:")
for share in dist1["shares"]:
    print(
        f"  {share['partner_name']}: {share['percentage_at_time']}% -> "
        f"{share['amount']}"
    )
total1 = sum(s["amount"] for s in dist1["shares"])
print(f"Sum of shares: {total1} (distributed total: {amount_to_distribute})")

print("\n" + "=" * 60)
print("STEP 3: Change Blake's percentage, record second distribution")
print("=" * 60)
update_partner_percentage(conn, p2, 25.0)
update_partner_percentage(conn, p1, 55.0)
print("Updated: Alex 55%, Blake 25%, Casey 20%")

period2_start = "2026-04-01"
period2_end = "2026-04-30"
amount2 = 2000
dist2_id = record_profit_distribution(
    conn,
    period2_start,
    period2_end,
    amount2,
    distribution_date="2026-05-01",
)
dist2 = get_profit_distribution(conn, dist2_id)
dist1_check = get_profit_distribution(conn, dist1_id)

print("\nDistribution #1 stored percentages (should be unchanged):")
for share in dist1_check["shares"]:
    print(f"  {share['partner_name']}: {share['percentage_at_time']}%")

print("\nDistribution #2 per-partner breakdown (new percentages):")
for share in dist2["shares"]:
    print(
        f"  {share['partner_name']}: {share['percentage_at_time']}% -> "
        f"{share['amount']}"
    )
total2 = sum(s["amount"] for s in dist2["shares"])
print(f"Sum of shares: {total2} (distributed total: {amount2})")

print("\n" + "=" * 60)
print("STEP 4: Try distribution when percentages don't sum to 100")
print("=" * 60)
update_partner_percentage(conn, p3, 15.0)
total = get_active_percentage_total(conn)
print(f"Current active total: {total:.2f}%")
try:
    record_profit_distribution(conn, "2026-05-01", "2026-05-31", 1000)
except ValueError as exc:
    print(f"Rejected as expected: {exc}")

update_partner_percentage(conn, p3, 20.0)

print("\n" + "=" * 60)
print("STEP 5: Alex payout history")
print("=" * 60)
history = get_partner_payout_history(conn, p1)
running = 0
for row in history:
    running += row["amount"]
    print(
        f"  {row['distribution_date']} | period {row['period_start']} to "
        f"{row['period_end']} | {row['percentage_at_time']}% | {row['amount']}"
    )
print(f"Total received by Alex: {running}")

conn.close()
os.unlink(DB_PATH)
