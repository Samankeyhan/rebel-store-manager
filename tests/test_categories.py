import pytest

from db.categories import (
    create_category,
    deactivate_category,
    get_category,
    list_categories,
    list_category_tree,
    reactivate_category,
    update_category,
)
from db.errors import ConflictError, NotFoundError, ValidationError
from db.materials import add_material
from db.products import add_product, deactivate_product
from tests.helpers import cat

SEEDED = {"آلبوم", "کاست", "وینیل", "آینه", "پوستر", "استیکر", "تی‌شرت", "سایر", "فندک"}


def test_seeded_product_categories(test_db):
    rows = list_categories(test_db, "PRODUCT")
    assert {r["name"] for r in rows} == SEEDED
    assert all(r["parent_id"] is None and r["is_active"] == 1 for r in rows)
    assert list_categories(test_db, "MATERIAL") == []


def test_create_and_get_top_level(test_db):
    category_id = create_category(test_db, "MATERIAL", "  چاپ  ")
    category = get_category(test_db, category_id)
    assert category["name"] == "چاپ"  # stripped
    assert category["kind"] == "MATERIAL"
    assert category["parent_id"] is None
    assert category["parent_name"] is None
    assert category["is_active"] == 1
    assert get_category(test_db, 9999) is None


def test_create_subcategory_and_list_children(test_db):
    lighters = cat(test_db, "فندک")
    big = create_category(test_db, "PRODUCT", "فندک بزرگ", parent_id=lighters)
    small = create_category(test_db, "PRODUCT", "فندک کوچک", parent_id=lighters)

    assert get_category(test_db, big)["parent_name"] == "فندک"
    children = list_categories(test_db, "PRODUCT", parent_id=lighters)
    assert [c["id"] for c in children] == [big, small]
    # Top-level listing never includes subcategories.
    assert big not in {c["id"] for c in list_categories(test_db, "PRODUCT")}


def test_list_category_tree(test_db):
    lighters = cat(test_db, "فندک")
    big = create_category(test_db, "PRODUCT", "فندک بزرگ", parent_id=lighters)
    hidden = create_category(test_db, "PRODUCT", "فندک قدیمی", parent_id=lighters)
    deactivate_category(test_db, hidden)

    tree = {t["id"]: t for t in list_category_tree(test_db, "PRODUCT")}
    assert len(tree) == len(SEEDED)
    assert [c["id"] for c in tree[lighters]["children"]] == [big]
    assert tree[cat(test_db, "VINYL")]["children"] == []

    full = {t["id"]: t for t in list_category_tree(test_db, "PRODUCT", include_inactive=True)}
    assert {c["id"] for c in full[lighters]["children"]} == {big, hidden}


def test_list_filters_inactive_unless_asked(test_db):
    category_id = create_category(test_db, "MATERIAL", "قدیمی")
    deactivate_category(test_db, category_id)
    assert list_categories(test_db, "MATERIAL") == []
    assert [c["id"] for c in list_categories(test_db, "MATERIAL", include_inactive=True)] == [category_id]


@pytest.mark.parametrize("bad", ["", "   "])
def test_empty_name_refused(test_db, bad):
    with pytest.raises(ValidationError) as exc_info:
        create_category(test_db, "PRODUCT", bad)
    assert exc_info.value.field == "name"


def test_invalid_kind_refused(test_db):
    with pytest.raises(ValidationError) as exc_info:
        create_category(test_db, "SUPPLIER", "X")
    assert exc_info.value.field == "kind"
    with pytest.raises(ValidationError):
        list_categories(test_db, "SUPPLIER")


def test_parent_must_be_same_kind(test_db):
    with pytest.raises(ValidationError, match="PRODUCT category") as exc_info:
        create_category(test_db, "MATERIAL", "A3", parent_id=cat(test_db, "POSTER"))
    assert exc_info.value.field == "parent_id"


def test_no_subcategory_of_a_subcategory(test_db):
    big = create_category(test_db, "PRODUCT", "فندک بزرگ", parent_id=cat(test_db, "فندک"))
    with pytest.raises(ValidationError, match="already a subcategory") as exc_info:
        create_category(test_db, "PRODUCT", "خیلی بزرگ", parent_id=big)
    assert exc_info.value.field == "parent_id"


def test_parent_must_exist_and_be_active(test_db):
    with pytest.raises(ValidationError, match="does not exist"):
        create_category(test_db, "PRODUCT", "X", parent_id=9999)
    unused = create_category(test_db, "PRODUCT", "کلاه")
    deactivate_category(test_db, unused)
    with pytest.raises(ValidationError, match="inactive"):
        create_category(test_db, "PRODUCT", "کلاه لبه‌دار", parent_id=unused)


def test_name_unique_among_siblings(test_db):
    lighters = cat(test_db, "فندک")
    create_category(test_db, "PRODUCT", "فندک بزرگ", parent_id=lighters)

    with pytest.raises(ConflictError):
        create_category(test_db, "PRODUCT", "وینیل")  # top-level duplicate
    with pytest.raises(ConflictError):
        create_category(test_db, "PRODUCT", " فندک بزرگ ", parent_id=lighters)

    # Inactive siblings still hold the name (reactivate instead).
    old = create_category(test_db, "PRODUCT", "کلاه")
    deactivate_category(test_db, old)
    with pytest.raises(ConflictError):
        create_category(test_db, "PRODUCT", "کلاه")


