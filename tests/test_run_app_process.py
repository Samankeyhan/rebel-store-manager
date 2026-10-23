"""tools/run_app: the pid file, "is it ours", stop, log rotation, the build rules, database choice and the whole start flow, with
fakes for everything outside the script; plus one real start and stop on a temp database."""

import json
import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from db.backup import backups_dir_for, list_backups
from db.connection import PROJECT_ROOT, init_db
from tools.run_app import __main__ as app
from tools.run_app import frontend, procs

TASKLIST_PY = '"python.exe","4242","Console","1","52,000 K"\n'
TASKLIST_NOTEPAD = '"notepad.exe","4242","Console","1","9,000 K"\n'
TASKLIST_NONE = "INFO: No tasks are running which match the specified criteria.\n"
NETSTAT = """
Active Connections

  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       1000
  TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       4242
  TCP    127.0.0.1:8001         0.0.0.0:0              LISTENING       777
  TCP    127.0.0.1:50000        127.0.0.1:8000         ESTABLISHED     4242
"""


def runner(tasklist=TASKLIST_PY, netstat=NETSTAT):
    def run(command, **kwargs):
        name = command[0]
        text = tasklist if name == "tasklist" else netstat if name == "netstat" else ""
        return SimpleNamespace(returncode=0, stdout=text, stderr="")

    return run


# -------------------------------------------------------------------- state files


def test_the_pid_file_round_trips_and_a_bad_one_is_ignored(tmp_path):
    procs.write_pid(tmp_path, 4242, 8000, "C:\\x\\shop.db")
    assert procs.read_pid(tmp_path)["pid"] == 4242 and procs.read_pid(tmp_path)["port"] == 8000
    assert procs.last_port(tmp_path) == 8000
    procs.remove_pid(tmp_path)
    assert procs.read_pid(tmp_path) is None and procs.last_port(tmp_path) == 8000  # the last port is remembered
    (tmp_path / procs.PID_FILE).write_text("{broken")
    assert procs.read_pid(tmp_path) is None
    (tmp_path / procs.PID_FILE).write_text(json.dumps({"pid": "x", "port": 1}))
    assert procs.read_pid(tmp_path) is None


# ------------------------------------------------------------------ is it ours?


def test_tasklist_and_netstat_are_parsed():
    assert procs.tasklist_image(4242, runner()) == "python.exe"
    assert procs.tasklist_image(4242, runner(TASKLIST_NONE)) is None
    assert procs.listening_pid(8000, runner()) == 4242
    assert procs.listening_pid(8001, runner()) == 777
    assert procs.listening_pid(9999, runner()) is None  # nothing listens; the ESTABLISHED line is not a listener
    assert procs.listening_pid(50000, runner()) is None


def test_a_process_is_ours_only_if_python_and_listening_on_the_recorded_port():
    info = {"pid": 4242, "port": 8000}
    assert procs.is_ours(info, runner()) is True
    assert procs.is_ours(info, runner(TASKLIST_NOTEPAD)) is False  # a recycled pid: not python
    assert procs.is_ours({"pid": 4242, "port": 8001}, runner()) is False  # python, but the port belongs to another pid
    assert procs.is_ours({"pid": 4242, "port": 9999}, runner()) is False  # python, not listening anywhere
    assert procs.is_ours(info, runner(TASKLIST_NONE)) is False


# -------------------------------------------------------------------------- stop


def test_stop_without_a_pid_file_says_not_running(tmp_path):
    lines = []
    assert procs.stop(tmp_path, lines.append, runner(), kill=lambda pid: pytest.fail("must not kill")) == 1
    assert "not running" in lines[0]


def test_stop_kills_nothing_that_is_not_ours(tmp_path):
    procs.write_pid(tmp_path, 4242, 8000, "db")
    lines = []
    killed = []
    code = procs.stop(tmp_path, lines.append, runner(TASKLIST_NOTEPAD), kill=killed.append, backup=lambda port: pytest.fail("no backup either"))
    assert code == 1 and killed == []
    assert any("not running or not ours" in line for line in lines)
    assert procs.read_pid(tmp_path) is not None  # the process exists: the file is left alone


