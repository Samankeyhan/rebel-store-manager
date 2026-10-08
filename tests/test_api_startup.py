"""The API applies pending migrations on startup, or refuses to start."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from db.connection import MIGRATIONS_DIR, get_connection, init_db

ALL_MIGRATIONS = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql"))
LATEST = ALL_MIGRATIONS[-1]


def _db_missing_latest_migration(tmp_path):
    """A DB at every migration but the newest, holding one product and one batch
    (and the seeded settings, so the newest migration's effect on them shows).

    Seeded with whatever columns that schema has, so the test keeps working as
    new migrations ship.
    """
    older = tmp_path / "older_migrations"
    older.mkdir()
    for name in ALL_MIGRATIONS[:-1]:
        (older / name).write_text((MIGRATIONS_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    db_path = tmp_path / "shop.db"
    init_db(str(db_path), migrations_dir=str(older))
    conn = get_connection(str(db_path))
    try:
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(products)")}
        if "category_id" in columns:
            category_id = conn.execute(
                "SELECT id FROM categories WHERE kind = 'PRODUCT' AND name = 'وینیل'"
            ).fetchone()[0]
            product_id = conn.execute(
                "INSERT INTO products (name, category, category_id, retail_price, wholesale_price) "
                "VALUES ('Startup Vinyl', 'VINYL', ?, 3000, 2000)",
                (category_id,),
            ).lastrowid
        else:
            product_id = conn.execute(
                "INSERT INTO products (name, category, retail_price, wholesale_price) "
                "VALUES ('Startup Vinyl', 'VINYL', 3000, 2000)"
            ).lastrowid
        conn.execute(
            "INSERT INTO production_batches (product_id, quantity_produced, unit_cost) VALUES (?, 4, 500)",
            (product_id,),
        )
    finally:
        conn.close()
    return db_path


def _applied(db_path):
    conn = get_connection(str(db_path))
    try:
        return [r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations ORDER BY id")]
    finally:
        conn.close()


def _columns(db_path, table):
    conn = get_connection(str(db_path))
    try:
        return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def _setting(db_path, key):
    conn = get_connection(str(db_path))
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _no_overrides():
    # Exercise the real get_db / REBEL_DB path, not a test override.
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_startup_applies_pending_migration(tmp_path, monkeypatch):
    db_path = _db_missing_latest_migration(tmp_path)
    monkeypatch.setenv("REBEL_DB", str(db_path))
    assert LATEST not in _applied(db_path)

    # Without the startup event (no `with`), nothing applies the newest
    # migration: it is not recorded, and materials has no min_stock yet
    # (011). (Earlier migrations added the columns /products and /production
    # need, and reads 500'd without them.)
    assert _applied(db_path) == ALL_MIGRATIONS[:-1]
    assert "min_stock" not in _columns(db_path, "materials")
    assert "fee_cap" in _columns(db_path, "payment_methods")
    assert _setting(db_path, "default_shipping_charge") == "1800000"

    with TestClient(app) as client:
        response = client.get("/products")
        assert response.status_code == 200, response.text
        assert [p["name"] for p in response.json()] == ["Startup Vinyl"]
        assert response.json()[0]["category_name"] == "وینیل"
        categories = client.get("/categories", params={"kind": "PRODUCT"})
        assert categories.status_code == 200, categories.text
        assert len(categories.json()) == 9
        batches = client.get("/production")
        assert batches.status_code == 200, batches.text
        # The pre-existing batch gets no invented creation time or total.
        assert batches.json()[0]["created_at"] is None
        assert batches.json()[0]["total_cost"] is None
        created = client.post(
            "/payment-methods", json={"name": "Card", "settlement_rule": "IMMEDIATE"}
        )
        assert created.status_code == 201, created.text
        assert created.json()["fee_cap"] is None
        material = client.post(
            "/materials", json={"name": "Test Box", "type": "STOCK", "unit_cost": 1000}
        )
        assert material.status_code == 201, material.text
        assert material.json()["min_stock"] is None

    # Startup applied and recorded the newest migration (011 adds min_stock and
    # touches no setting; money has been integer Rial since 009).
    assert _applied(db_path) == ALL_MIGRATIONS
    assert LATEST in _applied(db_path)
    assert "min_stock" in _columns(db_path, "materials")
    assert _setting(db_path, "default_shipping_charge") == "1800000"


def test_startup_on_current_db_is_a_no_op(tmp_path, monkeypatch):
    db_path = tmp_path / "shop.db"
    init_db(str(db_path))
    monkeypatch.setenv("REBEL_DB", str(db_path))

    for _ in range(2):
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200

    assert _applied(db_path) == ALL_MIGRATIONS
    # init_db only backs up before applying something; nothing was pending.
    assert not (tmp_path / "backups").exists()


def test_startup_refuses_when_migrations_cannot_apply(tmp_path, monkeypatch):
    db_path = tmp_path / "shop.db"
    init_db(str(db_path))
    conn = get_connection(str(db_path))
    try:
        # As if an already-applied migration file had been edited afterwards.
        conn.execute("UPDATE schema_migrations SET content_hash = 'edited' WHERE filename = ?", (LATEST,))
    finally:
        conn.close()
    monkeypatch.setenv("REBEL_DB", str(db_path))

    with pytest.raises(RuntimeError, match="refusing to start") as exc_info:
        with TestClient(app):
            pass
    assert str(db_path) in str(exc_info.value)
    assert "has been modified" in str(exc_info.value)
