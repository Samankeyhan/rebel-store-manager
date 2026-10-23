"""The screens the one-process server serves: `frontend/out/`, built once with `NEXT_PUBLIC_API_URL=/api`.
A marker file `frontend/out/.rebel-build.json` {api, git} records what the build was made for. The screens must be rebuilt when
`out/` or its marker is missing or was built for another API address; when they were built from an older git commit the
script only says so (the owner decides: `start-rebel.cmd --rebuild`)."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Callable

API_BASE = "/api"
MARKER = ".rebel-build.json"


class BuildError(Exception):
    pass


def git_head(root: Path, run: Callable = subprocess.run) -> str | None:
    """The current commit (None when git is not installed or this is not a repository)."""
    try:
        result = run(["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (result.stdout or "").strip()
    return text if getattr(result, "returncode", 1) == 0 and text else None


def read_marker(out_dir: Path) -> dict | None:
    try:
        data = json.loads((out_dir / MARKER).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def build_state(out_dir: Path, head: str | None, rebuild: bool) -> tuple[str, str]:
    """('ok' | 'build' | 'older', reason). 'build' means the screens must be built before starting."""
    if rebuild:
        return "build", "a rebuild was asked for"
    if not (out_dir / "index.html").is_file():
        return "build", "the screens have not been built yet"
    marker = read_marker(out_dir)
    if marker is None or marker.get("api") != API_BASE:
        return "build", f"the screens were not built for the one-process server (API address {API_BASE})"
    if head and marker.get("git") and marker["git"] != head:
        return "older", "the screens were built from an older version of the code"
    return "ok", "the screens are up to date"


def installed(frontend: Path) -> bool:
    """True when the dependencies are really there: the `next` launcher exists (a node_modules folder alone can be half-installed)."""
    bin_dir = frontend / "node_modules" / ".bin"
    return (bin_dir / "next.cmd").is_file() or (bin_dir / "next").is_file()


def build(
    root: Path,
    out_dir: Path,
    log_path: Path,
    head: str | None,
    which: Callable = shutil.which,
    run: Callable = subprocess.run,
    env: dict | None = None,
) -> None:
    """`npm ci` (only when node_modules/.bin/next.cmd is missing: an existing but half-installed node_modules is not enough) and `npm run build` with the API address set to /api. Raises BuildError."""
    npm = which("npm")
    if which("node") is None or npm is None:
        raise BuildError(
            "Node.js is needed once to build the screens, and it was not found.\n"
            "Install the LTS version from https://nodejs.org (accept the defaults), close this window, and double-click start-rebel.cmd again."
        )
    frontend = root / "frontend"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    full_env = dict(env or {})
    full_env["NEXT_PUBLIC_API_URL"] = API_BASE
    steps = []
    if not installed(frontend):
        steps.append([npm, "ci"])
    steps.append([npm, "run", "build"])
    with open(log_path, "wb") as log:
        for step in steps:
            log.write(f"$ {' '.join(step[1:])}\n".encode())
            try:
                result = run(step, cwd=str(frontend), env=full_env, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
            except (OSError, subprocess.SubprocessError) as exc:
                raise BuildError(f"Could not run npm ({type(exc).__name__}).") from None
            if getattr(result, "returncode", 1) != 0:
                raise BuildError(f"Building the screens failed (npm {' '.join(step[1:])}).")
    if not (out_dir / "index.html").is_file():
        raise BuildError("The build finished but frontend/out/index.html is missing.")
    (out_dir / MARKER).write_text(json.dumps({"api": API_BASE, "git": head}), encoding="utf-8")
