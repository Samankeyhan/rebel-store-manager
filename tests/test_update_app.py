"""tools/update_app: preflight refusals, the integrity gate, the confirmation, the step order, the log and state file, the automatic rollback and --recover.
git, npm, pip, the app and the integrity / migrate processes are faked (tests/update_app_harness.py); the folder, the database, the backup and the sha256 checks are real."""

import json
from pathlib import Path

import pytest

from tests.update_app_harness import NEW, OLD, Args, FakeCtx, change_database, make_root, sha
from tools.update_app import log as logmod
from tools.update_app.__main__ import main
from tools.update_app.recover import recover
from tools.update_app.steps import run_update

ONE_MIGRATION = "A\tmigrations/014_x.sql\n"


@pytest.fixture
def ctx(tmp_path):
    return FakeCtx(make_root(tmp_path))


def update(ctx, yes=True):
    return run_update(Args(yes=yes), ctx)


def state_of(ctx):
    return logmod.read_state(ctx.logs)


def backup_file(ctx) -> Path:
    (found,) = (ctx.db.parent / "backups" / "pre-update").glob("daily-*.db")
    return found


# ------------------------------------------------------------------ preflight


def test_a_branch_other_than_main_is_refused_and_nothing_is_stopped(ctx):
    ctx.branch = "feat/x"
    assert update(ctx) == 1
    assert "feat/x" in ctx.text and "stop" not in ctx.calls and "backup" not in ctx.calls


def test_a_detached_head_is_refused(ctx):
    ctx.branch = "HEAD"
    assert update(ctx) == 1 and "detached" in ctx.text


def test_changed_tracked_files_are_refused_and_listed(ctx):
    ctx.dirty = [" M api/main.py"]
    assert update(ctx) == 1
    assert "api/main.py" in ctx.text and "stop" not in ctx.calls


def test_untracked_files_are_refused_too(ctx):
    ctx.dirty = ["?? notes.txt"]
    assert update(ctx) == 1 and "notes.txt" in ctx.text and "stop" not in ctx.calls


def test_local_commits_that_are_not_on_origin_are_refused(ctx):
    ctx.ancestor_rc = 1
    assert update(ctx) == 1 and "not on origin/main" in ctx.text and "stop" not in ctx.calls


def test_a_missing_virtual_environment_is_refused(ctx):
    (ctx.root / ".venv" / "Scripts" / "python.exe").unlink()
    assert update(ctx) == 1 and "environment was not found" in ctx.text


def test_a_failed_fetch_means_could_not_run(ctx):
    ctx.fetch_rc = 1
    assert update(ctx) == 2 and "git fetch failed" in ctx.text and "stop" not in ctx.calls


def test_up_to_date_exits_zero_without_touching_anything(ctx):
    ctx.remote = OLD
    assert update(ctx, yes=False) == 0
    assert "up to date" in ctx.text.lower()
    assert not {"stop", "backup", "ask", "integrity"} & set(ctx.calls)


def test_the_index_is_refreshed_before_the_status_is_read(ctx):
    update(ctx)
    refresh = ctx.calls.index("git update-index --refresh -q")
    assert refresh < ctx.calls.index("git status --porcelain")


def test_a_rebel_db_pointing_elsewhere_is_refused(ctx, tmp_path):
    ctx.env = {"REBEL_DB": str(tmp_path / "other.db")}
    assert update(ctx) == 1 and "REBEL_DB" in ctx.text and ctx.calls == []


# ------------------------------------------------------------------ integrity gate


def test_a_warning_does_not_block_the_update(ctx):
    ctx.integrity_results = [(0, "WARN something\nOK\n"), (0, "OK\n")]
    assert update(ctx) == 0


@pytest.mark.parametrize("code", [1, 2])
def test_integrity_exit_1_and_2_block_before_anything_is_stopped(ctx, code):
    ctx.integrity_results = [(code, "x FAIL y\nFAILED: 1 problems\n")]
    assert update(ctx) == 1
    assert "already has problems" in ctx.text and "stop" not in ctx.calls and "backup" not in ctx.calls


# ------------------------------------------------------------------ confirmation


def test_no_stop_call_without_confirmation(ctx):
    ctx.answers = ["no"]
    assert update(ctx, yes=False) == 1
    assert "Cancelled" in ctx.text and "stop" not in ctx.calls and "backup" not in ctx.calls and "git pull --ff-only origin" not in ctx.calls


def test_end_of_input_counts_as_no(ctx):
    ctx.answers = []
    assert update(ctx, yes=False) == 1 and "stop" not in ctx.calls


