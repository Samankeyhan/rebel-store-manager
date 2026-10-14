"""python -m tools.run_app [--rebuild] [--no-browser] [--port N]   start the app (the .cmd file does this)
python -m tools.run_app --stop                                    stop it (after a best-effort backup)

Starts ONE detached process, `api.serve:app` (screens at /, API at /api) on 127.0.0.1, waits until it answers, opens the browser.
By default (REBEL_DB not set) it uses data/shop.db: that is the owner's daily use. An existing REBEL_DB is honoured and the
database file in use is always printed. Exit codes: 0 ok, 1 could not start / could not stop, 2 the environment is not ready."""

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from db.backup import backups_dir_for, list_backups
from db.connection import PROJECT_ROOT
from tools.run_app import frontend, ports, procs

DEFAULT_DB = "data/shop.db"


class StartError(Exception):
    """A clear, plain-language reason the app cannot start; `code` is the exit code."""

    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


@dataclass
class Ctx:
    """Everything the script touches outside itself; tests pass fakes."""

    root: Path = PROJECT_ROOT
    env: dict = field(default_factory=lambda: dict(os.environ))
    out: Callable[[str], None] = print
    which: Callable = shutil.which
    run: Callable = subprocess.run
    popen: Callable = subprocess.Popen
    health: Callable[[int], bool] = procs.health_ok
    busy: Callable[[int], bool] = ports.is_busy
    open_browser: Callable[[str], object] = webbrowser.open
    sleep: Callable[[float], None] = time.sleep
    python: str = sys.executable
    version: tuple = tuple(sys.version_info[:3])
    wait_seconds: float = 30.0


# ------------------------------------------------------------------ checks


def check_environment(ctx: Ctx) -> None:
    if ctx.version < (3, 11):
        raise StartError(
            f"Python 3.11 or newer is needed (this is {'.'.join(map(str, ctx.version))}).\n"
            "Recreate the environment with a newer Python: python -m venv .venv ; .venv\\Scripts\\pip install -r requirements.txt"
        )
    missing = [name for name in ("fastapi", "uvicorn") if importlib.util.find_spec(name) is None]
    if missing:
        raise StartError(
            f"Python packages are missing ({', '.join(missing)}).\n"
            "Open PowerShell in the project folder and run: .venv\\Scripts\\pip install -r requirements.txt"
        )


def choose_database(ctx: Ctx) -> tuple[Path, bool]:
    """(the database file to use, True when it does not exist yet and will be created empty)."""
    explicit = ctx.env.get("REBEL_DB")
    raw = Path(explicit or DEFAULT_DB)
    path = (raw if raw.is_absolute() else ctx.root / raw).resolve()
    data_folder = (ctx.root / "data").resolve()
    if explicit and not path.is_file():
        raise StartError(
            f"REBEL_DB points to a file that does not exist: {path}\n"
            "Check the path, or remove REBEL_DB to use data\\shop.db (PowerShell: Remove-Item Env:REBEL_DB)."
        )
    if explicit and path.parent == data_folder and path.name != "shop.db":
        raise StartError(
            f"REBEL_DB is {path}, inside the real data folder.\n"
            "Backups and logs are kept next to the database file, so a practice copy here would write into data\\backups.\n"
            "Put the copy in its own folder, for example data\\restore-test\\shop.db, and point REBEL_DB at that."
        )
    return path, not path.is_file()


# ------------------------------------------------------------------- start


def summary(ctx: Ctx, url: str, db: Path, logs: Path) -> None:
    backups = backups_dir_for(db)
    found = list_backups(backups)
    newest = f"{len(found)} kept, newest {found[0]['name']}" if found else "none yet"
    ctx.out("")
    ctx.out("Rebel Store Manager is running.")
    ctx.out(f"  Open       : {url}")
    ctx.out(f"  Database   : {db}")
    ctx.out(f"  Backups    : {backups}  ({newest})")
    ctx.out(f"  Logs       : {logs}")
    ctx.out("  To stop    : double-click stop-rebel.cmd  (it makes a backup first)")


