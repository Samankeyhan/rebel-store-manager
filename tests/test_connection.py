import os
import tempfile

import pytest

from db.connection import get_connection, init_db, transaction
from db.errors import InsufficientStockError
from db.materials import add_material, get_material
from db.partners import add_partner, list_partners
from db.production import list_production_batches, run_production_batch
from db.products import add_product, get_product
from db.recipes import add_recipe_item


def test_init_db_raises_on_modified_migration_hash():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        db_path = temp_file.name

    try:
        init_db(db_path)

        conn = get_connection(db_path)
        conn.execute(
            "UPDATE schema_migrations SET content_hash = ? WHERE filename = ?",
            ("deadbeef", "001_initial_schema.sql"),
        )
        conn.commit()
        conn.close()

        with pytest.raises(RuntimeError, match="has been modified after being applied"):
            init_db(db_path)
    finally:
        os.unlink(db_path)


def test_transaction_nested_call_joins_without_committing(test_db):
    test_db.execute("BEGIN")
    try:
        add_partner(test_db, "Alice", 50.0)
        assert test_db.in_transaction  # inner call used SAVEPOINT+RELEASE, not a
                                        # real commit — outer transaction still open
    finally:
        test_db.rollback()

    assert not any(
        p["name"] == "Alice" for p in list_partners(test_db, active_only=False)
    )


def test_transaction_outer_failure_rolls_back_nested_work(test_db):
    with pytest.raises(RuntimeError):
        with transaction(test_db):
            add_partner(test_db, "Bob", 50.0)
            raise RuntimeError("simulated failure after nested write")

    assert not any(
        p["name"] == "Bob" for p in list_partners(test_db, active_only=False)
    )


def test_transaction_standalone_failure_leaves_db_unchanged(test_db):
    product_id = add_product(test_db, "Widget", "OTHER", 1000, 800)
    material_id = add_material(test_db, "Wire", "STOCK", 100, initial_stock=1)
    add_recipe_item(test_db, product_id, material_id, quantity_needed=5)

    with pytest.raises(InsufficientStockError):
        run_production_batch(test_db, product_id, quantity_produced=1)

    assert get_product(test_db, product_id)["current_stock"] == 0
    assert get_material(test_db, material_id)["current_stock"] == 1
    assert list_production_batches(test_db) == []


def test_transaction_nested_failure_caught_by_caller_undoes_only_inner_work(test_db):
    with transaction(test_db):
        add_partner(test_db, "Alice", 50.0)
        try:
            with transaction(test_db):
                add_partner(test_db, "Bob", 50.0)
                raise RuntimeError("simulated failure")
        except RuntimeError:
            pass  # caller catches it and continues — outer transaction keeps going

    partners = list_partners(test_db, active_only=False)
    assert any(p["name"] == "Alice" for p in partners)
    assert not any(p["name"] == "Bob" for p in partners)