def test_a_stale_pid_file_is_removed_and_nothing_is_killed(tmp_path):
    procs.write_pid(tmp_path, 4242, 8000, "db")
    lines = []
    assert procs.stop(tmp_path, lines.append, runner(TASKLIST_NONE), kill=lambda pid: pytest.fail("must not kill")) == 1
    assert any("not running or not ours" in line for line in lines) and procs.read_pid(tmp_path) is None


def test_stop_asks_for_a_backup_then_kills_the_tree_and_removes_the_pid_file(tmp_path):
    procs.write_pid(tmp_path, 4242, 8000, "db")
    order = []
    lines = []
    code = procs.stop(
        tmp_path, lines.append, runner(),
        backup=lambda port: (order.append(("backup", port)) or (True, "daily-2026-10-14-080000.db")),
        kill=lambda pid: (order.append(("kill", pid)) or True),
    )
    assert code == 0 and order == [("backup", 8000), ("kill", 4242)]
    assert procs.read_pid(tmp_path) is None
    assert any("daily-2026-10-14-080000.db" in line for line in lines) and lines[-1] == "Stopped."


def test_a_failed_backup_warns_and_still_stops(tmp_path):
    procs.write_pid(tmp_path, 4242, 8000, "db")
    lines = []
    killed = []
    code = procs.stop(tmp_path, lines.append, runner(), backup=lambda port: (False, "the server answered 500"), kill=lambda pid: killed.append(pid) or True)
    assert code == 0 and killed == [4242]
    assert any(line.startswith("WARNING: no backup was made before stopping") for line in lines)


def test_a_process_that_will_not_die_is_exit_2(tmp_path):
    procs.write_pid(tmp_path, 4242, 8000, "db")
    lines = []
    assert procs.stop(tmp_path, lines.append, runner(), backup=lambda p: (True, "x"), kill=lambda pid: False) == 2
    assert procs.read_pid(tmp_path) is not None and any("Task Manager" in line for line in lines)


def test_asking_for_a_backup_never_raises_when_nothing_answers():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    ok, detail = procs.ask_for_backup(free_port, timeout=1)
    assert ok is False and detail


# -------------------------------------------------------------------------- logs


def test_the_server_log_rotates_when_big_and_keeps_five(tmp_path):
    log = tmp_path / "server.out.log"
    for n in range(8):
        log.write_bytes(b"x" * 50)
        procs.rotate(log, max_bytes=10, keep=5)
        log.write_bytes(f"run {n}".encode() * 10)  # the new run's output
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["server.out.log", "server.out.log.1", "server.out.log.2", "server.out.log.3", "server.out.log.4", "server.out.log.5"]
    log.write_bytes(b"small")
    procs.rotate(log, max_bytes=10, keep=5)
    assert log.read_bytes() == b"small"  # under the limit: untouched


def test_tail_of_a_missing_log_is_a_message_not_a_crash(tmp_path):
    assert procs.tail(tmp_path / "none.log") == "(no log yet)"
    (tmp_path / "a.log").write_text("\n".join(f"line {n}" for n in range(30)), encoding="utf-8")
    assert procs.tail(tmp_path / "a.log", 3) == "line 27\nline 28\nline 29"


def test_waiting_for_the_server(tmp_path):
    process = SimpleNamespace(poll=lambda: None)
    answers = iter([False, False, True])
    assert procs.wait_until_up(1, process, 5, health=lambda p: next(answers), sleep=lambda s: None) is True
    dead = SimpleNamespace(poll=lambda: 1)
    assert procs.wait_until_up(1, dead, 5, health=lambda p: False, sleep=lambda s: None) is False  # ended: no waiting
    assert procs.wait_until_up(1, process, 0.0, health=lambda p: False, sleep=lambda s: None) is False  # timed out


# ------------------------------------------------------------------ the screens


def make_out(folder: Path, api="/api", git="abc"):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text("<html></html>")
    if api is not None:
        (folder / frontend.MARKER).write_text(json.dumps({"api": api, "git": git}))
    return folder


