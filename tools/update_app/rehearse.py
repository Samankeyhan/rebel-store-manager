"""`--rehearse PATH`: run the next migrations on a COPY of a database and prove nothing in it changed.
The copy is made with SQLite's backup API into data/restore-test/rehearsal-<moment>/shop.db (so backups and logs the migration writes land in
that folder). Steps: integrity before, figures before, init_db in a fresh process, integrity after, figures after, compare.
Never touches git, the app, data/shop.db, data/backups or data/logs; a path inside data/ (outside data/restore-test) is refused."""

import sqlite3
from pathlib import Path

from tools.update_app import invariants
from tools.update_app.context import Ctx
from tools.update_app.fsutil import sha256_file, sqlite_copy
from tools.update_app.steps import failing_lines, moment_of


def _inside(path: Path, folder: Path) -> bool:
    return path == folder or folder in path.parents


def rehearse(ctx: Ctx, raw_path: str) -> int:
    say = ctx.out
    source = Path(raw_path)
    source = (source if source.is_absolute() else Path.cwd() / source).resolve()
    data = (ctx.root / "data").resolve()
    if _inside(source, data) and not _inside(source, data / "restore-test"):
        say(f"Refused: {source} is inside the real data folder. Rehearse on a copy in data\\restore-test\\<name>\\ instead.")
        return 1
    if not source.is_file():
        say(f"Could not run: {source} does not exist.")
        return 2
    folder = data / "restore-test" / f"rehearsal-{moment_of(ctx)}"
    copy = folder / "shop.db"
    try:
        sqlite_copy(source, copy)
    except (OSError, sqlite3.Error) as exc:
        say(f"Could not run: the copy failed ({type(exc).__name__}: {exc})")
        return 2
    say(f"Rehearsal copy: {copy}  (sha256 {sha256_file(copy)[:16]})")

    code, text = ctx.integrity(copy)
    if code != 0:
        say(f"REHEARSAL FAILED: the integrity check before found problems (exit {code}):\n{failing_lines(text)}")
        return 1
    try:
        before = invariants.collect(copy)
    except Exception as exc:  # figures that cannot be read are as bad as figures that differ
        say(f"Could not run: the figures before could not be read ({type(exc).__name__}: {exc})")
        return 2
    code, text = ctx.migrate(copy)
    for line in text.splitlines():
        say(f"  {line}")
    if code != 0:
        say("REHEARSAL FAILED: the migration failed.")
        return 1
    code, text = ctx.integrity(copy)
    if code != 0:
        say(f"REHEARSAL FAILED: the integrity check after found problems (exit {code}):\n{failing_lines(text)}")
        return 1
    try:
        after = invariants.collect(copy)
    except Exception as exc:
        say(f"REHEARSAL FAILED: the figures after could not be read ({type(exc).__name__}: {exc})")
        return 1
    new_files = sorted(p.name for p in (ctx.root / "migrations").glob("*.sql") if p.name not in set(before["migrations"]))
    failures, info = invariants.compare(before, after, new_files)
    say(f"Tables compared: {len(set(before['counts']) & set(after['counts']))}; materials {len(before['materials'])}; products {len(before['products'])}; "
        f"settlements {before['settlements']['count']}; new migrations applied: {len(set(after['migrations']) - set(before['migrations']))}")
    for line in info:
        say(f"  INFO {line}")
    if failures:
        say("REHEARSAL FAILED: figures changed:")
        for line in failures:
            say(f"  DIFF {line}")
        return 1
    say("REHEARSAL OK: every figure is the same before and after.")
    return 0
