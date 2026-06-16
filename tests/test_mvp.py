from __future__ import annotations

import os

os.environ["AGENT_MODE"] = "rules"
os.environ["OPENAI_API_KEY"] = ""

from src.models.schemas import Intent
from src.storage.db import get_messages, get_stats, init_db
from src.tools.executor import execute


def test_mvp_recommend_trace_after_sale_and_history_flow(agent_handle) -> None:
    init_db()

    recommend = agent_handle("300左右，要甜一点、气味不要太重，推荐一下")
    assert recommend.intent == Intent.CONSULT_BUDGET
    assert len(recommend.cards) > 0
    assert "【结论】可以买" not in recommend.reply_text
    assert (
        "【推荐】" in recommend.reply_text
        or "金枕" in recommend.reply_text
        or any(card.type.value == "product_recommend" for card in recommend.cards)
    )

    trace = agent_handle("TR20260609002", session_id=recommend.session_id)
    assert trace.conclusion == "可以买"

    after_sale = agent_handle("榴莲过生了，要退款")
    assert after_sale.intent == Intent.AFTER_SALE
    assert after_sale.after_sale is not None
    assert "问题类型" in after_sale.reply_text

    after_sale_with_order = agent_handle(
        "订单号 ORD_10001，果子过熟坏了，有照片",
        session_id=after_sale.session_id,
        user_id="demo_user",
    )
    assert after_sale_with_order.after_sale is not None
    assert after_sale_with_order.after_sale.order_id == "ORD_10001"

    history = get_messages(recommend.session_id)
    assert len(history) >= 2

    stats = get_stats()
    assert stats["sessions"] >= 1


def test_mvp_consultation_and_evaluation_paths(agent_handle) -> None:
    gift = agent_handle("送礼选什么榴莲好？")
    assert gift.intent == Intent.CONSULT_BUDGET
    assert "【推荐】" in gift.reply_text or len(gift.cards) > 0 or "榴莲" in gift.reply_text

    compare = agent_handle("猫山王和金枕有什么区别")
    assert compare.intent == Intent.CONSULT_VARIETY
    assert "我会从" in compare.reply_text
    assert "首先" in compare.reply_text or "先说" in compare.reply_text
    assert "【推荐】" not in compare.reply_text

    musang = agent_handle("预算300左右，要甜一点、气味不要太重，你觉得猫山王怎么样")
    assert musang.intent == Intent.CONSULT_EVALUATE
    assert musang.conclusion == "不建议"
    assert "【结论】" in musang.reply_text
    assert "【推荐】" not in musang.reply_text

    golden_pillow = agent_handle("预算300左右，要甜一点、气味不要太重，你觉得金枕怎么样")
    assert golden_pillow.intent == Intent.CONSULT_EVALUATE
    assert golden_pillow.conclusion == "可以买"


def test_mvp_trace_tool_has_new_batch() -> None:
    trace = execute("query_trace_code", {"trace_code": "TR20260607003"})

    assert trace.success
    assert trace.data["variety"] == "干尧"
