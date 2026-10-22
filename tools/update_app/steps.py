"""The update itself, nine steps; it stops at the first failure. Exit codes: 0 done / up to date, 1 refused or rolled back, 2 could not run.
  1 preflight   2 integrity check before   (read-only; nothing is changed up to here)
  3 stop the app   4 verified backup into backups/pre-update   (the state file `update-state.json` is written at step 3)
  5 git pull --ff-only   6 dependencies + screens   7 migrate (fresh process)   8 integrity check after   9 start the app
A failure in steps 5-9 rolls back (rollback.py): a failed pull with HEAD unchanged only restarts the app; steps 6-9 also restore the database.
Step 9 does not roll back when the app answers healthy anyway (a late start). The integrity check blocks on exit 1 (FAIL) and 2 (could not run), never on WARN (exit 0)."""

from pathlib import Path

from tools.run_app import frontend
from tools.update_app import log as logmod
from tools.update_app.context import PRE_UPDATE, Ctx
from tools.update_app.errors import CannotRun, Refused
from tools.update_app.fsutil import sha256_file
from tools.update_app.preflight import Plan, preflight
from tools.update_app.rollback import LOCKFILE, REQUIREMENTS, roll_back

KEEP_PRE_UPDATE = 10
LOCK_TRIES = 5
CONFIRM_WORD = "YES"


def moment_of(ctx: Ctx) -> str:
    return ctx.now().strftime("%Y%m%d-%H%M%S")


def check_database_choice(ctx: Ctx) -> None:
    chosen = ctx.env.get("REBEL_DB")
    if chosen:
        path = Path(chosen)
        path = (path if path.is_absolute() else ctx.root / path).resolve()
        if path != ctx.db:
            raise Refused(f"REBEL_DB points to {path}, not to {ctx.db}. The update only works on this folder's data\\shop.db.\nPowerShell: Remove-Item Env:REBEL_DB")
    if not ctx.db.is_file():
        raise Refused(f"The database was not found: {ctx.db}")


def refuse_if_unfinished(ctx: Ctx) -> None:
    state = logmod.read_state(ctx.logs)
    if state is None:
        if logmod.state_exists(ctx.logs):
            raise Refused(f"{ctx.logs / logmod.STATE_FILE} exists but cannot be read. Ask the planning chat before updating.")
        return
    live = isinstance(state.get("pid"), int) and state["pid"] != ctx.pid and ctx.process_alive(state["pid"])
    step = state.get("step")
    if live:
        raise Refused(f"Another update seems to be running (pid {state['pid']}, step {step}). Wait for it to finish.")
    raise Refused(
        f"An earlier update did not finish: it reached step {step}/9 ({logmod.STEP_NAMES.get(step, '?')}). Log: {state.get('log')}\n"
        "Recover with:  .venv\\Scripts\\python -m tools.update_app --recover\n"
        "(it undoes what the update did; docs/RUNNING.md section 6b). A new update will not start until then."
    )


def failing_lines(text: str) -> str:
    keys = ("FAIL", "ERROR", "INCOMPLETE", "CANNOT")
    return "\n".join(line for line in text.splitlines() if any(key in line for key in keys))[-3000:]


def confirm(ctx: Ctx, args, plan: Plan) -> None:
    say = ctx.out
    say(f"Update from {plan.old_head[:10]} to {plan.new_head[:10]}: {len(plan.commits)} new commits")
    for line in plan.commits[:15]:
        say(f"  {line}")
    if len(plan.commits) > 15:
        say(f"  ... and {len(plan.commits) - 15} more")
    if plan.migration_changes:
        say("Database migrations in this update (the database will be changed):")
        for line in plan.migration_changes:
            say(f"  {line}")
    else:
        say("No database migrations in this update.")
    if getattr(args, "yes", False):
        return
    say("The app will close now. Is anyone entering data right now? Type YES to continue; anything else cancels.")
    say("برنامه بسته می‌شود. الان کسی در حال ثبت اطلاعات است؟ برای ادامه YES بنویسید.")
    try:
        answer = ctx.ask("> ")
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer.strip() != CONFIRM_WORD:
        raise Refused("Cancelled. Nothing was changed.")


