from voice_agent.portal_overlay import toggle_overlay


if __name__ == "__main__":
    result = toggle_overlay()
    raise SystemExit(0 if result is not False else 1)
