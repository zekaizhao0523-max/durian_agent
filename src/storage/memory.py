from __future__ import annotations

import json
import re

from src.models.schemas import SessionSlots
from src.storage.db import (
    add_user_memory,
    get_batch_experiences,
    get_user_memories,
    get_user_profile,
    upsert_user_profile,
)

RATING_PATTERN = re.compile(r"(好吃|满意|不错|打\s*(\d)\s*分|(\d)\s*分)")
DISLIKE_PATTERN = re.compile(r"(不好吃|不满意|难吃|失望|过生|过熟)")


def build_long_term_context(user_id: str | None) -> str:
    """将长期记忆格式化为可注入 System Prompt 的文本。"""
    if not user_id:
        return ""

    parts: list[str] = []

    profile = get_user_profile(user_id)
    if profile:
        tags = profile.get("taste_tags") or []
        if isinstance(tags, str):
            tags = json.loads(tags)
        line_parts = []
        if tags:
            line_parts.append(f"口味偏好：{'、'.join(tags)}")
        if profile.get("budget_min") and profile.get("budget_max"):
            line_parts.append(f"常用预算：{profile['budget_min']}-{profile['budget_max']} 元")
        if profile.get("favorite_variety"):
            line_parts.append(f"偏好品种：{profile['favorite_variety']}")
        if profile.get("notes"):
            line_parts.append(f"备注：{profile['notes']}")
        if line_parts:
            parts.append("【用户画像】\n" + "；".join(line_parts))

    experiences = get_batch_experiences(user_id, limit=3)
    if experiences:
        exp_lines = []
        for exp in experiences:
            seg = []
            if exp.get("variety"):
                seg.append(exp["variety"])
            if exp.get("trace_code"):
                seg.append(f"批次码 {exp['trace_code']}")
            if exp.get("rating"):
                seg.append(f"评分 {exp['rating']}/5")
            if exp.get("note"):
                seg.append(exp["note"])
            if seg:
                exp_lines.append("- " + "，".join(seg))
        if exp_lines:
            parts.append("【历史批次体验】\n" + "\n".join(exp_lines))

    memories = get_user_memories(user_id, limit=5)
    if memories:
        mem_lines = [f"- {m['content']}" for m in memories if m.get("content")]
        if mem_lines:
            parts.append("【记住的事实】\n" + "\n".join(mem_lines))

    return "\n\n".join(parts)


def sync_slots_to_profile(user_id: str | None, slots: SessionSlots) -> None:
    """从会话槽位同步到长期用户画像。

    当前只沉淀相对稳定的偏好：预算、口味标签和品种偏好。
    """
    if not user_id:
        return

    budget_min = slots.budget[0] if slots.budget else None
    budget_max = slots.budget[1] if slots.budget else None

    upsert_user_profile(
        user_id=user_id,
        taste_tags=slots.taste_tags or None,
        budget_min=budget_min,
        budget_max=budget_max,
        favorite_variety=slots.variety,
    )


def extract_memories_from_message(user_id: str | None, message: str, slots: SessionSlots) -> None:
    """从用户消息中提取可长期记住的事实。

    这是一套保守的规则抽取：只有明确出现评价、差评或“记住/下次”
    这类表达时才写入长期记忆，避免把一次性闲聊误存成偏好。
    """
    if not user_id:
        return

    rating_match = RATING_PATTERN.search(message)
    if rating_match and slots.trace_code:
        rating = None
        for g in rating_match.groups():
            if g and g.isdigit():
                rating = int(g)
                break
        add_user_memory(
            user_id,
            f"对批次 {slots.trace_code} 的评价：{message[:60]}",
            memory_type="experience",
        )

    if DISLIKE_PATTERN.search(message) and slots.trace_code:
        add_user_memory(
            user_id,
            f"对批次 {slots.trace_code} 不满：{message[:60]}",
            memory_type="experience",
        )

    if "以后" in message or "下次" in message or "记住" in message:
        add_user_memory(user_id, message[:120], memory_type="preference")
