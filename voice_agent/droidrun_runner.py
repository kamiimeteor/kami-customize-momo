import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
NO_ACTIVE_WINDOW_ERROR = "No active window or root filtered out"
PORTAL_A11Y_SERVICE = "com.droidrun.portal/.service.DroidrunAccessibilityService"


@dataclass(frozen=True)
class CommandExecutionResult:
    exit_code: int
    status: str
    detail: str | None = None


def _resolve_executable(env_name: str, command_name: str, fallback: Path | None) -> str:
    override = os.environ.get(env_name)
    if override:
        return override

    resolved = shutil.which(command_name)
    if resolved:
        return resolved

    if fallback and fallback.exists():
        return str(fallback)

    raise FileNotFoundError(
        f"Unable to find '{command_name}'. Set {env_name} or install it."
    )


def _read_config_value(key: str) -> str | None:
    if not CONFIG_PATH.exists():
        return None

    pattern = re.compile(rf"^\s*{re.escape(key)}:\s*(.+?)\s*$", re.MULTILINE)
    match = pattern.search(CONFIG_PATH.read_text(encoding="utf-8"))
    if not match:
        return None

    value = match.group(1).strip()
    if value in {"null", "None", "''", '""', ""}:
        return None
    return value


def _get_serial() -> str | None:
    return _read_config_value("serial")


def _adb_base_cmd() -> list[str]:
    adb_bin = _resolve_executable(
        "ADB_BIN",
        "adb",
        Path("/opt/homebrew/bin/adb"),
    )
    serial = _get_serial()
    cmd = [adb_bin]
    if serial:
        cmd.extend(["-s", serial])
    return cmd


def _run_capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _run_quiet(cmd: list[str]) -> int:
    result = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode


