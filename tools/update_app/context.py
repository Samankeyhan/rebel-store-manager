"""Everything the updater touches outside itself, in one place; tests replace the methods with fakes.
Every module the updater needs is imported here and in `__main__` before any step runs: after `git pull` the files on disk are the
NEW version, and a lazy import would mix old and new code. The updater that runs is therefore always the previous version."""

import os
import shutil
import subprocess
import sys
import time
from argparse import Namespace
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from db.backup import make_backup
from db.connection import PROJECT_ROOT
from tools.go_live_reset.__main__ import lock_problem, server_running
from tools.run_app import __main__ as run_app
from tools.run_app import frontend, procs

DB_RELATIVE = Path("data") / "shop.db"
PRE_UPDATE = Path("backups") / "pre-update"
UTF8_ENV = {"PYTHONUTF8": "1"}


@dataclass
class Ctx:
    root: Path = PROJECT_ROOT
    env: dict = field(default_factory=lambda: dict(os.environ))
    out: Callable[[str], None] = print
    ask: Callable[[str], str] = input
    run: Callable = subprocess.run
    which: Callable = shutil.which
    sleep: Callable[[float], None] = time.sleep
    now: Callable[[], datetime] = datetime.now
    python: str = sys.executable
    pid: int = field(default_factory=os.getpid)
    port: int = 8000
    no_browser: bool = False

    @property
    def db(self) -> Path:
        return (self.root / DB_RELATIVE).resolve()

    @property
    def logs(self) -> Path:
        return self.db.parent / "logs"

    @property
    def venv_python(self) -> Path:
        return self.root / ".venv" / "Scripts" / "python.exe"

    # ------------------------------------------------------------------ git / processes

    def command(self, command: list[str], cwd: Path | None = None, timeout: int = 1800):
        """Run a command, text output captured; a program that cannot start gives returncode 127 instead of raising."""
        env = dict(self.env)
        env.update(UTF8_ENV)
        try:
            return self.run(command, cwd=str(cwd or self.root), capture_output=True, text=True, encoding="utf-8",
                            errors="replace", env=env, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            return SimpleNamespace(returncode=127, stdout="", stderr=f"{type(exc).__name__}: {exc}")

    def git(self, *args: str):
        return self.command(["git", *args], timeout=600)

    def integrity(self, db: Path) -> tuple[int, str]:
        result = self.command([self.python, "-m", "tools.integrity_check", "--db", str(db)])
        return result.returncode, (result.stdout or "") + (result.stderr or "")

    def migrate(self, db: Path) -> tuple[int, str]:
        """Apply the pending migrations in a FRESH python process, so the code that was just pulled runs init_db."""
        result = self.command([self.python, "-m", "tools.update_app.migrate", "--db", str(db)])
        return result.returncode, (result.stdout or "") + (result.stderr or "")

    def pip_install(self) -> tuple[int, str]:
        result = self.command([self.python, "-m", "pip", "install", "-r", "requirements.txt"])
        return result.returncode, (result.stdout or "") + (result.stderr or "")

    def npm_ci(self) -> tuple[int, str]:
        npm = self.which("npm")
        if npm is None:
            return 127, "npm was not found (install Node.js LTS from https://nodejs.org)"
        result = self.command([npm, "ci"], cwd=self.root / "frontend")
        return result.returncode, (result.stdout or "") + (result.stderr or "")

    def build_screens(self, head: str | None) -> None:
        """npm run build for the code now on disk. Raises frontend.BuildError."""
        out_dir = Path(self.env.get("REBEL_FRONTEND_DIR") or self.root / "frontend" / "out")
        frontend.build(self.root, out_dir, self.logs / "build.log", head, self.which, self.run, self.env)

    # ------------------------------------------------------------------ the app

    def app_info(self) -> dict | None:
        return procs.read_pid(self.logs)

    def app_is_ours(self, info: dict) -> bool:
        return procs.is_ours(info, self.run)

    def image_of(self, pid: int) -> str | None:
        return procs.tasklist_image(pid, self.run)

    def remove_pid_file(self) -> None:
        procs.remove_pid(self.logs)

    def stop_app(self) -> int:
        return procs.stop(self.logs, self.out, self.run)

    def start_app(self) -> int:
        args = Namespace(rebuild=False, no_browser=self.no_browser, port=self.port, stop=False)
        env = dict(self.env)
        env["REBEL_DB"] = str(self.db)
        inner = run_app.Ctx(root=self.root, env=env, out=self.out, which=self.which, run=self.run, python=self.python)
        try:
            return run_app.start(args, inner)
        except run_app.StartError as exc:
            self.out(str(exc))
            return exc.code

    def healthy(self) -> bool:
        """The app answers /api/health on the port its pid file names (or the one it used last)."""
        info = self.app_info()
        port = info["port"] if info else procs.last_port(self.logs)
        return port is not None and procs.health_ok(port)

    def other_server(self) -> str | None:
        """Why a Rebel server seems to be running on this database (checked after our own stop), or None."""
        return server_running(self.db)

    def db_lock_problem(self) -> str | None:
        return lock_problem(self.db)

    def make_backup(self, folder: Path, keep: int) -> dict:
        return make_backup(self.db, backups_dir=folder, keep=keep)

    def process_alive(self, pid: int) -> bool:
        image = self.image_of(pid)
        return image is not None and image.lower().startswith("python")
