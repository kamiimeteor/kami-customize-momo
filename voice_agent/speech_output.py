from __future__ import annotations

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import os
import re
import subprocess
import sys
import threading
from functools import lru_cache
from pathlib import Path

from voice_agent.openai_tts import openai_tts_enabled, synthesize_to_file
from voice_agent.persona import load_persona_config


PREFERRED_ZH_VOICES = (
    "Tingting",
    "Meijia",
    "Sin-ji",
    "Eddy (Chinese (China mainland))",
    "Flo (Chinese (China mainland))",
    "Grandma (Chinese (China mainland))",
    "Grandpa (Chinese (China mainland))",
)


def speech_enabled() -> bool:
    override = os.environ.get("MOMO_SPEECH_ENABLED")
    if override is not None:
        return override.strip().lower() in {"1", "true", "yes", "on"}
    return load_persona_config().voice_output_enabled


def _debug_enabled() -> bool:
    return os.environ.get("MOMO_SPEECH_DEBUG", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _debug(message: str) -> None:
    if _debug_enabled():
        print(f"[momo-speech] {message}", file=sys.stderr, flush=True)


@lru_cache(maxsize=1)
def _available_voices() -> tuple[str, ...]:
    if sys.platform != "darwin":
        return ()

    result = subprocess.run(
        ["say", "-v", "?"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ()

    voices: list[str] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^(.*?)\s+[a-z]{2}_[A-Z]{2}\s+#", stripped)
        if not match:
            continue
        voice = match.group(1).strip()
        voices.append(voice)
    return tuple(voices)


def _resolve_voice() -> str | None:
    config = load_persona_config()
    configured_voice = config.system_voice_output_voice.strip()
    available = _available_voices()

    if configured_voice:
        if configured_voice in available:
            return configured_voice
        # Accept direct configured voice even if parsing missed it.
        return configured_voice

    for voice in PREFERRED_ZH_VOICES:
        if voice in available:
            return voice
    return None


def _build_say_command(text: str) -> list[str]:
    config = load_persona_config()
    cmd = [config.system_voice_output_command]
    voice = _resolve_voice()
    if voice:
        cmd.extend(["-v", voice])
    if config.system_voice_output_rate > 0:
        cmd.extend(["-r", str(config.system_voice_output_rate)])
    cmd.append(text)
    return cmd


def _play_audio_file_blocking(path: Path) -> int:
    result = subprocess.run(
        ["/usr/bin/afplay", str(path)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
    return result.returncode


def _provider() -> str:
    override = os.environ.get("MOMO_SPEECH_PROVIDER", "").strip().lower()
    if override:
        return override
    return load_persona_config().voice_output_provider.strip().lower() or "system"


def _speak_with_system(text: str) -> int:
    _debug(f"system fallback voice={_resolve_voice()!r}")
    result = subprocess.run(
        _build_say_command(text),
        check=False,
    )
    return result.returncode


def speak_text(text: str) -> None:
    text = text.strip()
    if not text or not speech_enabled() or sys.platform != "darwin":
        if text and _debug_enabled():
            _debug("speech skipped because disabled or unsupported platform")
        return

    provider = _provider()
    _debug(
        f"provider={provider} enabled={speech_enabled()} openai_key={openai_tts_enabled()}"
    )
    if provider == "openai" and openai_tts_enabled():
        def _run() -> None:
            try:
                _debug("attempting openai tts synthesis")
                audio_path = synthesize_to_file(text)
                _debug(f"openai tts synthesis ok path={audio_path}")
                _play_audio_file_blocking(audio_path)
            except Exception as exc:
                _debug(f"openai tts failed, falling back to system: {exc}")
                subprocess.Popen(
                    _build_say_command(text),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

        threading.Thread(target=_run, daemon=True).start()
        return

    subprocess.Popen(
        _build_say_command(text),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def speak_text_blocking(text: str) -> int:
    text = text.strip()
    if not text or sys.platform != "darwin":
        return 1

    provider = _provider()
    _debug(
        f"blocking provider={provider} enabled={speech_enabled()} openai_key={openai_tts_enabled()}"
    )
    if provider == "openai" and openai_tts_enabled():
        try:
            _debug("blocking openai tts synthesis start")
            audio_path = synthesize_to_file(text)
            _debug(f"blocking openai tts synthesis ok path={audio_path}")
            return _play_audio_file_blocking(audio_path)
        except Exception as exc:
            _debug(f"blocking openai tts failed, falling back to system: {exc}")
            return _speak_with_system(text)

    return _speak_with_system(text)
