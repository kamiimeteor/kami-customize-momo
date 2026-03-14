try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import sounddevice as sd
from scipy.io.wavfile import write
from pathlib import Path

fs = 16000
seconds = 5

OUTPUT_PATH = Path(__file__).resolve().parent / "voice_test.wav"


def main() -> int:
    print("Recording for 5 seconds...")
    audio = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype="int16")
    sd.wait()
    write(str(OUTPUT_PATH), fs, audio)
    print(f"Saved to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
