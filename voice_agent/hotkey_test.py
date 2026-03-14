try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

from pynput import keyboard

def on_activate():
    print("HOTKEY TRIGGERED")

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
        print("Listening... press Command + Shift + K")
        listener.join()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
