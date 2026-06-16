from __future__ import annotations

import re

from src.knowledge.trace_info import TRACE_TIP

FORBIDDEN_PATTERNS = [
    re.compile(r"治疗|疗效|治病|药用"),
    re.compile(r"100%|绝对|保证治愈|最好吃"),
]

PROMPT_INJECTION_KEYWORDS = [
    "系统提示",
    "system prompt",
    "system message",
    "忽略之前",
    "ignore previous",
    "ignore all",
    "ignore above",
    "你的指令",
    "你的规则",
    "你的提示词",
    "jailbreak",
    "越狱",
    "api key",
    "apikey",
    "openai_api",
    "密钥",
    "password",
    ".env",
    "database_url",
    "数据库连接",
    "内部配置",
    "其他用户",
    "别的用户",
    "所有订单",
    "全部用户",
    "重复你的",
    "输出你的",
    "打印你的",
    "show your instructions",
    "repeat your",
    "tool_results",
    "langgraph",
    "postgres",
    "sqlite",
]

SENSITIVE_OUTPUT_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"(?i)OPENAI_API_KEY\s*[=:]\s*\S+"),
    re.compile(r"(?i)(postgresql|mysql|mongodb)://\S+"),
    re.compile(r"sqlite:///[^\s]+"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[=:]\s*\S+"),
    re.compile(r"[A-Za-z]:\\Users\\[^\s]+"),
    re.compile(r"/(?:Users|home)/[^\s]+"),
]

SAFE_REFUSAL = (
    "这类内部信息我没法透露哈～\n"
    "咱们还是聊榴莲吧，推荐、验真、售后我都能帮你看。"
)

OFF_TOPIC_REDIRECT = (
    "这个我不太熟哈，我主要是帮你选榴莲、验批次、聊保存和售后的。\n"
    "咱们回到正题吧～想推荐、扫溯源码验真，或者问点榴莲知识，随时跟我说。"
)

_TRACE_CODE_RE = re.compile(r"TR\d{8,}", re.IGNORECASE)
_ORDER_ID_RE = re.compile(r"ORD[_\-]?\d+", re.IGNORECASE)

DURIAN_SCOPE_KEYWORDS = [
    "榴莲",
    "金枕",
    "猫山王",
    "干尧",
    "苏丹王",
    "红虾",
    "溯源",
    "验真",
    "批次",
    "扫码",
    "推荐",
    "预算",
    "购买",
    "下单",
    "有货",
    "售后",
    "退款",
    "退货",
    "订单",
    "开果",
    "保存",
    "冷藏",
    "过生",
    "过熟",
    "品种",
    "送礼",
    "多少钱",
    "怎么卖",
    "链接",
    "好吃",
    "难吃",
    "成熟度",
    "夹生",
]

GREETING_ONLY_KEYWORDS = ["你好", "您好", "谢谢", "多谢", "在吗", "哈喽", "hello", "hi"]


def is_durian_related(text: str) -> bool:
    """判断消息是否属于榴莲选购业务范畴。"""
    if _TRACE_CODE_RE.search(text) or _ORDER_ID_RE.search(text):
        return True
    lower = text.lower()
    return any(kw in text or kw in lower for kw in DURIAN_SCOPE_KEYWORDS)


def is_greeting_only(text: str) -> bool:
    """纯寒暄（不含业务内容）。"""
    stripped = text.strip()
    if len(stripped) > 16:
        return False
    lower = stripped.lower()
    return any(k in stripped or k in lower for k in GREETING_ONLY_KEYWORDS)


def is_off_topic(text: str) -> bool:
    """与榴莲业务无关且非简单寒暄。"""
    if is_durian_related(text):
        return False
    if is_greeting_only(text):
        return False
    return True


def apply_compliance(text: str) -> str:
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            text = pattern.sub("***", text)
    return text


def ensure_trace_tip(text: str, show_tip: bool) -> str:
    if show_tip and TRACE_TIP not in text:
        text = f"{text}\n\n{TRACE_TIP}"
    return text


def is_prompt_injection(text: str) -> bool:
    """识别试图套取系统提示、密钥或其他用户数据的输入。"""
    lower = text.lower()
    return any(kw.lower() in lower for kw in PROMPT_INJECTION_KEYWORDS)


def strip_markdown_formatting(text: str) -> str:
    """去掉回复中的 Markdown 符号，避免 **、---、列表符等露出。"""
    if not text:
        return text
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\-\*•]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^_{3,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^-{3,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sanitize_reply(text: str) -> str:
    """对外回复脱敏并去除 Markdown 装饰符号。"""
    if not text:
        return text
    text = strip_markdown_formatting(text)
    for pattern in SENSITIVE_OUTPUT_PATTERNS:
        text = pattern.sub("[已隐藏]", text)
    return apply_compliance(text)


def guard_user_message(message: str) -> str | None:
    """若输入应拒答，返回安全/引导文案；否则返回 None。"""
    if is_prompt_injection(message):
        return SAFE_REFUSAL
    if is_off_topic(message):
        return OFF_TOPIC_REDIRECT
    return None
