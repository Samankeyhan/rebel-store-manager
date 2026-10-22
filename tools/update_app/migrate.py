"""python -m tools.update_app.migrate --db FILE : run `init_db` on a database in THIS fresh process and print `APPLIED <migration>` per migration applied.
The updater starts it as a separate process after `git pull`, so the code that was just pulled does the migrating. Exit 0 ok, 1 failed."""

import argparse
import sqlite3
import sys
from pathlib import Path

from db.connection import init_db


def applied_names(path: Path) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        return {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}
    except sqlite3.DatabaseError:
        return set()
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(prog="python -m tools.update_app.migrate")
    parser.add_argument("--db", required=True)
    args = parser.parse_args(argv)
    path = Path(args.db).resolve()
    before = applied_names(path)
    try:
        collisions = init_db(str(path))
    except Exception as exc:  # any failure: the caller rolls back
        print(f"MIGRATION FAILED: {type(exc).__name__}: {exc}")
        return 1
    for name in sorted(applied_names(path) - before):
        print(f"APPLIED {name}")
    if collisions:
        print(f"NOTE: {len(collisions)} name collisions have no key yet")
    print("MIGRATION OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
