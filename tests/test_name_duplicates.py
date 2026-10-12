"""Duplicate-name protection: the same name in another Persian/Arabic spelling is the same name,
on create and rename, in every table with a unique name (db/name_keys.py)."""

import json

import pytest

from db import name_keys
from db.categories import create_category, deactivate_category, update_category
from db.errors import ConflictError, ErrorCode, ValidationError
from db.expenses import add_expense_category
from db.names import name_key
from db.packaging import create_kit
from db.payment_methods import add_payment_method, deactivate_payment_method, update_payment_method

ARABIC = "كتاب ٣"  # Arabic Kaf, Arabic-Indic digit
PERSIAN = "کتاب 3"  # Persian Kaf, ASCII digit
PERSIAN_DIGITS = "کتاب ۳"


def _pay(conn, name):
    return add_payment_method(conn, name, "IMMEDIATE")


def _cat(conn, name):
    return create_category(conn, "PRODUCT", name)


# table, create function, name column table, code expected
CREATORS = [
    ("payment_methods", _pay, ErrorCode.PAYMENT_METHOD_DUPLICATE_NAME, "payment_method"),
    ("categories", _cat, ErrorCode.CATEGORY_DUPLICATE_NAME, "category"),
    ("packaging_kits", create_kit, ErrorCode.NAME_DUPLICATE, "packaging_kit"),
    ("expense_categories", add_expense_category, ErrorCode.NAME_DUPLICATE, "expense_category"),
]
IDS = [c[0] for c in CREATORS]


def _assert_duplicate(exc_info, code, entity, existing_id):
    exc = exc_info.value
    assert type(exc) is ConflictError
    assert exc.code == code
    assert exc.details == {"entity": entity, "existing_id": existing_id}


@pytest.mark.parametrize("table, create, code, entity", CREATORS, ids=IDS)
@pytest.mark.parametrize("second", [ARABIC, PERSIAN, PERSIAN_DIGITS, "  کتاب‏  ۳ "])
def test_a_spelling_variant_of_an_existing_name_is_refused(test_db, table, create, code, entity, second):
    first = create(test_db, ARABIC)
    with pytest.raises(ConflictError) as exc_info:
        create(test_db, second)
    _assert_duplicate(exc_info, code, entity, first)
    assert test_db.execute(f"SELECT COUNT(*) FROM {table} WHERE name LIKE 'کتاب%' OR name LIKE 'كتاب%'").fetchone()[0] == 1


@pytest.mark.parametrize("table, create, code, entity", CREATORS, ids=IDS)
def test_a_new_name_is_saved_in_stored_form_with_its_key(test_db, table, create, code, entity):
    row_id = create(test_db, "  كتاب‏  ٣ ")
    row = test_db.execute(f"SELECT name, name_key FROM {table} WHERE id = ?", (row_id,)).fetchone()
    assert row["name"] == "کتاب ۳"
    assert row["name_key"] == name_key("کتاب 3") == "کتاب 3"


@pytest.mark.parametrize("table, create, code, entity", CREATORS, ids=IDS)
def test_a_name_with_only_invisible_characters_is_empty(test_db, table, create, code, entity):
    with pytest.raises(ValidationError) as exc_info:
        create(test_db, "​ ‎")
    assert exc_info.value.field == "name"


@pytest.mark.parametrize("table, create, code, entity", CREATORS, ids=IDS)
def test_a_null_key_pair_blocks_a_third_row(test_db, table, create, code, entity):
    """Rows the backfill left without a key (a collision pair) still count for new names."""
    a = create(test_db, "Pair One")
    b = create(test_db, "Other Name")
    for row_id, name in ((a, "Fictional Item"), (b, "fictional  item")):  # distinct text, same key
        test_db.execute(f"UPDATE {table} SET name = ?, name_key = NULL WHERE id = ?", (name, row_id))
    with pytest.raises(ConflictError) as exc_info:
        create(test_db, "FICTIONAL ITEM")
    _assert_duplicate(exc_info, code, entity, a)


@pytest.mark.parametrize("table, create, code, entity", CREATORS, ids=IDS)
def test_the_unique_index_is_the_final_guard_against_a_race(test_db, monkeypatch, table, create, code, entity):
    first = create(test_db, ARABIC)
    real = name_keys.find_existing_id
    calls = []

    def blind_first_time(*args, **kwargs):  # the pre-check misses: another writer got in between
        calls.append(1)
        return None if len(calls) == 1 else real(*args, **kwargs)

    monkeypatch.setattr(name_keys, "find_existing_id", blind_first_time)
    with pytest.raises(ConflictError) as exc_info:
        create(test_db, PERSIAN)
    _assert_duplicate(exc_info, code, entity, first)
    assert len(calls) == 2


