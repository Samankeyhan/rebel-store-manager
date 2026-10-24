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


def test_the_go_live_section_names_the_tool_its_options_and_the_files_it_makes():
    section = TEXT.split("## 10. Go-live reset")[1]
    assert importlib.util.find_spec("tools.go_live_reset") is not None
    for needle in ("python -m tools.go_live_reset", "--apply", "RESET shop.db", "--product-unit-cost", "--reset-service-costs",
                   "pre-go-live", "audit-archive-golive-", "clear the stocktake draft", "invoice PDFs", "tools.integrity_check"):
        assert needle.lower() in section.lower(), needle
    from tools.go_live_reset.__main__ import main  # noqa: F401  the documented module runs


def test_the_real_use_guide_tells_the_owner_to_type_the_cost_on_every_material_gain():
    text = (ROOT / "docs" / "real-use-test.md").read_text(encoding="utf-8")
    assert "Type the unit cost on every material gain" in text and "go-live reset" in text


def test_the_update_section_names_the_command_its_options_the_files_and_the_rollbacks():
    update = TEXT[TEXT.index("## 6. Update the app"):TEXT.index("## 7.")]
    assert (ROOT / "update-rebel.cmd").is_file() and importlib.util.find_spec("tools.update_app") is not None
    for needle in ("update-rebel.cmd", "--rehearse", "--recover", "--yes", "type yes", "pre-update", "update-state.json", "update-<moment>.log",
                   "shop-failed-update-", "the previous version", "untracked", "git reset --hard", "never touches git, the app",
                   "WARN` never stops it", "exit code 0 = done, 1 = refused or rolled back, 2 = could not run"):
        assert needle.lower() in update.lower(), needle
    manual = update[update.index("## 6a."):update.index("## 6b.")]
    assert "Everything entered since the update is lost" in manual and "git reset --hard <old HEAD" in manual
    interrupted = update[update.index("## 6b."):]
    for step in ("| 1 or 2 |", "| 3 or 4 |", "| 5 |", "| 6, 7 or 8 |", "| 9 |"):
        assert step in interrupted, step


def test_the_mark_live_subsection_names_the_command_the_phrase_and_the_steps_in_order():
    section = TEXT.split("### Mark a database live")[1]
    steps = [".\stop-rebel.cmd", "-m tools.go_live_reset --mark-live\n", "-m tools.go_live_reset --mark-live --apply", "MARK LIVE shop.db", ".\start-rebel.cmd"]
    position = 0
    for step in steps:
        found = section.find(step, position)
        assert found >= 0, step
        position = found
