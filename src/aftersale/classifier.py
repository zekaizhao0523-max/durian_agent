from __future__ import annotations

import re

from src.aftersale.rules import CLASSIFIER_KEYWORDS, PROBLEM_TYPES

_PHOTO_HINT = re.compile(r"照片|图片|拍了|已发图|附图|上传")
_ORDER_HINT = re.compile(r"ORD[_\-]?\d+", re.IGNORECASE)
_TIME_HINT = re.compile(r"签收|昨天|今天|小时前|刚收到")


def classify_problem(message: str) -> str:
    """根据用户描述分类售后问题类型。"""
    text = message.strip()
    scores: dict[str, int] = {}

    for problem_type, keywords in CLASSIFIER_KEYWORDS.items():
        score = sum(2 for kw in keywords if kw in text)
        if score:
            scores[problem_type] = score

    if not scores:
        if any(k in text for k in ["售后", "不满意", "投诉", "怎么办"]):
            return "general"
        return "general"

    return max(scores, key=scores.get)


def problem_label(problem_type: str) -> str:
    return PROBLEM_TYPES.get(problem_type, problem_type)


def detect_provided_evidence(message: str, has_order: bool) -> set[str]:
    """从用户消息中识别已提供的凭证。"""
    provided: set[str] = set()
    if has_order or _ORDER_HINT.search(message):
        provided.add("order_id")
    if _PHOTO_HINT.search(message):
        provided.add("fruit_photos")
        provided.add("package_photos")
    if _TIME_HINT.search(message):
        provided.add("sign_time")
    if any(k in message for k in ["称重", "公斤", "斤", "不够秤"]):
        provided.add("weight_photos")
    if len(message.strip()) >= 8:
        provided.add("problem_desc")
    return provided
