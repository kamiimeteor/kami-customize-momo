from __future__ import annotations

import argparse
import json
import time
from typing import Any

from voice_agent.diagnostics import (
    NO_ACTIVE_WINDOW_ERROR,
    _get_serial,
    command_probe,
    google_genai_key_status,
    inspect_current_app_state,
    list_connected_devices,
    llm_providers_from_config,
    open_app_via_helper_result,
    resolve_adb_bin_path,
    resolve_droidrun_bin_path,
    run_fix_portal_script,
    runtime_python_probe,
)
from voice_agent.openai_tts import openai_tts_enabled
from voice_agent.persona import load_persona_config


def _probe_environment() -> dict[str, Any]:
    runtime_python = runtime_python_probe()
    adb = command_probe("adb", resolve_adb_bin_path(), ["version"])
    droidrun = command_probe("droidrun", resolve_droidrun_bin_path(), ["--help"])
    ffmpeg = command_probe("ffmpeg", "ffmpeg", ["-version"])
    return {
        "runtime_python": runtime_python.to_dict(),
        "adb": adb.to_dict(),
        "droidrun": droidrun.to_dict(),
        "ffmpeg": ffmpeg.to_dict(),
    }


def _probe_llm_and_keys(persona_provider: str, voice_enabled: bool) -> dict[str, Any]:
    llm_providers = list(llm_providers_from_config())
    google_key_ok, google_key_name = google_genai_key_status()
    openai_key_ok = openai_tts_enabled()

    google_required = any(provider == "GoogleGenAI" for provider in llm_providers)
    openai_required = voice_enabled and persona_provider == "openai"

    return {
        "llm_providers": llm_providers,
        "google_genai": {
            "required": google_required,
            "ok": google_key_ok,
            "env_name": google_key_name,
        },
        "openai_tts": {
            "required": openai_required,
            "ok": openai_key_ok,
            "env_name": "OPENAI_API_KEY" if openai_key_ok else None,
        },
    }


