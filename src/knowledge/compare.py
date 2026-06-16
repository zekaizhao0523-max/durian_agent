from __future__ import annotations

COMPARE_KEYWORDS = ["对比", "区别", "不同", "哪个好", "哪种好", "比一比", "比较"]
VARIETIES = ["猫山王", "金枕", "干尧", "黑刺", "苏丹王", "红虾"]
_POINT_LABELS = ["首先", "其次", "再聊聊", "还有"]


def is_compare_question(message: str) -> bool:
    """用户是否在问品种之间的对比。"""
    if any(k in message for k in ["对比", "区别", "不同", "比一比", "比较"]):
        return True
    mentioned = [v for v in VARIETIES if v in message]
    if len(mentioned) >= 2:
        return True
    return False


def format_comparison_reply(
    message: str,
    chunk: dict | None,
    product_hint: str | None = None,
) -> str:
    """把百科对比内容格式化为「我会从…方面对比，首先…其次…」的自然话术。"""
    comparison = (chunk or {}).get("comparison")
    if comparison:
        aspects = comparison.get("aspects", "口感、气味、价格和适合人群")
        points = comparison.get("points", [])
        parts = [f"我会从{aspects}这几个方面帮你对比一下。\n"]
        for idx, point in enumerate(points):
            label = _POINT_LABELS[idx] if idx < len(_POINT_LABELS) else "另外"
            parts.append(f"\n{label}是{point['name']}：{point['text']}")
        summary = comparison.get("summary")
        if summary:
            parts.append(f"\n\n{summary}")
    elif chunk and chunk.get("content"):
        parts = [
            "我会从口感、气味、价格和适合人群这几个方面帮你梳理一下。\n\n",
            chunk["content"],
        ]
    else:
        parts = ["你想对比哪几个品种？跟我说一下偏好，我帮你逐条分析。"]

    if product_hint:
        parts.append(f"\n\n对了，店里现在有在售的 {product_hint}，感兴趣可以点下面卡片看看。")

    return "".join(parts)
