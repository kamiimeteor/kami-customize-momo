from __future__ import annotations

import argparse
import json
import time

from voice_agent.diagnostics import (
    NO_ACTIVE_WINDOW_ERROR,
    _get_serial,
    inspect_current_app_state,
    list_connected_devices,
    open_app_via_helper,
)
from voice_agent.openai_tts import openai_tts_enabled
from voice_agent.persona import load_persona_config


def _build_snapshot(expected_app_name: str | None) -> dict[str, object]:
    persona = load_persona_config()
    readiness = inspect_current_app_state(expected_app_name)
    portal_status = "ok" if readiness.portal_ready else "error"
    if readiness.portal_error == NO_ACTIVE_WINDOW_ERROR:
        portal_status = "no_active_window"

    return {
        "configured_serial": _get_serial(),
        "connected_devices": list(list_connected_devices()),
        "voice_output": {
            "enabled": persona.voice_output_enabled,
            "provider": persona.voice_output_provider,
            "openai_key": openai_tts_enabled(),
            "openai_voice": persona.openai_tts_voice,
            "openai_speed": persona.openai_tts_speed,
        },
        "portal": {
            "status": portal_status,
            "ready": readiness.portal_ready,
            "error": readiness.portal_error,
            "accessibility_enabled": readiness.accessibility_enabled,
            "portal_service_enabled": readiness.portal_service_enabled,
        },
        "foreground": readiness.foreground.to_dict(),
        "app_probe": {
            "expected_app_name": readiness.expected_app_name,
            "compatibility_status": readiness.compatibility_status,
            "compatibility_note": readiness.compatibility_note,
            "likely_unreadable": readiness.likely_unreadable,
        },
    }


def _print_human(snapshot: dict[str, object]) -> None:
    portal = snapshot["portal"]
    foreground = snapshot["foreground"]
    voice_output = snapshot["voice_output"]
    app_probe = snapshot["app_probe"]

    print("momo doctor")
    print(f"configured_serial: {snapshot['configured_serial'] or 'auto'}")
    devices = snapshot["connected_devices"]
    print(f"connected_devices: {', '.join(devices) if devices else 'none'}")
    print(
        "voice_output:"
        f" enabled={voice_output['enabled']}"
        f" provider={voice_output['provider']}"
        f" openai_key={voice_output['openai_key']}"
        f" voice={voice_output['openai_voice']}"
        f" speed={voice_output['openai_speed']}"
    )
    print(
        "portal:"
        f" status={portal['status']}"
        f" accessibility_enabled={portal['accessibility_enabled']}"
        f" portal_service_enabled={portal['portal_service_enabled']}"
    )
    if portal["error"]:
        print(f"portal_error: {portal['error']}")
    print(
        "foreground:"
        f" title={foreground['title'] or '-'}"
        f" package={foreground['package_name'] or '-'}"
        f" activity={foreground['activity_name'] or '-'}"
    )
    print(
        "app_probe:"
        f" expected={app_probe['expected_app_name'] or '-'}"
        f" compatibility={app_probe['compatibility_status']}"
        f" likely_unreadable={app_probe['likely_unreadable']}"
    )
    if app_probe["compatibility_note"]:
        print(f"note: {app_probe['compatibility_note']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", help="app name to diagnose")
    parser.add_argument(
        "--open-app",
        action="store_true",
        help="open the target app before checking readability",
    )
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    args = parser.parse_args()

    if args.open_app:
        if not args.app:
            raise SystemExit("--open-app requires --app")
        if not open_app_via_helper(args.app):
            raise SystemExit(f"failed to open app: {args.app}")
        time.sleep(4.0)

    snapshot = _build_snapshot(args.app)
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        _print_human(snapshot)