def start(args: argparse.Namespace, ctx: Ctx) -> int:
    say = ctx.out
    check_environment(ctx)
    db, is_new = choose_database(ctx)
    logs = db.parent / "logs"
    say(f"Database file: {db}")
    if is_new:
        say("NOTE: this file does not exist yet: a NEW EMPTY DATABASE will be created.")

    info = procs.read_pid(logs)
    if info is not None:
        if procs.is_ours(info, ctx.run) and ctx.health(info["port"]):
            url = f"http://localhost:{info['port']}/"
            say(f"Rebel Store Manager is already running at {url}")
            if not args.no_browser:
                ctx.open_browser(url)
            return 0
        procs.remove_pid(logs)  # a leftover file of a server that is gone

    out_dir = Path(ctx.env.get("REBEL_FRONTEND_DIR") or ctx.root / "frontend" / "out")
    head = frontend.git_head(ctx.root, ctx.run)
    state, reason = frontend.build_state(out_dir, head, args.rebuild)
    if state == "build":
        say(f"Building the screens ({reason}). This takes a minute or two...")
        try:
            frontend.build(ctx.root, out_dir, logs / "build.log", head, ctx.which, ctx.run, ctx.env)
        except frontend.BuildError as exc:
            say(str(exc))
            say(f"Last lines of the build log ({logs / 'build.log'}):\n{procs.tail(logs / 'build.log')}")
            return 1
        say("The screens are built.")
    elif state == "older":
        say(f"NOTICE: {reason}. If you updated the app with git pull, run: start-rebel.cmd --rebuild")

    ranges = ports.excluded_ranges(ctx.run)
    try:
        port, busy, reserved = ports.find_port(args.port, ranges=ranges, busy=ctx.busy)
    except ports.NoFreePort as exc:
        raise StartError(str(exc), 1) from None
    if busy or reserved:
        say(f"Skipped ports: busy {busy or 'none'}, reserved by Windows {reserved or 'none'}.")
    previous = procs.last_port(logs)
    if previous is not None and previous != port:
        say(f"NOTE: the port is {port}, last time it was {previous}. Browser memory (a half-typed stocktake) belongs to one port.")

    env = dict(ctx.env)
    env["REBEL_DB"] = str(db)
    env["PYTHONUTF8"] = "1"
    command = [ctx.python, "-m", "uvicorn", "api.serve:app", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"]
    process = procs.start_detached(command, env, ctx.root, logs / procs.SERVER_LOG, ctx.popen)
    procs.write_pid(logs, process.pid, port, str(db))
    say(f"Starting the server on port {port}...")
    if not procs.wait_until_up(port, process, ctx.wait_seconds, ctx.health, ctx.sleep):
        procs.kill_tree(process.pid, ctx.run)
        procs.remove_pid(logs)
        say(f"The server did not start within {int(ctx.wait_seconds)} seconds.")
        say(f"Last lines of {logs / procs.SERVER_LOG}:\n{procs.tail(logs / procs.SERVER_LOG)}")
        return 1
    server_pid = procs.listening_pid(port, ctx.run) or process.pid
    procs.write_pid(logs, server_pid, port, str(db), launcher=process.pid)
    url = f"http://localhost:{port}/"
    if not args.no_browser:
        ctx.open_browser(url)
    summary(ctx, url, db, logs)
    return 0


def stop(ctx: Ctx) -> int:
    db, _ = choose_database(ctx)
    return procs.stop(db.parent / "logs", ctx.out, ctx.run)


def main(argv: list[str] | None = None, ctx: Ctx | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(prog="python -m tools.run_app", description="Start or stop Rebel Store Manager.")
    parser.add_argument("--stop", action="store_true", help="stop the running app (after a best-effort backup)")
    parser.add_argument("--rebuild", action="store_true", help="rebuild the screens first (after a git pull)")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument("--port", type=int, default=ports.DEFAULT_PORT, help="first port to try (default 8000)")
    args = parser.parse_args(argv)
    ctx = ctx or Ctx()
    try:
        return stop(ctx) if args.stop else start(args, ctx)
    except StartError as exc:
        ctx.out(str(exc))
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
