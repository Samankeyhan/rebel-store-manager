"""Guard: money is integer Rial everywhere; only db/currency.py converts it
(Rial <-> Toman, for display). Anything else multiplying or dividing by 10
(or by 0.1) in db/, api/ or pdf/ is a unit slip and fails this test."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("db", "api", "pdf")

# Allow-list (path -> why):
ALLOWED = {
    # The backend's single place that knows Toman = Rial / 10 (display only).
    "db/currency.py": "the display conversion itself",
}

PATTERN = re.compile(
    r"""
      [*/%]\s*10(?![\d._])          # x * 10, x / 10, x // 10, x % 10
    | (?<![\d._])10\s*\*            # 10 * x
    | [*/]\s*0?\.1(?![\d])          # x * 0.1, x / .1
    | divmod\([^)]*,\s*10\s*\)      # divmod(x, 10)
    | RIAL_PER_TOMAN                # the constant, outside its module
    """,
    re.VERBOSE,
)


def _offenders() -> list[str]:
    hits = []
    for folder in SCANNED:
        for path in sorted((ROOT / folder).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel in ALLOWED:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if PATTERN.search(line):
                    hits.append(f"{rel}:{number}: {line.strip()}")
    return hits


def test_no_money_is_scaled_by_ten_outside_db_currency():
    assert _offenders() == []


def test_the_guard_catches_what_it_should():
    for line in ("x = amount * 10", "y = rial / 10", "z = rial // 10", "t = 10 * price",
                 "u = price * 0.1", "w, r = divmod(rial, 10)", "v = n * RIAL_PER_TOMAN"):
        assert PATTERN.search(line), line
    for line in ("fee_bps / 10000", "x * 100", "x / 1000", "jy // 31", "range(10)", "days = 10"):
        assert not PATTERN.search(line), line
