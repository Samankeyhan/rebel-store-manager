"""docs/RUNNING.md names real files, modules and commands (a guide that points at things that do not exist is worse than none)."""

import importlib.util
import re
from pathlib import Path

from db.backup import DEFAULT_KEEP

ROOT = Path(__file__).resolve().parent.parent
TEXT = (ROOT / "docs" / "RUNNING.md").read_text(encoding="utf-8")


def test_every_cmd_file_and_python_module_the_guide_names_exists():
    names = set(re.findall(r"\.\\([\w-]+\.cmd)", TEXT)) | set(re.findall(r"`([\w-]+\.cmd)`", TEXT))
    assert {"start-rebel.cmd", "stop-rebel.cmd"} <= names
    for name in names:
        assert (ROOT / name).is_file(), name
    modules = set(re.findall(r"-m (tools\.[\w.]+)", TEXT))
    assert {"tools.integrity_check", "tools.run_app"} & modules
    for module in modules:
        assert importlib.util.find_spec(module) is not None, module


def test_the_guide_has_the_restore_steps_in_order_and_the_real_numbers():
    steps = [
        ".\\stop-rebel.cmd",
        "Rename-Item data\\shop.db",
        "Copy-Item data\\backups\\daily-",
        ".\\start-rebel.cmd",
        "tools.integrity_check",
    ]
    restore = TEXT[TEXT.index("## 4. Restore"):TEXT.index("## 5.")]
    position = 0
    for step in steps:
        found = restore.find(step, position)
        assert found >= 0, step
        position = found
    assert f"newest {DEFAULT_KEEP}" in TEXT or f"newest **{DEFAULT_KEEP}**" in TEXT
    assert "robocopy data\\backups" in TEXT and "data\\restore-test" in TEXT


def test_the_files_the_guide_says_are_ignored_by_git_are_ignored():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    assert "data/logs/" in ignored and "data/restore-test/" in ignored and "data/backups/" in ignored
