from __future__ import annotations

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from voice_agent.persona import load_persona_config


API_URL = "https://api.openai.com/v1/audio/speech"


def openai_tts_enabled() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped or default


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return float(value)


def synthesize_to_file(text: str) -> Path:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    config = load_persona_config()
    body = {
        "model": _env_str("OPENAI_TTS_MODEL", config.openai_tts_model),
        "voice": _env_str("OPENAI_TTS_VOICE", config.openai_tts_voice),
        "input": text,
        "response_format": _env_str(
            "OPENAI_TTS_RESPONSE_FORMAT",
            config.openai_tts_response_format,
        ),
        "speed": _env_float("OPENAI_TTS_SPEED", config.openai_tts_speed),
    }
    instructions = _env_str("OPENAI_TTS_INSTRUCTIONS", config.openai_tts_instructions)
    if instructions:
        body["instructions"] = instructions

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            audio = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI TTS request failed: {exc.code} {detail}") from exc

    response_format = str(body["response_format"]).lower()
    suffix = ".wav"
    if response_format == "mp3":
        suffix = ".mp3"
    elif response_format == "aac":
        suffix = ".aac"
    elif response_format == "opus":
        suffix = ".opus"
    elif response_format == "flac":
        suffix = ".flac"
    elif response_format == "pcm":
        suffix = ".pcm"

    tmp = tempfile.NamedTemporaryFile(prefix="momo_openai_tts_", suffix=suffix, delete=False)
    try:
        tmp.write(audio)
        return Path(tmp.name)
    finally:
        tmp.close()
