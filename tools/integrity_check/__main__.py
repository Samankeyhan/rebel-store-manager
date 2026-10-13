"""CLI of the integrity check: path handling, header, one line per check, last line OK / FAILED / INCOMPLETE, exit code."""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from db.connection import PROJECT_ROOT
from tools.integrity_check.checks import run_checks
from tools.integrity_check.readonly import fingerprint, open_readonly, schema_version
from tools.integrity_check.report import CannotRun, final_line

# The header is always exactly this many lines (title, five facts, run time, separator): a daily comparison of two
# reports skips them with `Select-Object -Skip 9`.
HEADER_LINES = 9


def resolve_path(db_arg: str | None) -> Path:
    """--db (relative to the current folder), else $REBEL_DB, else data/shop.db (both relative to the project folder)."""
    if db_arg:
        return Path(db_arg)
    path = Path(os.environ.get("REBEL_DB") or "data/shop.db")
    return path if path.is_absolute() else PROJECT_ROOT / path


def _utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass  # a stream that cannot be reconfigured (a test capture) keeps its own encoding


def main(argv: list[str] | None = None) -> int:
    _utf8_output()
    parser = argparse.ArgumentParser(
        prog="python -m tools.integrity_check",
        description="Read-only consistency check of the shop database. Exit 0 OK, 1 problems, 2 could not run.",
    )
    parser.add_argument("--db", help="database file (default: $REBEL_DB, else data/shop.db)")
    args = parser.parse_args(argv)
    path = resolve_path(args.db)

    try:
        conn = open_readonly(path)
        try:
            number, name = schema_version(conn)
            facts = fingerprint(path)
            now = datetime.now().astimezone()
            header = [
                "Rebel Store Manager - integrity check (read-only)",
                f"Database : {path}",
                f"Size     : {facts['size']} bytes",
                f"Modified : {facts['mtime']} (local)",
                f"SHA-256  : {facts['sha256']}",
                f"Schema   : {name} (version {number})",
                f"Run at   : {now.strftime('%Y-%m-%d %H:%M:%S %z')} / {now.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
                "",
                "-" * 60,
            ]
            assert len(header) == HEADER_LINES
            print("\n".join(header))
            results = run_checks(conn, number)
        finally:
            conn.close()
    except CannotRun as exc:
        print(f"CANNOT RUN: {exc}")
        return 2

    for result in results:
        print("\n".join(result.render()))
    last, code = final_line(results)
    print(last)
    return code


if __name__ == "__main__":
    sys.exit(main())
