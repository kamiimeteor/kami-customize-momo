from __future__ import annotations

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore # noqa: F401

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from voice_agent.droidrun_runner import CommandExecutionResult, run_droidrun_command_result
from voice_agent.memory import (
    InteractionRecord,
    build_memory_prompt_context,
    record_interaction,
)
from voice_agent.persona import build_persona_context, load_preference_overrides
from voice_agent.speech_output import speak_text


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LLM_WORKER_PATH = Path(__file__).resolve().parent / "llm_worker.py"
NON_ACTIONABLE_UTTERANCES = {
    "嗯",
    "啊",
    "哦",
    "呃",
    "诶",
    "哈",
    "好",
    "好的",
    "行",
    "可以",
    "知道了",
    "算了",
}
ACTION_HINTS = (
    "打开",
    "启动",
    "搜索",
    "搜",
    "查",
    "看看",
    "点开",
    "点击",
    "进入",
    "发送",
    "发给",
    "回复",
    "切换",
    "关闭",
    "返回",
    "播放",
    "暂停",
    "拨打",
    "打开第",
    "下拉",
    "上滑",
    "记住",
)


@dataclass(frozen=True)
class AssistantTurn:
    spoken_reply: str
    asks_clarification: bool = False


def _resolve_runtime_python() -> str | None:
    override = os.environ.get("DROIDRUN_PYTHON")
    if override:
        return override

    fallback = Path.home() / "droidrun-env" / "bin" / "python"
    if fallback.exists():
        return str(fallback)
    return None


def _worker_payload_base(user_text: str) -> dict[str, Any]:
    preference_overrides = load_preference_overrides()
    return {
        "user_text": user_text,
        "persona_context": build_persona_context(),
        "memory_context": build_memory_prompt_context(),
        "preference_overrides": preference_overrides,
    }


def _reply_length_pref() -> str:
    return load_preference_overrides().get("reply_length", "short")


def _confirmation_style_pref() -> str:
    return load_preference_overrides().get("confirmation_style", "direct_execute")


def _initiative_style_pref() -> str:
    return load_preference_overrides().get("initiative_style", "low_interrupt")


def _speak_only_after_actionable_command() -> bool:
    from voice_agent.persona import load_persona_config

    return load_persona_config().speak_only_after_actionable_command


def _compress_reply(text: str) -> str:
    text = text.strip()
    if _reply_length_pref() != "short":
        return text
    replacements = (
        ("我来帮你", "我来"),
        ("我先帮你", "我先"),
        ("我已经帮你", "已经"),
        ("我这边已经", "已经"),
        ("我建议", "建议"),
    )
    for src, dst in replacements:
        text = text.replace(src, dst)
    return text


def _needs_confirmation_preference(user_text: str) -> bool:
    stripped = user_text.strip()
    if _confirmation_style_pref() != "confirm_first":
        return False
    if any(token in stripped for token in ("还是", "或者")):
        return True
    # Commands that only open an app are lightweight but preference says to confirm first.
    if stripped.startswith(("打开", "启动")) and not any(
        token in stripped for token in ("搜索", "搜", "点击", "进入", "查", "打开第")
    ):
        return True
    return False


def _extract_open_target(user_text: str) -> str | None:
    stripped = user_text.strip()
    for prefix in ("打开", "启动"):
        if stripped.startswith(prefix):
            target = stripped[len(prefix):].strip(" ，,。.!！")
            return target or None
    return None


def _is_actionable_command(user_text: str) -> bool:
    stripped = user_text.strip()
    if not stripped:
        return False

    if stripped in NON_ACTIONABLE_UTTERANCES:
        return False

    if any(hint in stripped for hint in ACTION_HINTS):
        return True

    if any(token in stripped for token in ("还是", "或者")) and len(stripped) >= 4:
        return True

    if len(stripped) <= 2:
        return False

    # Keep free-form but clearly task-like instructions actionable.
    return len(stripped) >= 5


