"""The application log (api/logsetup.py): next to the database, rotating, informative, and free of names and amounts."""

import logging
import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.logsetup as logsetup
from api.main import app
from api.logsetup import logs_dir_for, sanitized_traceback

LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} (INFO|WARNING|ERROR) rebel\.[a-z.]+ .+")


def log_file() -> Path:
    return logs_dir_for(os.environ["REBEL_DB"]) / "app.log"


def read_log() -> str:
    return log_file().read_text(encoding="utf-8")


def test_the_log_sits_in_a_logs_folder_next_to_the_database_with_the_documented_format(tmp_path):
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert log_file() == tmp_path / "logs" / "app.log"
    lines = read_log().splitlines()
    assert lines and all(LINE.match(line) for line in lines), lines
    text = "\n".join(lines)
    assert "INFO rebel.app starting; database file: " in text and "rebel_db_guard.db" in text
    assert "schema: 016_purchase_invoices.sql" in text or "schema: 0" in text
    assert "migrations applied now: " in text
    assert "INFO rebel.backup daily backup made (startup): daily-" in text
    assert text.rstrip().endswith("stopped")


def test_migrations_applied_at_startup_are_logged_by_name(tmp_path):
    with TestClient(app):
        pass
    assert "migrations applied now: 001_initial_schema.sql" in read_log()  # a new database applies them all


def test_the_defaults_are_one_megabyte_by_five_files():
    assert (logsetup.MAX_BYTES, logsetup.BACKUP_COUNT) == (1_000_000, 5)


def test_the_log_rotates_and_keeps_the_newest_files_only(tmp_path, monkeypatch):
    monkeypatch.setattr(logsetup, "MAX_BYTES", 400)
    monkeypatch.setattr(logsetup, "BACKUP_COUNT", 2)
    with TestClient(app):
        logger = logging.getLogger("rebel.app")
        for n in range(80):
            logger.info("filler line number %d to make the file grow", n)
    names = sorted(p.name for p in (tmp_path / "logs").iterdir())
    assert names == ["app.log", "app.log.1", "app.log.2"]
    assert all(p.stat().st_size <= 600 for p in (tmp_path / "logs").iterdir())


def test_the_handler_is_removed_at_shutdown(tmp_path):
    logger = logging.getLogger("rebel")
    before = list(logger.handlers)
    with TestClient(app):
        assert len(logger.handlers) == len(before) + 1
    assert logger.handlers == before


def test_an_unusable_log_folder_does_not_stop_the_app(tmp_path):
    (tmp_path / "logs").write_text("a file where the folder should be")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


# --------------------------------------------------------------- what is logged


def test_handled_errors_are_logged_by_code_status_and_path_only(tmp_path):
    with TestClient(app) as client:
        client.post("/suppliers", json={"name": "سمن کتاب ۱۲۳۴۵"})
        again = client.post("/suppliers", json={"name": "كتاب ٣"})
        client.post("/suppliers", json={"name": "کتاب 3"})
        assert again.status_code == 201
        assert client.post("/suppliers", json={"name": "کتاب ۳"}).status_code == 409
        assert client.post("/expenses", json={"expense_category_id": 1, "amount": 2**64}).status_code == 422
        assert client.get("/products?secret_query=987654321").status_code == 200
    text = read_log()
    assert "handled error code=NAME_DUPLICATE status=409 path=/suppliers" in text
    assert "handled error code=AMOUNT_TOO_LARGE status=422 path=/expenses" in text


def test_no_body_name_amount_or_query_reaches_the_log(tmp_path):
    secrets = ["سمن کتاب", "کتاب", "9876543211", "secret_query", "123456789"]
    with TestClient(app) as client:
        client.post("/suppliers", json={"name": "سمن کتاب", "phone": "09123456789"})
        client.post("/suppliers", json={"name": "سمن کتاب"})  # a duplicate: its message names the supplier
        client.post("/expenses", json={"expense_category_id": 1, "amount": 9876543211})
        client.post("/materials", json={"name": "x", "type": "STOCK", "unit_cost": -5})
        client.get("/orders?start_date=2026-01-01&secret_query=9876543211")
    text = read_log()
    for secret in secrets:
        assert secret not in text, secret


def test_an_unexpected_error_is_a_plain_500_envelope_with_a_traceback_without_its_message(tmp_path, monkeypatch):
    import api.routers.suppliers as suppliers_router

    def boom(conn):
        raise ValueError("customer سمن owes 9876543211 Rial")

    monkeypatch.setattr(suppliers_router, "list_suppliers", boom)
    with TestClient(app) as client:
        response = client.get("/suppliers")
    assert response.status_code == 500
    assert response.json() == {"error": {"type": "InternalError", "code": "APP_ERROR", "message": "Internal error", "field": None, "details": {}}}
    text = read_log()
    assert "unexpected error status=500 path=/suppliers" in text
    assert "builtins.ValueError (message withheld)" in text and "suppliers.py" in text and "in boom" in text
    assert "9876543211" not in text and "سمن" not in text and "owes" not in text


def test_the_traceback_helper_names_class_and_frames_only():
    def inner():
        raise KeyError("a private name")

    try:
        inner()
    except KeyError as exc:
        text = sanitized_traceback(exc)
    assert text.startswith("builtins.KeyError (message withheld)") and "in inner" in text and "private" not in text


def test_a_failing_backup_is_logged_with_its_reason_not_its_message(tmp_path, monkeypatch, caplog):
    import api.startup as startup
    from db.errors import BackupError

    def full(path, *args, **kwargs):
        raise BackupError("no space left on C:\\Users\\Someone\\data", "disk_full")

    monkeypatch.setattr(startup, "backup_if_none_today", full)
    with TestClient(app):
        pass
    text = read_log()
    assert "ERROR rebel.backup daily backup failed (startup): disk_full" in text
    assert "Someone" not in text
