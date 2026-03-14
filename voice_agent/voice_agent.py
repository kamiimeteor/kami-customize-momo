try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import sounddevice as sd
from scipy.io.wavfile import write
import whisper
import os
from voice_agent.audio_input import describe_input_device, resolve_input_device
from voice_agent.conversation import process_user_command
from voice_agent.persona import startup_banner

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
fs = 16000
seconds = 4
model = whisper.load_model("base")


def main() -> int:
    try:
        input_device = resolve_input_device(fs, channels=1, dtype="int16")
    except Exception as e:
        print(f"Microphone initialization failed: {e}")
        return 1

    print(startup_banner())
    print(f"🎤 Using input device: {describe_input_device(input_device)}")
    print("🎙️ Speak...")
    audio = sd.rec(
        int(seconds * fs),
        samplerate=fs,
        channels=1,
        dtype="int16",
        device=input_device,
    )
    sd.wait()
    wav_path = os.path.join(SCRIPT_DIR, "cmd.wav")
    write(wav_path, fs, audio)

    text = model.transcribe(wav_path)["text"]
    print("🧠 You said:", text)
    return process_user_command(text, source="voice_once")


if __name__ == "__main__":
    raise SystemExit(main())
