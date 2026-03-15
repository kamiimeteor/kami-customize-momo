from __future__ import annotations

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
NO_ACTIVE_WINDOW_ERROR = "No active window or root filtered out"
PORTAL_A11Y_SERVICE = "com.droidrun.portal/.service.DroidrunAccessibilityService"
PORTAL_A11Y_SERVICE_ALIASES = (
    PORTAL_A11Y_SERVICE,
    "com.droidrun.portal/com.droidrun.portal.service.DroidrunAccessibilityService",
)

KNOWN_APP_COMPATIBILITY = (
    {
        "name": "微信",
        "package": "com.tencent.mm",
        "status": "restricted",
        "note": "WeChat can expose a focused window but still withhold a usable accessibility root from Portal on this device.",
    },
    {
        "name": "小红书",
        "package": "com.xingin.xhs",
        "status": "supported",
        "note": "Xiaohongshu is currently readable by Portal on this device.",
    },
)


@dataclass(frozen=True)
class ForegroundApp:
    title: str | None = None
    package_name: str | None = None
    activity_name: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "title": self.title,
            "package_name": self.package_name,
            "activity_name": self.activity_name,
        }


@dataclass(frozen=True)
class AppReadinessReport:
    expected_app_name: str | None
    portal_ready: bool
    portal_error: str | None
    accessibility_enabled: bool | None
    portal_service_enabled: bool
    foreground: ForegroundApp
    compatibility_status: str
    compatibility_note: str | None
    likely_unreadable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_app_name": self.expected_app_name,
            "portal_ready": self.portal_ready,
            "portal_error": self.portal_error,
            "accessibility_enabled": self.accessibility_enabled,
            "portal_service_enabled": self.portal_service_enabled,
            "foreground": self.foreground.to_dict(),
            "compatibility_status": self.compatibility_status,
            "compatibility_note": self.compatibility_note,
            "likely_unreadable": self.likely_unreadable,
        }


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


def adb_base_cmd() -> list[str]:
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


def run_capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _extract_json_payload(raw_output: str) -> Any:
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


def query_portal_state() -> tuple[bool, str | None, dict[str, Any] | None]:
    output = run_capture(
        adb_base_cmd()
        + ["shell", "content", "query", "--uri", "content://com.droidrun.portal/state_full"]
    )
    payload = _extract_json_payload(output.stdout)

    if isinstance(payload, dict):
        if payload.get("status") == "error":
            return False, payload.get("error") or payload.get("message"), None
        if "result" in payload and isinstance(payload["result"], dict):
            payload = payload["result"]

    if isinstance(payload, dict) and all(
        key in payload for key in ("a11y_tree", "phone_state", "device_context")
    ):
        return True, None, payload

    if output.returncode != 0:
        return False, output.stderr.strip() or output.stdout.strip(), None

    return False, "Portal state is unavailable", None


def get_accessibility_state() -> tuple[bool | None, tuple[str, ...]]:
    enabled_raw = run_capture(
        adb_base_cmd() + ["shell", "settings", "get", "secure", "accessibility_enabled"]
    )
    services_raw = run_capture(
        adb_base_cmd()
        + ["shell", "settings", "get", "secure", "enabled_accessibility_services"]
    )

    enabled_value = enabled_raw.stdout.strip()
    accessibility_enabled: bool | None
    if enabled_value in {"1", "0"}:
        accessibility_enabled = enabled_value == "1"
    else:
        accessibility_enabled = None

    services_value = services_raw.stdout.strip()
    if services_value in {"", "null", "None"}:
        return accessibility_enabled, ()

    services = tuple(item.strip() for item in services_value.split(":") if item.strip())
    return accessibility_enabled, services


def list_connected_devices() -> tuple[str, ...]:
    output = run_capture(adb_base_cmd()[:1] + ["devices", "-l"])
    devices: list[str] = []
    for line in output.stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("List of devices attached"):
            continue
        parts = stripped.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return tuple(devices)


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE).lower()


def _foreground_from_portal_payload(payload: dict[str, Any] | None) -> ForegroundApp:
    if not isinstance(payload, dict):
        return ForegroundApp()

    phone_state = payload.get("phone_state", {})
    if not isinstance(phone_state, dict):
        return ForegroundApp()

    return ForegroundApp(
        title=str(phone_state.get("currentApp") or "").strip() or None,
        package_name=str(phone_state.get("packageName") or "").strip() or None,
        activity_name=str(phone_state.get("activityName") or "").strip() or None,
    )


