"""python -m tools.update_app [--yes] [--port N] [--no-browser]    update the app safely (update-rebel.cmd does this)
python -m tools.update_app --recover                                undo an update that was interrupted
python -m tools.update_app --rehearse PATH                          try the next migrations on a copy of a database
Exit codes: 0 done / up to date, 1 refused or rolled back, 2 could not run. The updater that runs is always the previous version: every module
it needs is imported here, before `git pull` changes the files on disk. See docs/RUNNING.md section 6."""

import argparse
import sys

from tools.update_app import (  # noqa: F401  (all imported up front on purpose)
    context,
    errors,
    fsutil,
    invariants,
    log,
    migrate,
    preflight,
    recover,
    rehearse,
    rollback,
    steps,
)


def main(argv: list[str] | None = None, ctx: context.Ctx | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(prog="python -m tools.update_app", description="Safe update of Rebel Store Manager.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--recover", action="store_true", help="undo an update that was interrupted")
    mode.add_argument("--rehearse", metavar="PATH", help="try the migrations on a copy of this database (changes nothing else)")
    parser.add_argument("--yes", action="store_true", help="do not ask before closing the app")
    parser.add_argument("--port", type=int, default=8000, help="first port to try when the app starts (default 8000)")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser when the app starts")
    args = parser.parse_args(argv)
    ctx = ctx or context.Ctx()
    ctx.port, ctx.no_browser = args.port, args.no_browser
    try:
        if args.rehearse:
            return rehearse.rehearse(ctx, args.rehearse)
        if args.recover:
            return recover.recover(ctx)
        return steps.run_update(args, ctx)
    except KeyboardInterrupt:
        ctx.out("Interrupted. If the update had started, run:  .venv\\Scripts\\python -m tools.update_app --recover")
        return 2


if __name__ == "__main__":
    sys.exit(main())
