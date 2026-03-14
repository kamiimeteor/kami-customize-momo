try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from voice_agent.memory import load_memory_profile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PERSONA_DIR = PROJECT_ROOT / "agent"
PERSONA_CONFIG_PATH = PERSONA_DIR / "CONFIG.json"

PERSONA_FILES = {
    "identity": PERSONA_DIR / "IDENTITY.md",
    "soul": PERSONA_DIR / "SOUL.md",
    "user": PERSONA_DIR / "USER.md",
    "rules": PERSONA_DIR / "RULES.md",
    "heartbeat": PERSONA_DIR / "HEARTBEAT.md",
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


@dataclass(frozen=True)
class PersonaConfig:
    name: str
    relationship: str
    role_summary: str
    identity_style: tuple[str, ...]
    default_language: str
    keep_replies_short: bool
    avoid_empty_reassurance: bool
    prefer_action_over_explanation: bool
    ask_follow_up_only_when_needed: bool
    speak_only_after_actionable_command: bool
    allow_unsolicited_dialogue: bool
    initiative_mode: str
    speak_up_when: tuple[str, ...]
    voice_tone: str
    voice_humor: str
    voice_energy: str
    voice_output_enabled: bool
    voice_output_provider: str
    system_voice_output_command: str
    system_voice_output_voice: str
    system_voice_output_rate: int
    openai_tts_model: str
    openai_tts_voice: str
    openai_tts_response_format: str
    openai_tts_speed: float
    openai_tts_instructions: str


@dataclass(frozen=True)
class RuntimePersonaProfile:
    config: PersonaConfig
    sections: dict[str, str]
    remembered_notes: tuple[str, ...]


@lru_cache(maxsize=1)
def load_persona_sections() -> dict[str, str]:
    return {name: _read_text(path) for name, path in PERSONA_FILES.items()}


@lru_cache(maxsize=1)
def load_persona_config() -> PersonaConfig:
    raw = json.loads(_read_text(PERSONA_CONFIG_PATH))
    interaction_rules = raw.get("interaction_rules", {})
    initiative_policy = raw.get("initiative_policy", {})
    voice_profile = raw.get("voice_profile", {})
    voice_output = raw.get("voice_output", {})
    return PersonaConfig(
        name=raw.get("name", "momo"),
        relationship=raw.get("relationship", "AI friend and capable personal assistant"),
        role_summary=raw.get("role_summary", "voice-first mobile companion"),
        identity_style=tuple(raw.get("identity_style", [])),
        default_language=interaction_rules.get("default_language", "zh-CN"),
        keep_replies_short=bool(interaction_rules.get("keep_replies_short", True)),
        avoid_empty_reassurance=bool(interaction_rules.get("avoid_empty_reassurance", True)),
        prefer_action_over_explanation=bool(
            interaction_rules.get("prefer_action_over_explanation", True)
        ),
        ask_follow_up_only_when_needed=bool(
            interaction_rules.get("ask_follow_up_only_when_needed", True)
        ),
        speak_only_after_actionable_command=bool(
            interaction_rules.get("speak_only_after_actionable_command", True)
        ),
        allow_unsolicited_dialogue=bool(
            interaction_rules.get("allow_unsolicited_dialogue", False)
        ),
        initiative_mode=initiative_policy.get("default_mode", "low_interrupt"),
        speak_up_when=tuple(initiative_policy.get("speak_up_when", [])),
        voice_tone=voice_profile.get("tone", "natural, direct, warm"),
        voice_humor=voice_profile.get("humor", "dry and occasional"),
        voice_energy=voice_profile.get("energy", "calm"),
        voice_output_enabled=bool(voice_output.get("enabled", False)),
        voice_output_provider=voice_output.get("provider", "system"),
        system_voice_output_command=voice_output.get("system_command", "say"),
        system_voice_output_voice=voice_output.get("system_voice", ""),
        system_voice_output_rate=int(voice_output.get("system_rate", 185)),
        openai_tts_model=voice_output.get("openai_model", "gpt-4o-mini-tts"),
        openai_tts_voice=voice_output.get("openai_voice", "coral"),
        openai_tts_response_format=voice_output.get("openai_response_format", "wav"),
        openai_tts_speed=float(voice_output.get("openai_speed", 0.95)),
        openai_tts_instructions=voice_output.get(
            "openai_instructions",
            "Speak in natural Mandarin Chinese with a calm and encouraging tone.",
        ),
    )


def load_recent_memory_notes(limit: int = 5) -> tuple[str, ...]:
    profile = load_memory_profile()
    notes: list[str] = []
    preferred_name = profile.get("preferred_name")
    user_name = profile.get("user_name")
    if preferred_name:
        notes.append(f"user prefers to be addressed as {preferred_name}")
    if user_name:
        notes.append(f"user name is {user_name}")

    for fact_type in (
        "likes",
        "dislikes",
        "communication_style",
        "working_style",
        "relationship_preference",
        "recurring_goal",
        "important_context",
        "remember",
    ):
        values = profile.get(fact_type, [])
        if not isinstance(values, list):
            continue
        for value in values:
            notes.append(f"{fact_type}: {value}")
            if len(notes) >= limit:
                return tuple(notes[:limit])

    preference_overrides = profile.get("preference_overrides", {})
    if isinstance(preference_overrides, dict):
        for facet, item in preference_overrides.items():
            if not isinstance(item, dict):
                continue
            value = str(item.get("value", "")).strip()
            source_value = str(item.get("source_value", "")).strip()
            if not value:
                continue
            note = f"{facet}: {value}"
            if source_value:
                note += f" ({source_value})"
            notes.append(note)
            if len(notes) >= limit:
                return tuple(notes[:limit])
    return tuple(notes)


def build_runtime_profile() -> RuntimePersonaProfile:
    return RuntimePersonaProfile(
        config=load_persona_config(),
        sections=load_persona_sections(),
        remembered_notes=load_recent_memory_notes(),
    )


def load_preference_overrides() -> dict[str, str]:
    raw = load_memory_profile().get("preference_overrides", {})
    if not isinstance(raw, dict):
        return {}

    overrides: dict[str, str] = {}
    for facet, item in raw.items():
        if not isinstance(item, dict):
            continue
        value = str(item.get("value", "")).strip()
        if value:
            overrides[facet] = value
    return overrides


def build_persona_context() -> str:
    profile = build_runtime_profile()
    config = profile.config
    ordered_names = ["identity", "soul", "user", "rules", "heartbeat"]
    section_text = "\n\n".join(profile.sections[name] for name in ordered_names)

    lines = [
        f"name: {config.name}",
        f"relationship: {config.relationship}",
        f"role_summary: {config.role_summary}",
        f"default_language: {config.default_language}",
        f"identity_style: {', '.join(config.identity_style)}",
        f"voice_tone: {config.voice_tone}",
        f"initiative_mode: {config.initiative_mode}",
        "speak_up_when:",
    ]
    lines.extend(f"- {item}" for item in config.speak_up_when)
    preference_overrides = load_preference_overrides()
    if preference_overrides:
        lines.append("preference_overrides:")
        lines.extend(f"- {facet}: {value}" for facet, value in preference_overrides.items())
    if profile.remembered_notes:
        lines.append("recent_memory:")
        lines.extend(f"- {note}" for note in profile.remembered_notes)

    return "\n".join(lines) + "\n\n" + section_text


def active_profile_summary() -> str:
    profile = build_runtime_profile()
    config = profile.config

    lines = [
        f"# {config.name} active profile",
        "",
        "## Runtime",
        f"- relationship: {config.relationship}",
        f"- role: {config.role_summary}",
        f"- default_language: {config.default_language}",
        f"- style: {', '.join(config.identity_style)}",
        f"- tone: {config.voice_tone}",
        f"- humor: {config.voice_humor}",
        f"- energy: {config.voice_energy}",
        f"- initiative: {config.initiative_mode}",
        f"- voice_output_enabled: {config.voice_output_enabled}",
        f"- voice_output_provider: {config.voice_output_provider}",
        "",
        "## Interaction Rules",
        f"- keep_replies_short: {config.keep_replies_short}",
        f"- avoid_empty_reassurance: {config.avoid_empty_reassurance}",
        f"- prefer_action_over_explanation: {config.prefer_action_over_explanation}",
        f"- ask_follow_up_only_when_needed: {config.ask_follow_up_only_when_needed}",
        f"- speak_only_after_actionable_command: {config.speak_only_after_actionable_command}",
        f"- allow_unsolicited_dialogue: {config.allow_unsolicited_dialogue}",
        "",
        "## Speak Up When",
    ]
    lines.extend(f"- {item}" for item in config.speak_up_when)
    lines.extend(["", "## Remembered User Notes"])
    if profile.remembered_notes:
        lines.extend(f"- {note}" for note in profile.remembered_notes)
    else:
        lines.append("- no stable user notes remembered yet")
    preference_overrides = load_memory_profile().get("preference_overrides", {})
    if preference_overrides:
        lines.extend(["", "## Preference Overrides"])
        for facet, item in preference_overrides.items():
            if not isinstance(item, dict):
                continue
            lines.append(f"- {facet}: {item.get('value')}")
    return "\n".join(lines)


def startup_banner() -> str:
    profile = build_runtime_profile()
    config = profile.config
    style = ", ".join(config.identity_style[:3]) or "concise, thoughtful"
    lines = [
        f"{config.name} ready",
        f"role: {config.relationship}",
        f"style: {style}",
    ]
    if profile.remembered_notes:
        lines.append(f"memory: {profile.remembered_notes[0]}")
    return "\n".join(lines)
