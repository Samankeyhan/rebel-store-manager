"""The double-click files start-rebel.cmd and stop-rebel.cmd: their text, and (on Windows) one real run of each on a temp database."""

import os
import subprocess
import sys

import pytest

from db.connection import PROJECT_ROOT, init_db
from tools.run_app import procs
from tests.test_run_app_process import make_out


def test_the_cmd_files_check_the_environment_and_call_the_module():
    start = (PROJECT_ROOT / "start-rebel.cmd").read_bytes()
    stop = (PROJECT_ROOT / "stop-rebel.cmd").read_bytes()
    for text in (start, stop):
        assert b"\r\n" in text and b"\n" not in text.replace(b"\r\n", b"")  # Windows line endings
        assert b'cd /d "%~dp0"' in text and b".venv\\Scripts\\python.exe" in text
    assert b"-m tools.run_app %*" in start and b"pip install -r requirements.txt" in start
    assert b"-m tools.run_app --stop" in stop


@pytest.mark.skipif(sys.platform != "win32", reason="runs the Windows .cmd files")
def test_the_cmd_files_start_and_stop_the_real_app_on_a_temp_database(tmp_path):
    work = tmp_path / "practice"
    work.mkdir()
    db = work / "shop.db"
    init_db(str(db))
    out = make_out(tmp_path / "out", git=None)
    env = {**os.environ, "REBEL_DB": str(db), "REBEL_FRONTEND_DIR": str(out)}
    info = None
    start = subprocess.run(
        ["cmd", "/c", r".\start-rebel.cmd", "--no-browser", "--port", "8360"],
        cwd=PROJECT_ROOT, env=env, input=b"\n", capture_output=True, timeout=120,
    )
    try:
        text = start.stdout.decode("utf-8", "replace")
        info = procs.read_pid(work / "logs")
        assert start.returncode == 0, text
        assert info is not None and procs.health_ok(info["port"], timeout=5), text
        assert "Rebel Store Manager is running." in text and str(db) in text
    finally:
        stop = subprocess.run(
            ["cmd", "/c", r".\stop-rebel.cmd"], cwd=PROJECT_ROOT, env=env, input=b"\n", capture_output=True, timeout=120
        )
        if info is not None and procs.health_ok(info["port"], timeout=1):  # never leave a test server behind
            for pid in (info["pid"], info.get("launcher")):
                if pid:
                    procs.kill_tree(pid)
    assert stop.returncode == 0, stop.stdout.decode("utf-8", "replace")
    assert procs.read_pid(work / "logs") is None and procs.health_ok(info["port"], timeout=1) is False
