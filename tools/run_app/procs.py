"""The pid file, "is this process really ours?", detached start, log rotation, and stopping.
Files live in the `logs/` folder next to the database in use: `rebel.pid.json` {pid, port, db, started} while the server
runs, `run-state.json` {last_port} for good.
Stopping kills nothing unless the pid is a python process AND that process is listening on the port written in the pid file;
otherwise it prints "not running or not ours"."""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable

PID_FILE = "rebel.pid.json"
STATE_FILE = "run-state.json"
SERVER_LOG = "server.out.log"
LOG_BYTES = 1_000_000
LOG_KEEP = 5

NOT_OURS = "not running or not ours"


# ------------------------------------------------------------------ state files


def write_pid(logs: Path, pid: int, port: int, db: str, launcher: int | None = None) -> None:
    """`pid` is the server process (the one listening on `port`); `launcher` is the process that started it (a virtual
    environment's python.exe is a small launcher that runs the real interpreter as its child: both must go when stopping)."""
    logs.mkdir(parents=True, exist_ok=True)
    data = {"pid": pid, "launcher": launcher, "port": port, "db": db, "started": datetime.now().isoformat(timespec="seconds")}
    (logs / PID_FILE).write_text(json.dumps(data), encoding="utf-8")
    (logs / STATE_FILE).write_text(json.dumps({"last_port": port}), encoding="utf-8")


def read_pid(logs: Path) -> dict | None:
    try:
        data = json.loads((logs / PID_FILE).read_text(encoding="utf-8"))
        return data if isinstance(data.get("pid"), int) and isinstance(data.get("port"), int) else None
    except (OSError, ValueError, AttributeError):
        return None


def remove_pid(logs: Path) -> None:
    try:
        (logs / PID_FILE).unlink()
    except OSError:
        pass


def last_port(logs: Path) -> int | None:
    try:
        value = json.loads((logs / STATE_FILE).read_text(encoding="utf-8")).get("last_port")
        return value if isinstance(value, int) else None
    except (OSError, ValueError, AttributeError):
        return None


# -------------------------------------------------------------- is it ours?


def tasklist_image(pid: int, run: Callable = subprocess.run) -> str | None:
    """The image name of a running process ("python.exe"), or None when there is no such process."""
    try:
        result = run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    for line in (result.stdout or "").splitlines():
        parts = [part.strip('"') for part in line.split('","')]
        if len(parts) >= 2 and parts[1].strip('"') == str(pid):
            return parts[0].strip('"')
    return None


def listening_pid(port: int, run: Callable = subprocess.run) -> int | None:
    """The pid that listens on 127.0.0.1/0.0.0.0:port according to netstat, or None."""
    try:
        result = run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    for line in (result.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
            if parts[1].rsplit(":", 1)[-1] == str(port) and parts[4].isdigit():
                return int(parts[4])
    return None


def is_ours(info: dict, run: Callable = subprocess.run) -> bool:
    """The pid file's process is a python process and it listens on the port the pid file names."""
    image = tasklist_image(info["pid"], run)
    if image is None or not image.lower().startswith("python"):
        return False
    return listening_pid(info["port"], run) == info["pid"]


def health_ok(port: int, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False


# ------------------------------------------------------------------- logs


def rotate(path: Path, max_bytes: int = LOG_BYTES, keep: int = LOG_KEEP) -> None:
    """Shift `server.out.log` to `.1 … .keep` when it is over `max_bytes` (the oldest falls off)."""
    try:
        if not path.is_file() or path.stat().st_size <= max_bytes:
            return
        oldest = path.with_name(f"{path.name}.{keep}")
        if oldest.exists():
            oldest.unlink()
        for number in range(keep - 1, 0, -1):
            source = path.with_name(f"{path.name}.{number}")
            if source.exists():
                os.replace(source, path.with_name(f"{path.name}.{number + 1}"))
        os.replace(path, path.with_name(f"{path.name}.1"))
    except OSError:
        pass  # rotating is housekeeping; the server must still start


def tail(path: Path, lines: int = 20) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return "(no log yet)"


# ------------------------------------------------------------------- start


def start_detached(command: list[str], env: dict, cwd: Path, log_path: Path, popen: Callable = subprocess.Popen):
    """Start the server without a console window, output into the log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rotate(log_path)
    log = open(log_path, "ab")
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": log, "stderr": subprocess.STDOUT, "cwd": str(cwd), "env": env}
    if sys.platform == "win32":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        kwargs["creationflags"] = flags | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    else:
        kwargs["start_new_session"] = True
    try:
        return popen(command, **kwargs)
    finally:
        log.close()


def wait_until_up(port: int, process, seconds: float = 30.0, health: Callable = health_ok, sleep: Callable = time.sleep) -> bool:
    """Poll the health URL until it answers; give up early when the process has already ended."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if health(port):
            return True
        if process.poll() is not None:
            return False
        sleep(0.5)
    return False


# -------------------------------------------------------------------- stop


def ask_for_backup(port: int, timeout: float = 15.0) -> tuple[bool, str]:
    """POST /api/backups, best effort, short timeout. (True, name) or (False, reason)."""
    request = urllib.request.Request(f"http://127.0.0.1:{port}/api/backups", data=b"", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            return True, str(body.get("name", ""))
    except urllib.error.HTTPError as exc:
        return False, f"the server answered {exc.code}"
    except (OSError, urllib.error.URLError, ValueError) as exc:
        return False, type(exc).__name__


def kill_tree(pid: int, run: Callable = subprocess.run) -> bool:
    try:
        result = run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return getattr(result, "returncode", 1) == 0


def stop(
    logs: Path,
    out: Callable[[str], None] = print,
    run: Callable = subprocess.run,
    backup: Callable[[int], tuple[bool, str]] = ask_for_backup,
    kill: Callable[[int], bool] | None = None,
) -> int:
    """0 stopped, 1 not running or not ours (nothing was killed), 2 the process would not die."""
    info = read_pid(logs)
    if info is None:
        out("Rebel Store Manager is not running (no pid file).")
        return 1
    if not is_ours(info, run):
        out(f"{NOT_OURS}: pid {info['pid']} is not a python process listening on port {info['port']}. Nothing was stopped.")
        if tasklist_image(info["pid"], run) is None:
            remove_pid(logs)  # a stale file: its process is gone
            out("(The old pid file was removed.)")
        return 1
    ok, detail = backup(info["port"])
    out(f"Backup before stopping: {detail} saved." if ok else f"WARNING: no backup was made before stopping ({detail}). Stopping anyway.")
    killer = kill or (lambda pid: kill_tree(pid, run))
    if not killer(info["pid"]):
        out(f"Could not stop process {info['pid']}. Close it from Task Manager (python.exe).")
        return 2
    launcher = info.get("launcher")
    if isinstance(launcher, int) and launcher != info["pid"]:
        image = tasklist_image(launcher, run)
        if image is not None and image.lower().startswith("python"):
            killer(launcher)  # the launcher normally ended with its child; a lingering python launcher goes too
    remove_pid(logs)
    out("Stopped.")
    return 0