def test_same_name_allowed_across_parents_and_kinds(test_db):
    create_category(test_db, "PRODUCT", "بزرگ", parent_id=cat(test_db, "فندک"))
    create_category(test_db, "PRODUCT", "بزرگ", parent_id=cat(test_db, "POSTER"))
    create_category(test_db, "MATERIAL", "وینیل")  # same as a PRODUCT top-level
    create_category(test_db, "PRODUCT", "بزرگ")  # top-level vs child
    assert len(list_categories(test_db, "MATERIAL")) == 1


def test_rename(test_db):
    category_id = create_category(test_db, "MATERIAL", "چاپ")
    update_category(test_db, category_id, name="چاپ دیجیتال")
    assert get_category(test_db, category_id)["name"] == "چاپ دیجیتال"
    # Renaming to its own name is not a conflict.
    update_category(test_db, category_id, name="چاپ دیجیتال")


def test_rename_conflict_and_empty(test_db):
    with pytest.raises(ConflictError):
        update_category(test_db, cat(test_db, "VINYL"), name="کاست")
    with pytest.raises(ValidationError):
        update_category(test_db, cat(test_db, "VINYL"), name=" ")
    assert get_category(test_db, cat(test_db, "VINYL"))["name"] == "وینیل"


def test_update_unknown_raises_not_found(test_db):
    with pytest.raises(NotFoundError):
        update_category(test_db, 9999, name="X")
    with pytest.raises(NotFoundError):
        deactivate_category(test_db, 9999)
    with pytest.raises(NotFoundError):
        reactivate_category(test_db, 9999)


def test_deactivate_refused_while_used_by_product(test_db):
    vinyl = cat(test_db, "VINYL")
    add_product(test_db, "Vinyl", vinyl, 1000, 800)
    with pytest.raises(ConflictError, match="used by 1 product"):
        deactivate_category(test_db, vinyl)
    assert get_category(test_db, vinyl)["is_active"] == 1


def test_deactivate_refused_while_used_by_inactive_product(test_db):
    vinyl = cat(test_db, "VINYL")
    deactivate_product(test_db, add_product(test_db, "Vinyl", vinyl, 1000, 800))
    with pytest.raises(ConflictError, match="used by 1 product"):
        deactivate_category(test_db, vinyl)


def test_deactivate_refused_while_used_by_material(test_db):
    printing = create_category(test_db, "MATERIAL", "چاپ")
    add_material(test_db, "A3", "SERVICE", 100, category_id=printing)
    with pytest.raises(ConflictError, match="used by 1 material"):
        deactivate_category(test_db, printing)


def test_deactivate_refused_with_active_children_then_allowed(test_db):
    unused = create_category(test_db, "PRODUCT", "کلاه")
    child = create_category(test_db, "PRODUCT", "کلاه لبه‌دار", parent_id=unused)
    with pytest.raises(ConflictError, match="active subcategories"):
        deactivate_category(test_db, unused)

    deactivate_category(test_db, child)
    deactivate_category(test_db, unused)
    assert get_category(test_db, unused)["is_active"] == 0
    assert get_category(test_db, child)["is_active"] == 0  # no cascade surprises


def test_reactivate(test_db):
    unused = create_category(test_db, "PRODUCT", "کلاه")
    deactivate_category(test_db, unused)
    reactivate_category(test_db, unused)
    assert get_category(test_db, unused)["is_active"] == 1


def test_reactivate_child_refused_while_parent_inactive(test_db):
    unused = create_category(test_db, "PRODUCT", "کلاه")
    child = create_category(test_db, "PRODUCT", "کلاه لبه‌دار", parent_id=unused)
    deactivate_category(test_db, child)
    deactivate_category(test_db, unused)

    with pytest.raises(ConflictError, match="Parent category"):
        reactivate_category(test_db, child)
    reactivate_category(test_db, unused)
    reactivate_category(test_db, child)
    assert get_category(test_db, child)["is_active"] == 1


def test_update_is_active_uses_the_same_rules(test_db):
    vinyl = cat(test_db, "VINYL")
    add_product(test_db, "Vinyl", vinyl, 1000, 800)
    with pytest.raises(ConflictError):
        update_category(test_db, vinyl, is_active=False)

    unused = create_category(test_db, "PRODUCT", "کلاه")
    update_category(test_db, unused, is_active=False)
    assert get_category(test_db, unused)["is_active"] == 0
    update_category(test_db, unused, is_active=True)
    assert get_category(test_db, unused)["is_active"] == 1


def test_update_rename_rolls_back_when_deactivation_refused(test_db):
    vinyl = cat(test_db, "VINYL")
    add_product(test_db, "Vinyl", vinyl, 1000, 800)
    with pytest.raises(ConflictError):
        update_category(test_db, vinyl, name="صفحه", is_active=False)
    assert get_category(test_db, vinyl)["name"] == "وینیل"