def test_the_question_is_in_english_and_persian_and_yes_continues(ctx):
    ctx.answers = ["YES"]
    assert update(ctx, yes=False) == 0
    assert "Type YES" in ctx.text and "YES بنویسید" in ctx.text


def test_the_yes_flag_skips_the_question(ctx):
    ctx.answers = []
    assert update(ctx, yes=True) == 0 and "ask" not in ctx.calls


# ------------------------------------------------------------------ step order


def test_the_steps_run_in_order_and_dependencies_only_when_their_files_changed(ctx):
    ctx.pid_info = {"pid": 4242, "port": 8000}
    ctx.name_status = ONE_MIGRATION
    ctx.changed = "requirements.txt\nfrontend/package-lock.json\nmigrations/014_x.sql\n"
    ctx.migrate_result = (0, "APPLIED 014_x.sql\nMIGRATION OK\n")
    assert update(ctx) == 0
    relevant = [c for c in ctx.calls if not c.startswith("git ") or c.startswith("git pull")]
    assert relevant == ["integrity", "stop", "lock probe", "backup", "git pull --ff-only origin",
                        "pip", "npm ci", "build b", "migrate", "integrity", "start"]
    assert "Updated to" in ctx.text and "به‌روزرسانی انجام شد" in ctx.text


def test_no_pip_or_npm_ci_when_nothing_changed_there(ctx):
    ctx.changed = "api/main.py\n"
    assert update(ctx) == 0
    assert "pip" not in ctx.calls and "npm ci" not in ctx.calls and "build b" in ctx.calls


def test_a_locked_database_refuses_restarts_the_app_and_clears_the_state(ctx):
    ctx.pid_info = {"pid": 4242, "port": 8000}
    ctx.lock_problems = ["the database is locked (x)"]
    assert update(ctx) == 1
    assert "locked" in ctx.text and "backup" not in ctx.calls and ctx.calls.count("lock probe") == 5
    assert ctx.calls[-1] == "start" and state_of(ctx) is None


def test_a_pid_file_that_is_not_our_app_is_never_stopped(ctx):
    ctx.pid_info = {"pid": 4242, "port": 8000}
    ctx.pid_ours = False
    assert update(ctx) == 1
    assert "not this app" in ctx.text and "stop" not in ctx.calls and "backup" not in ctx.calls


def test_a_leftover_pid_file_of_a_dead_process_is_removed_and_the_update_goes_on(ctx):
    ctx.pid_info = {"pid": 4242, "port": 8000}
    ctx.pid_ours = False
    ctx.pid_image = None
    assert update(ctx) == 0 and "remove pid file" in ctx.calls and "stop" not in ctx.calls


def test_a_stop_failure_aborts_before_the_backup(ctx):
    ctx.pid_info = {"pid": 4242, "port": 8000}
    ctx.stop_code = 2
    assert update(ctx) == 1 and "backup" not in ctx.calls and "could not be stopped" in ctx.text


def test_another_server_on_the_database_refuses(ctx):
    ctx.other = "a Rebel server answers on port 8003"
    assert update(ctx) == 1 and "8003" in ctx.text and "backup" not in ctx.calls


def test_a_failed_backup_aborts_before_the_pull_and_restarts_the_app(ctx):
    ctx.pid_info = {"pid": 4242, "port": 8000}
    ctx.backup_error = OSError("disk full")
    assert update(ctx) == 1
    assert "safety backup failed" in ctx.text and not any(c.startswith("git pull") for c in ctx.calls)
    assert ctx.calls[-1] == "start" and state_of(ctx) is None


# ------------------------------------------------------------------ log and state


def test_old_head_and_backup_hash_are_recorded_before_the_pull(ctx):
    seen = {}
    original = ctx.git

    def spy(*args):
        if args[0] == "pull":
            seen["state"] = state_of(ctx)
            seen["log"] = Path(seen["state"]["log"]).read_text(encoding="utf-8")
        return original(*args)

    ctx.git = spy
    assert update(ctx) == 0
    state = seen["state"]
    assert state["old_head"] == OLD and state["step"] == 5
    assert state["backup_sha256"] == sha(Path(state["backup_path"]))
    assert OLD in seen["log"] and state["backup_sha256"] in seen["log"] and "STEP 4/9 backup: DONE" in seen["log"]


def test_the_state_file_is_removed_after_success_and_the_log_says_done(ctx):
    assert update(ctx) == 0
    assert state_of(ctx) is None
    (log,) = ctx.logs.glob("update-*.log")
    text = log.read_text(encoding="utf-8")
    assert "UPDATE DONE" in text and "STEP 9/9 start the app: DONE" in text


