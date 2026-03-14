import argparse
import os

from voice_agent.speech_output import speak_text_blocking


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="*", help="text to speak")
    parser.add_argument("--voice")
    parser.add_argument("--speed", type=float)
    parser.add_argument("--instructions")
    parser.add_argument("--model")
    args = parser.parse_args()

    if args.voice:
        os.environ["OPENAI_TTS_VOICE"] = args.voice
    if args.speed is not None:
        os.environ["OPENAI_TTS_SPEED"] = str(args.speed)
    if args.instructions:
        os.environ["OPENAI_TTS_INSTRUCTIONS"] = args.instructions
    if args.model:
        os.environ["OPENAI_TTS_MODEL"] = args.model

    text = " ".join(args.text).strip() or "你好，我是 momo。现在开始测试语音播报。"
    raise SystemExit(speak_text_blocking(text))
