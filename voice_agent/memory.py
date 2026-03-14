from __future__ import annotations

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory"
DAILY_DIR = MEMORY_DIR / "daily"
HEARTBEAT_DIR = MEMORY_DIR / "heartbeat"
FACTS_PATH = MEMORY_DIR / "facts.jsonl"
LATEST_HEARTBEAT_PATH = HEARTBEAT_DIR / "latest.md"
PROFILE_PATH = MEMORY_DIR / "profile.json"

SINGLE_VALUE_FACT_TYPES = {
    "preferred_name",
    "user_name",
}
LIST_FACT_TYPES = {
    "likes",
    "dislikes",
    "communication_style",
    "working_style",
    "relationship_preference",
    "recurring_goal",
    "important_context",
    "remember",
}
SOURCE_SCORE_BONUS = {
    "manual": 0.25,
    "llm": 0.15,
    "regex": 0.05,
}
PREFERENCE_OVERRIDE_RULES = {
    "reply_length": {
        "short": ("简短", "短一点", "少废话", "简洁", "别说太多", "短一些"),
        "detailed": ("详细", "展开", "多说一点", "说清楚", "讲细一点"),
    },
    "confirmation_style": {
        "direct_execute": ("直接做", "少确认", "不用确认", "别老确认", "先做"),
        "confirm_first": ("先确认", "先问我", "确认一下", "先跟我确认"),
    },
    "tone_style": {
        "playful": ("幽默一点", "俏皮一点", "嘴贫一点", "活泼一点"),
        "neutral": ("正经一点", "别贫", "少开玩笑", "严肃一点"),
    },
    "initiative_style": {
        "low_interrupt": ("少打扰", "别老提醒", "低打扰", "安静一点"),
        "proactive": ("主动一点", "多提醒我", "催我一下", "多问一句"),
    },
}


@dataclass
class InteractionRecord:
    source: str
    text: str
    outcome: str
    detail: str | None = None
    assistant_before: str | None = None
    assistant_after: str | None = None
    memory_facts: list[dict[str, Any]] | None = None


def ensure_memory_dirs() -> None:
    MEMORY_DIR.mkdir(exist_ok=True)
    DAILY_DIR.mkdir(exist_ok=True)
    HEARTBEAT_DIR.mkdir(exist_ok=True)
    FACTS_PATH.touch(exist_ok=True)
    if not PROFILE_PATH.exists():
        PROFILE_PATH.write_text("{}", encoding="utf-8")


def _now() -> datetime:
    return datetime.now()


def _today_path() -> Path:
    return DAILY_DIR / f"{_now().date().isoformat()}.md"


def _append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(text)


def record_interaction(record: InteractionRecord) -> None:
    ensure_memory_dirs()
    now = _now()
    path = _today_path()

    if not path.exists() or path.stat().st_size == 0:
        _append_text(path, f"# {now.date().isoformat()}\n\n")

    lines = [
        f"## {now.strftime('%H:%M:%S')}",
        f"- source: {record.source}",
        f"- user: {record.text}",
        f"- outcome: {record.outcome}",
    ]
    if record.detail:
        lines.append(f"- detail: {record.detail}")
    if record.assistant_before:
        lines.append(f"- momo_before: {record.assistant_before}")
    if record.assistant_after:
        lines.append(f"- momo_after: {record.assistant_after}")
    lines.append("")
    _append_text(path, "\n".join(lines) + "\n")

    facts = extract_facts(record.text)
    if record.memory_facts:
        facts.extend(record.memory_facts)
    append_facts(facts)


def extract_facts(text: str) -> list[dict[str, Any]]:
    cleaned = text.strip()
    facts: list[dict[str, Any]] = []

    patterns = [
        ("preferred_name", r"以后叫我(.+)$"),
        ("preferred_name", r"你可以叫我(.+)$"),
        ("user_name", r"我叫(.+)$"),
        ("likes", r"我喜欢(.+)$"),
        ("dislikes", r"我不喜欢(.+)$"),
        ("remember", r"记住(.+)$"),
        ("communication_style", r"(?:以后|之后)?(?:跟我|对我)?说话(.+)$"),
        ("working_style", r"(?:以后|下次)?(?:直接|先)(.+)$"),
    ]

    for fact_type, pattern in patterns:
        match = re.search(pattern, cleaned)
        if not match:
            continue

        value = match.group(1).strip("。！!，, ")
        if not value:
            continue

        facts.append(
            {
                "timestamp": _now().isoformat(timespec="seconds"),
                "type": fact_type,
                "value": value,
                "source_text": cleaned,
                "source": "regex",
                "confidence": 0.7,
            }
        )

    return facts


def append_fact(fact: dict[str, Any]) -> None:
    append_facts([fact])


