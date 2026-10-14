"""CLI of the go-live reset: guards, backup, typed confirmation, then `db.go_live.apply_go_live`; prints what it does.
Dry-run (the default) changes nothing: it rehearses the real reset on an in-memory copy and prints before / after per table.
Exit codes: 0 done, dry-run fine, or already reset; 1 refused, aborted or rolled back (the database is as it was); 2 could not run."""

import argparse
import os
import socket
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from db import go_live
from db.backup import absolute_db_path
from db.connection import MIGRATIONS_DIR, PROJECT_ROOT, get_connection
from db.errors import AppError, BackupError
from tools.integrity_check.checks import run_checks
from tools.integrity_check.readonly import fingerprint, open_readonly, schema_version
from tools.integrity_check.report import CannotRun, final_line
from tools.run_app import procs

PORTS = range(8000, 8100)
LOCK_SECONDS = 2
REMINDERS = (
    "Before you start entering real data:",
    "  1. Clear the stocktake draft in EVERY browser you use (stocktake screen, 'clear draft'): a saved draft would come back with old counts.",
    "  2. Move the old invoice PDFs away (they are named invoice_INV-000001.pdf ... like the new ones will be).",
    "  3. Enter the opening stock in the stocktake screen, then run: python -m tools.integrity_check",
    "  4. A stocktake gain on a MATERIAL does not ask for a cost: type the unit cost on every material gain.",
)


def resolve_path(db_arg: str | None) -> Path:
    if db_arg:
        return Path(db_arg)
    path = Path(os.environ.get("REBEL_DB") or "data/shop.db")
    return path if path.is_absolute() else PROJECT_ROOT / path


def _utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


# ------------------------------------------------------------------ guards


def _listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def _answers_health(port: int) -> bool:
    for url_path in ("/api/health", "/health"):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{url_path}", timeout=1) as response:
                if response.status == 200:
                    return True
        except (OSError, urllib.error.URLError, ValueError):
            continue
    return False


def server_running(db_path: Path) -> str | None:
    """Why the app seems to be running on this database, or None. The pid file lives in logs/ next to the database."""
    logs = db_path.parent / "logs"
    info = procs.read_pid(logs)
    if info is not None and procs.is_ours(info):
        return f"the app is running (pid {info['pid']}, port {info['port']})"
    ports = set(PORTS)
    if info is not None:
        ports.add(info["port"])
    last = procs.last_port(logs)
    if last is not None:
        ports.add(last)
    for port in sorted(ports):
        if _listening(port) and _answers_health(port):
            return f"a Rebel server answers on port {port}"
    return None


def lock_problem(db_path: Path) -> str | None:
    """Why the database cannot be locked now (another program has it open for writing), or None."""
    conn = sqlite3.connect(db_path, timeout=LOCK_SECONDS, isolation_level=None)
    try:
        conn.execute("BEGIN EXCLUSIVE")
        conn.execute("ROLLBACK")
        return None
    except sqlite3.OperationalError as exc:
        return f"the database is locked ({exc})"
    finally:
        conn.close()


def head_schema() -> int:
    return int(max(p.name for p in MIGRATIONS_DIR.glob("*.sql")).split("_", 1)[0])


def integrity_verifier(conn: sqlite3.Connection) -> list[str]:
    """Problems found by the integrity checks on `conn` (FAIL, WARN or ERROR; SKIPPED and INFO are fine)."""
    number, _ = schema_version(conn)
    problems = []
    for result in run_checks(conn, number):
        if result.fails or result.warns or result.error is not None:
            problems.append(" / ".join(line.strip() for line in result.render()))
    return problems


# ---------------------------------------------------------------- reporting


def _table(before: dict, after: dict | None) -> list[str]:
    lines = [f"  {'table':<30}{'class':<12}{'before':>8}" + (f"{'after':>8}" if after is not None else "")]
    for table in sorted(before):
        cls = go_live.TABLE_CLASS.get(table, "?")
        line = f"  {table:<30}{cls:<12}{before[table]:>8}"
        if after is not None:
            line += f"{after.get(table, 0):>8}"
            if before[table] != after.get(table, 0):
                line += "  <- changed"
        lines.append(line)
    return lines