def _call_llm_worker(mode: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if os.environ.get("MOMO_DISABLE_LLM", "").strip().lower() in {"1", "true", "yes"}:
        return None

    python_bin = _resolve_runtime_python()
    if not python_bin:
        return None

    result = subprocess.run(
        [python_bin, str(LLM_WORKER_PATH), mode],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    if result.returncode != 0:
        return None

    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return None


def _fallback_before_action(user_text: str) -> AssistantTurn:
    stripped = user_text.strip()
    if not stripped:
        return AssistantTurn("你再说一遍，我这次没听清。", asks_clarification=True)

    if len(stripped) <= 2:
        return AssistantTurn("你想让我具体做什么？", asks_clarification=True)

    if any(token in stripped for token in ("还是", "或者")):
        return AssistantTurn("你更想让我先做哪一个？", asks_clarification=True)

    if _needs_confirmation_preference(stripped):
        target = _extract_open_target(stripped)
        if target:
            return AssistantTurn(
                f"你是只打开{target}，还是还要继续操作？",
                asks_clarification=True,
            )
        return AssistantTurn("你是想先确认一下再让我做吗？", asks_clarification=True)

    if stripped.startswith(("打开", "启动")):
        reply = "好，我先帮你打开。"
        if _reply_length_pref() != "short":
            reply = "好，我先帮你打开，然后看情况继续。"
        return AssistantTurn(_compress_reply(reply))
    if "搜索" in stripped or "搜" in stripped:
        reply = "行，我来帮你搜一下。"
        if _reply_length_pref() != "short":
            reply = "行，我来帮你搜一下，尽量一步到位。"
        return AssistantTurn(_compress_reply(reply))
    reply = "收到，我来处理。"
    if _reply_length_pref() != "short":
        reply = "收到，我先按你的意思处理。"
    return AssistantTurn(_compress_reply(reply))


def _fallback_after_action(user_text: str, result: CommandExecutionResult) -> str:
    if result.exit_code == 0:
        if "搜索" in user_text or "搜" in user_text:
            reply = "好了，我已经帮你开始搜了。"
        else:
            reply = "好了，我这边已经处理了。"
        if _initiative_style_pref() == "proactive" and _reply_length_pref() != "short":
            reply = reply.rstrip("。") + "，你要的话我也可以继续下一步。"
        return _compress_reply(reply)

    detail = (result.detail or "").lower()
    if "app_ui_unreadable_known" in detail:
        reply = "这个 App 的当前页面已经打开了，但我还是读不到界面。"
        if "微信" in (result.detail or ""):
            reply = "微信已经打开了，但它这个页面我现在还是读不到。"
        if _initiative_style_pref() == "proactive":
            reply = reply.rstrip("。") + "，先换个页面或者先换个 App 试更稳。"
        return _compress_reply(reply)
    if "app_ui_unreadable" in detail:
        reply = "这个 App 已经打开了，但当前页面还是读不到。"
        if _initiative_style_pref() == "proactive":
            reply = "这个 App 已经打开了，但当前页面还是读不到。你先换个页面再试。"
        return _compress_reply(reply)
    if "portal_recovery" in detail or "portal_not_ready_after_recovery" in detail:
        reply = "微信已经打开了，但 Portal 还是读不到界面。"
        if _initiative_style_pref() == "proactive":
            reply = "微信已经打开了，但 Portal 还是读不到界面。你先等一会儿再试，或者手动跑一下修复。"
        return _compress_reply(reply)
    if "portal" in detail:
        reply = "这次没跑通，像是 Portal 状态不对。"
        if _initiative_style_pref() == "proactive":
            reply = "这次没跑通，像是 Portal 状态不对，你可以先修一下。"
        return _compress_reply(reply)
    if "direct_open_failed" in detail:
        reply = "App 没拉起来，我再换个方式也行。"
        return _compress_reply(reply)
    reply = "这次没跑通，我建议再试一次。"
    if _initiative_style_pref() == "proactive" and _reply_length_pref() != "short":
        reply = "这次没跑通，你先再试一次，不行我再换个方式。"
    if _initiative_style_pref() == "low_interrupt" and _reply_length_pref() == "short":
        reply = "这次没跑通，再试一次看看。"
    return _compress_reply(reply)


def _generate_before_action_reply(user_text: str) -> AssistantTurn:
    payload = _worker_payload_base(user_text)
    llm_output = _call_llm_worker("before_action", payload)
    if not llm_output:
        return _fallback_before_action(user_text)

    spoken_reply = str(llm_output.get("spoken_reply", "")).strip()
    asks_clarification = bool(llm_output.get("asks_clarification", False))
    clarification_question = str(llm_output.get("clarification_question", "")).strip()
    if asks_clarification and clarification_question:
        spoken_reply = clarification_question
    if not spoken_reply:
        return _fallback_before_action(user_text)
    return AssistantTurn(
        spoken_reply=_compress_reply(spoken_reply),
        asks_clarification=asks_clarification,
    )


def _generate_after_action_reply(
    user_text: str,
    result: CommandExecutionResult,
) -> str:
    payload = _worker_payload_base(user_text)
    payload.update(
        {
            "status": result.status,
            "detail": result.detail,
        }
    )
    llm_output = _call_llm_worker("after_action", payload)
    if not llm_output:
        return _fallback_after_action(user_text, result)

    spoken_reply = str(llm_output.get("spoken_reply", "")).strip()
    if not spoken_reply:
        return _fallback_after_action(user_text, result)
    return _compress_reply(spoken_reply)


def _extract_memory_facts(
    source: str,
    user_text: str,
    outcome: str,
    detail: str | None,
    assistant_before: str | None,
    assistant_after: str | None,
) -> list[dict[str, Any]]:
    payload = _worker_payload_base(user_text)
    payload.update(
        {
            "source": source,
            "outcome": outcome,
            "detail": detail,
            "assistant_before": assistant_before,
            "assistant_after": assistant_after,
        }
    )
    llm_output = _call_llm_worker("memory", payload)
    if not llm_output:
        return []

    candidates = llm_output.get("candidates", [])
    memory_facts: list[dict[str, Any]] = []
    for candidate in candidates:
        value = str(candidate.get("value", "")).strip()
        fact_type = str(candidate.get("type", "")).strip()
        if not value or not fact_type:
            continue
        memory_facts.append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "type": fact_type,
                "value": value,
                "reason": str(candidate.get("reason", "")).strip(),
                "confidence": float(candidate.get("confidence", 0.0) or 0.0),
                "source": "llm",
                "source_text": user_text,
            }
        )
    return memory_facts


