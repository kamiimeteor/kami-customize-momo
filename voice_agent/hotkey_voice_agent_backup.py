try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import sounddevice as sd
from scipy.io.wavfile import write
import whisper
from pynput import keyboard
from voice_agent.droidrun_runner import run_droidrun_command

fs = 16000
seconds = 4
model = whisper.load_model("small")

def voice_session():
    print("🎙️ Voice session started (say 退出 to stop)")
    while True:
        audio = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype="int16")
        sd.wait()
        write("cmd.wav", fs, audio)

        text = model.transcribe("cmd.wav", language="zh")["text"].strip()
        print("🧠:", text)

        if "退出" in text:
            print("👋 Voice session ended")
            break

        if len(text) > 1:
            run_droidrun_command(text)

def on_activate():
    voice_session()

def main() -> int:
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