def _invoice_pdfs() -> int:
    folder = PROJECT_ROOT / "invoices"
    return len(list(folder.glob("*.pdf"))) if folder.is_dir() else 0


def _describe(result: dict, out) -> None:
    out("Table by table:")
    for line in _table(result["before"], result["after"]):
        out(line)
    merge = result["merge"]
    if merge:
        out(f"Payment methods: id {merge['duplicate_id']} merged into id {merge['survivor_id']} (DigiPay); "
            f"{result['references_repointed']} references re-pointed.")
    else:
        out("Payment methods: no duplicate to merge.")
    for key, was in result["values_before"].items():
        now = result["values_after"][key]
        if was != now:
            out(f"  {key}: {was} -> {now}")
    out("Counters restart: INV and PUR at 0 (the next sale is INV-000001, the next purchase PUR-000001).")


def _reminders(out) -> None:
    out("")
    out(f"Old invoice PDFs in the project's invoices folder: {_invoice_pdfs()} (this tool deletes nothing).")
    for line in REMINDERS:
        out(line)


# --------------------------------------------------------------------- main


def main(argv=None, *, input_fn=input, out=print, server_check=server_running, backup=None) -> int:
    _utf8_output()
    parser = argparse.ArgumentParser(
        prog="python -m tools.go_live_reset",
        description="One-time go-live reset: turns the test database into a clean production database. Default is a dry-run. "
                    "Exit 0 done, 1 refused or rolled back, 2 could not run.",
    )
    parser.add_argument("--db", help="database file (default: $REBEL_DB, else data/shop.db)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="change nothing, show before / after (the default)")
    mode.add_argument("--apply", action="store_true", help="do the reset (asks for a typed confirmation)")
    parser.add_argument("--product-unit-cost", choices=go_live.PRODUCT_COST_CHOICES, default="null",
                        help="unit cost of every product after the reset (default null = 'unknown, enter it')")
    parser.add_argument("--reset-service-costs", action="store_true",
                        help="also set the unit cost of SERVICE materials to 0 (default: they keep it)")
    args = parser.parse_args(argv)
    path = resolve_path(args.db)
    if backup is None:
        from db.backup import make_backup as backup

    # ---- can it run at all (exit 2)
    try:
        conn = open_readonly(path)
        try:
            number, name = schema_version(conn)
            if number != head_schema():
                raise CannotRun(f"the database is at schema {number:03d}; start the app once so it is migrated to {head_schema():03d}")
            missing = go_live.unclassified_tables(conn)
            if missing:
                raise CannotRun(f"tables without a go-live class: {missing}")
            facts_before = fingerprint(path)
            state = go_live.assess(conn, args.product_unit_cost, args.reset_service_costs)
            try:
                go_live.payment_method_merge(conn)
            except AppError as exc:
                raise CannotRun(str(exc)) from None
            memory = sqlite3.connect(":memory:", isolation_level=None)
            conn.backup(memory)
            memory.row_factory = sqlite3.Row
            memory.execute("PRAGMA foreign_keys = ON")
        finally:
            conn.close()
    except (CannotRun, sqlite3.Error) as exc:
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            out(f"REFUSED: the database is locked ({exc}). Close every program using it (stop-rebel.cmd), then try again. Nothing was changed.")
            return 1
        out(f"CANNOT RUN: {exc}")
        return 2

    out("Rebel Store Manager - go-live reset " + ("(APPLY)" if args.apply else "(dry-run, changes nothing)"))
    out(f"Database : {path}")
    out(f"Schema   : {name}")
    out(f"Size     : {facts_before['size']} bytes, modified {facts_before['mtime']}, sha256 {facts_before['sha256']}")
    out(f"Options  : product unit cost -> {args.product_unit_cost}; SERVICE material costs -> "
        f"{'0' if args.reset_service_costs else 'kept'}")
    out("-" * 60)

    if state["state"] == "live":
        memory.close()
        out("REFUSED: this database already went live and holds data; the reset never erases a live database.")
        out(f"  marker: {', '.join(state['markers'])}; data: {'; '.join(state['problems'])}")
        out("  To rehearse again, copy a backup into its own folder under data\\restore-test\\ and run the tool there.")
        return 1
    if state["state"] == "already_reset":
        memory.close()
        out(f"Already reset ({', '.join(state['markers'])}): nothing to do, nothing was changed.")
        return 0

    # ---- rehearsal on an in-memory copy (the dry-run's before / after, and the apply's preview)
    try:
        with tempfile.TemporaryDirectory() as scratch:
            rehearsal = go_live.apply_go_live(
                memory, Path(scratch) / "rehearsal.jsonl", args.product_unit_cost, args.reset_service_costs,
                verify=integrity_verifier,
            )
    except AppError as exc:
        out(f"REFUSED by the rehearsal (nothing was changed): {exc}")
        return 1
    finally:
        memory.close()
    _describe(rehearsal, out)
    out("Integrity checks on the result of the rehearsal: all clear (no FAIL, WARN or ERROR).")

    if not args.apply:
        facts_after = fingerprint(path)
        same = facts_after == facts_before
        out(f"The database file is {'unchanged' if same else 'CHANGED (unexpected!)'}: {facts_after['size']} bytes, sha256 {facts_after['sha256']}.")
        _reminders(out)
        out("Dry-run only. To do it for real: stop the app, then run again with --apply.")
        return 0 if same else 1

    # ---- apply: server, lock, confirmation, backup, the reset
    reason = server_check(path)
    if reason is None:
        reason = lock_problem(path)
    if reason is not None:
        out(f"REFUSED: {reason}. Run stop-rebel.cmd (and close every program using the database), then try again. Nothing was changed.")
        return 1

    phrase = f"RESET {path.name}"
    folder = absolute_db_path(path).parent
    out("")
    out("THIS ERASES every order, purchase, production batch, expense, settlement, postage payment, stock movement and the audit log.")
    out(f"A verified backup is made first, in {folder / 'backups' / 'pre-go-live'}")
    out(f"Type exactly   {phrase}   and press Enter to continue; anything else cancels.")
    try:
        typed = input_fn("> ")
    except EOFError:
        typed = ""
    if typed.replace("﻿", "").strip() != phrase:  # a piped answer from Windows PowerShell can start with a BOM
        out("Cancelled: the confirmation did not match. Nothing was changed.")
        return 1

    try:
        made = backup(path, backups_dir=folder / "backups" / "pre-go-live")
    except BackupError as exc:
        out(f"ABORTED: the backup failed ({exc}). Nothing was changed.")
        return 1
    out(f"Backup   : {made['path']} ({made['size']} bytes, checked)")

    conn = get_connection(str(absolute_db_path(path)))
    try:
        result = go_live.apply_go_live(
            conn, go_live.archive_path_for(folder), args.product_unit_cost, args.reset_service_costs,
            verify=integrity_verifier,
        )
    except Exception as exc:
        out(f"ROLLED BACK: {exc}")
        out(f"The database is as it was. The backup stays at {made['path']}.")
        return 1
    finally:
        conn.close()

    out("DONE. The reset was applied in one transaction.")
    _describe(result, out)
    out(f"Audit log: {result['archive']['rows']} rows archived to {result['archive']['path']} "
        f"(sha256 {result['archive']['sha256'][:16]}), one reset row left.")
    out(f"Marker   : {', '.join(result['markers'])}")

    check = open_readonly(path)
    try:
        number, _ = schema_version(check)
        results = run_checks(check, number)
    finally:
        check.close()
    for item in results:
        out("\n".join(item.render()))
    last, code = final_line(results)
    out(last)
    facts_after = fingerprint(path)
    out(f"Database now: {facts_after['size']} bytes, modified {facts_after['mtime']}, sha256 {facts_after['sha256']}")
    _reminders(out)
    if code != 0:
        out(f"The integrity check after the commit is not OK. Restore {made['path']} (docs/RUNNING.md, section 4) and report this.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
