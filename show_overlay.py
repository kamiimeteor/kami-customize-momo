from voice_agent.portal_overlay import set_overlay_visible


if __name__ == "__main__":
    raise SystemExit(0 if set_overlay_visible(True) else 1)