def test_when_the_screens_must_be_built(tmp_path):
    out = tmp_path / "out"
    assert frontend.build_state(out, "abc", False)[0] == "build"  # missing
    make_out(out, api=None)
    assert frontend.build_state(out, "abc", False)[0] == "build"  # no marker
    make_out(out, api="http://localhost:8000")
    assert frontend.build_state(out, "abc", False)[0] == "build"  # built for the two-server setup
    make_out(out, api="/api", git="abc")
    assert frontend.build_state(out, "abc", False)[0] == "ok"
    assert frontend.build_state(out, "abc", True)[0] == "build"  # --rebuild
    state, reason = frontend.build_state(out, "def", False)
    assert state == "older" and "older" in reason  # a notice, not a rebuild
    assert frontend.build_state(out, None, False)[0] == "ok"  # no git: nothing to compare


def test_building_needs_node_and_says_how_to_get_it(tmp_path):
    with pytest.raises(frontend.BuildError) as exc_info:
        frontend.build(tmp_path, tmp_path / "out", tmp_path / "build.log", "abc", which=lambda name: None)
    assert "Node.js" in str(exc_info.value) and "nodejs.org" in str(exc_info.value)


def test_building_runs_npm_with_the_api_address_and_writes_the_marker(tmp_path):
    (tmp_path / "frontend").mkdir()
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs["env"]["NEXT_PUBLIC_API_URL"], kwargs["env"].get("PATH")))
        if command[1:] == ["run", "build"]:
            make_out(tmp_path / "frontend" / "out", api=None)
        return SimpleNamespace(returncode=0)

    frontend.build(tmp_path, tmp_path / "frontend" / "out", tmp_path / "logs" / "build.log", "abc", which=lambda n: f"C:/{n}", run=fake_run, env={"PATH": "p"})
    assert [c[0][1:] for c in calls] == [["ci"], ["run", "build"]]  # node_modules missing: npm ci first
    assert all(c[1] == "/api" and c[2] == "p" for c in calls)
    assert frontend.read_marker(tmp_path / "frontend" / "out") == {"api": "/api", "git": "abc"}
    (tmp_path / "frontend" / "node_modules" / ".bin").mkdir(parents=True)
    (tmp_path / "frontend" / "node_modules" / ".bin" / "next.cmd").write_text("")
    calls.clear()
    frontend.build(tmp_path, tmp_path / "frontend" / "out", tmp_path / "logs" / "build.log", "abc", which=lambda n: n, run=fake_run, env={})
    assert [c[0][1:] for c in calls] == [["run", "build"]]


def test_a_node_modules_folder_without_the_next_launcher_gets_npm_ci(tmp_path):
    # Seen on a shop laptop: node_modules existed but node_modules\.bin\next.cmd did not.
    bin_dir = tmp_path / "frontend" / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "other.cmd").write_text("")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command[1:])
        if command[1:] == ["run", "build"]:
            make_out(tmp_path / "frontend" / "out", api=None)
        return SimpleNamespace(returncode=0)

    assert not frontend.installed(tmp_path / "frontend")
    frontend.build(tmp_path, tmp_path / "frontend" / "out", tmp_path / "b.log", "abc", which=lambda n: n, run=fake_run, env={})
    assert calls == [["ci"], ["run", "build"]]
    assert (tmp_path / "b.log").read_text().startswith("$ ci")


def test_an_empty_node_modules_folder_is_not_installed(tmp_path):
    (tmp_path / "frontend" / "node_modules").mkdir(parents=True)
    assert not frontend.installed(tmp_path / "frontend")
    (tmp_path / "frontend" / "node_modules" / ".bin").mkdir()
    (tmp_path / "frontend" / "node_modules" / ".bin" / "next.cmd").write_text("")
    assert frontend.installed(tmp_path / "frontend")


