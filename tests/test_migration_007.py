from pathlib import Path

from db.connection import MIGRATIONS_DIR, get_connection, init_db

BEFORE_007 = tuple(
    name for name in sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql")) if name < "007"
)

# This test is about 007 alone: later migrations (e.g. 009, money x 10 in Rial)
# would change the rows it compares, so it applies migrations only up to 007.
UP_TO_007 = tuple(
    name for name in sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql")) if name < "008"
)


def _migrations_dir(tmp_path: Path, name: str, filenames) -> Path:
    dest = tmp_path / name
    dest.mkdir()
    for filename in filenames:
        content = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
        (dest / filename).write_text(content, encoding="utf-8")
    return dest


def test_007_seeds_display_currency_and_touches_nothing_else(tmp_path):
    assert BEFORE_007[-1] == "006_production_batch_created_at_and_total.sql"
    db_path = tmp_path / "shop.db"
    init_db(str(db_path), migrations_dir=str(_migrations_dir(tmp_path, "at_006", BEFORE_007)))

    conn = get_connection(str(db_path))
    try:
        # An owner who already changed a setting keeps it.
        conn.execute("UPDATE settings SET value = '250000' WHERE key = 'default_shipping_charge'")
        conn.commit()
        settings_before = {r["key"]: r["value"] for r in conn.execute("SELECT * FROM settings")}
        channels_before = [dict(r) for r in conn.execute("SELECT * FROM channel_settings ORDER BY channel")]
    finally:
        conn.close()
    assert "display_currency" not in settings_before

    init_db(str(db_path), migrations_dir=str(_migrations_dir(tmp_path, "up_to_007", UP_TO_007)))

    conn = get_connection(str(db_path))
    try:
        settings_after = {r["key"]: r["value"] for r in conn.execute("SELECT * FROM settings")}
        # Later migrations may add channel_settings columns; 007 must not
        # change the columns that existed when it ran.
        channels_after = [
            {k: dict(r)[k] for k in channels_before[0]}
            for r in conn.execute("SELECT * FROM channel_settings ORDER BY channel")
        ]
        applied = [r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations")]
    finally:
        conn.close()

    assert settings_after.pop("display_currency") == "TOMAN"
    assert settings_after == settings_before
    assert channels_after == channels_before
    assert "007_display_currency.sql" in applied


def test_007_keeps_an_existing_display_currency_row(tmp_path):
    db_path = tmp_path / "shop.db"
    init_db(str(db_path), migrations_dir=str(_migrations_dir(tmp_path, "at_006", BEFORE_007)))
    conn = get_connection(str(db_path))
    try:
        conn.execute("INSERT INTO settings (key, value) VALUES ('display_currency', 'RIAL')")
        conn.commit()
    finally:
        conn.close()

    init_db(str(db_path))

    conn = get_connection(str(db_path))
    try:
        value = conn.execute("SELECT value FROM settings WHERE key = 'display_currency'").fetchone()[0]
    finally:
        conn.close()
    assert value == "RIAL"
