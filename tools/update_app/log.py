"""The update log (`data/logs/update-<moment>.log`, one line per event, flushed to disk at once) and the state file
(`data/logs/update-state.json`) that says how far an update got. The state file exists only while an update is in progress or was
interrupted; a new update refuses to start while it exists, and `--recover` reads it."""

import json
import os
from pathlib import Path

STATE_FILE = "update-state.json"
STEP_NAMES = {
    1: "preflight",
    2: "integrity check before",
    3: "stop the app",
    4: "backup",
    5: "git pull",
    6: "dependencies and screens",
    7: "migrate",
    8: "integrity check after",
    9: "start the app",
}


class UpdateLog:
    def __init__(self, logs: Path, moment: str):
        logs.mkdir(parents=True, exist_ok=True)
        self.path = logs / f"update-{moment}.log"

    def line(self, text: str) -> None:
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(text.rstrip("\n") + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def step(self, number: int, status: str, detail: str = "") -> None:
        self.line(f"STEP {number}/9 {STEP_NAMES[number]}: {status}" + (f" - {detail}" if detail else ""))


def write_state(logs: Path, state: dict) -> None:
    logs.mkdir(parents=True, exist_ok=True)
    temp = logs / (STATE_FILE + ".tmp")
    with open(temp, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(state, indent=1))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, logs / STATE_FILE)


def read_state(logs: Path) -> dict | None:
    try:
        data = json.loads((logs / STATE_FILE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def state_exists(logs: Path) -> bool:
    return (logs / STATE_FILE).exists()


def clear_state(logs: Path) -> None:
    try:
        (logs / STATE_FILE).unlink()
    except OSError:
        pass