def test_a_failed_build_is_an_error_with_the_step_named(tmp_path):
    (tmp_path / "frontend" / "node_modules" / ".bin").mkdir(parents=True)
    (tmp_path / "frontend" / "node_modules" / ".bin" / "next.cmd").write_text("")
    with pytest.raises(frontend.BuildError) as exc_info:
        frontend.build(tmp_path, tmp_path / "frontend" / "out", tmp_path / "b.log", "abc", which=lambda n: n, run=lambda *a, **k: SimpleNamespace(returncode=1), env={})
    assert "npm run build" in str(exc_info.value)
    with pytest.raises(frontend.BuildError) as exc_info:  # npm "succeeded" but produced nothing
        frontend.build(tmp_path, tmp_path / "frontend" / "out", tmp_path / "b.log", "abc", which=lambda n: n, run=lambda *a, **k: SimpleNamespace(returncode=0), env={})
    assert "index.html" in str(exc_info.value)


# ----------------------------------------------------------------------- the database


def ctx_for(root: Path, env=None, **overrides):
    lines = []
    ctx = app.Ctx(root=root, env=env or {}, out=lines.append, version=(3, 13, 1), **overrides)
    return ctx, lines


def test_the_default_database_is_data_shop_db_and_a_missing_one_is_announced(tmp_path):
    ctx, _ = ctx_for(tmp_path)
    db, is_new = app.choose_database(ctx)
    assert db == (tmp_path / "data" / "shop.db").resolve() and is_new is True
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "shop.db").write_bytes(b"x")
    assert app.choose_database(ctx)[1] is False


def test_an_existing_rebel_db_is_honoured_and_a_missing_one_refused(tmp_path):
    copy = tmp_path / "scratch" / "shop.db"
    copy.parent.mkdir()
    copy.write_bytes(b"x")
    ctx, _ = ctx_for(tmp_path, {"REBEL_DB": str(copy)})
    assert app.choose_database(ctx) == (copy.resolve(), False)
    ctx, _ = ctx_for(tmp_path, {"REBEL_DB": str(tmp_path / "nope.db")})
    with pytest.raises(app.StartError) as exc_info:
        app.choose_database(ctx)
    assert "does not exist" in str(exc_info.value) and exc_info.value.code == 2


def test_a_practice_copy_inside_the_real_data_folder_is_refused(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "shop-2026-10-13.db").write_bytes(b"x")
    (tmp_path / "data" / "shop.db").write_bytes(b"x")
    ctx, _ = ctx_for(tmp_path, {"REBEL_DB": str(tmp_path / "data" / "shop-2026-10-13.db")})
    with pytest.raises(app.StartError) as exc_info:
        app.choose_database(ctx)
    assert "its own folder" in str(exc_info.value) and "data\\restore-test" in str(exc_info.value)
    ctx, _ = ctx_for(tmp_path, {"REBEL_DB": str(tmp_path / "data" / "shop.db")})  # the real file itself is fine
    assert app.choose_database(ctx)[0] == (tmp_path / "data" / "shop.db").resolve()
    (tmp_path / "data" / "restore-test").mkdir()
    (tmp_path / "data" / "restore-test" / "shop.db").write_bytes(b"x")
    ctx, _ = ctx_for(tmp_path, {"REBEL_DB": str(tmp_path / "data" / "restore-test" / "shop.db")})
    assert app.choose_database(ctx)[1] is False


def test_python_and_packages_are_checked_with_clear_messages(monkeypatch, tmp_path):
    ctx, _ = ctx_for(tmp_path)
    ctx.version = (3, 9, 0)
    with pytest.raises(app.StartError, match="Python 3.11 or newer"):
        app.check_environment(ctx)
    ctx.version = (3, 13, 1)
    app.check_environment(ctx)
    monkeypatch.setattr(app.importlib.util, "find_spec", lambda name: None if name == "uvicorn" else object())
    with pytest.raises(app.StartError, match=r"packages are missing \(uvicorn\)") as exc_info:
        app.check_environment(ctx)
    assert "pip install -r requirements.txt" in str(exc_info.value)


# -------------------------------------------------------------------- the whole flow