def test_other_integrity_errors_are_not_reported_as_duplicates():
    import sqlite3

    assert name_keys.is_name_violation(sqlite3.IntegrityError("UNIQUE constraint failed: suppliers.name_key"))
    assert name_keys.is_name_violation(sqlite3.IntegrityError("UNIQUE constraint failed: payment_methods.name"))
    assert name_keys.is_name_violation(
        sqlite3.IntegrityError("UNIQUE constraint failed: categories.kind, categories.name_key")
    )
    assert not name_keys.is_name_violation(sqlite3.IntegrityError("FOREIGN KEY constraint failed"))
    assert not name_keys.is_name_violation(sqlite3.IntegrityError("UNIQUE constraint failed: orders.invoice_number"))


def test_the_index_error_text_for_a_partial_index_is_recognised(test_db):
    test_db.execute("INSERT INTO suppliers (name, name_key) VALUES ('a', 'a')")
    with pytest.raises(Exception) as exc_info:
        test_db.execute("INSERT INTO suppliers (name, name_key) VALUES ('b', 'a')")
    assert name_keys.is_name_violation(exc_info.value)


# ------------------------------------------------------- deactivated rows, rename


def test_a_deactivated_payment_method_keeps_its_name_reserved(test_db):
    first = _pay(test_db, ARABIC)
    deactivate_payment_method(test_db, first)
    with pytest.raises(ConflictError) as exc_info:
        _pay(test_db, PERSIAN)
    _assert_duplicate(exc_info, ErrorCode.PAYMENT_METHOD_DUPLICATE_NAME, "payment_method", first)


def test_a_deactivated_category_keeps_its_name_reserved(test_db):
    first = _cat(test_db, ARABIC)
    deactivate_category(test_db, first)
    with pytest.raises(ConflictError) as exc_info:
        _cat(test_db, PERSIAN)
    _assert_duplicate(exc_info, ErrorCode.CATEGORY_DUPLICATE_NAME, "category", first)


def test_rename_a_payment_method_to_a_variant_of_another_is_refused(test_db):
    other = _pay(test_db, ARABIC)
    mine = _pay(test_db, "Mine")
    with pytest.raises(ConflictError) as exc_info:
        update_payment_method(test_db, mine, name=PERSIAN)
    _assert_duplicate(exc_info, ErrorCode.PAYMENT_METHOD_DUPLICATE_NAME, "payment_method", other)
    assert test_db.execute("SELECT name FROM payment_methods WHERE id = ?", (mine,)).fetchone()[0] == "Mine"


def test_rename_a_payment_method_to_a_variant_of_itself_is_allowed_and_rekeyed(test_db):
    mine = _pay(test_db, ARABIC)
    update_payment_method(test_db, mine, name="  كتاب   3 ")
    row = test_db.execute("SELECT name, name_key FROM payment_methods WHERE id = ?", (mine,)).fetchone()
    assert (row["name"], row["name_key"]) == ("کتاب 3", "کتاب 3")


def test_rename_a_category_to_a_variant_of_a_sibling_is_refused(test_db):
    other = _cat(test_db, ARABIC)
    mine = _cat(test_db, "Mine")
    with pytest.raises(ConflictError) as exc_info:
        update_category(test_db, mine, name=PERSIAN_DIGITS)
    _assert_duplicate(exc_info, ErrorCode.CATEGORY_DUPLICATE_NAME, "category", other)
    assert test_db.execute("SELECT name FROM categories WHERE id = ?", (mine,)).fetchone()[0] == "Mine"
    update_category(test_db, other, name=PERSIAN)  # a variant of itself is fine
    assert test_db.execute("SELECT name_key FROM categories WHERE id = ?", (other,)).fetchone()[0] == "کتاب 3"


def test_categories_are_unique_among_siblings_only(test_db):
    parent_a = _cat(test_db, "Parent A")
    parent_b = _cat(test_db, "Parent B")
    create_category(test_db, "PRODUCT", ARABIC, parent_a)
    create_category(test_db, "PRODUCT", PERSIAN, parent_b)  # other parent: fine
    create_category(test_db, "MATERIAL", PERSIAN)  # other kind, top level: fine
    create_category(test_db, "PRODUCT", PERSIAN)  # top level product: fine (the child is not a sibling)
    with pytest.raises(ConflictError):
        create_category(test_db, "PRODUCT", PERSIAN_DIGITS, parent_a)
    with pytest.raises(ConflictError):
        create_category(test_db, "PRODUCT", ARABIC)


# --------------------------------------------------------------------- audit


def test_the_audit_log_holds_the_name_but_never_the_key(test_db):
    row_id = create_kit(test_db, "  كتاب ٣")
    entry = test_db.execute(
        "SELECT * FROM audit_log WHERE entity_type = 'packaging_kits' AND entity_id = ?", (str(row_id),)
    ).fetchone()
    assert entry["operation"] == "create_kit"
    assert json.loads(entry["after_json"])["name"] == "کتاب ۳"
    assert "name_key" not in entry["after_json"]
