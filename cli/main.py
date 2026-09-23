from db.connection import get_connection, init_db
from db.expenses import (
    add_expense,
    add_expense_category,
    deactivate_expense_category,
    get_total_expenses,
    list_expense_categories,
    list_expenses,
)
from db.materials import (
    VALID_TYPES,
    add_material,
    deactivate_material,
    get_low_stock_materials,
    get_material,
    list_materials,
)
from db.orders import (
    VALID_CHANNELS,
    get_order,
    get_revenue_summary,
    list_orders,
    record_order,
    update_order_status,
)
from db.products import (
    VALID_CATEGORIES,
    add_product,
    deactivate_product,
    get_product,
    list_products,
    update_product_prices,
)
from db.production import (
    get_production_batch,
    list_production_batches,
    run_production_batch,
)
from db.recipes import (
    add_recipe_item,
    calculate_recipe_cost,
    get_recipe,
    remove_recipe_item,
    update_recipe_item,
)
from db.returns import process_return
from db.reports import (
    get_channel_breakdown,
    get_expense_breakdown,
    get_low_stock_products,
    get_product_performance,
    get_profit_and_loss,
    get_shipping_summary,
    get_waste_report,
)
from db.purchases import (
    get_material_purchase,
    get_product_purchase,
    list_material_purchases,
    list_product_purchases,
    record_material_purchase,
    record_product_purchase,
)
from db.adjustments import (
    get_stock_movement,
    list_stock_adjustments,
    record_stock_adjustment,
)
from db.suppliers import add_supplier, get_supplier, list_suppliers, update_supplier
from db.partners import (
    add_partner,
    deactivate_partner,
    get_active_percentage_total,
    get_partner,
    list_partners,
    update_partner_percentage,
)
from db.distributions import (
    get_partner_payout_history,
    get_profit_distribution,
    get_undistributed_profit,
    list_profit_distributions,
    record_profit_distribution,
)
from pdf.invoice import generate_invoice_pdf