class FakeProcess:
    def __init__(self, pid=4242, alive=True):
        self.pid, self._alive = pid, alive

    def poll(self):
        return None if self._alive else 1


def flow_ctx(tmp_path, busy=(), health=True, process=None, env_extra=None):
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    scratch = tmp_path / "scratch"
    scratch.mkdir(exist_ok=True)
    db = scratch / "shop.db"
    db.write_bytes(b"x")
    make_out(root / "frontend" / "out", git=None)
    started = []
    opened = []
    killed = []

    def popen(command, **kwargs):
        started.append((command, kwargs))
        return process or FakeProcess()

    def run(command, **kwargs):
        if command[0] == "netsh":
            return SimpleNamespace(returncode=0, stdout=NETSH_BLOCK_8000_8001)
        if command[0] == "taskkill":
            killed.append(command)
            return SimpleNamespace(returncode=0, stdout="")
        if command[0] == "git":
            return SimpleNamespace(returncode=1, stdout="")
        return SimpleNamespace(returncode=0, stdout="")

    ctx, lines = ctx_for(
        root, {"REBEL_DB": str(db), **(env_extra or {})},
        popen=popen, run=run, health=lambda port: health, busy=lambda port: port in busy,
        open_browser=opened.append, sleep=lambda s: None, wait_seconds=1,
    )
    return ctx, lines, started, opened, killed, db


NETSH_BLOCK_8000_8001 = "Start Port    End Port\n----------    --------\n      8000        8001\n"


def parse(*argv):
    import argparse

    namespace = argparse.Namespace(stop=False, rebuild=False, no_browser=False, port=8000)
    for arg in argv:
        if arg == "--no-browser":
            namespace.no_browser = True
    return namespace


def test_start_skips_reserved_and_busy_ports_and_launches_one_detached_server(tmp_path):
    ctx, lines, started, opened, killed, db = flow_ctx(tmp_path, busy=(8002,))
    assert app.start(parse(), ctx) == 0
    ((command, kwargs),) = started
    assert command[1:] == ["-m", "uvicorn", "api.serve:app", "--host", "127.0.0.1", "--port", "8003", "--no-access-log"]
    assert kwargs["env"]["REBEL_DB"] == str(db.resolve())  # the chosen database is passed on
    assert opened == ["http://localhost:8003/"]
    text = "\n".join(lines)
    assert "Skipped ports: busy [8002], reserved by Windows [8000, 8001]" in text
    assert f"Database   : {db.resolve()}" in text and "Open       : http://localhost:8003/" in text
    assert "Logs       :" in text and "stop-rebel.cmd" in text
    info = procs.read_pid(db.parent / "logs")
    assert info["pid"] == 4242 and info["port"] == 8003


def test_start_announces_a_changed_port(tmp_path):
    ctx, lines, started, opened, killed, db = flow_ctx(tmp_path)
    procs.write_pid(db.parent / "logs", 1, 8000, str(db))
    procs.remove_pid(db.parent / "logs")  # leaves last_port = 8000 behind
    app.start(parse(), ctx)  # 8000 and 8001 are reserved in this fake: it must pick 8002
    assert any("the port is 8002, last time it was 8000" in line for line in lines)


def test_a_second_start_reuses_the_running_instance(tmp_path):
    ctx, lines, started, opened, killed, db = flow_ctx(tmp_path)
    procs.write_pid(db.parent / "logs", 4242, 8000, str(db))
    ctx.run = lambda command, **kw: SimpleNamespace(returncode=0, stdout=TASKLIST_PY if command[0] == "tasklist" else NETSTAT)
    assert app.start(parse(), ctx) == 0
    assert started == [] and opened == ["http://localhost:8000/"]
    assert any("already running at http://localhost:8000/" in line for line in lines)


def test_a_stale_pid_file_does_not_block_a_new_start(tmp_path):
    ctx, lines, started, opened, killed, db = flow_ctx(tmp_path)
    procs.write_pid(db.parent / "logs", 99999, 8000, str(db))
    assert app.start(parse(), ctx) == 0 and len(started) == 1