def append_facts(facts: list[dict[str, Any]]) -> None:
    if not facts:
        return

    ensure_memory_dirs()
    with FACTS_PATH.open("a", encoding="utf-8") as f:
        for fact in facts:
            f.write(json.dumps(fact, ensure_ascii=False) + "\n")
    rebuild_memory_profile()


def _normalized_value(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _canonical_item(value: str) -> str:
    normalized = _normalized_value(value)
    normalized = re.sub(r"^(喜欢|不喜欢|记住|以后|下次|请|麻烦)\s*", "", normalized)
    normalized = re.sub(r"[。！!，,；;]+$", "", normalized)
    return normalized


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.fromtimestamp(0)


def _fact_score(fact: dict[str, Any]) -> float:
    confidence = float(fact.get("confidence", 1.0) or 0.0)
    timestamp = _parse_timestamp(str(fact.get("timestamp", "")))
    source = str(fact.get("source", "")).strip().lower()
    recency_score = timestamp.timestamp() / 1_000_000_000
    return confidence + SOURCE_SCORE_BONUS.get(source, 0.0) + recency_score


def _is_better_fact(candidate: dict[str, Any], current: dict[str, Any] | None) -> bool:
    if current is None:
        return True

    candidate_score = _fact_score(candidate)
    current_score = _fact_score(current)
    if candidate_score != current_score:
        return candidate_score > current_score

    return _parse_timestamp(str(candidate.get("timestamp", ""))) > _parse_timestamp(
        str(current.get("timestamp", ""))
    )


def _detect_preference_override(value: str) -> tuple[str, str] | None:
    normalized = _canonical_item(value)
    for facet, choices in PREFERENCE_OVERRIDE_RULES.items():
        for label, phrases in choices.items():
            if any(phrase in normalized for phrase in phrases):
                return facet, label
    return None


def load_all_facts() -> list[dict[str, Any]]:
    ensure_memory_dirs()
    facts: list[dict[str, Any]] = []
    for line in FACTS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            facts.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return facts


def rebuild_memory_profile() -> dict[str, Any]:
    facts = load_all_facts()
    profile: dict[str, Any] = {
        "updated_at": _now().isoformat(timespec="seconds"),
        "preferred_name": None,
        "user_name": None,
        "likes": [],
        "dislikes": [],
        "communication_style": [],
        "working_style": [],
        "relationship_preference": [],
        "recurring_goal": [],
        "important_context": [],
        "remember": [],
        "preference_overrides": {},
        "conflicts": [],
    }
    single_winners: dict[str, dict[str, Any]] = {}
    list_winners: dict[str, dict[str, dict[str, Any]]] = {
        fact_type: {} for fact_type in LIST_FACT_TYPES
    }
    preference_winners: dict[str, dict[str, Any]] = {}
    cross_conflicts: dict[str, dict[str, Any]] = {}

    valid_facts: list[dict[str, Any]] = []
    for fact in facts:
        fact_type = str(fact.get("type", "")).strip()
        value = str(fact.get("value", "")).strip()
        if not fact_type or not value:
            continue

        confidence = float(fact.get("confidence", 1.0) or 0.0)
        if confidence < 0.55:
            continue
        valid_facts.append(fact)

    for fact in valid_facts:
        fact_type = str(fact.get("type", "")).strip()
        value = str(fact.get("value", "")).strip()

        if fact_type in SINGLE_VALUE_FACT_TYPES:
            previous = single_winners.get(fact_type)
            if _is_better_fact(fact, previous):
                if previous is not None and previous.get("value") != value:
                    profile["conflicts"].append(
                        {
                            "kind": "single_value_override",
                            "field": fact_type,
                            "kept": value,
                            "discarded": previous.get("value"),
                        }
                    )
                single_winners[fact_type] = fact
            continue

        if fact_type not in LIST_FACT_TYPES:
            continue

        canonical = _canonical_item(value)
        previous = list_winners[fact_type].get(canonical)
        if _is_better_fact(fact, previous):
            if previous is not None and previous.get("value") != value:
                profile["conflicts"].append(
                    {
                        "kind": "dedupe_override",
                        "field": fact_type,
                        "kept": value,
                        "discarded": previous.get("value"),
                    }
                )
            list_winners[fact_type][canonical] = fact

        preference_match = _detect_preference_override(value)
        if preference_match:
            facet, label = preference_match
            preference_fact = {
                "facet": facet,
                "label": label,
                **fact,
            }
            previous_preference = preference_winners.get(facet)
            if _is_better_fact(preference_fact, previous_preference):
                if previous_preference is not None and previous_preference.get("label") != label:
                    profile["conflicts"].append(
                        {
                            "kind": "preference_override",
                            "field": facet,
                            "kept": label,
                            "discarded": previous_preference.get("label"),
                        }
                    )
                preference_winners[facet] = preference_fact

    for fact_type, winner in single_winners.items():
        profile[fact_type] = winner.get("value")

    like_dislike_candidates: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for fact_type in ("likes", "dislikes"):
        for canonical, fact in list_winners[fact_type].items():
            like_dislike_candidates[canonical].append((fact_type, fact))

    for canonical, candidates in like_dislike_candidates.items():
        if len(candidates) == 1:
            fact_type, fact = candidates[0]
            cross_conflicts[f"{fact_type}:{canonical}"] = {
                "winner_type": fact_type,
                "winner_fact": fact,
            }
            continue

        winner_type, winner_fact = candidates[0]
        loser_type, loser_fact = candidates[1]
        if _is_better_fact(loser_fact, winner_fact):
            winner_type, loser_type = loser_type, winner_type
            winner_fact, loser_fact = loser_fact, winner_fact

        profile["conflicts"].append(
            {
                "kind": "likes_dislikes_conflict",
                "item": winner_fact.get("value"),
                "kept_type": winner_type,
                "discarded_type": loser_type,
                "discarded_value": loser_fact.get("value"),
            }
        )
        cross_conflicts[f"{winner_type}:{canonical}"] = {
            "winner_type": winner_type,
            "winner_fact": winner_fact,
        }

    for fact_type in LIST_FACT_TYPES:
        selected: list[dict[str, Any]] = []
        for canonical, fact in list_winners[fact_type].items():
            if fact_type in {"likes", "dislikes"}:
                key = f"{fact_type}:{canonical}"
                resolved = cross_conflicts.get(key)
                if not resolved or resolved["winner_fact"] is not fact:
                    continue
            preference_match = _detect_preference_override(str(fact.get("value", "")).strip())
            if preference_match:
                facet, _label = preference_match
                winner = preference_winners.get(facet)
                if winner is not None and winner.get("timestamp") != fact.get("timestamp"):
                    continue
            selected.append(fact)

        selected.sort(
            key=lambda fact: (
                _fact_score(fact),
                _parse_timestamp(str(fact.get("timestamp", ""))).timestamp(),
            ),
            reverse=True,
        )
        profile[fact_type] = [str(fact.get("value", "")).strip() for fact in selected]

    for facet, fact in preference_winners.items():
        profile["preference_overrides"][facet] = {
            "value": fact.get("label"),
            "source_type": fact.get("type"),
            "source_value": fact.get("value"),
            "confidence": float(fact.get("confidence", 0.0) or 0.0),
        }

    # Keep the conflict log readable and bounded.
    profile["conflicts"] = profile["conflicts"][-20:]

    PROFILE_PATH.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return profile


def load_memory_profile() -> dict[str, Any]:
    ensure_memory_dirs()
    raw = PROFILE_PATH.read_text(encoding="utf-8").strip()
    if not raw or raw == "{}":
        return rebuild_memory_profile()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return rebuild_memory_profile()


def build_memory_prompt_context() -> str:
    profile = load_memory_profile()
    compact_profile = {
        key: value
        for key, value in profile.items()
        if value not in (None, [], {}, "")
    }
    return json.dumps(compact_profile, ensure_ascii=False, indent=2)


def load_recent_daily_entries(limit: int = 20) -> list[str]:
    ensure_memory_dirs()
    paths = sorted(DAILY_DIR.glob("*.md"))
    entries: list[str] = []
    for path in reversed(paths):
        text = path.read_text(encoding="utf-8").strip()
        if text:
            entries.append(text)
        if len(entries) >= limit:
            break
    return entries


def load_recent_facts(limit: int = 20) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for fact in reversed(load_all_facts()):
        facts.append(fact)
        if len(facts) >= limit:
            break
    return facts


def generate_heartbeat() -> str:
    ensure_memory_dirs()
    recent_entries = load_recent_daily_entries(limit=3)
    recent_facts = load_recent_facts(limit=5)

    outcomes_text = "\n".join(recent_entries)
    failure_count = outcomes_text.count("outcome: failed")
    success_count = outcomes_text.count("outcome: completed")

    lines = [
        "# momo heartbeat",
        "",
        f"- generated_at: {_now().isoformat(timespec='seconds')}",
        "",
        "## 状态",
    ]

    if failure_count >= 2:
        lines.append("- 最近有重复失败，值得优先检查环境或流程。")
    elif success_count > 0:
        lines.append("- 最近交互整体正常，执行链路可用。")
    else:
        lines.append("- 最近还没有足够多的交互记录。")

    lines.extend(["", "## 新近记忆"])
    if recent_facts:
        for fact in recent_facts:
            lines.append(f"- {fact.get('type')}: {fact.get('value')}")
    else:
        lines.append("- 暂无新的稳定事实。")

    lines.extend(["", "## 建议"])
    if failure_count >= 2:
        lines.append("- 下次先检查 Portal 与音频设备状态。")
    else:
        lines.append("- 保持低打扰，继续记录互动与偏好。")

    content = "\n".join(lines) + "\n"
    LATEST_HEARTBEAT_PATH.write_text(content, encoding="utf-8")
    return content
