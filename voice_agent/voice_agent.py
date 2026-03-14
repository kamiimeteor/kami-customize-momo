try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import sounddevice as sd
from scipy.io.wavfile import write
import whisper
import os
from voice_agent.droidrun_runner import run_droidrun_command

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
fs = 16000
seconds = 4
model = whisper.load_model("base")


def main() -> int:
    print("🎙️ Speak...")
    audio = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype="int16")
    sd.wait()
    wav_path = os.path.join(SCRIPT_DIR, "cmd.wav")
    write(wav_path, fs, audio)

    text = model.transcribe(wav_path)["text"]
    print("🧠 You said:", text)
    return run_droidrun_command(text)


if __name__ == "__main__":
    raise SystemExit(main())
