try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import subprocess
from pathlib import Path

from voice_agent.droidrun_runner import _adb_base_cmd

STATE_PATH = Path(__file__).resolve().parent.parent / ".portal_overlay_state"


def _write_state(visible: bool) -> None:
    STATE_PATH.write_text("visible\n" if visible else "hidden\n", encoding="utf-8")


def _read_state() -> bool:
    if not STATE_PATH.exists():
        return True
    return STATE_PATH.read_text(encoding="utf-8").strip() != "hidden"


def set_overlay_visible(visible: bool) -> bool:
    visible_str = "true" if visible else "false"
    result = subprocess.run(
        _adb_base_cmd()
        + [
            "shell",
            "content",
            "insert",
            "--uri",
            "content://com.droidrun.portal/overlay_visible",
            "--bind",
            f"visible:b:{visible_str}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    _write_state(visible)
    return True


def toggle_overlay() -> bool:
    new_visible = not _read_state()
    if not set_overlay_visible(new_visible):
        return False
    return new_visible
