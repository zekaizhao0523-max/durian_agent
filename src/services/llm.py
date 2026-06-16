from __future__ import annotations

import logging

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


def polish_reply(
    draft_reply: str,
    intent: str | None,
    tool_facts: str,
    user_message: str,
) -> str | None:
    """可选 LLM 润色。未配置 API Key 时返回 None，沿用模板回复。"""
    settings = get_settings()
    if not settings.llm_enabled or not settings.openai_api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        prompt = (
            "你是榴莲选购助手小榴。请基于【事实数据】润色【草稿回复】，让语气像靠谱的导购朋友："
            "口语自然、好懂，少用客服腔和生硬套话；禁止 **、---、列表符等 Markdown；禁止编造价格、库存、批次信息。"
            "若用户问题与榴莲无关，不要回答其内容，只保留引导回到正题的表述。"
            "推荐类用【推荐】【理由】【下一步】；"
            "用户点名某品种问是否适合时用【结论】【理由】【下一步】；"
            "品种对比（两种及以上）用「我会从…方面对比，首先…其次…」口语分段，不用【推荐】【结论】；"
            "判断某批次时用【结论】。【下一步】。\n\n"
            f"用户问题：{user_message}\n"
            f"意图：{intent}\n"
            f"事实数据：\n{tool_facts}\n\n"
            f"草稿回复：\n{draft_reply}"
        )
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": "只使用提供的事实，不新增未给出的商品或批次。语气口语自然，像导购朋友聊天。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        content = resp.choices[0].message.content
        return content.strip() if content else None
    except Exception as exc:
        logger.warning("LLM polish skipped: %s", exc)
        return None
