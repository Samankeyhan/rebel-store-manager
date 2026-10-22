"""Undo a failed (or interrupted) update, in this order: keep the failed database for diagnosis, verify the pre-update backup, put it back
over shop.db (sha256 checked), `git reset --hard <old HEAD>`, reinstall dependencies when requirements.txt / package-lock.json differ between
the two commits, rebuild the screens, start the old version. `restore_db=False` (a failed `git pull` with HEAD unchanged) only restarts the app.
Returns 1 = rolled back, 2 = the rollback itself failed (the message gives the manual commands, docs/RUNNING.md section 6a)."""

import os
import shutil
import sqlite3
from pathlib import Path

from tools.run_app import frontend
from tools.update_app.context import PRE_UPDATE, Ctx
from tools.update_app.fsutil import sha256_file, sqlite_copy
from tools.update_app.log import UpdateLog

LOCKFILE = "frontend/package-lock.json"
REQUIREMENTS = "requirements.txt"


class RollbackError(Exception):
    pass


def keep_failed_database(ctx: Ctx, log: UpdateLog, moment: str) -> Path | None:
    """Best effort: a consistent copy of the migrated database as `backups/pre-update/shop-failed-update-<moment>.db`."""
    target = ctx.db.parent / PRE_UPDATE / f"shop-failed-update-{moment}.db"
    try:
        sqlite_copy(ctx.db, target)
    except (OSError, sqlite3.Error) as exc:
        log.line(f"could not keep the failed database ({type(exc).__name__}: {exc}); continuing")
        return None
    log.line(f"failed database kept as {target}")
    return target


def restore_database(ctx: Ctx, backup_path: Path, expected_sha: str, log: UpdateLog) -> None:
    if not backup_path.is_file():
        raise RollbackError(f"the pre-update backup is missing: {backup_path}")
    if sha256_file(backup_path) != expected_sha:
        raise RollbackError(f"the pre-update backup does not match its recorded sha256 ({backup_path}); nothing was restored")
    temp = ctx.db.with_name(ctx.db.name + ".restore-tmp")
    shutil.copyfile(backup_path, temp)
    if sha256_file(temp) != expected_sha:
        temp.unlink(missing_ok=True)
        raise RollbackError("the copy of the backup does not match its sha256; shop.db was not replaced")
    os.replace(temp, ctx.db)
    for suffix in ("-wal", "-shm", "-journal"):
        ctx.db.with_name(ctx.db.name + suffix).unlink(missing_ok=True)
    if sha256_file(ctx.db) != expected_sha:
        raise RollbackError("shop.db does not match the backup after the restore")
    log.line(f"database restored from {backup_path}; sha256 verified {expected_sha}")


def _run(ctx: Ctx, log: UpdateLog, what: str, result: tuple[int, str]) -> None:
    code, text = result
    log.line(f"{what}: exit {code}\n{text.strip()[-2000:]}")
    if code != 0:
        raise RollbackError(f"{what} failed")


def roll_back(ctx: Ctx, state: dict, log: UpdateLog, moment: str, reason: str, restore_db: bool) -> int:
    say = ctx.out
    old_head = state["old_head"]
    log.line(f"ROLLBACK START ({reason}); restore_db={restore_db}")
    say(f"Going back to the previous version ({reason})...")
    try:
        backup_path = Path(state["backup_path"]) if state.get("backup_path") else None
        if restore_db:
            if backup_path is None or not state.get("backup_sha256"):
                raise RollbackError("no pre-update backup was recorded")
            keep_failed_database(ctx, log, moment)
            if not backup_path.is_file() or sha256_file(backup_path) != state["backup_sha256"]:
                raise RollbackError(f"the pre-update backup is missing or does not match its sha256: {backup_path}")
        head = ctx.git("rev-parse", "HEAD").stdout.strip()
        moved = head != old_head
        changed: set[str] = set()
        if moved:
            changed = {line for line in (ctx.git("diff", "--name-only", head, old_head).stdout or "").splitlines() if line.strip()}
        if restore_db:
            restore_database(ctx, backup_path, state["backup_sha256"], log)
            say("The database is restored from the pre-update backup (checked).")
        if moved:
            reset = ctx.git("reset", "--hard", old_head)
            log.line(f"git reset --hard {old_head}: exit {reset.returncode} {(reset.stderr or '').strip()}")
            if reset.returncode != 0:
                raise RollbackError("git reset --hard failed")
            if REQUIREMENTS in changed:
                _run(ctx, log, "pip install -r requirements.txt (old version)", ctx.pip_install())
            if LOCKFILE in changed:
                _run(ctx, log, "npm ci (old version)", ctx.npm_ci())
            try:
                ctx.build_screens(old_head)
            except frontend.BuildError as exc:
                raise RollbackError(f"rebuilding the old screens failed: {exc}") from None
            log.line("old screens rebuilt")
        code = ctx.start_app()
        log.line(f"start the old version: exit {code}")
        if code != 0:
            raise RollbackError("the old version did not start")
    except RollbackError as exc:
        log.line(f"ROLLBACK FAILED: {exc}")
        say(f"THE ROLLBACK FAILED: {exc}")
        say(f"Your data is safe in the backup {state.get('backup_path')}. Do the manual steps in docs/RUNNING.md section 6a (old HEAD {old_head}).")
        say(f"Log: {log.path}")
        return 2
    log.line("ROLLBACK DONE")
    say(f"Rolled back to {old_head[:10]}. " + ("Your data is as it was before the update. " if restore_db else "Nothing in your data changed. "))
    say("به‌روزرسانی ناموفق بود و برنامه به نسخهٔ قبلی برگشت.")
    say(f"Log: {log.path}")
    return 1