def _focused_window_title() -> str | None:
    output = run_capture(adb_base_cmd() + ["shell", "dumpsys", "accessibility"])
    for line in output.stdout.splitlines():
        stripped = line.strip()
        if "A11yWindow[AccessibilityWindowInfo[" not in stripped:
            continue
        if "focused=true" not in stripped or "active=true" not in stripped:
            continue
        match = re.search(r"title=(.*?), displayId=", stripped)
        if not match:
            continue
        title = match.group(1).strip()
        if title and title != "null":
            return title
    return None


def _foreground_from_dumpsys() -> ForegroundApp:
    title = _focused_window_title()

    commands = [
        adb_base_cmd() + ["shell", "dumpsys", "activity", "activities"],
        adb_base_cmd() + ["shell", "dumpsys", "window", "windows"],
    ]
    patterns = (
        r"mResumedActivity:.*?\s([A-Za-z0-9._]+)/([A-Za-z0-9.$_]+)",
        r"topResumedActivity=.*?\s([A-Za-z0-9._]+)/([A-Za-z0-9.$_]+)",
        r"mCurrentFocus=.*?\s([A-Za-z0-9._]+)/([A-Za-z0-9.$_]+)",
        r"mFocusedApp=.*?\s([A-Za-z0-9._]+)/([A-Za-z0-9.$_]+)",
    )

    for command in commands:
        output = run_capture(command)
        for pattern in patterns:
            match = re.search(pattern, output.stdout)
            if not match:
                continue
            package_name = match.group(1).strip()
            activity_name = match.group(2).strip()
            return ForegroundApp(
                title=title,
                package_name=package_name or None,
                activity_name=activity_name or None,
            )

    return ForegroundApp(title=title)


def get_foreground_app(portal_payload: dict[str, Any] | None = None) -> ForegroundApp:
    foreground = _foreground_from_portal_payload(portal_payload)
    if foreground.package_name or foreground.title:
        return foreground
    return _foreground_from_dumpsys()


def _app_matches_expected(expected_app_name: str | None, foreground: ForegroundApp) -> bool:
    expected = _normalize(expected_app_name)
    if not expected:
        return False

    candidates = [
        _normalize(foreground.title),
        _normalize(foreground.package_name),
        _normalize(foreground.activity_name),
    ]
    return any(expected and expected in candidate for candidate in candidates if candidate)


def classify_app_compatibility(
    expected_app_name: str | None,
    foreground: ForegroundApp,
) -> tuple[str, str | None]:
    expected = _normalize(expected_app_name)
    title = _normalize(foreground.title)
    package_name = foreground.package_name or ""

    for item in KNOWN_APP_COMPATIBILITY:
        if expected and expected == _normalize(item["name"]):
            return str(item["status"]), str(item["note"])
        if title and title == _normalize(item["name"]):
            return str(item["status"]), str(item["note"])
        if package_name == item["package"]:
            return str(item["status"]), str(item["note"])

    return "unknown", None


def inspect_current_app_state(expected_app_name: str | None = None) -> AppReadinessReport:
    portal_ready, portal_error, payload = query_portal_state()
    accessibility_enabled, services = get_accessibility_state()
    foreground = get_foreground_app(payload)
    compatibility_status, compatibility_note = classify_app_compatibility(
        expected_app_name,
        foreground,
    )

    foreground_matches = _app_matches_expected(expected_app_name, foreground)
    likely_unreadable = (
        not portal_ready
        and portal_error == NO_ACTIVE_WINDOW_ERROR
        and (
            foreground_matches
            or (
                compatibility_status == "restricted"
                and bool(foreground.package_name or foreground.title)
            )
        )
    )

    return AppReadinessReport(
        expected_app_name=expected_app_name,
        portal_ready=portal_ready,
        portal_error=portal_error,
        accessibility_enabled=accessibility_enabled,
        portal_service_enabled=any(service in services for service in PORTAL_A11Y_SERVICE_ALIASES),
        foreground=foreground,
        compatibility_status=compatibility_status,
        compatibility_note=compatibility_note,
        likely_unreadable=likely_unreadable,
    )


def probe_expected_app_readability(expected_app_name: str) -> tuple[bool, str | None]:
    report = inspect_current_app_state(expected_app_name)
    if not report.likely_unreadable:
        return False, None

    if report.compatibility_status == "restricted":
        return True, f"app_ui_unreadable_known: {expected_app_name}"
    return True, f"app_ui_unreadable: {expected_app_name}"


def open_app_via_helper(app_name: str) -> bool:
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