def test_a_new_update_refuses_while_an_interrupted_one_left_its_state(ctx):
    logmod.write_state(ctx.logs, {"pid": 99, "step": 6, "log": "x.log", "old_head": OLD})
    assert update(ctx) == 1
    assert "did not finish" in ctx.text and "--recover" in ctx.text and ctx.calls == []


def test_a_live_update_process_is_reported_as_running(ctx):
    logmod.write_state(ctx.logs, {"pid": 99, "step": 6})
    ctx.alive_pids = {99}
    assert update(ctx) == 1 and "Another update seems to be running" in ctx.text


# ------------------------------------------------------------------ automatic rollback


def assert_database_restored(ctx):
    state_backup = backup_file(ctx)
    assert sha(ctx.db) == sha(state_backup)
    assert not ctx.db.with_name("shop.db.restore-tmp").exists()


def test_a_failed_pull_with_head_unchanged_only_restarts_the_app(ctx):
    ctx.pull_rc = 1
    original = sha(ctx.db)
    ctx.migrate_effect = lambda db: pytest.fail("must not migrate")
    assert update(ctx) == 1
    assert "git pull failed" in ctx.text and ctx.head == OLD
    assert not any(c.startswith("git reset") for c in ctx.calls)
    assert "build a" not in ctx.calls and ctx.calls[-1] == "start" and "Nothing in your data changed" in ctx.text
    assert sha(ctx.db) == original and state_of(ctx) is None


def test_a_failing_dependency_install_restores_database_and_code(ctx):
    ctx.changed = "requirements.txt\n"
    ctx.pip_rc = 1
    assert update(ctx) == 1
    assert ctx.head == OLD and "build a" in ctx.calls and ctx.calls[-1] == "start"
    assert_database_restored(ctx)
    assert "Rolled back" in ctx.text and "برگشت" in ctx.text


def test_a_failing_migration_restores_the_database_even_if_it_changed_it(ctx):
    ctx.migrate_effect = change_database
    ctx.migrate_result = (1, "MIGRATION FAILED: OperationalError: nope\n")
    assert update(ctx) == 1
    assert ctx.head == OLD and sha(ctx.db) == sha(backup_file(ctx))
    assert ctx.calls[-1] == "start"


def test_the_failed_migrated_database_is_kept_for_diagnosis(ctx):
    ctx.migrate_effect = change_database
    ctx.integrity_results = [(0, "OK"), (1, "x FAIL y\nFAILED: 1 problems")]
    assert update(ctx) == 1
    (kept,) = (ctx.db.parent / "backups" / "pre-update").glob("shop-failed-update-*.db")
    import sqlite3

    conn = sqlite3.connect(kept)
    try:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'dummy_new'").fetchone() is not None
    finally:
        conn.close()
    assert_database_restored(ctx)


def test_a_migration_count_that_does_not_match_the_new_files_rolls_back(ctx):
    ctx.name_status = ONE_MIGRATION
    ctx.migrate_result = (0, "MIGRATION OK\n")  # nothing APPLIED, one file expected
    assert update(ctx) == 1 and "0 migrations were applied" in ctx.text and ctx.head == OLD


def test_integrity_after_failing_rolls_back(ctx):
    ctx.integrity_results = [(0, "OK"), (1, "c1 FAIL stock\nFAILED: 1 problems")]
    assert update(ctx) == 1
    assert "FAIL stock" in ctx.text and ctx.head == OLD and ctx.calls[-1] == "start"
    assert_database_restored(ctx)


def test_rollback_reinstalls_python_packages_and_npm_when_those_files_differed(ctx):
    ctx.changed = "requirements.txt\nfrontend/package-lock.json\n"
    ctx.integrity_results = [(0, "OK"), (1, "FAIL x")]
    assert update(ctx) == 1
    after_reset = ctx.calls[len(ctx.calls) - 1 - ctx.calls[::-1].index("integrity") + 1:]
    assert after_reset.count("pip") == 1 and after_reset.count("npm ci") == 1 and after_reset[-1] == "start"
    assert after_reset.index("pip") < after_reset.index("build a") < after_reset.index("start")


def test_a_corrupt_backup_stops_the_rollback_before_anything_is_replaced(ctx):
    def damage(db):
        change_database(db)
        backup_file(ctx).write_bytes(b"damaged")

    ctx.migrate_effect = damage
    ctx.migrate_result = (1, "MIGRATION FAILED\n")
    assert update(ctx) == 2
    assert "THE ROLLBACK FAILED" in ctx.text and "section 6a" in ctx.text
    assert not any(c.startswith("git reset") or c == "start" for c in ctx.calls)
    assert state_of(ctx) is not None