class Update:
    def __init__(self, ctx: Ctx, args, plan: Plan):
        self.ctx, self.args, self.plan = ctx, args, plan
        self.moment = moment_of(ctx)
        self.log = logmod.UpdateLog(ctx.logs, self.moment)
        self.state = {
            "pid": ctx.pid, "log": str(self.log.path), "db": str(ctx.db), "old_head": plan.old_head, "new_head": plan.new_head,
            "backup_path": None, "backup_sha256": None, "step": 2, "app_was_running": False, "restarted": False,
            "started": self.moment,
        }
        self.stopped = False

    def enter(self, number: int) -> None:
        self.state["step"] = number
        logmod.write_state(self.ctx.logs, self.state)
        self.log.step(number, "START")

    # -------------------------------------------------------------- steps 3-4

    def stop_app(self) -> None:
        ctx = self.ctx
        info = ctx.app_info()
        if info is not None:
            if ctx.app_is_ours(info):
                self.state["app_was_running"] = True
                logmod.write_state(ctx.logs, self.state)
                code = ctx.stop_app()
                self.stopped = True
                if code != 0:
                    raise Refused("The app could not be stopped (see the message above). Close it by hand, then run the update again.")
            elif ctx.image_of(info["pid"]) is None:
                ctx.remove_pid_file()  # a leftover file of a server that is gone
            else:
                raise Refused(
                    f"The pid file names process {info['pid']}, which is not this app (not a python process listening on port {info['port']}). "
                    "Nothing was stopped, on purpose. Close the app yourself, then run the update again."
                )
        reason = ctx.other_server()
        if reason:
            raise Refused(f"{reason}. Stop it (stop-rebel.cmd or close it) and run the update again.")
        problem = None
        for _ in range(LOCK_TRIES):
            problem = ctx.db_lock_problem()
            if problem is None:
                break
            ctx.sleep(2)
        if problem:
            raise Refused(f"{problem}. Another program has the database open; close it and run the update again.")

    def backup(self) -> None:
        ctx = self.ctx
        folder = ctx.db.parent / PRE_UPDATE
        failure = None
        made = None
        try:
            made = ctx.make_backup(folder, KEEP_PRE_UPDATE)
        except Exception as exc:  # BackupError or an OS error: either way nothing may be updated without a backup
            failure = f"{type(exc).__name__}: {exc}"
        if failure:
            raise Refused(f"The safety backup failed ({failure}). Nothing was updated.")
        path = Path(made["path"])
        digest = sha256_file(path)
        self.state["backup_path"], self.state["backup_sha256"] = str(path), digest
        logmod.write_state(ctx.logs, self.state)
        self.log.line(f"old HEAD {self.plan.old_head}; target {self.plan.new_head}")
        self.log.line(f"backup {path.name} sha256 {digest}")
        ctx.out(f"Safety backup: {path}")

    # -------------------------------------------------------------- steps 5-8 (each returns an error text, or None)

    def pull(self) -> str | None:
        result = self.ctx.git("pull", "--ff-only", "origin", "main")
        self.log.line(f"git pull: exit {result.returncode}\n{(result.stdout or '').strip()}\n{(result.stderr or '').strip()}")
        if result.returncode != 0:
            return "git pull failed: " + (result.stderr or "").strip()[-300:]
        return None

    def dependencies(self) -> str | None:
        ctx, changed = self.ctx, self.plan.changed
        head = ctx.git("rev-parse", "HEAD").stdout.strip()
        if REQUIREMENTS in changed:
            code, text = ctx.pip_install()
            self.log.line(f"pip install -r requirements.txt: exit {code}\n{text.strip()[-2000:]}")
            if code != 0:
                return "installing the Python packages failed"
        if LOCKFILE in changed:
            code, text = ctx.npm_ci()
            self.log.line(f"npm ci: exit {code}\n{text.strip()[-2000:]}")
            if code != 0:
                return "npm ci failed"
        try:
            ctx.build_screens(head)
        except frontend.BuildError as exc:
            self.log.line(f"build: {exc}")
            return f"building the screens failed: {exc}"
        return None

    def migrate(self) -> str | None:
        code, text = self.ctx.migrate(self.ctx.db)
        self.log.line(f"migrate: exit {code}\n{text.strip()[-3000:]}")
        if code != 0:
            return "the database migration failed: " + text.strip()[-300:]
        applied = [line.split(None, 1)[1] for line in text.splitlines() if line.startswith("APPLIED ")]
        for name in applied:
            self.ctx.out(f"  migration applied: {name}")
        wanted = len(self.plan.new_migrations)
        if len(applied) != wanted:
            return f"{len(applied)} migrations were applied but the update brought {wanted} new migration files"
        return None

    def integrity_after(self) -> str | None:
        code, text = self.ctx.integrity(self.ctx.db)
        self.log.line(f"integrity check after: exit {code}\n{text.strip()[-6000:]}")
        if code != 0:
            return f"the integrity check after the update found problems (exit {code}):\n{failing_lines(text)}"
        return None

    # -------------------------------------------------------------- the run

    def fail_before_pull(self, error: Exception) -> int:
        """Steps 3-4 failed: nothing was changed. Restart the app if we stopped it."""
        ctx = self.ctx
        self.log.line(f"REFUSED: {error}")
        ctx.out(str(error))
        if self.stopped:
            ctx.out("Starting the app again...")
            self.log.line(f"restart after refusal: exit {ctx.start_app()}")
        logmod.clear_state(ctx.logs)
        ctx.out("چیزی تغییر نکرد؛ اطلاعات شما سالم است.")
        ctx.out(f"Log: {self.log.path}")
        return 1

    def rolled_back(self, reason: str, restore_db: bool) -> int:
        code = roll_back(self.ctx, self.state, self.log, self.moment, reason, restore_db)
        if code == 1:
            logmod.clear_state(self.ctx.logs)  # a failed rollback keeps the state file for --recover
        return code

    def run(self) -> int:
        ctx, say = self.ctx, self.ctx.out
        self.log.line(f"update started {self.moment}; old HEAD {self.plan.old_head}")
        self.log.line("integrity check before: passed (exit 0)")
        self.enter(3)
        try:
            self.stop_app()
            self.log.step(3, "DONE")
            self.enter(4)
            self.backup()
            self.log.step(4, "DONE")
        except Refused as exc:
            self.log.step(self.state["step"], "FAILED")
            return self.fail_before_pull(exc)

        for number, work, label in ((5, self.pull, "pull"), (6, self.dependencies, "dependencies"), (7, self.migrate, "migrate"), (8, self.integrity_after, "integrity after")):
            self.enter(number)
            error = work()
            if error is not None:
                self.log.step(number, "FAILED", error)
                say(f"FAILED at step {number}/9 ({label}): {error}")
                return self.rolled_back(error, restore_db=number >= 6)
            self.log.step(number, "DONE")

        self.enter(9)
        code = ctx.start_app()
        if code != 0:
            if ctx.healthy():
                self.log.line("the app did not report in time but answers healthy now: treated as a late start, no rollback")
                say("The app started late but is healthy now.")
            else:
                self.log.step(9, "FAILED", f"start exit {code}")
                say("FAILED at step 9/9 (start the app): the new version did not become healthy.")
                return self.rolled_back("the new version did not start", restore_db=True)
        self.log.step(9, "DONE")
        self.state["restarted"] = True
        logmod.write_state(ctx.logs, self.state)
        self.log.line("UPDATE DONE")
        logmod.clear_state(ctx.logs)
        say(f"Updated to {self.plan.new_head[:10]}. Log: {self.log.path}")
        say("به‌روزرسانی انجام شد.")
        return 0


def run_update(args, ctx: Ctx) -> int:
    say = ctx.out
    try:
        check_database_choice(ctx)
        refuse_if_unfinished(ctx)
        plan = preflight(ctx)
        if plan.up_to_date:
            say(f"Already up to date ({plan.old_head[:10]}). Nothing to do.")
            say("برنامه به‌روز است.")
            return 0
        code, text = ctx.integrity(ctx.db)
        if code != 0:
            raise Refused(
                f"The database already has problems (integrity check exit {code}), so it will not be updated:\n{failing_lines(text)}\n"
                "Nothing was changed. Send this to the planning chat."
            )
        confirm(ctx, args, plan)
    except Refused as exc:
        say(str(exc))
        say("چیزی تغییر نکرد؛ اطلاعات شما سالم است.")
        return 1
    except CannotRun as exc:
        say(f"The update could not run: {exc}")
        return 2
    return Update(ctx, args, plan).run()
