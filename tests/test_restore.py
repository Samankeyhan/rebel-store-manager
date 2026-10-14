"""Restoring a backup (documented in docs/RUNNING.md, done by hand): the automated version of that procedure on a fictional shop.
A backup is copied in as shop.db in a NEW folder; the app opens it without changing anything, it serves the same data, and
`python -m tools.integrity_check` says OK."""

import hashlib
import shutil
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

import db.orders
import db.settlements
from api.main import app
from db.backup import list_backups, make_backup
from db.connection import get_connection, init_db
from db.materials import add_material
from db.orders import record_order
from db.partners import add_partner
from db.payment_methods import add_payment_method
from db.production import run_production_batch
from db.products import add_product
from db.purchases import record_material_purchase
from db.recipes import add_recipe_item
from tests.helpers import cat
from tools.integrity_check import __main__ as integrity


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fictional_shop(path: Path) -> dict:
    """Some of everything the integrity check looks at."""
    init_db(str(path))
    conn = get_connection(str(path))
    try:
        method = add_payment_method(conn, "Fictional Card", "IMMEDIATE", fee_bps=100)
        box = add_material(conn, "Fictional Box", "STOCK", 12_000, initial_stock=20)
        tee = add_product(conn, "Fictional Tee", cat(conn, "TSHIRT"), 3_000_000, 2_000_000)
        add_recipe_item(conn, tee, box, 2)
        record_material_purchase(conn, box, 10, 150_000)
        run_production_batch(conn, tee, 5)
        order = record_order(
            conn, "WEBSITE", [{"product_id": tee, "quantity": 2, "unit_price": 3_000_000}],
            shipping_charge=0, postage_cost=0, packaging_kit_id=None, payment_method_id=method, status="COMPLETED",
        )
        add_partner(conn, "Fictional Partner", 100)
        conn.commit()
        return {"order": order, "tee": tee, "box": box}
    finally:
        conn.close()


def counts(path: Path) -> dict:
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("products", "materials", "orders", "order_items", "stock_movements", "production_batches",
                          "material_purchases", "payment_methods", "partners", "audit_log")
        }
    finally:
        conn.close()


def test_a_backup_restores_into_a_new_folder_opens_unchanged_and_passes_the_integrity_check(tmp_path, monkeypatch, capsys):
    live = tmp_path / "live" / "shop.db"
    live.parent.mkdir()
    ids = fictional_shop(live)
    before_live = sha(live)

    result = make_backup(live)  # what the app does daily
    assert sha(live) == before_live  # making a backup only reads
    backup_file = Path(result["path"])

    # the manual procedure: a COPY of the backup becomes data\shop.db of a fresh folder
    restored = tmp_path / "restore-test" / "shop.db"
    restored.parent.mkdir()
    shutil.copy2(backup_file, restored)
    restored_hash = sha(restored)

    # the integrity check, as the guide says to run it
    assert integrity.main(["--db", str(restored)]) == 0
    output = capsys.readouterr().out
    assert output.strip().splitlines()[-1] == "OK", output
    assert sha(restored) == restored_hash  # the check only reads

    # the app opens it: no migration is pending, so nothing changes in the file's data, and the same rows are served
    assert counts(restored) == counts(live)
    monkeypatch.setenv("REBEL_DB", str(restored))
    with TestClient(app) as client:
        order = client.get(f"/orders/{ids['order']}")
        assert order.status_code == 200 and order.json()["order"]["status"] == "COMPLETED"
        assert client.get(f"/materials/{ids['box']}").json()["name"] == "Fictional Box"
        assert [p["name"] for p in client.get("/products").json()] == ["Fictional Tee"]
        assert client.get("/backups").json()["folder"] == str(restored.parent / "backups")  # its own backups folder
    assert counts(restored) == counts(live)
    # the live database and its backups folder were never touched by any of this
    assert sha(live) == before_live
    assert [i["name"] for i in list_backups(live.parent / "backups")] == [backup_file.name]


def test_the_restored_copy_keeps_working_after_a_new_sale(tmp_path, monkeypatch):
    live = tmp_path / "live" / "shop.db"
    live.parent.mkdir()
    ids = fictional_shop(live)
    result = make_backup(live)
    restored = tmp_path / "restore-test" / "shop.db"
    restored.parent.mkdir()
    shutil.copy2(result["path"], restored)
    monkeypatch.setenv("REBEL_DB", str(restored))
    with TestClient(app) as client:
        response = client.post("/orders", json={
            "channel": "WEBSITE", "shipping_charge": 0, "postage_cost": 0, "packaging_kit_id": None, "payment_method_id": None,
            "items": [{"product_id": ids["tee"], "quantity": 1, "unit_price": 3_000_000}],
        })
        assert response.status_code == 201, response.text
    assert counts(restored)["orders"] == counts(live)["orders"] + 1  # the restored copy is a live database of its own


def test_a_damaged_backup_is_caught_by_the_integrity_tool_not_silently_used(tmp_path, capsys):
    live = tmp_path / "live" / "shop.db"
    live.parent.mkdir()
    fictional_shop(live)
    result = make_backup(live)
    broken = tmp_path / "restore-test" / "shop.db"
    broken.parent.mkdir()
    data = bytearray(Path(result["path"]).read_bytes())
    data[:100] = bytes(100)
    broken.write_bytes(bytes(data))
    assert integrity.main(["--db", str(broken)]) == 2  # cannot even be opened as a database
    assert "CANNOT RUN" in capsys.readouterr().out
