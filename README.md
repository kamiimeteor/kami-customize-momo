# Momo

Momo is a voice-first customization layer built on top of [DroidRun](https://github.com/droidrun/droidrun).

Right now, it focuses on a practical goal: letting a Mac user trigger DroidRun with voice, hotkeys, and a few quality-of-life fixes around Portal and overlay control. Long term, this repo is meant to grow into a more personal mobile companion with its own identity, memory, and spoken interaction style.

## Status

This project is experimental.

Current version:

- wraps DroidRun with local voice input
- supports hotkey-based recording on macOS
- adds Portal recovery and overlay visibility helpers
- keeps the customization layer thin instead of replacing DroidRun's planner

Planned direction:

- a stronger personality and system identity for Momo
- memory across interactions
- more proactive thinking, questions, and replies
- full voice-to-voice interaction instead of silent execution

## What It Does Today

- Start and stop recording with `Command + Shift + K`
- Transcribe spoken Mandarin commands locally with Whisper
- Forward commands into DroidRun
- Wake the device and recover from common Portal state failures
- Hide, show, or toggle the Portal overlay from the Mac

Typical commands:

- `打开小红书搜索二狗伦敦出票`
- `在小红书里面搜索伦敦租房`
- `打开微信搜索张三`

## Architecture

Momo is intentionally small.

1. Audio is recorded on the Mac with `sounddevice`.
2. Whisper transcribes the command locally.
3. The wrapper forwards the text into DroidRun.
4. If needed, the wrapper performs a thinner direct app-open fallback.
5. Portal helpers handle overlay toggling and common recovery steps.

The goal is not to reimplement DroidRun. The goal is to give it a more usable local interface and a path toward a more personal agent experience.

## Requirements

You need:

- macOS
- a connected Android device with ADB working
- a working DroidRun installation
- a Python environment that can run both DroidRun and this wrapper
- microphone access on macOS

Useful tools and libraries:

- `adb`
- `ffmpeg`
- `portaudio`
- Python packages such as `droidrun`, `openai-whisper`, `sounddevice`, `numpy`, `scipy`, and `pynput`

If your local environment differs, you can override the default paths with:

- `DROIDRUN_PYTHON`
- `DROIDRUN_BIN`
- `ADB_BIN`

## Quick Start

Clone the repo and enter the project directory:

```bash
git clone https://github.com/kamiimeteor/kami-customize-momo.git "$HOME/Documents/AI_projects/momo-droidrun"
cd "$HOME/Documents/AI_projects/momo-droidrun"
```

Install the system dependencies you need on macOS:

```bash
brew install android-platform-tools ffmpeg portaudio
```

Install Python dependencies in the same environment where DroidRun is available:

```bash
pip install droidrun openai-whisper sounddevice numpy scipy pynput
```

Make sure DroidRun itself is working first. Then run:

```bash
./run.sh
```

Default behavior:

- press `Command + Shift + K` once to start recording
- press it again to stop recording and run the command

## Launch Modes

Default mode:

```bash
./run.sh
```

Push-to-toggle recording:

```bash
./run_push_to_talk.sh
```

Fixed 4-second hotkey recording:

```bash
./run_hotkey.sh
```

Press `Enter` to speak:

```bash
./run_voice_loop.sh
```

Single 4-second recording:

```bash
./run_voice_once.sh
```

## Portal Helpers

Reinstall and recover Portal:

```bash
./fix_portal.sh
```

Run a one-shot health check:

```bash
./run_doctor.sh
```

The doctor now checks:

- runtime Python path and version
- required Python modules for Momo and DroidRun
- `adb`, `droidrun`, and `ffmpeg`
- configured LLM providers and whether their API keys are visible in the current shell
- OpenAI TTS readiness
- Portal accessibility state and current foreground app readability

Hide the overlay:

```bash
./hide_overlay.sh
```

Show the overlay:

```bash
./show_overlay.sh
```

Toggle overlay visibility once:

```bash
./toggle_overlay.sh
```

Run a hotkey listener for overlay toggle:

```bash
./run_overlay_hotkey.sh
```

Then press:

- `Command + Shift + O`

## Configuration Notes

Main runtime settings live in `config.yaml`.

Important notes:

- this repo currently assumes DroidRun is already configured
- the default shell scripts prefer `$HOME/droidrun-env/bin/python` and `$HOME/droidrun-env/bin/droidrun`
- if your setup differs, override the paths with environment variables instead of editing every script

Persona settings live under `agent/`:

- `agent/CONFIG.json` stores structured runtime settings such as role, tone, and initiative policy
- `agent/*.md` stores the longer-form identity, rules, and user model
- inspect the active merged profile with `python3 -m momo_cli.persona`
- inspect the current long-term memory snapshot with `python3 -m momo_cli.memory_profile`

Reply layer:

- Momo now generates a short spoken/text reply before and after each command
- the reply chain reuses the same LLM configuration that DroidRun already uses in `config.yaml`
- long-term preferences are extracted into `memory/facts.jsonl` and merged into `memory/profile.json`
- resolved preference overrides such as reply length and confirmation style now directly affect reply generation
- by default, momo stays silent unless the recognized speech looks like an actionable command
- voice playback supports `openai` and `system`; the current default is `openai`
- OpenAI playback requires `OPENAI_API_KEY`
- if OpenAI TTS fails, it falls back to the built-in macOS `say` command
- you can still override playback temporarily with `MOMO_SPEECH_ENABLED=1` or `MOMO_SPEECH_PROVIDER=system`

Example:

```bash
DROIDRUN_PYTHON=/path/to/python ./run.sh
```

Doctor examples:

```bash
./run_doctor.sh
./run_doctor.sh --app 微信
./run_doctor.sh --app 小红书 --open-app
```

The last section of the output is `recommendations`, which tells you the next concrete fix instead of just printing raw state.

## Troubleshooting

### DroidRun opens the app but does not continue

Look for this error:

```text
No active window or root filtered out
```

This usually means Portal cannot read the current UI state, not that the natural-language command itself is wrong.

If `./run_doctor.sh --app 微信 --open-app` shows `likely_unreadable=True`, that means the phone did open WeChat but Portal still could not get a usable accessibility root from the current WeChat page. On this device, WeChat is currently treated as a restricted app, while Xiaohongshu is known to work.

If you see this instead:

```text
Portal state check failed: Accessibility service not available
```

that means Android currently does not have the `Droidrun Portal` accessibility service bound. Run:

```bash
./fix_portal.sh
```

If it still fails after that, keep the phone unlocked, open Android Accessibility settings, and confirm `Droidrun Portal` shows as enabled.

Try:

```bash
./fix_portal.sh
```

Then wait 10 to 30 seconds and run the command again.

### `FP16 is not supported on CPU; using FP32 instead`

This is a Whisper runtime notice, not a failure.

It means Whisper is running on CPU and automatically falling back to FP32.

### Overlay boxes are too noisy on the phone

Use:

```bash
./hide_overlay.sh
```

Or start the toggle hotkey listener:

```bash
./run_overlay_hotkey.sh
```

## Project Structure

```text
.
├── agent/
│   ├── CONFIG.json
│   ├── IDENTITY.md / SOUL.md / USER.md / RULES.md / HEARTBEAT.md
│   └── README.md
├── config.yaml
├── run*.sh
├── fix_portal.sh
├── hide_overlay.sh / show_overlay.sh / toggle_overlay.sh
├── momo_cli/
│   ├── heartbeat.py
│   ├── hotkey_*.py
│   ├── hide_overlay.py / show_overlay.py / toggle_overlay.py
│   ├── voice_agent_loop.py
│   ├── voice_agent_once.py
│   └── voice_test.py
├── memory/
│   ├── facts.jsonl
│   ├── profile.json
│   └── heartbeat/latest.md
├── voice_agent/
│   ├── droidrun_runner.py
│   ├── droidrun_open_app.py
│   ├── conversation.py
│   ├── llm_worker.py
│   ├── memory.py
│   ├── hotkey_push_to_talk.py
│   ├── hotkey_voice_agent.py
│   ├── persona.py
│   ├── portal_overlay.py
│   ├── speech_output.py
│   ├── voice_agent.py
│   └── voice_agent_loop.py
└── 用户操作手册.md
```

## Roadmap

- Define Momo's character, tone, and identity layer
- Add persistent memory and preference tracking
- Move from silent execution to spoken responses
- Let Momo ask clarifying questions instead of only obeying commands
- Keep the wrapper lightweight while extending the user experience

## Credits

- Built on top of [DroidRun](https://github.com/droidrun/droidrun)
- Voice transcription powered by Whisper

## License

This repository currently inherits a lot of behavior from upstream DroidRun, but it is its own customization project. Add or update the license in this repository before treating it as a fully polished public release.
