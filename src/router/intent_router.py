from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.models.schemas import Intent, SessionSlots


@dataclass
class RouteResult:
    """规则路由结果：意图 + 更新后的槽位 + 简单置信度。"""

    intent: Intent
    slots: SessionSlots = field(default_factory=SessionSlots)
    confidence: float = 1.0


TRACE_CODE_PATTERN = re.compile(r"TR\d{8,}", re.IGNORECASE)
ORDER_ID_PATTERN = re.compile(r"ORD[_\-]?\d+", re.IGNORECASE)
BUDGET_PATTERNS = [
    re.compile(r"(?:预算\s*)?(\d{2,4})\s*(左右|块|元|以内|上下)"),
    re.compile(r"(\d{2,4})\s*元左右"),
]
TRACE_META_KEYWORDS = [
    "包含什么信息",
    "有什么信息",
    "哪些信息",
    "包含哪些",
    "码是什么意思",
    "溯源码是什么",
    "怎么生成",
    "怎么来的",
    "是什么意思",
]
VARIETY_EVAL_KEYWORDS = [
    "怎么样",
    "合适吗",
    "适不适合",
    "值得买",
    "能买吗",
    "你觉得",
    "你觉得怎么样",
    "好不好",
    "可以吗",
    "适合我",
    "适合吗",
]


def _extract_trace_code(text: str) -> str | None:
    """从文本中提取批次溯源码。"""
    match = TRACE_CODE_PATTERN.search(text)
    return match.group(0).upper() if match else None


def _extract_order_id(text: str) -> str | None:
    """从文本中提取订单号，并统一成 ORD_123 格式。"""
    match = ORDER_ID_PATTERN.search(text)
    return match.group(0).upper().replace("-", "_") if match else None


def _extract_budget(text: str) -> list[int] | None:
    """从用户表述中提取预算区间；忽略溯源码/订单号中的数字。"""
    cleaned = TRACE_CODE_PATTERN.sub(" ", text)
    cleaned = ORDER_ID_PATTERN.sub(" ", cleaned)

    for pattern in BUDGET_PATTERNS:
        match = pattern.search(cleaned)
        if not match:
            continue
        center = int(match.group(1))
        if center > 2000:
            continue
        margin = max(50, int(center * 0.2))
        return [max(0, center - margin), center + margin]
    return None


def _extract_variety(text: str) -> str | None:
    """识别用户提到的榴莲品种。"""
    varieties = ["猫山王", "金枕", "干尧", "黑刺", "苏丹王", "红虾", "金枕头"]
    for v in varieties:
        if v in text:
            return v
    return None


def _extract_taste_tags(text: str) -> list[str]:
    """把自然语言偏好映射成商品搜索用的口味标签。"""
    tags = []
    mapping = {
        "甜": "偏甜",
        "苦": "偏苦",
        "气味不重": "气味适中",
        "气味淡": "气味适中",
        "气味浓": "气味浓郁",
        "绵密": "绵密",
    }
    for key, tag in mapping.items():
        if key in text and tag not in tags:
            tags.append(tag)
    return tags


def _is_variety_evaluation(text: str, variety: str | None) -> bool:
    """用户点名某品种并询问是否适合（而非开放式推荐）。"""
    if not variety:
        return False
    return any(k in text for k in VARIETY_EVAL_KEYWORDS)


def route_intent(message: str, existing_slots: SessionSlots | None = None) -> RouteResult:
    """规则模式的意图识别入口。

    这里同时做槽位提取和意图判断；优先级从高风险/强确定性场景开始：
    人工/售后 > 溯源 > 购买 > 购后服务 > 推荐咨询 > 闲聊。
    """
    text = message.strip()
    slots = SessionSlots()
    if existing_slots:
        slots = existing_slots.model_copy(deep=True)

    trace_code = _extract_trace_code(text)
    if trace_code:
        slots.trace_code = trace_code

    order_id = _extract_order_id(text)
    if order_id:
        slots.order_id = order_id

    variety = _extract_variety(text)
    if variety:
        slots.variety = variety

    budget = _extract_budget(text)
    if budget:
        slots.budget = budget

    taste_tags = _extract_taste_tags(text)
    if taste_tags:
        slots.taste_tags = list(dict.fromkeys(slots.taste_tags + taste_tags))

    lower = text.lower()

    if any(k in text for k in ["投诉", "举报", "骗子", "太差了"]):
        return RouteResult(Intent.HUMAN_HANDOFF, slots)

    if any(k in text for k in ["退款", "退货", "售后", "过生", "过熟", "坏了", "理赔", "赔付", "不满意"]):
        return RouteResult(Intent.AFTER_SALE, slots)

    if order_id and any(k in text for k in ["订单", "ORD", "ord"]):
        return RouteResult(Intent.AFTER_SALE, slots)

    if any(k in text for k in TRACE_META_KEYWORDS):
        return RouteResult(Intent.CONSULT_VARIETY, slots)

    if trace_code or any(k in text for k in ["溯源", "扫码", "验真", "查码", "批次码"]):
        return RouteResult(Intent.TRACE_QUERY, slots)

    if any(k in text for k in ["买", "下单", "链接", "有货", "购买", "怎么卖"]):
        return RouteResult(Intent.PURCHASE_INTENT, slots)

    if any(k in text for k in ["开果", "怎么开", "保存", "冷藏", "冻", "能吃吗"]):
        return RouteResult(Intent.POST_PURCHASE, slots)

    if _is_variety_evaluation(text, variety):
        return RouteResult(Intent.CONSULT_EVALUATE, slots)

    if budget or any(k in text for k in ["推荐", "预算", "多少钱", "帮我选", "哪个好", "送礼", "礼盒", "体面"]):
        return RouteResult(Intent.CONSULT_BUDGET, slots)

    if variety or any(k in text for k in ["区别", "对比", "哪个好", "品种", "哪种"]):
        return RouteResult(Intent.CONSULT_VARIETY, slots)

    if any(k in lower for k in ["你好", "谢谢", "在吗", "hello"]):
        return RouteResult(Intent.CHITCHAT, slots, confidence=0.8)

    return RouteResult(Intent.CHITCHAT, slots, confidence=0.5)
