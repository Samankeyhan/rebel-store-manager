"""Finding a free port for the app: the default first, then the next ones; a port is skipped when something is already
listening on it or when Windows has reserved it (`netsh interface ipv4 show excludedportrange protocol=tcp`).
Everything that touches the system (netsh, a socket) is a parameter, so the logic is tested with invented busy and reserved ports."""

import re
import socket
import subprocess
from typing import Callable

DEFAULT_PORT = 8000
SPAN = 100  # 8000..8099

_RANGE = re.compile(r"^\s*(\d+)\s+(\d+)\s*\*?\s*$")


class NoFreePort(Exception):
    def __init__(self, first: int, last: int, busy: list[int], reserved: list[int]):
        self.first, self.last, self.busy, self.reserved = first, last, busy, reserved
        super().__init__(
            f"No free port between {first} and {last} (busy: {busy or 'none'}; reserved by Windows: {reserved or 'none'})."
        )


def parse_excluded_ranges(text: str) -> list[tuple[int, int]]:
    """The (start, end) pairs of netsh's table; header lines, blank lines and the `*` note are ignored."""
    ranges = []
    for line in text.splitlines():
        match = _RANGE.match(line)
        if match:
            ranges.append((int(match.group(1)), int(match.group(2))))
    return ranges


def excluded_ranges(run: Callable[..., "subprocess.CompletedProcess"] = subprocess.run) -> list[tuple[int, int]]:
    """The ranges Windows reserves for TCP; an empty list when netsh is not there or fails (a bind test then decides)."""
    try:
        result = run(
            ["netsh", "interface", "ipv4", "show", "excludedportrange", "protocol=tcp"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_excluded_ranges(result.stdout or "") if getattr(result, "returncode", 1) == 0 else []


def is_excluded(port: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= port <= end for start, end in ranges)


def is_busy(port: int, host: str = "127.0.0.1") -> bool:
    """Something listens on the port, or it cannot be bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.3)
        if probe.connect_ex((host, port)) == 0:
            return True
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as binder:
        try:
            binder.bind((host, port))
        except OSError:
            return True
    return False


def find_port(
    preferred: int = DEFAULT_PORT,
    span: int = SPAN,
    ranges: list[tuple[int, int]] | None = None,
    busy: Callable[[int], bool] = is_busy,
) -> tuple[int, list[int], list[int]]:
    """(port, busy ports skipped, reserved ports skipped). Raises NoFreePort when none of preferred..preferred+span-1 is usable."""
    reserved_ranges = ranges if ranges is not None else []
    skipped_busy: list[int] = []
    skipped_reserved: list[int] = []
    for port in range(preferred, preferred + span):
        if is_excluded(port, reserved_ranges):
            skipped_reserved.append(port)
        elif busy(port):
            skipped_busy.append(port)
        else:
            return port, skipped_busy, skipped_reserved
    raise NoFreePort(preferred, preferred + span - 1, skipped_busy, skipped_reserved)
