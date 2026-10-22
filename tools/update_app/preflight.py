"""Step 1: the repository is on main with nothing changed, `.venv` exists, `git fetch` works. Returns what would come in.
Nothing is stopped or changed here. `git status --porcelain` counts untracked files too: the folders the app creates (data/, invoices/*.pdf,
frontend/out ...) are covered by .gitignore, so anything listed is the owner's own change."""

from dataclasses import dataclass, field

from tools.update_app.context import Ctx
from tools.update_app.errors import CannotRun, Refused


@dataclass
class Plan:
    old_head: str
    new_head: str
    commits: list[str] = field(default_factory=list)
    migration_changes: list[str] = field(default_factory=list)
    new_migrations: list[str] = field(default_factory=list)
    changed: set[str] = field(default_factory=set)

    @property
    def up_to_date(self) -> bool:
        return self.old_head == self.new_head


def _lines(result) -> list[str]:
    return [line for line in (result.stdout or "").splitlines() if line.strip()]


def preflight(ctx: Ctx) -> Plan:
    if not ctx.venv_python.is_file():
        raise Refused(
            f"The Python environment was not found: {ctx.venv_python}\n"
            "Open PowerShell in the project folder and run: python -m venv .venv ; .venv\\Scripts\\pip install -r requirements.txt"
        )
    ctx.git("update-index", "--refresh", "-q")  # file times can differ from git's index; this only refreshes it
    branch = ctx.git("rev-parse", "--abbrev-ref", "HEAD")
    if branch.returncode != 0:
        raise CannotRun(f"git could not read the current branch: {(branch.stderr or '').strip()}")
    name = (branch.stdout or "").strip()
    if name != "main":
        where = "not on any branch (detached HEAD)" if name == "HEAD" else f"on branch '{name}'"
        raise Refused(f"This copy is {where}. Updates only run on 'main'. Nothing was changed.\nAsk the planning chat before switching branches.")
    status = ctx.git("status", "--porcelain")
    if status.returncode != 0:
        raise CannotRun(f"git status failed: {(status.stderr or '').strip()}")
    dirty = _lines(status)
    if dirty:
        shown = "\n".join(f"  {line}" for line in dirty[:10]) + (f"\n  ... and {len(dirty) - 10} more" if len(dirty) > 10 else "")
        raise Refused(
            "There are changed or untracked files in the project folder, so the update would not be safe:\n"
            f"{shown}\nNothing was changed. Ask the planning chat what to do with them (the update never stashes, deletes or overwrites them)."
        )
    fetch = ctx.git("fetch", "origin")
    if fetch.returncode != 0:
        raise CannotRun(f"git fetch failed (is the internet connected?): {(fetch.stderr or '').strip()}")
    old = ctx.git("rev-parse", "HEAD")
    new = ctx.git("rev-parse", "origin/main")
    if old.returncode != 0 or new.returncode != 0:
        raise CannotRun("git could not read the commits (HEAD / origin/main).")
    old_head, new_head = old.stdout.strip(), new.stdout.strip()
    ancestor = ctx.git("merge-base", "--is-ancestor", "HEAD", "origin/main")
    if ancestor.returncode == 1:
        raise Refused("This copy has commits that are not on origin/main, so the update cannot fast-forward. Nothing was changed.")
    if ancestor.returncode != 0:
        raise CannotRun(f"git merge-base failed: {(ancestor.stderr or '').strip()}")
    plan = Plan(old_head, new_head)
    if plan.up_to_date:
        return plan
    plan.commits = _lines(ctx.git("log", "--oneline", f"{old_head}..{new_head}"))
    plan.migration_changes = _lines(ctx.git("diff", "--name-status", old_head, new_head, "--", "migrations"))
    plan.new_migrations = [parts[1] for parts in (line.split(None, 1) for line in plan.migration_changes) if parts[0] == "A" and len(parts) > 1]
    plan.changed = set(_lines(ctx.git("diff", "--name-only", old_head, new_head)))
    return plan
