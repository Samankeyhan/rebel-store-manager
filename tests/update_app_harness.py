"""Fakes for tools.update_app: a scripted git, scripted integrity / migrate / pip / npm / build / app start-stop, over a real temp folder with a real
migrated database (so the verified backup, the sha256 and the restore are real). Nothing here runs git, npm, pip or the app."""

import hashlib
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from db.connection import init_db
from tools.run_app import frontend
from tools.update_app.context import Ctx

OLD = "a" * 40
NEW = "b" * 40


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class FakeCtx(Ctx):
    """A Ctx whose outside world is scripted. `calls` records what happened, in order."""

    def __init__(self, root: Path, **overrides):
        super().__init__(root=root, env={}, out=self._say, ask=self._ask, sleep=lambda s: None)
        self.lines: list[str] = []
        self.calls: list[str] = []
        self.answers: list[str] = ["YES"]
        self.now = self._clock().__next__
        # git
        self.branch = "main"
        self.head = OLD
        self.remote = NEW
        self.dirty: list[str] = []
        self.fetch_rc = 0
        self.ancestor_rc = 0
        self.pull_rc = 0
        self.commits = ["bbbbbbb add something"]
        self.name_status = ""
        self.changed = ""
        # processes and scripted results
        self.integrity_results: list[tuple[int, str]] = []
        self.migrate_effect = None  # a function(db) run by the fake migrate
        self.migrate_result = (0, "MIGRATION OK\n")
        self.pip_rc = 0
        self.npm_rc = 0
        self.build_error: str | None = None
        self.start_codes: list[int] = [0]
        self.stop_code = 0
        self.healthy_value = False
        self.pid_info: dict | None = None
        self.pid_ours = True
        self.pid_image: str | None = "python.exe"
        self.other = None
        self.lock_problems: list[str | None] = [None]
        self.backup_error: Exception | None = None
        self.alive_pids: set[int] = set()
        for key, value in overrides.items():
            setattr(self, key, value)

    # ----------------------------------------------------------- plumbing
    @staticmethod
    def _clock():
        moment = datetime(2026, 10, 22, 9, 0, 0)
        while True:
            yield moment
            moment += timedelta(seconds=1)

    def _say(self, text: str) -> None:
        self.lines.append(text)

    def _ask(self, prompt: str) -> str:
        self.calls.append("ask")
        if not self.answers:
            raise EOFError
        return self.answers.pop(0)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    # ----------------------------------------------------------- git
    def git(self, *args):
        self.calls.append("git " + " ".join(args[:3]))
        out = ""
        rc = 0
        if args[:2] == ("rev-parse", "--abbrev-ref"):
            out = self.branch
        elif args[:2] == ("status", "--porcelain"):
            out = "\n".join(self.dirty)
        elif args[0] == "fetch":
            rc = self.fetch_rc
        elif args == ("rev-parse", "HEAD"):
            out = self.head
        elif args == ("rev-parse", "origin/main"):
            out = self.remote
        elif args[0] == "merge-base":
            rc = self.ancestor_rc
        elif args[0] == "log":
            out = "\n".join(self.commits)
        elif args[:2] == ("diff", "--name-status"):
            out = self.name_status
        elif args[:2] == ("diff", "--name-only"):
            out = self.changed
        elif args[0] == "pull":
            rc = self.pull_rc
            if rc == 0:
                self.head = self.remote
        elif args[:2] == ("reset", "--hard"):
            self.head = args[2]
        return SimpleNamespace(returncode=rc, stdout=out + ("\n" if out else ""), stderr="boom" if rc else "")

    # ----------------------------------------------------------- processes
    def integrity(self, db):
        self.calls.append("integrity")
        return self.integrity_results.pop(0) if self.integrity_results else (0, "OK\n")

    def migrate(self, db):
        self.calls.append("migrate")
        if self.migrate_effect:
            self.migrate_effect(db)
        return self.migrate_result

    def pip_install(self):
        self.calls.append("pip")
        rc, self.pip_rc = self.pip_rc, 0  # only the first install fails; the one in the rollback works
        return rc, "pip output"

    def npm_ci(self):
        self.calls.append("npm ci")
        return self.npm_rc, "npm output"

    def build_screens(self, head):
        self.calls.append(f"build {head[:1] if head else None}")
        if self.build_error:
            raise frontend.BuildError(self.build_error)

    def app_info(self):
        return self.pid_info

    def app_is_ours(self, info):
        return self.pid_ours

    def image_of(self, pid):
        return self.pid_image

    def remove_pid_file(self):
        self.calls.append("remove pid file")
        self.pid_info = None

    def stop_app(self):
        self.calls.append("stop")
        return self.stop_code

    def start_app(self):
        self.calls.append("start")
        return self.start_codes.pop(0) if len(self.start_codes) > 1 else self.start_codes[0]

    def healthy(self):
        return self.healthy_value

    def other_server(self):
        return self.other

    def db_lock_problem(self):
        self.calls.append("lock probe")
        return self.lock_problems.pop(0) if len(self.lock_problems) > 1 else self.lock_problems[0]

    def make_backup(self, folder, keep):
        self.calls.append("backup")
        if self.backup_error:
            raise self.backup_error
        return super().make_backup(folder, keep)

    def process_alive(self, pid):
        return pid in self.alive_pids


def make_root(tmp_path: Path) -> Path:
    root = tmp_path / "shop"
    (root / ".venv" / "Scripts").mkdir(parents=True)
    (root / ".venv" / "Scripts" / "python.exe").write_bytes(b"")
    (root / "data").mkdir()
    init_db(str(root / "data" / "shop.db"))
    return root


def change_database(db) -> None:
    """What a migration would do: change the file."""
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE IF NOT EXISTS dummy_new (id INTEGER)")
    conn.commit()
    conn.close()


class Args(SimpleNamespace):
    yes = False