def _ensure_device_awake() -> None:
    base = _adb_base_cmd()
    commands = [
        ["shell", "input", "keyevent", "KEYCODE_WAKEUP"],
        ["shell", "wm", "dismiss-keyguard"],
    ]

    for command in commands:
        subprocess.run(
            base + command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def _press_home() -> None:
    subprocess.run(
        _adb_base_cmd() + ["shell", "input", "keyevent", "KEYCODE_HOME"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _restart_portal_accessibility_service() -> bool:
    base = _adb_base_cmd()
    commands = [
        ["shell", "settings", "put", "secure", "accessibility_enabled", "0"],
        ["shell", "settings", "put", "secure", "enabled_accessibility_services", PORTAL_A11Y_SERVICE],
        ["shell", "settings", "put", "secure", "accessibility_enabled", "1"],
    ]

    for command in commands:
        if _run_quiet(base + command) != 0:
            return False
        time.sleep(0.5)
    return True


def _open_accessibility_settings() -> None:
    _run_quiet(
        _adb_base_cmd()
        + ["shell", "am", "start", "-a", "android.settings.ACCESSIBILITY_SETTINGS"]
    )


def _extract_json_payload(raw_output: str):
    for line in raw_output.splitlines():
        line = line.strip()
        if "result=" in line:
            candidate = line.split("result=", 1)[1].strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        if line.startswith("{") or line.startswith("["):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

    try:
        return json.loads(raw_output.strip())
    except json.JSONDecodeError:
        return None


def _query_portal_state() -> tuple[bool, str | None]:
    output = _run_capture(
        _adb_base_cmd()
        + ["shell", "content", "query", "--uri", "content://com.droidrun.portal/state_full"]
    )
    payload = _extract_json_payload(output.stdout)

    if isinstance(payload, dict):
        if payload.get("status") == "error":
            return False, payload.get("error") or payload.get("message")
        if "result" in payload and isinstance(payload["result"], dict):
            payload = payload["result"]

    if isinstance(payload, dict) and all(
        key in payload for key in ("a11y_tree", "phone_state", "device_context")
    ):
        return True, None

    if output.returncode != 0:
        return False, output.stderr.strip() or output.stdout.strip()

    return False, "Portal state is unavailable"


def _extract_app_launch_intent(command: str) -> tuple[str | None, bool]:
    explicit_patterns = [
        r"^\s*(?:open|launch|start)\s+(.+?)\s*$",
        r"^\s*(?:打开|启动)\s*(.+?)\s*$",
    ]

    remainder = None
    for pattern in explicit_patterns:
        match = re.match(pattern, command, flags=re.IGNORECASE)
        if match:
            remainder = match.group(1).strip()
            break

    split_patterns = [
        r"\bthen\b",
        r"\band\b",
        r"然后",
        r"再",
        r"并且",
        r"，",
        r",",
        r"。",
        r";",
        r"；",
    ]

    if remainder:
        app_name, task = _split_embedded_follow_up(remainder)
        if app_name and task:
            return app_name, True

        parts = re.split(
            "|".join(split_patterns),
            remainder,
            maxsplit=1,
            flags=re.IGNORECASE,
        )
        app_name = parts[0].strip(" .，,;；。")
        has_follow_up = False
        if len(parts) > 1:
            has_follow_up = bool(parts[1].strip(" .，,;；。"))
        return (app_name or None), has_follow_up

    contextual_patterns = [
        r"^\s*在(?P<app>.+?)(?:里面|里|中)(?P<task>.+)$",
        r"^\s*用(?P<app>.+?)(?P<task>搜索.+)$",
        r"^\s*(?:in|inside|on)\s+(?P<app>.+?)[,:]\s*(?P<task>.+)$",
    ]

    for pattern in contextual_patterns:
        match = re.match(pattern, command, flags=re.IGNORECASE)
        if not match:
            continue

        app_name = match.group("app").strip(" .，,;；。")
        task = match.group("task").strip(" .，,;；。")
        if app_name and task:
            return app_name, True

    return None, False


def _split_embedded_follow_up(remainder: str) -> tuple[str | None, str | None]:
    action_markers = [
        "搜索",
        "搜",
        "查找",
        "查一下",
        "看看",
        "浏览",
        "进入",
        "打开第",
        "点开",
        "点击",
        "search ",
        "search for ",
        "find ",
        "scroll ",
        "open the ",
    ]

    normalized = remainder.strip(" .，,;；。")
    lower_normalized = normalized.lower()

    for marker in action_markers:
        marker_index = (
            lower_normalized.find(marker.lower())
            if marker.isascii()
            else normalized.find(marker)
        )
        if marker_index <= 0:
            continue

        app_name = normalized[:marker_index].strip(" .，,;；。")
        task = normalized[marker_index:].strip(" .，,;；。")
        if app_name and task:
            return app_name, task

    return None, None


def _direct_open_app(app_name: str) -> bool:
    override = os.environ.get("DROIDRUN_PYTHON")
    if override:
        python_bin = override
    else:
        fallback = Path.home() / "droidrun-env" / "bin" / "python"
        if fallback.exists():
            python_bin = str(fallback)
        else:
            python_bin = _resolve_executable("DROIDRUN_PYTHON", "python", None)

    helper_script = Path(__file__).resolve().parent / "droidrun_open_app.py"
    result = subprocess.run([python_bin, str(helper_script), app_name], check=False)
    return result.returncode == 0


def _run_droidrun(command: str) -> int:
    droidrun_bin = _resolve_executable(
        "DROIDRUN_BIN",
        "droidrun",
        Path.home() / "droidrun-env" / "bin" / "droidrun",
    )
    result = subprocess.run(
        [droidrun_bin, "run", command],
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    return result.returncode


def _run_droidrun_setup() -> bool:
    droidrun_bin = _resolve_executable(
        "DROIDRUN_BIN",
        "droidrun",
        Path.home() / "droidrun-env" / "bin" / "droidrun",
    )
    result = subprocess.run(
        [droidrun_bin, "setup"],
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    return result.returncode == 0


def _wait_for_portal_ready(timeout_seconds: float = 8.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        ready, _ = _query_portal_state()
        if ready:
            return True
        time.sleep(0.5)
    return False


def _attempt_portal_recovery(
    *,
    app_name: str | None = None,
    settle_seconds: float = 25.0,
    timeout_seconds: float = 25.0,
) -> tuple[bool, str | None]:
    print("Portal is still not ready. Attempting automatic recovery...")
    if _restart_portal_accessibility_service():
        print("Restarted Portal accessibility service.")
        if _wait_for_portal_ready(timeout_seconds=8.0):
            if app_name:
                _press_home()
                time.sleep(1.0)
                print(f"Re-opening '{app_name}' after accessibility restart...")
                if not _direct_open_app(app_name):
                    return False, f"direct_open_failed_after_recovery: {app_name}"
                if not _wait_for_portal_ready(timeout_seconds=timeout_seconds):
                    return False, f"portal_not_ready_after_recovery_reopen: {app_name}"
            return True, None

    if not _run_droidrun_setup():
        return False, "portal_recovery_setup_failed"

    print(f"Waiting {int(settle_seconds)}s for Portal service to settle...")
    time.sleep(settle_seconds)

    if not _wait_for_portal_ready(timeout_seconds=timeout_seconds):
        if app_name:
            _press_home()
            time.sleep(1.0)
            print(f"Re-opening '{app_name}' after Portal recovery...")
            if not _direct_open_app(app_name):
                return False, f"direct_open_failed_after_recovery: {app_name}"
            if _wait_for_portal_ready(timeout_seconds=timeout_seconds):
                return True, None
        return False, f"portal_recovery_not_ready: {app_name or 'unknown_app'}"

    if app_name:
        _press_home()
        time.sleep(1.0)
        print(f"Re-opening '{app_name}' after Portal recovery...")
        if not _direct_open_app(app_name):
            return False, f"direct_open_failed_after_recovery: {app_name}"
        if not _wait_for_portal_ready(timeout_seconds=timeout_seconds):
            return False, f"portal_not_ready_after_recovery_reopen: {app_name}"

    return True, None


def _prime_target_app_context(
    command: str,
    *,
    timeout_seconds: float = 12.0,
) -> tuple[bool, str | None]:
    app_name, has_follow_up = _extract_app_launch_intent(command)
    if not app_name or not has_follow_up:
        return True, None

    print(f"Priming target app '{app_name}' before running DroidRun...")
    if not _direct_open_app(app_name):
        return False, f"direct_open_failed: {app_name}"

    if not _wait_for_portal_ready(timeout_seconds=timeout_seconds):
        recovered, detail = _attempt_portal_recovery(app_name=app_name)
        if not recovered:
            return False, detail or f"portal_not_ready_after_open: {app_name}"

    return True, None


def run_droidrun_command_result(command: str) -> CommandExecutionResult:
    _ensure_device_awake()
    ready, error = _query_portal_state()
    if ready:
        primed, detail = _prime_target_app_context(command)
        if not primed:
            print("Opened the target app, but Portal still is not ready.")
            print("Keep the app in the foreground and try again.")
            return CommandExecutionResult(
                exit_code=1,
                status="failed",
                detail=detail,
            )

        exit_code = _run_droidrun(command)
        detail = None if exit_code == 0 else f"droidrun_exit_code={exit_code}"
        status = "completed" if exit_code == 0 else "failed"
        return CommandExecutionResult(exit_code=exit_code, status=status, detail=detail)

    if error != NO_ACTIVE_WINDOW_ERROR:
        print(f"Portal state check failed: {error}")
        if error == "Accessibility service not available":
            recovered, detail = _attempt_portal_recovery()
            if recovered:
                primed, prime_detail = _prime_target_app_context(command)
                if not primed:
                    return CommandExecutionResult(
                        exit_code=1,
                        status="failed",
                        detail=prime_detail,
                    )

                exit_code = _run_droidrun(command)
                detail = None if exit_code == 0 else f"droidrun_exit_code={exit_code}"
                status = "completed" if exit_code == 0 else "failed"
                return CommandExecutionResult(
                    exit_code=exit_code,
                    status=status,
                    detail=detail,
                )

            _open_accessibility_settings()
        return CommandExecutionResult(
            exit_code=1,
            status="failed",
            detail=f"portal_state_check_failed: {error}",
        )

    app_name, should_rerun_original_command = _extract_app_launch_intent(command)
    if not app_name:
        print("DroidRun cannot read the current UI.")
        print("Bring a normal app to the foreground on the phone, then try again.")
        return CommandExecutionResult(
            exit_code=1,
            status="failed",
            detail="portal_no_active_window",
        )

    print(f"Portal has no usable active window. Trying to open '{app_name}' directly...")
    if not _direct_open_app(app_name):
        print(f"Failed to open '{app_name}' directly.")
        return CommandExecutionResult(
            exit_code=1,
            status="failed",
            detail=f"direct_open_failed: {app_name}",
        )

    if not _wait_for_portal_ready():
        recovered, detail = _attempt_portal_recovery(app_name=app_name)
        if not recovered:
            print("Opened the app, but Portal still cannot read the UI.")
            print("Keep the app in the foreground and try again.")
            return CommandExecutionResult(
                exit_code=1,
                status="failed",
                detail=detail or f"portal_not_ready_after_open: {app_name}",
            )

    if should_rerun_original_command:
        exit_code = _run_droidrun(command)
        detail = None if exit_code == 0 else f"droidrun_exit_code={exit_code}"
        status = "completed" if exit_code == 0 else "failed"
        return CommandExecutionResult(exit_code=exit_code, status=status, detail=detail)

    return CommandExecutionResult(
        exit_code=0,
        status="completed",
        detail=f"app_opened_directly: {app_name}",
    )


def run_droidrun_command(command: str) -> int:
    return run_droidrun_command_result(command).exit_code
