try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

from pynput import keyboard

from voice_agent.portal_overlay import toggle_overlay


def on_activate() -> None:
    result = toggle_overlay()
    if result is False:
        print("Failed to toggle Portal overlay")
        return
    status = "shown" if result else "hidden"
    print(f"Portal overlay {status}")


def main() -> int:
    hotkey = keyboard.HotKey(
        keyboard.HotKey.parse("<cmd>+<shift>+o"),
        on_activate,
    )

    def for_canonical(handler):
        return lambda key: handler(listener.canonical(key))

    with keyboard.Listener(
        on_press=for_canonical(hotkey.press),
        on_release=for_canonical(hotkey.release),
    ) as listener:
        print("⌨️ Press Command + Shift + O to show or hide the Portal overlay")
        listener.join()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
