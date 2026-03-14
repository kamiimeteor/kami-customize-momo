try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import sounddevice as sd
from scipy.io.wavfile import write
import whisper
from pynput import keyboard
import os
from voice_agent.audio_input import describe_input_device, resolve_input_device
from voice_agent.conversation import process_user_command
from voice_agent.persona import startup_banner

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
fs = 16000
seconds = 4
model = whisper.load_model("small")
input_device = None

def voice_session():
    print("🎙️ Voice session started (say 退出 to stop)")
    wav_path = os.path.join(SCRIPT_DIR, "cmd.wav")
    while True:
        audio = sd.rec(
            int(seconds * fs),
            samplerate=fs,
            channels=1,
            dtype="int16",
            device=input_device,
        )
        sd.wait()
        write(wav_path, fs, audio)

        text = model.transcribe(wav_path, language="zh")["text"].strip()
        print("🧠:", text)

        if "退出" in text:
            print("👋 Voice session ended")
            break

        if len(text) > 1:
            process_user_command(text, source="hotkey_fixed_window")

def on_activate():
    voice_session()

def main() -> int:
    global input_device

    try:
        input_device = resolve_input_device(fs, channels=1, dtype="int16")
    except Exception as e:
        print(f"Microphone initialization failed: {e}")
        return 1

    print(startup_banner())
    print(f"🎤 Using input device: {describe_input_device(input_device)}")

    hotkey = keyboard.HotKey(
        keyboard.HotKey.parse("<cmd>+<shift>+k"),
        on_activate,
    )

    def for_canonical(handler):
        return lambda key: handler(listener.canonical(key))

    with keyboard.Listener(
        on_press=for_canonical(hotkey.press),
        on_release=for_canonical(hotkey.release),
    ) as listener:
        print("⌨️ Press Command + Shift + K to start voice agent")
        listener.join()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
