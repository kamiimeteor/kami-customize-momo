try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import sounddevice as sd
from scipy.io.wavfile import write
from pathlib import Path
from voice_agent.audio_input import describe_input_device, resolve_input_device

fs = 16000
seconds = 5

OUTPUT_PATH = Path(__file__).resolve().parent / "voice_test.wav"


def main() -> int:
    try:
        input_device = resolve_input_device(fs, channels=1, dtype="int16")
    except Exception as e:
        print(f"Microphone initialization failed: {e}")
        return 1

    print(f"🎤 Using input device: {describe_input_device(input_device)}")
    print("Recording for 5 seconds...")
    audio = sd.rec(
        int(seconds * fs),
        samplerate=fs,
        channels=1,
        dtype="int16",
        device=input_device,
    )
    sd.wait()
    write(str(OUTPUT_PATH), fs, audio)
    print(f"Saved to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
