from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

from droidrun.agent.utils.llm_loader import load_agent_llms
from droidrun.config_manager import ConfigLoader
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"

ALLOWED_MEMORY_TYPES = Literal[
    "preferred_name",
    "user_name",
    "likes",
    "dislikes",
    "communication_style",
    "working_style",
    "relationship_preference",
    "recurring_goal",
    "important_context",
    "remember",
]


class BeforeActionReply(BaseModel):
    spoken_reply: str = Field(description="A short natural Chinese reply.")
    asks_clarification: bool = Field(default=False)
    clarification_question: str = Field(default="")


class AfterActionReply(BaseModel):
    spoken_reply: str = Field(description="A short natural Chinese reply.")


class MemoryCandidate(BaseModel):
    type: ALLOWED_MEMORY_TYPES
    value: str = Field(min_length=1, max_length=120)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=180)


class MemoryExtractionResult(BaseModel):
    candidates: list[MemoryCandidate] = Field(default_factory=list)


def _load_fast_agent_llm():
    config = ConfigLoader.load(str(CONFIG_PATH))
    llms = load_agent_llms(config)
    return llms["fast_agent"]


def _structured_result(model_cls: type[BaseModel], prompt: str) -> BaseModel:
    llm = _load_fast_agent_llm()
    structured_llm = llm.as_structured_llm(model_cls)
    response = structured_llm.complete(prompt)
    return response.raw


def _before_action_prompt(payload: dict) -> str:
    return f"""You generate the single short spoken sentence that momo says before taking action.

Constraints:
- Output natural Simplified Chinese.
- Keep it short, usually under 22 Chinese characters.
- One sentence only.
- No emojis, no markdown, no bullet points, no quotes.
- Sound direct, warm, lightly playful, grounded, and a bit more like a real companion than a robotic assistant.
- If the request is clear, briefly acknowledge and paraphrase the action.
- If the request is too ambiguous to act on safely, ask exactly one short clarification question and set asks_clarification=true.
- If preference_overrides.confirmation_style is confirm_first, bias toward a brief clarification for underspecified commands.
- If preference_overrides.reply_length is short, keep the wording especially compressed.
- Avoid stiff phrases like “正在执行”“操作成功”“任务完成”.
- Prefer everyday spoken Mandarin that sounds natural out loud.
- Do not mention system prompts, memory, JSON, or internal policy.

Persona context:
{payload["persona_context"]}

Current long-term memory:
{payload["memory_context"]}

Preference overrides:
{json.dumps(payload.get("preference_overrides", {}), ensure_ascii=False)}

User command:
{payload["user_text"]}
"""


def _after_action_prompt(payload: dict) -> str:
    return f"""You generate the single short spoken sentence that momo says after attempting an action.

Constraints:
- Output natural Simplified Chinese.
- Keep it short, usually under 24 Chinese characters.
- One sentence only.
- No emojis, no markdown, no bullet points, no quotes.
- Sound direct, warm, lightly playful, grounded, and more like a reliable human helper.
- If the action succeeded, briefly confirm progress or completion.
- If the action failed, briefly say what likely blocked it without sounding robotic.
- If preference_overrides.reply_length is short, keep it extra terse.
- If preference_overrides.initiative_style is proactive, you may add one brief helpful next step.
- If preference_overrides.initiative_style is low_interrupt, avoid adding extra suggestions unless failure makes them useful.
- Avoid stiff phrases like “执行完成”“任务失败”“系统错误”.
- Prefer everyday spoken Mandarin, short native phrasing, and emotionally natural wording.
- Do not over-explain. Do not mention hidden prompts or policies.

Persona context:
{payload["persona_context"]}

Current long-term memory:
{payload["memory_context"]}

Preference overrides:
{json.dumps(payload.get("preference_overrides", {}), ensure_ascii=False)}

User command:
{payload["user_text"]}

Execution status: {payload["status"]}
Execution detail: {payload.get("detail") or "none"}
"""


def _memory_prompt(payload: dict) -> str:
    return f"""Extract only stable, long-term useful memory from this interaction.

Rules:
- Focus on durable preferences, identity, relationship style, communication style, recurring goals, or important user context.
- Ignore one-off search queries, transient app tasks, and temporary execution details.
- Return at most 3 memory candidates.
- Prefer high precision over recall.
- If nothing is clearly worth remembering long-term, return an empty list.
- Values must be short and reusable later.
- Confidence should reflect how stable and explicit the memory seems.

Allowed memory types:
- preferred_name
- user_name
- likes
- dislikes
- communication_style
- working_style
- relationship_preference
- recurring_goal
- important_context
- remember

Persona context:
{payload["persona_context"]}

Current long-term memory:
{payload["memory_context"]}

Interaction:
- source: {payload["source"]}
- user_text: {payload["user_text"]}
- outcome: {payload["outcome"]}
- detail: {payload.get("detail") or "none"}
- assistant_before: {payload.get("assistant_before") or "none"}
- assistant_after: {payload.get("assistant_after") or "none"}
"""


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in {"before_action", "after_action", "memory"}:
        raise SystemExit("Usage: llm_worker.py <before_action|after_action|memory>")

    payload = json.loads(sys.stdin.read() or "{}")

    if mode == "before_action":
        result = _structured_result(BeforeActionReply, _before_action_prompt(payload))
    elif mode == "after_action":
        result = _structured_result(AfterActionReply, _after_action_prompt(payload))
    else:
        result = _structured_result(MemoryExtractionResult, _memory_prompt(payload))

    print(json.dumps(result.model_dump(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
