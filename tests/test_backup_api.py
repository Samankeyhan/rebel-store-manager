"""GET /backups and POST /backups: the folder of the served database, the last outcome, a backup on demand."""

import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

import db.backup as backup
from api.main import app
from api.schemas.errors import ErrorEnvelope
from db.backup import STATUS_FILE, backups_dir_for
from db.connection import init_db

ENVELOPE = TypeAdapter(ErrorEnvelope)


@pytest.fixture
def served(tmp_path):
    """The database the API serves (REBEL_DB, in tmp_path) with its schema, and a client that does not run the lifespan
    (so the startup backup does not interfere)."""
    path = Path(os.environ["REBEL_DB"])
    init_db(str(path))
    return TestClient(app), path


def test_with_no_backup_yet_the_folder_is_named_and_the_list_is_empty(served):
    client, path = served
    body = client.get("/backups").json()
    assert body["folder"] == str(backups_dir_for(path))
    assert (body["keep"], body["count"], body["last"], body["items"]) == (60, 0, None, [])


def test_a_backup_on_demand_is_created_listed_and_remembered(served):
    client, path = served
    response = client.post("/backups")
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["name"].startswith("daily-") and created["size"] > 0 and (created["keep"], created["count"]) == (60, 1)
    assert (backups_dir_for(path) / created["name"]).is_file()

    body = client.get("/backups").json()
    assert body["count"] == 1 and [i["name"] for i in body["items"]] == [created["name"]]
    assert body["last"]["ok"] is True and body["last"]["name"] == created["name"] and body["last"]["reason"] is None
    assert body["items"][0]["created_at"] and body["items"][0]["size"] == created["size"]


def test_the_list_shows_the_newest_ten_and_the_count_of_all(served):
    client, path = served
    folder = backups_dir_for(path)
    folder.mkdir()
    for n in range(12):
        (folder / f"daily-2026-08-{n + 1:02d}-000000.db").write_bytes(b"x")
    body = client.get("/backups").json()
    assert body["count"] == 12 and len(body["items"]) == 10
    assert body["items"][0]["name"] == "daily-2026-08-12-000000.db"


def test_a_failed_backup_is_a_500_in_the_envelope_with_a_typed_reason_and_is_remembered(served, monkeypatch):
    client, path = served

    def full(source, target):
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(backup, "_copy", full)
    response = client.post("/backups")
    assert response.status_code == 500
    error = response.json()["error"]
    assert (error["type"], error["code"], error["details"]) == ("BackupError", "BACKUP_FAILED", {"reason": "disk_full"})
    ENVELOPE.validate_python(response.json())
    last = client.get("/backups").json()["last"]
    assert last["ok"] is False and last["reason"] == "disk_full" and last["name"] is None
    assert (backups_dir_for(path) / STATUS_FILE).is_file()


def test_backups_never_appear_in_the_openapi_as_a_restore(served):
    client, _ = served
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths["/backups"]) == {"get", "post"}  # no restore or delete endpoint
    assert "500" in paths["/backups"]["post"]["responses"]