def test_a_step_9_failure_rolls_back_when_the_app_never_became_healthy(ctx):
    ctx.start_codes = [1, 0]
    ctx.migrate_effect = change_database
    assert update(ctx) == 1
    assert "did not become healthy" in ctx.text and ctx.head == OLD
    assert_database_restored(ctx)
    assert ctx.calls.count("start") == 2
    assert list((ctx.db.parent / "backups" / "pre-update").glob("shop-failed-update-*.db"))


def test_a_late_start_is_not_rolled_back(ctx):
    ctx.start_codes = [1]
    ctx.healthy_value = True
    ctx.migrate_effect = change_database
    assert update(ctx) == 0
    assert "late" in ctx.text and ctx.head == NEW and state_of(ctx) is None
    assert not list((ctx.db.parent / "backups" / "pre-update").glob("shop-failed-update-*.db"))


# ------------------------------------------------------------------ --recover


def test_recover_after_a_power_cut_in_the_migration_step_restores_everything(ctx):
    def cut(db):
        change_database(db)
        raise KeyboardInterrupt

    ctx.migrate_effect = cut
    with pytest.raises(KeyboardInterrupt):
        update(ctx)
    state = state_of(ctx)
    assert state["step"] == 7 and state["backup_sha256"]
    calls_before = len(ctx.calls)
    ctx.lines.clear()
    assert recover(ctx) == 0
    assert ctx.head == OLD and sha(ctx.db) == state["backup_sha256"] == sha(backup_file(ctx))
    assert ctx.calls[calls_before:][-1] == "start" and state_of(ctx) is None
    assert "step 7/9" in ctx.text and list(ctx.logs.glob("update-*-recover.log"))


def test_recover_before_the_pull_only_starts_the_app(ctx):
    ctx.pid_info = {"pid": 4242, "port": 8000}

    def cut(*args):
        raise KeyboardInterrupt

    ctx.make_backup = lambda folder, keep: (_ for _ in ()).throw(KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        update(ctx)
    assert state_of(ctx)["step"] == 4
    ctx.pid_info = None
    ctx.calls.clear()
    assert recover(ctx) == 0
    assert ctx.calls == ["git rev-parse HEAD", "start"] and state_of(ctx) is None


def test_recover_after_the_pull_without_a_migration_resets_the_code_but_keeps_the_database(ctx):
    def cut(db):
        raise KeyboardInterrupt

    ctx.migrate = lambda db: cut(db)
    with pytest.raises(KeyboardInterrupt):
        update(ctx)
    ctx.head = NEW
    state = state_of(ctx)
    assert state["step"] == 7
    state["step"] = 5
    logmod.write_state(ctx.logs, state)
    ctx.calls.clear()
    assert recover(ctx) == 0
    assert ctx.head == OLD and "build a" in ctx.calls and "restored" not in ctx.text


def test_recover_refuses_after_a_finished_update(ctx):
    logmod.write_state(ctx.logs, {"pid": 1, "step": 9, "restarted": True, "old_head": OLD})
    assert recover(ctx) == 1 and "had finished" in ctx.text and ctx.calls == []


def test_recover_refuses_while_the_app_runs_or_the_updater_is_alive(ctx):
    logmod.write_state(ctx.logs, {"pid": 99, "step": 7, "old_head": OLD})
    ctx.alive_pids = {99}
    assert recover(ctx) == 1 and "still running" in ctx.text
    ctx.alive_pids = set()
    ctx.pid_info = {"pid": 4242, "port": 8000}
    assert recover(ctx) == 1 and "The app is running" in ctx.text


def test_recover_without_a_state_file_changes_nothing(ctx):
    assert recover(ctx) == 1 and "no interrupted update" in ctx.text and ctx.calls == []


def test_recover_at_step_9_with_a_healthy_app_undoes_nothing(ctx):
    logmod.write_state(ctx.logs, {"pid": 1, "step": 9, "restarted": False, "old_head": OLD})
    ctx.healthy_value = True
    assert recover(ctx) == 0 and state_of(ctx) is None and "git reset" not in " ".join(ctx.calls)


# ------------------------------------------------------------------ command line


def test_main_runs_the_update_with_the_options(ctx):
    assert main(["--yes", "--port", "8123", "--no-browser"], ctx) == 0
    assert ctx.port == 8123 and ctx.no_browser is True


def test_main_recover_and_rehearse_are_exclusive(ctx):
    with pytest.raises(SystemExit):
        main(["--recover", "--rehearse", "x"], ctx)