def _build_snapshot(
    expected_app_name: str | None,
    open_app_result: dict[str, Any] | None,
    applied_fixes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    persona = load_persona_config()
    readiness = inspect_current_app_state(expected_app_name)
    portal_status = "ok" if readiness.portal_ready else "error"
    if readiness.portal_error == NO_ACTIVE_WINDOW_ERROR:
        portal_status = "no_active_window"

    environment = _probe_environment()
    providers = _probe_llm_and_keys(
        persona_provider=persona.voice_output_provider,
        voice_enabled=persona.voice_output_enabled,
    )

    snapshot = {
        "configured_serial": _get_serial(),
        "connected_devices": list(list_connected_devices()),
        "environment": environment,
        "providers": providers,
        "voice_output": {
            "enabled": persona.voice_output_enabled,
            "provider": persona.voice_output_provider,
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
        "app_open": open_app_result,
        "applied_fixes": applied_fixes or [],
        "fix_commands": [],
        "recommendations": [],
    }
    snapshot["fix_commands"] = _build_fix_commands(snapshot)
    snapshot["recommendations"] = _build_recommendations(snapshot)
    return snapshot


def _build_fix_commands(snapshot: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    portal = snapshot["portal"]
    providers = snapshot["providers"]
    app_probe = snapshot["app_probe"]

    if portal["accessibility_enabled"] is False or not portal["portal_service_enabled"]:
        commands.append("./fix_portal.sh")
    elif portal["status"] == "error" and portal["error"]:
        commands.append("./fix_portal.sh")
    elif portal["status"] == "no_active_window" and not app_probe["expected_app_name"]:
        commands.append("./run_doctor.sh --app 小红书 --open-app")

    if providers["google_genai"]["required"] and not providers["google_genai"]["ok"]:
        commands.append("export GEMINI_API_KEY='你的 Gemini API key'")
    if providers["openai_tts"]["required"] and not providers["openai_tts"]["ok"]:
        commands.append("export OPENAI_API_KEY='你的 OpenAI API key'")

    return commands


def _build_recommendations(snapshot: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []

    connected_devices = snapshot["connected_devices"]
    environment = snapshot["environment"]
    providers = snapshot["providers"]
    portal = snapshot["portal"]
    app_probe = snapshot["app_probe"]
    app_open = snapshot.get("app_open")

    if not connected_devices:
        recommendations.append("用 USB 连上手机，并确认 `adb devices` 能看到已授权设备。")

    if not environment["runtime_python"]["available"]:
        recommendations.append(
            "把可用的 DroidRun Python 环境设给 `DROIDRUN_PYTHON`，或确认 `$HOME/droidrun-env/bin/python` 存在。"
        )

    missing_modules = [
        name
        for name, ok in environment["runtime_python"]["required_modules"].items()
        if not ok
    ]
    if missing_modules:
        joined = ", ".join(missing_modules)
        recommendations.append(
            f"在运行环境里补装这些 Python 模块: {joined}。"
        )

    if not environment["adb"]["available"]:
        recommendations.append("安装 `adb`，或通过 `ADB_BIN` 指向正确路径。")

    if not environment["droidrun"]["available"]:
        recommendations.append("安装 `droidrun` CLI，或通过 `DROIDRUN_BIN` 指向正确路径。")

    if providers["google_genai"]["required"] and not providers["google_genai"]["ok"]:
        recommendations.append(
            "当前 `config.yaml` 在用 GoogleGenAI，给 shell 配上 `GEMINI_API_KEY` 或 `GOOGLE_API_KEY`。"
        )

    if providers["openai_tts"]["required"] and not providers["openai_tts"]["ok"]:
        recommendations.append(
            "当前语音输出走 OpenAI TTS，给 shell 配上 `OPENAI_API_KEY`，否则会回退或失声。"
        )

    if portal["accessibility_enabled"] is False or not portal["portal_service_enabled"]:
        recommendations.append("先跑 `./fix_portal.sh`，确认 Droidrun Portal 无障碍服务已开启。")

    if portal["status"] == "no_active_window" and not app_probe["expected_app_name"]:
        recommendations.append("保持手机亮屏解锁，并把一个正常 App 放到前台后再试。")

    if app_probe["likely_unreadable"]:
        if app_probe["compatibility_status"] == "restricted":
            recommendations.append(
                "当前这个 App 在本机上属于受限可读，换个页面试，或者优先换到小红书这类已验证可读的 App。"
            )
        else:
            recommendations.append("当前页面前台可见，但 Portal 读不到树，先换个页面再试。")
    elif app_probe["compatibility_status"] == "restricted":
        recommendations.append(
            "这个 App 当前被标记为受限兼容；如果后面动作跑不通，优先怀疑页面可读性，不要先怀疑 Portal 安装坏了。"
        )

    if app_open and not app_open["ok"]:
        recommendations.append(
            "这次 `--open-app` 没成功；先解决上面的运行环境或 LLM key 问题，再重试打开目标 App。"
        )

    if not recommendations:
        recommendations.append("当前核心链路基本正常，可以直接跑 `./run.sh` 做任务测试。")

    return recommendations


def _apply_safe_fixes(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    portal = snapshot["portal"]
    applied: list[dict[str, Any]] = []

    if portal["accessibility_enabled"] is False or not portal["portal_service_enabled"]:
        ok, detail = run_fix_portal_script()
        applied.append({"name": "fix_portal", "ok": ok, "detail": detail})
        return applied

    if portal["status"] == "error" and portal["error"]:
        ok, detail = run_fix_portal_script()
        applied.append({"name": "fix_portal", "ok": ok, "detail": detail})

    return applied


def _status_mark(ok: bool) -> str:
    return "OK" if ok else "FAIL"


def _print_human(snapshot: dict[str, Any]) -> None:
    env = snapshot["environment"]
    providers = snapshot["providers"]
    voice_output = snapshot["voice_output"]
    portal = snapshot["portal"]
    foreground = snapshot["foreground"]
    app_probe = snapshot["app_probe"]
    app_open = snapshot["app_open"]
    applied_fixes = snapshot["applied_fixes"]
    fix_commands = snapshot["fix_commands"]

    print("momo doctor")
    print(f"configured_serial: {snapshot['configured_serial'] or 'auto'}")
    devices = snapshot["connected_devices"]
    print(f"connected_devices: {', '.join(devices) if devices else 'none'}")
    print()

    print("environment")
    print(
        f"- runtime_python: {_status_mark(env['runtime_python']['available'])}"
        f" path={env['runtime_python']['python_path'] or '-'}"
        f" version={env['runtime_python']['version'] or '-'}"
    )
    if env["runtime_python"]["error"]:
        print(f"  error: {env['runtime_python']['error']}")
    modules = env["runtime_python"]["required_modules"]
    if modules:
        module_line = ", ".join(
            f"{name}={'ok' if ok else 'missing'}" for name, ok in modules.items()
        )
        print(f"  modules: {module_line}")
    print(
        f"- adb: {_status_mark(env['adb']['available'])}"
        f" path={env['adb']['path'] or '-'}"
        f" version={env['adb']['version'] or '-'}"
    )
    print(
        f"- droidrun: {_status_mark(env['droidrun']['available'])}"
        f" path={env['droidrun']['path'] or '-'}"
        f" version={env['droidrun']['version'] or '-'}"
    )
    print(
        f"- ffmpeg: {_status_mark(env['ffmpeg']['available'])}"
        f" path={env['ffmpeg']['path'] or '-'}"
        f" version={env['ffmpeg']['version'] or '-'}"
    )
    print()

    print("providers")
    print(
        f"- llm_providers: {', '.join(providers['llm_providers']) if providers['llm_providers'] else 'none'}"
    )
    print(
        f"- google_genai_key: {_status_mark(providers['google_genai']['ok'])}"
        f" required={providers['google_genai']['required']}"
        f" env={providers['google_genai']['env_name'] or '-'}"
    )
    print(
        f"- openai_tts_key: {_status_mark(providers['openai_tts']['ok'])}"
        f" required={providers['openai_tts']['required']}"
        f" env={providers['openai_tts']['env_name'] or '-'}"
    )
    print()

    print("voice_output")
    print(
        f"- enabled={voice_output['enabled']}"
        f" provider={voice_output['provider']}"
        f" voice={voice_output['openai_voice']}"
        f" speed={voice_output['openai_speed']}"
    )
    print()

    print("portal")
    print(
        f"- status={portal['status']}"
        f" accessibility_enabled={portal['accessibility_enabled']}"
        f" portal_service_enabled={portal['portal_service_enabled']}"
    )
    if portal["error"]:
        print(f"- error={portal['error']}")
    print()

    print("foreground")
    print(
        f"- title={foreground['title'] or '-'}"
        f" package={foreground['package_name'] or '-'}"
        f" activity={foreground['activity_name'] or '-'}"
    )
    print()

    print("app_probe")
    print(
        f"- expected={app_probe['expected_app_name'] or '-'}"
        f" compatibility={app_probe['compatibility_status']}"
        f" likely_unreadable={app_probe['likely_unreadable']}"
    )
    if app_probe["compatibility_note"]:
        print(f"- note={app_probe['compatibility_note']}")
    if app_open is not None:
        print(
            f"- open_app={_status_mark(app_open['ok'])}"
            f" detail={app_open['detail'] or '-'}"
        )
    if applied_fixes:
        for item in applied_fixes:
            print(f"- applied_fix={item['name']} {_status_mark(item['ok'])} detail={item['detail']}")
    print()

    print("fix_commands")
    if fix_commands:
        for item in fix_commands:
            print(f"- {item}")
    else:
        print("- none")
    print()

    print("recommendations")
    for item in snapshot["recommendations"]:
        print(f"- {item}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", help="app name to diagnose")
    parser.add_argument(
        "--open-app",
        action="store_true",
        help="open the target app before checking readability",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="apply safe automatic fixes such as Portal recovery, then re-check",
    )
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    args = parser.parse_args()

    open_app_result: dict[str, Any] | None = None
    if args.open_app:
        if not args.app:
            raise SystemExit("--open-app requires --app")
        ok, detail = open_app_via_helper_result(args.app)
        open_app_result = {"ok": ok, "detail": detail}
        if ok:
            time.sleep(4.0)

    snapshot = _build_snapshot(args.app, open_app_result)
    if args.fix:
        applied_fixes = _apply_safe_fixes(snapshot)
        if applied_fixes:
            snapshot = _build_snapshot(args.app, open_app_result, applied_fixes=applied_fixes)
        else:
            snapshot = _build_snapshot(
                args.app,
                open_app_result,
                applied_fixes=[{"name": "none", "ok": True, "detail": "no safe automatic fix was needed"}],
            )
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        _print_human(snapshot)
