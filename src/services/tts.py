from __future__ import annotations

import re

import edge_tts

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"
MAX_TTS_CHARS = 480

_MARKDOWN_RE = re.compile(r"\*+")
_SECTION_RE = re.compile(r"^【[^】]+】\s*", re.MULTILINE)


def text_for_speech(reply: str) -> str:
    """将 Agent 回复整理为适合朗读的短文本。"""
    text = reply.strip()
    if not text:
        return ""

    conclusion = re.search(r"【结论】\s*(.+?)(?:\n|$)", text)
    recommend = re.search(r"【推荐】\s*(.+?)(?:\n|$)", text)
    reasons = re.search(r"【理由】\s*\n?([\s\S]+?)(?:\n【|$)", text)
    next_step = re.search(r"【下一步】\s*\n?\s*[-·]?\s*(.+?)(?:\n|$)", text)

    parts: list[str] = []
    if recommend:
        parts.append(f"推荐{recommend.group(1).strip()}")
    elif conclusion:
        parts.append(conclusion.group(1).strip())
    if reasons:
        block = _SECTION_RE.sub("", reasons.group(1).strip())
        block = _MARKDOWN_RE.sub("", block)
        lines = [ln.strip().lstrip("1234567890.").strip() for ln in block.splitlines() if ln.strip()]
        if lines:
            parts.append("。".join(lines[:3]))
    elif not conclusion and not recommend:
        plain = _MARKDOWN_RE.sub("", text)
        plain = re.sub(r"\n{2,}", "。", plain)
        plain = plain.replace("\n", "，")
        parts.append(plain)

    if next_step:
        parts.append(f"下一步，{next_step.group(1).strip()}")

    spoken = "。".join(p for p in parts if p)
    spoken = re.sub(r"\s+", " ", spoken)
    spoken = re.sub(r"[#>`]", "", spoken)
    if len(spoken) > MAX_TTS_CHARS:
        spoken = spoken[:MAX_TTS_CHARS].rstrip("，。 ") + "。"
    return spoken


async def synthesize_speech(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    spoken = text_for_speech(text) or text.strip()[:MAX_TTS_CHARS]
    if not spoken:
        return b""

    communicate = edge_tts.Communicate(spoken, voice)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)