def _prompt_non_empty(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Value cannot be empty.")


def _prompt_int(prompt: str, min_value: int = 0) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
            if value < min_value:
                print(f"Must be >= {min_value}.")
                continue
            return value
        except ValueError:
            print("Please enter a valid integer.")


def _prompt_float(prompt: str, min_value: float = 0) -> float:
    while True:
        raw = input(prompt).strip()
        try:
            value = float(raw)
            if value < min_value:
                print(f"Must be >= {min_value}.")
                continue
            return value
        except ValueError:
            print("Please enter a valid number.")


def _prompt_category() -> str:
    print(f"Valid categories: {', '.join(VALID_CATEGORIES)}")
    while True:
        category = input("Category: ").strip().upper()
        if category in VALID_CATEGORIES:
            return category
        print(f"Invalid category. Choose one of: {', '.join(VALID_CATEGORIES)}")


def _prompt_material_type() -> str:
    print(f"Valid types: {', '.join(VALID_TYPES)}")
    while True:
        material_type = input("Type: ").strip().upper()
        if material_type in VALID_TYPES:
            return material_type
        print(f"Invalid type. Choose one of: {', '.join(VALID_TYPES)}")


def _handle_add_product(conn) -> None:
    while True:
        name = _prompt_non_empty("Product name: ")
        category = _prompt_category()
        retail_price = _prompt_int("Retail price (in smallest currency unit): ")
        wholesale_price = _prompt_int("Wholesale price (in smallest currency unit): ")
        made_to_order = input("Made to order? (y/n, default n): ").strip().lower() == "y"

        try:
            product_id = add_product(
                conn, name, category, retail_price, wholesale_price, made_to_order
            )
            print(f"Product added with id {product_id}.")
            return
        except ValueError as exc:
            print(f"Error: {exc}")
            print("Please try again.")


def _handle_list_products(conn) -> None:
    products = list_products(conn)
    if not products:
        print("No active products found.")
        return

    print(
        f"\n{'ID':<5} {'Name':<30} {'Category':<10} {'Retail':<8} {'Wholesale':<10} "
        f"{'Stock':<6} {'MTO':<4}"
    )
    print("-" * 80)
    for product in products:
        print(
            f"{product['id']:<5} {product['name']:<30} {product['category']:<10} "
            f"{product['retail_price']:<8} {product['wholesale_price']:<10} "
            f"{product['current_stock']:<6} {'yes' if product['made_to_order'] else 'no':<4}"
        )


def _prompt_initial_stock() -> float | None:
    while True:
        stock_input = input("Initial stock (default: 0): ").strip()
        if not stock_input:
            return None
        try:
            value = float(stock_input)
            if value < 0:
                print("Initial stock must be >= 0.")
                continue
            return value
        except ValueError:
            print("Please enter a valid number.")


def _handle_add_material(conn) -> None:
    while True:
        name = _prompt_non_empty("Material name: ")
        material_type = _prompt_material_type()
        unit_cost = _prompt_int("Unit cost (in smallest currency unit): ")
        unit = input("Unit (default: piece): ").strip() or "piece"

        initial_stock = None
        if material_type == "STOCK":
            initial_stock = _prompt_initial_stock()

        try:
            material_id = add_material(
                conn, name, material_type, unit_cost, unit=unit, initial_stock=initial_stock
            )
            print(f"Material added with id {material_id}.")
            return
        except ValueError as exc:
            print(f"Error: {exc}")
            print("Please try again.")


def _handle_list_materials(conn) -> None:
    materials = list_materials(conn)
    if not materials:
        print("No active materials found.")
        return

    print(f"\n{'ID':<5} {'Name':<30} {'Type':<8} {'Unit':<8} {'Stock':<8} {'Cost':<8}")
    print("-" * 75)
    for material in materials:
        stock = material["current_stock"]
        stock_display = "N/A" if stock is None else str(stock)
        print(
            f"{material['id']:<5} {material['name']:<30} {material['type']:<8} "
            f"{material['unit']:<8} {stock_display:<8} {material['unit_cost']:<8}"
        )


def _prompt_optional_int(prompt: str) -> int | None:
    while True:
        raw = input(prompt).strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            print("Please enter a valid integer, or press Enter to leave unchanged.")


def _handle_update_product_prices(conn) -> None:
    products = list_products(conn)
    if not products:
        print("No active products found.")
        return

    product_id = _prompt_choice_from_list(products, "product")
    if product_id is None:
        return

    product = next(p for p in products if p["id"] == product_id)
    print(
        f"\nCurrent prices for '{product['name']}': "
        f"retail {product['retail_price']}, wholesale {product['wholesale_price']}"
    )

    retail_price = _prompt_optional_int(
        "New retail price (blank to leave unchanged): "
    )
    wholesale_price = _prompt_optional_int(
        "New wholesale price (blank to leave unchanged): "
    )

    if retail_price is None and wholesale_price is None:
        print("No price changes provided.")
        return

    try:
        update_product_prices(
            conn,
            product_id,
            retail_price=retail_price,
            wholesale_price=wholesale_price,
        )
    except ValueError as exc:
        print(f"Error: {exc}")
        return

    updated = get_product(conn, product_id)
    print(f"\nUpdated prices for '{updated['name']}':")
    print(f"  Retail: {updated['retail_price']}")
    print(f"  Wholesale: {updated['wholesale_price']}")


def _handle_deactivate_product(conn) -> None:
    products = list_products(conn)
    if not products:
        print("No active products found.")
        return

    product_id = _prompt_choice_from_list(products, "product")
    if product_id is None:
        return

    product = next(p for p in products if p["id"] == product_id)
    confirm = input(
        f"\nConfirm deactivation of '{product['name']}'? (y/n): "
    ).strip().lower()
    if confirm != "y":
        print("Deactivation cancelled.")
        return

    deactivate_product(conn, product_id)
    print(f"Product '{product['name']}' deactivated.")


def _handle_deactivate_material(conn) -> None:
    materials = list_materials(conn)
    if not materials:
        print("No active materials found.")
        return

    material_id = _prompt_choice_from_list(materials, "material")
    if material_id is None:
        return

    material = next(m for m in materials if m["id"] == material_id)
    confirm = input(
        f"\nConfirm deactivation of '{material['name']}'? (y/n): "
    ).strip().lower()
    if confirm != "y":
        print("Deactivation cancelled.")
        return

    deactivate_material(conn, material_id)
    print(f"Material '{material['name']}' deactivated.")


def _prompt_choice_from_list(items: list, label: str) -> int | None:
    if not items:
        print(f"No {label} available.")
        return None

    for index, item in enumerate(items, start=1):
        print(f"  {index}. {item['name']}")

    while True:
        raw = input(f"\nSelect {label} (1-{len(items)}, or 0 to cancel): ").strip()
        try:
            choice = int(raw)
            if choice == 0:
                return None
            if 1 <= choice <= len(items):
                return items[choice - 1]["id"]
            print(f"Please enter a number between 0 and {len(items)}.")
        except ValueError:
            print("Please enter a valid number.")


def _prompt_positive_float(prompt: str) -> float:
    while True:
        raw = input(prompt).strip()
        try:
            value = float(raw)
            if value <= 0:
                print("Must be > 0.")
                continue
            return value
        except ValueError:
            print("Please enter a valid number.")


def _handle_add_or_update_recipe_item(conn) -> None:
    products = list_products(conn)
    product_id = _prompt_choice_from_list(products, "product")
    if product_id is None:
        return

    materials = list_materials(conn)
    material_id = _prompt_choice_from_list(materials, "material")
    if material_id is None:
        return

    quantity = _prompt_positive_float("Quantity needed: ")

    try:
        recipe_id = add_recipe_item(conn, product_id, material_id, quantity)
        print(f"Recipe item added with id {recipe_id}.")
    except ValueError as exc:
        if "already in the recipe" in str(exc):
            try:
                update_recipe_item(conn, product_id, material_id, quantity)
                print("Recipe item updated.")
            except ValueError as update_exc:
                print(f"Error: {update_exc}")
        else:
            print(f"Error: {exc}")


def _handle_view_recipe(conn) -> None:
    products = list_products(conn)
    product_id = _prompt_choice_from_list(products, "product")
    if product_id is None:
        return

    product = next(p for p in products if p["id"] == product_id)
    recipe = get_recipe(conn, product_id)

    if not recipe:
        print(f"\nNo recipe defined for '{product['name']}'.")
        return

    print(f"\nRecipe for: {product['name']}")
    print(f"{'Material':<30} {'Type':<8} {'Qty':<8} {'Unit':<8} {'Unit Cost':<10}")
    print("-" * 70)
    for item in recipe:
        print(
            f"{item['material_name']:<30} {item['material_type']:<8} "
            f"{item['quantity_needed']:<8} {item['material_unit']:<8} "
            f"{item['material_unit_cost']:<10}"
        )

    total_cost = calculate_recipe_cost(conn, product_id)
    print(f"\nEstimated total cost: {total_cost}")


def _handle_remove_recipe_item(conn) -> None:
    products = list_products(conn)
    product_id = _prompt_choice_from_list(products, "product")
    if product_id is None:
        return

    recipe = get_recipe(conn, product_id)
    if not recipe:
        print("This product has no recipe items to remove.")
        return

    print("\nRecipe items:")
    for index, item in enumerate(recipe, start=1):
        print(f"  {index}. {item['material_name']} (qty: {item['quantity_needed']})")

    while True:
        raw = input(
            f"\nSelect item to remove (1-{len(recipe)}, or 0 to cancel): "
        ).strip()
        try:
            choice = int(raw)
            if choice == 0:
                return
            if 1 <= choice <= len(recipe):
                material_id = recipe[choice - 1]["material_id"]
                break
            print(f"Please enter a number between 0 and {len(recipe)}.")
        except ValueError:
            print("Please enter a valid number.")

    try:
        remove_recipe_item(conn, product_id, material_id)
        print("Recipe item removed.")
    except ValueError as exc:
        print(f"Error: {exc}")


def manage_recipes(conn) -> None:
    while True:
        print("\n--- Manage Recipes ---")
        print("1. Add/update recipe item for a product")
        print("2. View recipe for a product")
        print("3. Remove a recipe item")
        print("4. Back to main menu")
        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            _handle_add_or_update_recipe_item(conn)
        elif choice == "2":
            _handle_view_recipe(conn)
        elif choice == "3":
            _handle_remove_recipe_item(conn)
        elif choice == "4":
            break
        else:
            print("Invalid option. Please enter 1-4.")


def _handle_run_production_batch(conn) -> None:
    products = list_products(conn)
    product_id = _prompt_choice_from_list(products, "product")
    if product_id is None:
        return

    product = next(p for p in products if p["id"] == product_id)
    recipe = get_recipe(conn, product_id)

    if not recipe:
        print(f"\nNo recipe defined for '{product['name']}'. Add one first.")
        return

    print(f"\nRecipe for: {product['name']}")
    print(f"{'Material':<30} {'Type':<8} {'Qty':<8} {'Unit Cost':<10}")
    print("-" * 60)
    for item in recipe:
        print(
            f"{item['material_name']:<30} {item['material_type']:<8} "
            f"{item['quantity_needed']:<8} {item['material_unit_cost']:<10}"
        )

    unit_cost = calculate_recipe_cost(conn, product_id)
    print(f"\nCost per unit: {unit_cost}")

    quantity = _prompt_int("Quantity to produce: ", min_value=1)

    try:
        batch_id = run_production_batch(conn, product_id, quantity)
    except ValueError as exc:
        print(f"\nError: {exc}")
        return

    batch_detail = get_production_batch(conn, batch_id)
    total_cost = batch_detail["batch"]["unit_cost"] * quantity
    updated_product = get_product(conn, product_id)

    print(f"\nProduction batch #{batch_id} completed successfully.")
    print(f"  Product: {product['name']}")
    print(f"  Quantity produced: {quantity}")
    print(f"  Total cost: {total_cost}")
    print(f"  New product stock: {updated_product['current_stock']}")
    print("\nMaterials consumed:")
    for item in batch_detail["materials"]:
        material = get_material(conn, item["material_id"])
        if item["material_type"] == "STOCK":
            remaining = material["current_stock"]
            print(
                f"  {item['material_name']}: used {item['quantity_used']}, "
                f"remaining {remaining}"
            )
        else:
            print(
                f"  {item['material_name']}: used {item['quantity_used']} "
                f"(service, no stock tracked)"
            )


def _handle_view_production_history(conn) -> None:
    batches = list_production_batches(conn)
    if not batches:
        print("\nNo production batches found.")
        return

    print(f"\n{'ID':<5} {'Product':<30} {'Qty':<6} {'Unit Cost':<10} {'Date':<20}")
    print("-" * 75)
    for batch in batches:
        print(
            f"{batch['id']:<5} {batch['product_name']:<30} "
            f"{batch['quantity_produced']:<6} {batch['unit_cost']:<10} "
            f"{batch['production_date']:<20}"
        )


def _prompt_channel() -> str | None:
    print("\nSales channels:")
    for index, channel in enumerate(VALID_CHANNELS, start=1):
        print(f"  {index}. {channel}")

    while True:
        raw = input(f"\nSelect channel (1-{len(VALID_CHANNELS)}, or 0 to cancel): ").strip()
        try:
            choice = int(raw)
            if choice == 0:
                return None
            if 1 <= choice <= len(VALID_CHANNELS):
                return VALID_CHANNELS[choice - 1]
            print(f"Please enter a number between 0 and {len(VALID_CHANNELS)}.")
        except ValueError:
            print("Please enter a valid number.")


def _default_unit_price(product, channel: str) -> int:
    if channel == "WHOLESALE":
        return product["wholesale_price"]
    return product["retail_price"]


def _prompt_order_status() -> str:
    print("\nOrder status:")
    print("  1. Draft")
    print("  2. Pending")
    print("  3. Paid")
    print("  4. Completed")
    while True:
        choice = input("Select status (1-4, default 4): ").strip()
        if choice == "" or choice == "4":
            return "COMPLETED"
        if choice == "1":
            return "DRAFT"
        if choice == "2":
            return "PENDING"
        if choice == "3":
            return "PAID"
        print("Please enter 1-4, or press Enter for Completed.")


def _preview_cart_totals(
    conn, cart: list[dict], shipping_charge: int | None, postage_cost: int | None, transaction_fee: int
) -> tuple[int, int]:
    """Rough preview only — a blank shipping/postage entry resolves to the
    channel's default inside record_order, not to 0 as shown here, and this
    preview doesn't account for a packaging kit's cost at all.
    """
    items_revenue = 0
    cogs = 0
    for item in cart:
        list_price = item["quantity"] * item["unit_price"]
        discount = item.get("discount_amount", 0)
        items_revenue += list_price - discount
        product = get_product(conn, item["product_id"])
        unit_cost = product["unit_cost"] if product["unit_cost"] is not None else 0
        cogs += unit_cost * item["quantity"]

    shipping_estimate = shipping_charge or 0
    postage_estimate = postage_cost or 0
    total = items_revenue + shipping_estimate
    profit = items_revenue - cogs - postage_estimate - transaction_fee
    return total, profit


def _handle_record_sale(conn) -> None:
    channel = _prompt_channel()
    if channel is None:
        return

    cart: list[dict] = []

    while True:
        products = list_products(conn)
        if not products:
            print("No active products available.")
            return

        print(f"\n{'#':<4} {'Name':<30} {'Stock':<8} {'Retail':<8} {'Wholesale':<10}")
        print("-" * 65)
        for index, product in enumerate(products, start=1):
            print(
                f"{index:<4} {product['name']:<30} {product['current_stock']:<8} "
                f"{product['retail_price']:<8} {product['wholesale_price']:<10}"
            )

        while True:
            raw = input(
                f"\nSelect product (1-{len(products)}, or 0 to finish): "
            ).strip()
            try:
                choice = int(raw)
                if choice == 0:
                    break
                if 1 <= choice <= len(products):
                    selected = products[choice - 1]
                    break
                print(f"Please enter a number between 0 and {len(products)}.")
            except ValueError:
                print("Please enter a valid number.")

        if choice == 0:
            if not cart:
                print("No items added. Sale cancelled.")
                return
            break

        default_price = _default_unit_price(selected, channel)
        quantity = _prompt_int("Quantity: ", min_value=1)
        price_input = input(
            f"Unit price (default {default_price}): "
        ).strip()
        unit_price = int(price_input) if price_input else default_price

        discount_input = input("Discount amount for this line (default 0): ").strip()
        discount_amount = int(discount_input) if discount_input else 0
        discount_reason = None
        if discount_amount > 0:
            discount_reason = input("Discount reason (optional): ").strip() or None

        cart.append(
            {
                "product_id": selected["id"],
                "product_name": selected["name"],
                "quantity": quantity,
                "unit_price": unit_price,
                "discount_amount": discount_amount,
                "discount_reason": discount_reason,
            }
        )
        print(f"Added: {quantity}x {selected['name']} @ {unit_price}")

        another = input("Add another item? (y/n): ").strip().lower()
        if another != "y":
            break

    customer_name = input("\nCustomer name (optional): ").strip() or None

    shipping_input = input("Shipping charge (leave blank for channel default): ").strip()
    shipping_charge = int(shipping_input) if shipping_input else None

    postage_input = input("Postage cost (leave blank for channel default/estimate): ").strip()
    postage_cost = int(postage_input) if postage_input else None

    fee_input = input("Transaction fee (default 0): ").strip()
    transaction_fee = int(fee_input) if fee_input else 0

    status = _prompt_order_status()

    total, profit = _preview_cart_totals(
        conn, cart, shipping_charge, postage_cost, transaction_fee
    )

    print("\n--- Order Summary ---")
    for item in cart:
        line_total = item["quantity"] * item["unit_price"] - item.get("discount_amount", 0)
        print(
            f"  {item['quantity']}x {item['product_name']} @ {item['unit_price']} "
            f"(line total: {line_total})"
        )
    shipping_display = shipping_charge if shipping_charge is not None else "(channel default)"
    postage_display = postage_cost if postage_cost is not None else "(channel default/estimate)"
    print(f"  Shipping charge: {shipping_display}")
    print(f"  Postage cost: {postage_display}")
    print(f"  Transaction fee: {transaction_fee}")
    print(f"  Status: {status}")
    print(f"  Total (rough estimate): {total}")
    print(f"  Estimated profit (rough estimate): {profit}")

    confirm = input("\nConfirm and record sale? (y/n): ").strip().lower()
    if confirm != "y":
        print("Sale cancelled.")
        return

    order_items = [
        {
            "product_id": item["product_id"],
            "quantity": item["quantity"],
            "unit_price": item["unit_price"],
            "discount_amount": item.get("discount_amount", 0),
            "discount_reason": item.get("discount_reason"),
        }
        for item in cart
    ]

    try:
        order_id = record_order(
            conn,
            channel,
            order_items,
            customer_name=customer_name,
            shipping_charge=shipping_charge,
            postage_cost=postage_cost,
            transaction_fee=transaction_fee,
            status=status,
        )
    except ValueError as exc:
        print(f"\nError: {exc}")
        print("Sale was not recorded. Adjust quantities or stock and try again.")
        return

    detail = get_order(conn, order_id)
    print(f"\nSale recorded successfully. Order #{order_id}")
    print(f"  Status: {detail['order']['status']}")
    print(f"  Total: {detail['customer_total']}")
    print(f"  Profit: {detail['profit']}")


def _display_order_detail(detail: dict) -> None:
    order = detail["order"]
    order_id = order["id"]
    print(f"\nOrder #{order_id}")
    print(f"  Invoice: {order['invoice_number'] or '-'}")
    print(f"  Date: {order['order_date']}")
    print(f"  Channel: {order['channel']}")
    print(f"  Status: {order['status']}")
    print(f"  Customer: {order['customer_name'] or '-'}")
    print(f"  Shipping charge: {order['shipping_charge']}")
    print(f"  Postage cost: {order['postage_cost']}")
    print(f"  Transaction fee: {order['transaction_fee']}")

    print("\nItems:")
    for item in detail["items"]:
        line_total = item["list_price"] - item["discount_amount"]
        print(
            f"  {item['quantity']}x {item['product_name']} — "
            f"list {item['list_price']}, discount {item['discount_amount']}, "
            f"effective unit {item['unit_price']}, cost at time {item['unit_cost_at_time']}, "
            f"line total {line_total}"
        )

    print(f"\n  Total: {detail['customer_total']}")
    print(f"  Profit: {detail['profit']}")


def _handle_list_orders(conn) -> None:
    orders = list_orders(conn)
    if not orders:
        print("\nNo orders found.")
        return

    print(
        f"\n{'ID':<5} {'Invoice':<12} {'Date':<20} {'Channel':<12} "
        f"{'Customer':<20} {'Total':<8} {'Status':<10}"
    )
    print("-" * 92)
    for order in orders:
        customer = order["customer_name"] or "-"
        invoice = order["invoice_number"] or "-"
        print(
            f"{order['id']:<5} {invoice:<12} {order['order_date']:<20} "
            f"{order['channel']:<12} {customer:<20} {order['customer_total']:<8} "
            f"{order['status']:<10}"
        )

    raw = input("\nEnter order ID for full detail (or press Enter to go back): ").strip()
    if not raw:
        return

    try:
        order_id = int(raw)
    except ValueError:
        print("Invalid order ID.")
        return

    try:
        detail = get_order(conn, order_id)
    except ValueError as exc:
        print(f"Error: {exc}")
        return

    _display_order_detail(detail)


def _handle_update_order_status(conn) -> None:
    raw = input("\nEnter order ID to update: ").strip()
    if not raw:
        return

    try:
        order_id = int(raw)
    except ValueError:
        print("Invalid order ID.")
        return

    try:
        detail = get_order(conn, order_id)
    except ValueError as exc:
        print(f"Error: {exc}")
        return

    current_status = detail["order"]["status"]
    print(f"\nOrder #{order_id} — current status: {current_status}")

    print("\nNew status:")
    print("  1. Draft")
    print("  2. Pending")
    print("  3. Paid")
    print("  4. Completed")
    while True:
        choice = input("Select new status (1-4): ").strip()
        status_map = {
            "1": "DRAFT",
            "2": "PENDING",
            "3": "PAID",
            "4": "COMPLETED",
        }
        if choice in status_map:
            new_status = status_map[choice]
            break
        print("Please enter 1-4.")

    if new_status == current_status:
        print(f"Order #{order_id} is already {current_status}.")
        return

    try:
        update_order_status(conn, order_id, new_status)
    except ValueError as exc:
        print(f"Error: {exc}")
        return

    updated = get_order(conn, order_id)
    print(f"Order #{order_id} status updated to {updated['order']['status']}")


def _handle_generate_invoice_pdf(conn) -> None:
    raw = input("\nEnter order ID to generate invoice PDF (or 0 to cancel): ").strip()
    try:
        order_id = int(raw)
    except ValueError:
        print("Invalid order ID.")
        return

    if order_id == 0:
        return

    try:
        path = generate_invoice_pdf(conn, order_id)
        print(f"Invoice PDF saved to: {path}")
    except ValueError as exc:
        print(f"Error: {exc}")


def _handle_view_orders(conn) -> None:
    while True:
        print("\nView Orders")
        print("  1. List orders / view detail")
        print("  2. Update order status")
        print("  3. Generate PDF Invoice")
        print("  4. Back")
        choice = input("Select option: ").strip()

        if choice == "1":
            _handle_list_orders(conn)
        elif choice == "2":
            _handle_update_order_status(conn)
        elif choice == "3":
            _handle_generate_invoice_pdf(conn)
        elif choice == "4":
            break
        else:
            print("Invalid option. Please enter 1-4.")


def _handle_process_return(conn) -> None:
    raw = input("\nEnter order ID to return (or 0 to cancel): ").strip()
    try:
        order_id = int(raw)
    except ValueError:
        print("Invalid order ID.")
        return

    if order_id == 0:
        return

    try:
        detail = get_order(conn, order_id)
    except ValueError as exc:
        print(f"Error: {exc}")
        return

    _display_order_detail(detail)

    print("\nReturn status:")
    print("  1. REFUNDED")
    print("  2. CANCELLED")
    status_choice = input("Select status (1-2): ").strip()
    if status_choice == "1":
        new_status = "REFUNDED"
    elif status_choice == "2":
        new_status = "CANCELLED"
    else:
        print("Invalid status choice.")
        return

    reason = input("Reason (optional): ").strip() or None

    confirm = input(
        f"\nConfirm {new_status} for order #{order_id}? This will restore stock. (y/n): "
    ).strip().lower()
    if confirm != "y":
        print("Return cancelled.")
        return

    try:
        process_return(conn, order_id, new_status, reason=reason)
    except ValueError as exc:
        print(f"\nError: {exc}")
        return

    detail = get_order(conn, order_id)
    print(f"\nOrder #{order_id} marked as {new_status}.")
    print("Stock restored for:")
    for item in detail["items"]:
        product = get_product(conn, item["product_id"])
        print(
            f"  {item['quantity']}x {item['product_name']} "
            f"(new stock: {product['current_stock']})"
        )


def _prompt_date_range() -> tuple[str | None, str | None]:
    start_date = input("Start date YYYY-MM-DD (optional): ").strip() or None
    end_date = input("End date YYYY-MM-DD (optional): ").strip() or None
    return start_date, end_date


def _handle_revenue_summary(conn) -> None:
    start_date = input("Start date YYYY-MM-DD (optional): ").strip() or None
    end_date = input("End date YYYY-MM-DD (optional): ").strip() or None

    summary = get_revenue_summary(
        conn, start_date=start_date, end_date=end_date
    )

    print("\n--- Revenue Summary ---")
    print("(Excludes DRAFT, CANCELLED, and REFUNDED orders)")
    print(f"  Orders counted: {summary['order_count']}")
    print(f"  Total revenue: {summary['total_revenue']}")
    print(f"  Total profit: {summary['total_profit']}")


def _handle_report_product_performance(conn) -> None:
    start_date, end_date = _prompt_date_range()
    rows = get_product_performance(conn, start_date=start_date, end_date=end_date)
    if not rows:
        print("\nNo product sales found for the selected period.")
        return

    print(
        f"\n{'Product':<30} {'Units':<8} {'Revenue':<10} {'Cost':<10} {'Profit':<10}"
    )
    print("-" * 75)
    for row in rows:
        print(
            f"{row['product_name']:<30} {row['units_sold']:<8} "
            f"{row['total_revenue']:<10} {row['total_cost']:<10} {row['total_profit']:<10}"
        )


def _handle_report_channel_breakdown(conn) -> None:
    start_date, end_date = _prompt_date_range()
    rows = get_channel_breakdown(conn, start_date=start_date, end_date=end_date)
    if not rows:
        print("\nNo orders found for the selected period.")
        return

    print(f"\n{'Channel':<15} {'Orders':<8} {'Revenue':<10} {'Profit':<10}")
    print("-" * 50)
    for row in rows:
        print(
            f"{row['channel']:<15} {row['order_count']:<8} "
            f"{row['total_revenue']:<10} {row['total_profit']:<10}"
        )


def _handle_report_low_stock_materials(conn) -> None:
    threshold = _prompt_float("Low stock threshold: ", min_value=0)
    materials = get_low_stock_materials(conn, threshold)
    if not materials:
        print(f"\nNo STOCK materials at or below {threshold}.")
        return

    print(f"\n{'ID':<5} {'Name':<30} {'Stock':<10} {'Unit':<8}")
    print("-" * 60)
    for material in materials:
        print(
            f"{material['id']:<5} {material['name']:<30} "
            f"{material['current_stock']:<10} {material['unit']:<8}"
        )


def _handle_report_low_stock_products(conn) -> None:
    threshold = _prompt_float("Low stock threshold: ", min_value=0)
    products = get_low_stock_products(conn, threshold)
    if not products:
        print(f"\nNo active products at or below {threshold}.")
        return

    print(f"\n{'ID':<5} {'Name':<30} {'Stock':<10}")
    print("-" * 50)
    for product in products:
        print(
            f"{product['id']:<5} {product['name']:<30} {product['current_stock']:<10}"
        )


def _handle_report_waste(conn) -> None:
    start_date, end_date = _prompt_date_range()
    rows = get_waste_report(conn, start_date=start_date, end_date=end_date)
    if not rows:
        print("\nNo waste events found for the selected period.")
        return

    print(
        f"\n{'Item':<30} {'Type':<10} {'Wasted':<10} {'Cost':<12} {'Events':<8} {'Unknown':<8}"
    )
    print("-" * 85)
    for row in rows:
        cost = row["cost"]
        cost_display = "-" if cost is None else str(cost)
        print(
            f"{row['item_name']:<30} {row['item_type']:<10} "
            f"{row['total_wasted']:<10} {cost_display:<12} {row['waste_event_count']:<8} "
            f"{row['unknown_cost_count']:<8}"
        )


def _handle_report_expense_breakdown(conn) -> None:
    start_date, end_date = _prompt_date_range()
    rows = get_expense_breakdown(conn, start_date=start_date, end_date=end_date)
    if not rows:
        print("\nNo expenses found for the selected period.")
        return

    print(f"\n{'Category':<25} {'Total':<12} {'Count':<8}")
    print("-" * 50)
    for row in rows:
        print(
            f"{row['category_name']:<25} {row['total_amount']:<12} "
            f"{row['expense_count']:<8}"
        )


def _handle_report_profit_and_loss(conn) -> None:
    start_date, end_date = _prompt_date_range()
    pnl = get_profit_and_loss(conn, start_date=start_date, end_date=end_date)

    print("\n--- Profit & Loss Summary ---")
    print(f"  Orders counted:       {pnl['order_count']}")
    print(f"  Items revenue:        {pnl['items_revenue']}")
    print(f"  Shipping revenue:     {pnl['shipping_revenue']}")
    print(f"  Total revenue:        {pnl['total_revenue']}")
    print(f"  COGS:                 {pnl['cogs']}")
    print(f"  Packaging cost:       {pnl['packaging_cost']}")
    print(f"  Postage (estimated):  {pnl['postage_estimated']}")
    print(f"  Transaction fees:     {pnl['transaction_fees']}")
    print(f"  Gross profit:         {pnl['gross_profit']}")
    print(f"  Postage (actual):     {pnl['postage_actual']}")
    print(f"  Postage variance:     {pnl['postage_variance']}")
    print(f"  Refund losses:        {pnl['refund_losses']}")
    print(f"  Waste cost:           {pnl['waste_cost']}")
    print(f"  Operating expenses:   {pnl['operating_expenses']}")
    print("  --------------------------------")
    print(f"  NET PROFIT:           {pnl['net_profit']}")


def _handle_report_shipping_summary(conn) -> None:
    start_date, end_date = _prompt_date_range()
    summary = get_shipping_summary(conn, start_date=start_date, end_date=end_date)

    print("\n--- Shipping Summary ---")
    print(f"  Orders counted:          {summary['order_count']}")
    print(f"  Shipping revenue:        {summary['shipping_revenue']}")
    print(f"  Packaging cost:          {summary['packaging_cost']}")
    print(f"  Postage (estimated):     {summary['postage_estimated']}")
    print(f"  Postage (actual):        {summary['postage_actual']}")
    print(f"  Net shipping result:     {summary['net_shipping_result']}")
    print(f"  Avg shipping/order:      {summary['avg_shipping_revenue']}")
    print(f"  Avg packaging/order:     {summary['avg_packaging_cost']}")
    print(f"  Avg postage actual/order:{summary['avg_postage_actual']}")
    print(f"  Avg net result/order:    {summary['avg_net_shipping_result']}")


def manage_reports(conn) -> None:
    while True:
        print("\n--- Reports ---")
        print("1. Product Performance")
        print("2. Channel Breakdown")
        print("3. Low Stock Alert — Materials")
        print("4. Low Stock Alert — Products")
        print("5. Waste Report")
        print("6. Expense Breakdown")
        print("7. Profit & Loss Summary")
        print("8. Shipping Summary")
        print("9. Back to main menu")
        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            _handle_report_product_performance(conn)
        elif choice == "2":
            _handle_report_channel_breakdown(conn)
        elif choice == "3":
            _handle_report_low_stock_materials(conn)
        elif choice == "4":
            _handle_report_low_stock_products(conn)
        elif choice == "5":
            _handle_report_waste(conn)
        elif choice == "6":
            _handle_report_expense_breakdown(conn)
        elif choice == "7":
            _handle_report_profit_and_loss(conn)
        elif choice == "8":
            _handle_report_shipping_summary(conn)
        elif choice == "9":
            break
        else:
            print("Invalid option. Please enter 1-9.")


def _handle_add_supplier(conn) -> None:
    while True:
        name = _prompt_non_empty("Supplier name: ")
        phone = input("Phone (optional): ").strip() or None
        email = input("Email (optional): ").strip() or None
        website = input("Website (optional): ").strip() or None
        notes = input("Notes (optional): ").strip() or None

        try:
            supplier_id = add_supplier(conn, name, phone, email, website, notes)
            print(f"Supplier added with id {supplier_id}.")
            return
        except ValueError as exc:
            print(f"Error: {exc}")
            print("Please try again.")


def _handle_list_suppliers(conn) -> None:
    suppliers = list_suppliers(conn)
    if not suppliers:
        print("\nNo suppliers found.")
        return

    print(f"\n{'ID':<5} {'Name':<30} {'Phone':<15} {'Email':<25}")
    print("-" * 80)
    for supplier in suppliers:
        phone = supplier["phone"] or "-"
        email = supplier["email"] or "-"
        print(
            f"{supplier['id']:<5} {supplier['name']:<30} {phone:<15} {email:<25}"
        )


def _handle_update_supplier(conn) -> None:
    suppliers = list_suppliers(conn)
    if not suppliers:
        print("No suppliers to update.")
        return

    supplier_id = _prompt_choice_from_list(suppliers, "supplier")
    if supplier_id is None:
        return

    supplier = get_supplier(conn, supplier_id)
    print(f"\nUpdating: {supplier['name']}")
    print("Leave a field blank to keep its current value.")

    name_input = input(f"Name [{supplier['name']}]: ").strip()
    phone_input = input(f"Phone [{supplier['phone'] or ''}]: ").strip()
    email_input = input(f"Email [{supplier['email'] or ''}]: ").strip()
    website_input = input(f"Website [{supplier['website'] or ''}]: ").strip()
    notes_input = input(f"Notes [{supplier['notes'] or ''}]: ").strip()

    updates: dict = {}
    if name_input:
        updates["name"] = name_input
    if phone_input:
        updates["phone"] = phone_input
    if email_input:
        updates["email"] = email_input
    if website_input:
        updates["website"] = website_input
    if notes_input:
        updates["notes"] = notes_input

    if not updates:
        print("No changes entered.")
        return

    try:
        update_supplier(conn, supplier_id, **updates)
        print("Supplier updated.")
    except ValueError as exc:
        print(f"Error: {exc}")


def manage_suppliers(conn) -> None:
    while True:
        print("\n--- Manage Suppliers ---")
        print("1. Add supplier")
        print("2. List suppliers")
        print("3. Update supplier")
        print("4. Back to main menu")
        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            _handle_add_supplier(conn)
        elif choice == "2":
            _handle_list_suppliers(conn)
        elif choice == "3":
            _handle_update_supplier(conn)
        elif choice == "4":
            break
        else:
            print("Invalid option. Please enter 1-4.")


def _prompt_optional_supplier(conn) -> int | None:
    suppliers = list_suppliers(conn)
    if not suppliers:
        print("No suppliers on file — continuing without a supplier link.")
        return None

    for index, supplier in enumerate(suppliers, start=1):
        print(f"  {index}. {supplier['name']}")

    while True:
        raw = input(
            f"\nSelect supplier (1-{len(suppliers)}, or 0 for none): "
        ).strip()
        try:
            choice = int(raw)
            if choice == 0:
                return None
            if 1 <= choice <= len(suppliers):
                return suppliers[choice - 1]["id"]
            print(f"Please enter a number between 0 and {len(suppliers)}.")
        except ValueError:
            print("Please enter a valid number.")


def _handle_record_material_purchase(conn) -> None:
    materials = [m for m in list_materials(conn) if m["type"] == "STOCK"]
    material_id = _prompt_choice_from_list(materials, "STOCK material")
    if material_id is None:
        return

    quantity = _prompt_positive_float("Quantity bought: ")
    total_paid = _prompt_int("Total paid (in smallest currency unit): ")

    use_supplier = input("Link to a supplier? (y/n): ").strip().lower()
    supplier_id = _prompt_optional_supplier(conn) if use_supplier == "y" else None

    purchase_date = input("Purchase date YYYY-MM-DD (optional): ").strip() or None
    notes = input("Notes (optional): ").strip() or None

    try:
        purchase_id = record_material_purchase(
            conn,
            material_id,
            quantity,
            total_paid,
            supplier_id=supplier_id,
            purchase_date=purchase_date,
            notes=notes,
        )
    except ValueError as exc:
        print(f"\nError: {exc}")
        return

    purchase = get_material_purchase(conn, purchase_id)
    material = get_material(conn, material_id)
    print(f"\nMaterial purchase recorded. Purchase #{purchase_id}")
    print(f"  Invoice: {purchase['invoice_number']}")
    print(f"  Unit cost: {purchase['unit_cost']}")
    print(f"  New stock: {material['current_stock']}")


def _handle_record_product_purchase(conn) -> None:
    products = list_products(conn)
    product_id = _prompt_choice_from_list(products, "product")
    if product_id is None:
        return

    quantity = _prompt_int("Quantity bought: ", min_value=1)
    total_paid = _prompt_int("Total paid (in smallest currency unit): ")

    use_supplier = input("Link to a supplier? (y/n): ").strip().lower()
    supplier_id = _prompt_optional_supplier(conn) if use_supplier == "y" else None

    purchase_date = input("Purchase date YYYY-MM-DD (optional): ").strip() or None
    notes = input("Notes (optional): ").strip() or None

    try:
        purchase_id = record_product_purchase(
            conn,
            product_id,
            quantity,
            total_paid,
            supplier_id=supplier_id,
            purchase_date=purchase_date,
            notes=notes,
        )
    except ValueError as exc:
        print(f"\nError: {exc}")
        return

    purchase = get_product_purchase(conn, purchase_id)
    product = get_product(conn, product_id)
    print(f"\nProduct purchase recorded. Purchase #{purchase_id}")
    print(f"  Invoice: {purchase['invoice_number']}")
    print(f"  Unit cost: {purchase['unit_cost']}")
    print(f"  New stock: {product['current_stock']}")


def _prompt_optional_item_filter(items: list, label: str) -> int | None:
    if not items:
        return None

    print(f"\nFilter by {label} (leave blank to skip):")
    for index, item in enumerate(items, start=1):
        print(f"  {index}. {item['name']}")

    while True:
        raw = input(f"Select {label} (1-{len(items)}, or blank for all): ").strip()
        if not raw:
            return None
        try:
            choice = int(raw)
            if 1 <= choice <= len(items):
                return items[choice - 1]["id"]
            print(f"Please enter a number between 1 and {len(items)}, or leave blank.")
        except ValueError:
            print("Please enter a valid number, or leave blank.")


def _handle_view_material_purchase_history(conn) -> None:
    materials = [m for m in list_materials(conn) if m["type"] == "STOCK"]
    material_id = _prompt_optional_item_filter(materials, "material")

    suppliers = list_suppliers(conn)
    supplier_id = _prompt_optional_item_filter(suppliers, "supplier")

    start_date, end_date = _prompt_date_range()

    purchases = list_material_purchases(
        conn,
        material_id=material_id,
        supplier_id=supplier_id,
        start_date=start_date,
        end_date=end_date,
    )
    if not purchases:
        print("\nNo material purchases found.")
        return

    print(
        f"\n{'ID':<5} {'Date':<20} {'Invoice':<12} {'Material':<25} "
        f"{'Qty':<8} {'Total':<8} {'Supplier':<20}"
    )
    print("-" * 105)
    for row in purchases:
        supplier = row["supplier_name"] or "-"
        print(
            f"{row['id']:<5} {row['purchase_date']:<20} {row['invoice_number']:<12} "
            f"{row['material_name']:<25} {row['quantity_bought']:<8} "
            f"{row['total_paid']:<8} {supplier:<20}"
        )


def _handle_view_product_purchase_history(conn) -> None:
    products = list_products(conn)
    product_id = _prompt_optional_item_filter(products, "product")

    suppliers = list_suppliers(conn)
    supplier_id = _prompt_optional_item_filter(suppliers, "supplier")

    start_date, end_date = _prompt_date_range()

    purchases = list_product_purchases(
        conn,
        product_id=product_id,
        supplier_id=supplier_id,
        start_date=start_date,
        end_date=end_date,
    )
    if not purchases:
        print("\nNo product purchases found.")
        return

    print(
        f"\n{'ID':<5} {'Date':<20} {'Invoice':<12} {'Product':<25} "
        f"{'Qty':<6} {'Total':<8} {'Supplier':<20}"
    )
    print("-" * 100)
    for row in purchases:
        supplier = row["supplier_name"] or "-"
        print(
            f"{row['id']:<5} {row['purchase_date']:<20} {row['invoice_number']:<12} "
            f"{row['product_name']:<25} {row['quantity_bought']:<6} "
            f"{row['total_paid']:<8} {supplier:<20}"
        )


def manage_purchases(conn) -> None:
    while True:
        print("\n--- Manage Purchases ---")
        print("1. Record Material Purchase")
        print("2. Record Product Purchase")
        print("3. View Material Purchase History")
        print("4. View Product Purchase History")
        print("5. Back to main menu")
        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            _handle_record_material_purchase(conn)
        elif choice == "2":
            _handle_record_product_purchase(conn)
        elif choice == "3":
            _handle_view_material_purchase_history(conn)
        elif choice == "4":
            _handle_view_product_purchase_history(conn)
        elif choice == "5":
            break
        else:
            print("Invalid option. Please enter 1-5.")


def _prompt_expense_category(conn) -> int | None:
    categories = list_expense_categories(conn)
    if not categories:
        print("No active expense categories. Add one first.")
        return None
    return _prompt_choice_from_list(categories, "expense category")


def _handle_add_expense_category(conn) -> None:
    while True:
        name = _prompt_non_empty("Category name: ")
        try:
            category_id = add_expense_category(conn, name)
            print(f"Expense category added with id {category_id}.")
            return
        except ValueError as exc:
            print(f"Error: {exc}")
            print("Please try again.")


def _handle_list_expense_categories(conn) -> None:
    categories = list_expense_categories(conn, active_only=False)
    if not categories:
        print("\nNo expense categories found.")
        return

    print(f"\n{'ID':<5} {'Name':<30} {'Active':<8}")
    print("-" * 45)
    for category in categories:
        active = "Yes" if category["is_active"] else "No"
        print(f"{category['id']:<5} {category['name']:<30} {active:<8}")


def _handle_deactivate_expense_category(conn) -> None:
    categories = list_expense_categories(conn)
    if not categories:
        print("No active expense categories found.")
        return

    category_id = _prompt_choice_from_list(categories, "expense category")
    if category_id is None:
        return

    category = next(c for c in categories if c["id"] == category_id)
    confirm = input(
        f"\nConfirm deactivation of '{category['name']}'? (y/n): "
    ).strip().lower()
    if confirm != "y":
        print("Deactivation cancelled.")
        return

    try:
        deactivate_expense_category(conn, category_id)
    except ValueError as exc:
        print(f"Error: {exc}")
        return

    print(f"Expense category '{category['name']}' deactivated.")


def _handle_add_expense(conn) -> None:
    category_id = _prompt_expense_category(conn)
    if category_id is None:
        return

    amount = _prompt_int("Amount (in smallest currency unit): ")
    description = input("Description (optional): ").strip() or None
    expense_date = input("Expense date YYYY-MM-DD (optional, default now): ").strip() or None

    try:
        expense_id = add_expense(
            conn,
            category_id,
            amount,
            description=description,
            expense_date=expense_date,
        )
        print(f"Expense added with id {expense_id}.")
    except ValueError as exc:
        print(f"Error: {exc}")


def _handle_list_expenses(conn) -> None:
    categories = list_expense_categories(conn)
    category_id = None
    if categories:
        print("\nFilter by category (leave blank to skip):")
        for index, category in enumerate(categories, start=1):
            print(f"  {index}. {category['name']}")
        raw = input(f"Select category (1-{len(categories)}, or blank): ").strip()
        if raw:
            try:
                choice = int(raw)
                if 1 <= choice <= len(categories):
                    category_id = categories[choice - 1]["id"]
            except ValueError:
                print("Invalid category filter, showing all categories.")

    start_date = input("Start date YYYY-MM-DD (optional): ").strip() or None
    end_date = input("End date YYYY-MM-DD (optional): ").strip() or None

    expenses = list_expenses(
        conn,
        category_id=category_id,
        start_date=start_date,
        end_date=end_date,
    )
    if not expenses:
        print("\nNo expenses found.")
        return

    print(f"\n{'ID':<5} {'Date':<20} {'Category':<20} {'Amount':<10} {'Description':<30}")
    print("-" * 90)
    for expense in expenses:
        desc = expense["description"] or "-"
        print(
            f"{expense['id']:<5} {expense['expense_date']:<20} "
            f"{expense['category_name']:<20} {expense['amount']:<10} {desc:<30}"
        )


def _handle_total_expenses(conn) -> None:
    start_date = input("Start date YYYY-MM-DD (optional): ").strip() or None
    end_date = input("End date YYYY-MM-DD (optional): ").strip() or None

    total = get_total_expenses(conn, start_date=start_date, end_date=end_date)
    print(f"\nTotal expenses: {total}")


def _prompt_item_type() -> str | None:
    print("\nItem type:")
    print("  1. MATERIAL")
    print("  2. PRODUCT")

    while True:
        raw = input("\nSelect item type (1-2, or 0 to cancel): ").strip()
        try:
            choice = int(raw)
            if choice == 0:
                return None
            if choice == 1:
                return "MATERIAL"
            if choice == 2:
                return "PRODUCT"
            print("Please enter 0, 1, or 2.")
        except ValueError:
            print("Please enter a valid number.")


def _prompt_active_item(conn, item_type: str) -> int | None:
    if item_type == "MATERIAL":
        items = [m for m in list_materials(conn) if m["type"] == "STOCK"]
        label = "STOCK material"
    else:
        items = list_products(conn)
        label = "product"
    return _prompt_choice_from_list(items, label)


def _prompt_nonzero_float(prompt: str) -> float:
    while True:
        raw = input(prompt).strip()
        try:
            value = float(raw)
            if value == 0:
                print("Must not be 0.")
                continue
            return value
        except ValueError:
            print("Please enter a valid number.")


def _get_item_stock(conn, item_type: str, item_id: int) -> float | int:
    if item_type == "MATERIAL":
        return get_material(conn, item_id)["current_stock"]
    return get_product(conn, item_id)["current_stock"]


def _handle_record_waste(conn) -> None:
    item_type = _prompt_item_type()
    if item_type is None:
        return

    item_id = _prompt_active_item(conn, item_type)
    if item_id is None:
        return

    stock_before = _get_item_stock(conn, item_type, item_id)
    quantity_wasted = _prompt_positive_float("Quantity wasted: ")
    notes = input("Notes (optional): ").strip() or None
    movement_date = input("Date YYYY-MM-DD (optional): ").strip() or None

    try:
        movement_id = record_stock_adjustment(
            conn,
            item_type,
            item_id,
            -quantity_wasted,
            "WASTE",
            notes=notes,
            movement_date=movement_date,
        )
    except ValueError as exc:
        print(f"\nError: {exc}")
        return

    stock_after = _get_item_stock(conn, item_type, item_id)
    movement = get_stock_movement(conn, movement_id)
    print(f"\nWaste recorded. Movement #{movement_id}")
    print(f"  Item: {movement['item_name']}")
    print(f"  Quantity wasted: {quantity_wasted}")
    print(f"  Stock before: {stock_before}")
    print(f"  Stock after: {stock_after}")


def _handle_record_adjustment(conn) -> None:
    item_type = _prompt_item_type()
    if item_type is None:
        return

    item_id = _prompt_active_item(conn, item_type)
    if item_id is None:
        return

    stock_before = _get_item_stock(conn, item_type, item_id)
    quantity_change = _prompt_nonzero_float(
        "Quantity change (+ to increase, - to decrease): "
    )
    notes = input("Notes (optional): ").strip() or None
    movement_date = input("Date YYYY-MM-DD (optional): ").strip() or None

    try:
        movement_id = record_stock_adjustment(
            conn,
            item_type,
            item_id,
            quantity_change,
            "ADJUSTMENT",
            notes=notes,
            movement_date=movement_date,
        )
    except ValueError as exc:
        print(f"\nError: {exc}")
        return

    stock_after = _get_item_stock(conn, item_type, item_id)
    movement = get_stock_movement(conn, movement_id)
    print(f"\nAdjustment recorded. Movement #{movement_id}")
    print(f"  Item: {movement['item_name']}")
    print(f"  Quantity change: {quantity_change}")
    print(f"  Stock before: {stock_before}")
    print(f"  Stock after: {stock_after}")


def _prompt_optional_reason() -> str | None:
    print("\nReason filter:")
    print("  1. WASTE")
    print("  2. ADJUSTMENT")

    while True:
        raw = input("Select reason (1-2, or blank for all): ").strip()
        if not raw:
            return None
        try:
            choice = int(raw)
            if choice == 1:
                return "WASTE"
            if choice == 2:
                return "ADJUSTMENT"
            print("Please enter 1, 2, or leave blank.")
        except ValueError:
            print("Please enter a valid number, or leave blank.")


def _handle_view_adjustment_history(conn) -> None:
    item_type_input = input(
        "Item type filter MATERIAL/PRODUCT (optional): "
    ).strip().upper()
    item_type = item_type_input if item_type_input in ("MATERIAL", "PRODUCT") else None
    if item_type_input and item_type is None:
        print("Invalid item type filter, showing all types.")

    reason = _prompt_optional_reason()
    start_date, end_date = _prompt_date_range()

    try:
        rows = list_stock_adjustments(
            conn,
            item_type=item_type,
            reason=reason,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        print(f"Error: {exc}")
        return

    if not rows:
        print("\nNo adjustment or waste movements found.")
        return

    print(
        f"\n{'ID':<5} {'Date':<20} {'Type':<10} {'Item':<25} "
        f"{'Change':<10} {'Reason':<12} {'Notes':<20}"
    )
    print("-" * 105)
    for row in rows:
        notes = row["notes"] or "-"
        print(
            f"{row['id']:<5} {row['movement_date']:<20} {row['item_type']:<10} "
            f"{row['item_name']:<25} {row['quantity_change']:<10} "
            f"{row['reason']:<12} {notes:<20}"
        )


def manage_adjustments(conn) -> None:
    while True:
        print("\n--- Stock Adjustments / Waste ---")
        print("1. Record Waste")
        print("2. Record Stock Adjustment (correction, +/-)")
        print("3. View Adjustment/Waste History")
        print("4. Back to main menu")
        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            _handle_record_waste(conn)
        elif choice == "2":
            _handle_record_adjustment(conn)
        elif choice == "3":
            _handle_view_adjustment_history(conn)
        elif choice == "4":
            break
        else:
            print("Invalid option. Please enter 1-4.")


def _prompt_percentage(prompt: str) -> float:
    while True:
        raw = input(prompt).strip()
        try:
            value = float(raw)
            if value <= 0 or value > 100:
                print("Percentage must be > 0 and <= 100.")
                continue
            return value
        except ValueError:
            print("Please enter a valid number.")


def _handle_add_partner(conn) -> None:
    while True:
        name = _prompt_non_empty("Partner name: ")
        percentage = _prompt_percentage("Ownership percentage (e.g. 50 for 50%): ")
        phone = input("Phone (optional): ").strip() or None
        email = input("Email (optional): ").strip() or None
        notes = input("Notes (optional): ").strip() or None

        try:
            partner_id = add_partner(
                conn, name, percentage, phone=phone, email=email, notes=notes
            )
            print(f"Partner added with id {partner_id}.")
            return
        except ValueError as exc:
            print(f"Error: {exc}")
            print("Please try again.")


def _handle_update_partner_percentage(conn) -> None:
    partners = list_partners(conn)
    partner_id = _prompt_choice_from_list(partners, "partner")
    if partner_id is None:
        return

    new_percentage = _prompt_percentage("New percentage: ")
    try:
        update_partner_percentage(conn, partner_id, new_percentage)
        print("Partner percentage updated.")
    except ValueError as exc:
        print(f"Error: {exc}")


def _handle_deactivate_partner(conn) -> None:
    partners = list_partners(conn)
    partner_id = _prompt_choice_from_list(partners, "partner")
    if partner_id is None:
        return

    try:
        deactivate_partner(conn, partner_id)
        print("Partner deactivated.")
    except ValueError as exc:
        print(f"Error: {exc}")


def _handle_list_partners(conn) -> None:
    partners = list_partners(conn)
    if not partners:
        print("No active partners found.")
        return

    total = get_active_percentage_total(conn)
    print(f"\n{'ID':<5} {'Name':<25} {'Percentage':<12}")
    print("-" * 45)
    for partner in partners:
        print(
            f"{partner['id']:<5} {partner['name']:<25} "
            f"{partner['current_percentage']:<12}"
        )

    print(f"\nActive percentages sum to {total:.2f}%")
    if abs(total - 100) > 0.01:
        print(f"⚠ Active percentages sum to {total:.2f}%, not 100%")


def _handle_record_profit_distribution(conn) -> None:
    period_start = _prompt_non_empty("Period start YYYY-MM-DD: ")
    period_end = _prompt_non_empty("Period end YYYY-MM-DD: ")

    pnl = get_profit_and_loss(conn, period_start, period_end)
    undistributed = get_undistributed_profit(conn, period_end)
    print("\n--- Profit & Loss for Selected Period ---")
    print(f"  Total Revenue:      {pnl['total_revenue']}")
    print(f"  Operating Expenses: {pnl['operating_expenses']}")
    print(f"  NET PROFIT:         {pnl['net_profit']}")
    print(f"  Undistributed profit as of {period_end}: {undistributed}")
    print(
        "\nYou may distribute less than the net profit if holding some back "
        "as reserve."
    )

    total_amount = _prompt_int(
        "Total amount to distribute (in smallest currency unit): "
    )
    notes = input("Notes (optional): ").strip() or None
    distribution_date = (
        input("Distribution date YYYY-MM-DD (optional): ").strip() or None
    )

    try:
        distribution_id = record_profit_distribution(
            conn,
            period_start,
            period_end,
            total_amount,
            distribution_date=distribution_date,
            notes=notes,
        )
        distribution = get_profit_distribution(conn, distribution_id)
        print(f"\nProfit distribution recorded with id {distribution_id}.")
        print(f"  Period: {period_start} to {period_end}")
        print(f"  Net profit available: {distribution['total_profit_available']}")
        print(f"  Amount distributed:   {distribution['total_amount_distributed']}")
        print("\nPer-partner breakdown:")
        print(f"  {'Partner':<25} {'Percentage':<12} {'Amount':<10}")
        print("  " + "-" * 50)
        for share in distribution["shares"]:
            print(
                f"  {share['partner_name']:<25} "
                f"{share['percentage_at_time']:<12} {share['amount']:<10}"
            )
    except ValueError as exc:
        print(f"Error: {exc}")


def _handle_view_distribution_history(conn) -> None:
    start_date, end_date = _prompt_date_range()
    distributions = list_profit_distributions(
        conn, start_date=start_date, end_date=end_date
    )
    if not distributions:
        print("No distributions found for the selected period.")
        return

    print(
        f"\n{'ID':<5} {'Date':<20} {'Period Start':<14} {'Period End':<14} "
        f"{'Distributed':<12}"
    )
    print("-" * 70)
    for row in distributions:
        print(
            f"{row['id']:<5} {row['distribution_date']:<20} "
            f"{row['period_start']:<14} {row['period_end']:<14} "
            f"{row['total_amount_distributed']:<12}"
        )

    while True:
        raw = input(
            f"\nSelect distribution to view (1-{len(distributions)}, or 0 to cancel): "
        ).strip()
        try:
            choice = int(raw)
            if choice == 0:
                return
            if 1 <= choice <= len(distributions):
                distribution = get_profit_distribution(
                    conn, distributions[choice - 1]["id"]
                )
                print(f"\n--- Distribution #{distribution['id']} ---")
                print(f"  Date: {distribution['distribution_date']}")
                print(f"  Period: {distribution['period_start']} to {distribution['period_end']}")
                print(f"  Net profit available: {distribution['total_profit_available']}")
                print(f"  Amount distributed:   {distribution['total_amount_distributed']}")
                notes = distribution["notes"] or "-"
                print(f"  Notes: {notes}")
                print("\n  Per-partner shares:")
                print(f"  {'Partner':<25} {'Percentage':<12} {'Amount':<10}")
                print("  " + "-" * 50)
                for share in distribution["shares"]:
                    print(
                        f"  {share['partner_name']:<25} "
                        f"{share['percentage_at_time']:<12} {share['amount']:<10}"
                    )
                return
            print(f"Please enter a number between 0 and {len(distributions)}.")
        except ValueError:
            print("Please enter a valid number.")


def _handle_view_partner_payout_history(conn) -> None:
    partners = list_partners(conn, active_only=False)
    partner_id = _prompt_choice_from_list(partners, "partner")
    if partner_id is None:
        return

    start_date, end_date = _prompt_date_range()
    history = get_partner_payout_history(
        conn, partner_id, start_date=start_date, end_date=end_date
    )
    partner = get_partner(conn, partner_id)
    if not history:
        print(f"No payout history found for {partner['name']}.")
        return

    print(f"\n--- Payout History: {partner['name']} ---")
    print(
        f"{'Date':<20} {'Period Start':<14} {'Period End':<14} "
        f"{'Percentage':<12} {'Amount':<10}"
    )
    print("-" * 75)
    running_total = 0
    for row in history:
        running_total += row["amount"]
        print(
            f"{row['distribution_date']:<20} {row['period_start']:<14} "
            f"{row['period_end']:<14} {row['percentage_at_time']:<12} "
            f"{row['amount']:<10}"
        )
    print(f"\nTotal received: {running_total}")


def manage_partners_and_distributions(conn) -> None:
    while True:
        print("\n--- Manage Partners & Profit Distribution ---")
        print("1. Add Partner")
        print("2. Update Partner Percentage")
        print("3. Deactivate Partner")
        print("4. List Partners")
        print("5. Record Profit Distribution")
        print("6. View Distribution History")
        print("7. View Partner Payout History")
        print("8. Back to main menu")
        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            _handle_add_partner(conn)
        elif choice == "2":
            _handle_update_partner_percentage(conn)
        elif choice == "3":
            _handle_deactivate_partner(conn)
        elif choice == "4":
            _handle_list_partners(conn)
        elif choice == "5":
            _handle_record_profit_distribution(conn)
        elif choice == "6":
            _handle_view_distribution_history(conn)
        elif choice == "7":
            _handle_view_partner_payout_history(conn)
        elif choice == "8":
            break
        else:
            print("Invalid option. Please enter 1-8.")


def manage_expenses(conn) -> None:
    while True:
        print("\n--- Manage Expenses ---")
        print("1. Add expense category")
        print("2. List expense categories")
        print("3. Add expense")
        print("4. List expenses")
        print("5. Show total expenses for a date range")
        print("6. Deactivate expense category")
        print("7. Back to main menu")
        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            _handle_add_expense_category(conn)
        elif choice == "2":
            _handle_list_expense_categories(conn)
        elif choice == "3":
            _handle_add_expense(conn)
        elif choice == "4":
            _handle_list_expenses(conn)
        elif choice == "5":
            _handle_total_expenses(conn)
        elif choice == "6":
            _handle_deactivate_expense_category(conn)
        elif choice == "7":
            break
        else:
            print("Invalid option. Please enter 1-7.")


def manage_products_and_materials(conn) -> None:
    while True:
        print("\n--- Manage Products & Materials ---")
        print("1. Add product")
        print("2. List products")
        print("3. Add material")
        print("4. List materials")
        print("5. Update product prices")
        print("6. Deactivate product")
        print("7. Deactivate material")
        print("8. Back to main menu")
        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            _handle_add_product(conn)
        elif choice == "2":
            _handle_list_products(conn)
        elif choice == "3":
            _handle_add_material(conn)
        elif choice == "4":
            _handle_list_materials(conn)
        elif choice == "5":
            _handle_update_product_prices(conn)
        elif choice == "6":
            _handle_deactivate_product(conn)
        elif choice == "7":
            _handle_deactivate_material(conn)
        elif choice == "8":
            break
        else:
            print("Invalid option. Please enter 1-8.")


def main() -> None:
    print("Rebel Store Manager")
    print("-------------------")

    while True:
        print("\n1. Initialize/update database")
        print("2. Exit")
        print("3. Manage Products & Materials")
        print("4. Manage Recipes")
        print("5. Run Production Batch")
        print("6. View Production History")
        print("7. Record Sale")
        print("8. View Orders")
        print("9. Manage Suppliers")
        print("10. Manage Purchases")
        print("11. Manage Expenses")
        print("12. Process Return/Cancellation")
        print("13. Revenue Summary")
        print("14. Stock Adjustments / Waste")
        print("15. Reports")
        print("16. Manage Partners & Profit Distribution")
        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            try:
                init_db()
                print("Database initialized/updated successfully.")
            except Exception as exc:
                print(f"Error initializing database: {exc}")
        elif choice == "2":
            print("Goodbye.")
            break
        elif choice == "3":
            conn = get_connection()
            try:
                manage_products_and_materials(conn)
            finally:
                conn.close()
        elif choice == "4":
            conn = get_connection()
            try:
                manage_recipes(conn)
            finally:
                conn.close()
        elif choice == "5":
            conn = get_connection()
            try:
                _handle_run_production_batch(conn)
            finally:
                conn.close()
        elif choice == "6":
            conn = get_connection()
            try:
                _handle_view_production_history(conn)
            finally:
                conn.close()
        elif choice == "7":
            conn = get_connection()
            try:
                _handle_record_sale(conn)
            finally:
                conn.close()
        elif choice == "8":
            conn = get_connection()
            try:
                _handle_view_orders(conn)
            finally:
                conn.close()
        elif choice == "9":
            conn = get_connection()
            try:
                manage_suppliers(conn)
            finally:
                conn.close()
        elif choice == "10":
            conn = get_connection()
            try:
                manage_purchases(conn)
            finally:
                conn.close()
        elif choice == "11":
            conn = get_connection()
            try:
                manage_expenses(conn)
            finally:
                conn.close()
        elif choice == "12":
            conn = get_connection()
            try:
                _handle_process_return(conn)
            finally:
                conn.close()
        elif choice == "13":
            conn = get_connection()
            try:
                _handle_revenue_summary(conn)
            finally:
                conn.close()
        elif choice == "14":
            conn = get_connection()
            try:
                manage_adjustments(conn)
            finally:
                conn.close()
        elif choice == "15":
            conn = get_connection()
            try:
                manage_reports(conn)
            finally:
                conn.close()
        elif choice == "16":
            conn = get_connection()
            try:
                manage_partners_and_distributions(conn)
            finally:
                conn.close()
        else:
            print("Invalid option. Please enter 1-16.")


if __name__ == "__main__":
    main()
