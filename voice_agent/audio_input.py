try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import os

import sounddevice as sd


def _device_name(device: int) -> str:
    return str(sd.query_devices(device)["name"])


def resolve_input_device(
    samplerate: int,
    channels: int = 1,
    dtype: str = "int16",
) -> int | None:
    env_device = os.environ.get("VOICE_INPUT_DEVICE")
    if env_device:
        device = int(env_device)
        sd.check_input_settings(
            device=device,
            samplerate=samplerate,
            channels=channels,
            dtype=dtype,
        )
        return device

    default_input, _default_output = sd.default.device
    if default_input is not None and int(default_input) >= 0:
        sd.check_input_settings(
            device=int(default_input),
            samplerate=samplerate,
            channels=channels,
            dtype=dtype,
        )
        return int(default_input)

    for index, device in enumerate(sd.query_devices()):
        if device["max_input_channels"] < channels:
            continue
        try:
            sd.check_input_settings(
                device=index,
                samplerate=samplerate,
                channels=channels,
                dtype=dtype,
            )
            return index
        except Exception:
            continue

    raise RuntimeError(
        "No usable microphone was found. Check macOS microphone permission or set VOICE_INPUT_DEVICE."
    )


def describe_input_device(device: int | None) -> str:
    if device is None:
        return "system default microphone"
    return _device_name(device)
