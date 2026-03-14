try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import sounddevice as sd
import numpy as np
import whisper
from pynput import keyboard
from voice_agent.audio_input import describe_input_device, resolve_input_device
from voice_agent.conversation import process_user_command
from voice_agent.persona import startup_banner

RATE = 16000
model = whisper.load_model("small")

recording = False
audio_chunks = []
stream = None

def callback(indata, frames, time, status):
    if recording:
        audio_chunks.append(indata.copy())

def toggle_recording():
    global recording, audio_chunks

    if not recording:
        audio_chunks = []
        recording = True
        print("🎙️ Recording started...")
    else:
        recording = False
        print("⏹️ Recording stopped")

        if not audio_chunks:
            print("No audio captured")
            return

        audio = np.concatenate(audio_chunks, axis=0).flatten()
        audio = audio.astype(np.float32) / 32768.0

        result = model.transcribe(audio, language="zh")
        text = result["text"].strip()
        print("🧠:", text)

        if text and "退出" not in text:
            process_user_command(text, source="push_to_talk")

def on_activate():
    toggle_recording()

def main() -> int:
    global stream

    try:
        input_device = resolve_input_device(RATE, channels=1, dtype="int16")
    except Exception as e:
        print(f"Microphone initialization failed: {e}")
        return 1

    print(startup_banner())
    print(f"🎤 Using input device: {describe_input_device(input_device)}")

    stream = sd.InputStream(
        device=input_device,
        samplerate=RATE,
        channels=1,
        dtype="int16",
        callback=callback,
    )
    stream.start()

    hotkey = keyboard.HotKey(
        keyboard.HotKey.parse("<cmd>+<shift>+k"),
        on_activate,
    )

    def for_canonical(handler):
        return lambda key: handler(listener.canonical(key))

    try:
        with keyboard.Listener(
            on_press=for_canonical(hotkey.press),
            on_release=for_canonical(hotkey.release),
        ) as listener:
            print("⌨️ Press Command + Shift + K once to start, press again to stop and run")
            listener.join()
    finally:
        if stream is not None:
            stream.stop()
            stream.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
