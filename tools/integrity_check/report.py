"""Result objects and the plain-text rendering of the integrity check.
A check returns a `CheckResult`: FAIL rows (problems: they change the exit code), WARN rows (listed every run, exit code unchanged), INFO lines, or SKIPPED / ERROR with a reason.
Money in rows is always integer Rial; a row names table, id, field, stored value, expected value and the difference."""

import json
from dataclasses import dataclass, field
from fractions import Fraction

PASS, FAIL, WARN, SKIPPED, ERROR = "PASS", "FAIL", "WARN", "SKIPPED", "ERROR"


class CannotRun(Exception):
    """The run could not start (missing file, not a Rebel database, unreadable): exit code 2."""


def fmt(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, Fraction):
        value = float(value)
    if isinstance(value, float):
        return f"{value:.12g}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(fmt(v) for v in value) + "]"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


@dataclass
class Row:
    table: str
    id: object
    field: str
    stored: object
    expected: object
    diff: object = None
    note: str = ""

    def render(self) -> str:
        text = (
            f"{self.table} id={fmt(self.id)} field={self.field} "
            f"stored={fmt(self.stored)} expected={fmt(self.expected)}"
        )
        if self.diff is not None:
            text += f" diff={fmt(self.diff)}"
        return text + (f"  ({self.note})" if self.note else "")


@dataclass
class CheckResult:
    key: str
    name: str
    summary: str = ""
    fails: list[Row] = field(default_factory=list)
    warns: list[Row] = field(default_factory=list)
    infos: list[str] = field(default_factory=list)
    skipped: str | None = None
    error: str | None = None

    @property
    def status(self) -> str:
        if self.error is not None:
            return ERROR
        if self.skipped is not None:
            return SKIPPED
        if self.fails:
            return FAIL
        if self.warns:
            return WARN
        return PASS

    def render(self) -> list[str]:
        head = f"{self.status:<8}{self.key}. {self.name}"
        if self.skipped is not None:
            return [f"{head} - {self.skipped}"]
        if self.error is not None:
            return [f"{head} - could not run: {self.error}"]
        counts = self.summary
        if self.fails:
            counts += f"; {len(self.fails)} problem{'s' if len(self.fails) != 1 else ''}"
        if self.warns:
            counts += f"; {len(self.warns)} warning{'s' if len(self.warns) != 1 else ''}"
        lines = [f"{head} - {counts}" if counts else head]
        lines += [f"    FAIL {row.render()}" for row in self.fails]
        lines += [f"    WARN {row.render()}" for row in self.warns]
        lines += [f"    INFO {text}" for text in self.infos]
        return lines


def final_line(results: list[CheckResult]) -> tuple[str, int]:
    """(the last line, the exit code): 0 OK, 1 problems, 2 a check could not run (the run is incomplete)."""
    problems = sum(len(r.fails) for r in results)
    errors = sum(1 for r in results if r.error is not None)
    if errors:
        return f"INCOMPLETE: {errors} checks failed to run; {problems} problems found", 2
    if problems:
        return f"FAILED: {problems} problems", 1
    return "OK", 0
