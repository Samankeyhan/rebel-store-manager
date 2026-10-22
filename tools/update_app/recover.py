"""`--recover`: undo an update that was interrupted (power cut, closed window), from `data/logs/update-state.json`.
Steps 3-5: the database was not changed (only the app was stopped, a backup made, maybe the code pulled): code is reset if it moved, the app restarted.
Steps 6-8: the database may have been migrated: full rollback. Step 9: full rollback unless the app answers healthy (a late start).
Refused when the update finished (the app was used: use the manual rollback), when the app runs, or when the update process is still alive."""

from tools.update_app import log as logmod
from tools.update_app.context import Ctx
from tools.update_app.errors import Refused
from tools.update_app.rollback import roll_back


def recover(ctx: Ctx) -> int:
    say = ctx.out
    state = logmod.read_state(ctx.logs)
    if state is None:
        say("There is no interrupted update to recover from (no update-state.json). Nothing was changed.")
        return 1
    try:
        if state.get("restarted"):
            raise Refused("That update had finished and the app was started. Anything entered since is not in the backup: use the manual rollback (docs/RUNNING.md section 6a) only if you really must.")
        if isinstance(state.get("pid"), int) and state["pid"] != ctx.pid and ctx.process_alive(state["pid"]):
            raise Refused(f"The update process (pid {state['pid']}) is still running. Wait for it, or close its window first.")
        info = ctx.app_info()
        if info is not None and ctx.app_is_ours(info):
            raise Refused("The app is running. Stop it (stop-rebel.cmd), then run --recover again.")
    except Refused as exc:
        say(str(exc))
        return 1
    moment = ctx.now().strftime("%Y%m%d-%H%M%S")
    log = logmod.UpdateLog(ctx.logs, moment + "-recover")
    step = state.get("step", 0)
    log.line(f"RECOVER from the interrupted update {state.get('started')} at step {step}; old HEAD {state.get('old_head')}")
    say(f"The earlier update stopped at step {step}/9 ({logmod.STEP_NAMES.get(step, '?')}).")
    if step == 9 and ctx.healthy():
        log.line("the app answers healthy: nothing to undo")
        logmod.clear_state(ctx.logs)
        say("The app is healthy; nothing to undo.")
        return 0
    code = roll_back(ctx, state, log, moment, f"recover after an interruption at step {step}", restore_db=step >= 6)
    if code == 1:
        logmod.clear_state(ctx.logs)
        return 0
    return code