def _announce(reply: str) -> None:
    reply = reply.strip()
    if not reply:
        return
    print(f"momo: {reply}", flush=True)
    speak_text(reply)


def process_user_command(text: str, source: str) -> int:
    cleaned = text.strip()
    if not cleaned:
        return 0

    if _speak_only_after_actionable_command() and not _is_actionable_command(cleaned):
        return 0

    before_turn = _generate_before_action_reply(cleaned)
    _announce(before_turn.spoken_reply)

    if before_turn.asks_clarification:
        memory_facts = _extract_memory_facts(
            source=source,
            user_text=cleaned,
            outcome="needs_clarification",
            detail="clarification_requested",
            assistant_before=before_turn.spoken_reply,
            assistant_after=None,
        )
        record_interaction(
            InteractionRecord(
                source=source,
                text=cleaned,
                outcome="needs_clarification",
                detail="clarification_requested",
                assistant_before=before_turn.spoken_reply,
                memory_facts=memory_facts,
            )
        )
        return 1

    result = run_droidrun_command_result(cleaned)
    after_reply = _generate_after_action_reply(cleaned, result)
    _announce(after_reply)

    memory_facts = _extract_memory_facts(
        source=source,
        user_text=cleaned,
        outcome=result.status,
        detail=result.detail,
        assistant_before=before_turn.spoken_reply,
        assistant_after=after_reply,
    )
    record_interaction(
        InteractionRecord(
            source=source,
            text=cleaned,
            outcome=result.status,
            detail=result.detail,
            assistant_before=before_turn.spoken_reply,
            assistant_after=after_reply,
            memory_facts=memory_facts,
        )
    )
    return result.exit_code
