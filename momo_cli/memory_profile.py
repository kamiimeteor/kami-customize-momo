from voice_agent.memory import load_memory_profile


if __name__ == "__main__":
    import json

    print(json.dumps(load_memory_profile(), ensure_ascii=False, indent=2))