def test_a_server_that_does_not_answer_is_stopped_and_its_log_shown(tmp_path):
    ctx, lines, started, opened, killed, db = flow_ctx(tmp_path, health=False, process=FakeProcess(alive=False))
    (db.parent / "logs").mkdir()
    (db.parent / "logs" / procs.SERVER_LOG).write_text("Traceback ... ImportError: boom")
    assert app.start(parse(), ctx) == 1
    text = "\n".join(lines)
    assert "did not start within 1 seconds" in text and "ImportError: boom" in text
    assert killed and procs.read_pid(db.parent / "logs") is None and opened == []


def test_no_free_port_is_a_clear_exit_1(tmp_path):
    ctx, lines, started, opened, killed, db = flow_ctx(tmp_path)
    ctx.busy = lambda port: True
    with pytest.raises(app.StartError) as exc_info:
        app.start(parse(), ctx)
    assert exc_info.value.code == 1 and "No free port between 8000 and 8099" in str(exc_info.value)
    assert started == []


def test_main_turns_a_start_error_into_its_message_and_exit_code(tmp_path):
    ctx, lines = ctx_for(tmp_path, {"REBEL_DB": str(tmp_path / "nope.db")})
    assert app.main(["--no-browser"], ctx) == 2
    assert "REBEL_DB points to a file that does not exist" in lines[0]


def test_start_builds_the_screens_first_when_they_are_missing_and_names_node_when_it_is_not_there(tmp_path):
    ctx, lines, started, opened, killed, db = flow_ctx(tmp_path)
    for leftover in (ctx.root / "frontend" / "out").iterdir():
        leftover.unlink()
    ctx.which = lambda name: None
    assert app.start(parse(), ctx) == 1
    text = "\n".join(lines)
    assert "Building the screens (the screens have not been built yet)" in text and "nodejs.org" in text
    assert started == []


# ------------------------------------------------------------ the real thing, once


@pytest.mark.skipif(sys.platform != "win32", reason="uses Windows tasklist, netstat and taskkill")
def test_a_real_start_and_stop_on_a_temp_database_on_a_non_default_port(tmp_path):
    """Starts the real server (one detached process) on a temp copy in its own folder, checks it answers, makes the stop backup,
    stops it and checks nothing is left. Never touches data/ (conftest guards that)."""
    work = tmp_path / "practice"
    work.mkdir()
    db = work / "shop.db"
    init_db(str(db))
    out = make_out(tmp_path / "out", git=None)
    (out / "index.html").write_text("<html><title>screens</title></html>")
    env = {**os.environ, "REBEL_DB": str(db), "REBEL_FRONTEND_DIR": str(out)}
    ctx = app.Ctx(root=PROJECT_ROOT, env=env, wait_seconds=60)
    lines = []
    ctx.out = lines.append
    assert app.main(["--no-browser", "--port", "8340"], ctx) == 0, "\n".join(lines)
    try:
        info = procs.read_pid(work / "logs")
        assert info is not None and 8340 <= info["port"] < 8440
        base = f"http://127.0.0.1:{info['port']}"
        assert json.loads(urllib.request.urlopen(f"{base}/api/health", timeout=10).read()) == {"status": "ok", "db": "ok"}
        assert "screens" in urllib.request.urlopen(f"{base}/", timeout=10).read().decode()
        assert len(list_backups(backups_dir_for(db))) == 1  # the startup backup
        assert (work / "logs" / "app.log").is_file() and (work / "logs" / procs.SERVER_LOG).is_file()
        assert any(str(db) in line for line in lines)
        # a second start finds it running and starts nothing
        again = []
        ctx.out = again.append
        assert app.main(["--no-browser", "--port", "8340"], ctx) == 0 and any("already running" in line for line in again)
    finally:
        stopped = []
        ctx.out = stopped.append
        code = app.main(["--stop"], ctx)
    assert code == 0, "\n".join(stopped)
    assert len(list_backups(backups_dir_for(db))) == 2  # the backup made on stop
    assert procs.read_pid(work / "logs") is None
    assert procs.health_ok(info["port"], timeout=1) is False
