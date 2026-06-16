"""榴莲电商 AI 售后 Agent — LangGraph Studio 入口。

本模块导出两个图：
- graph：完整榴莲 Agent（推荐 / 验真 / 知识 / 售后 tool-calling）
- after_sale_graph：售后分诊专用图（分类 → 规则命中 → 结构化输出）

业务工具（非模板 utc_now / calculator）：
- query_trace_code、search_products、get_order_detail
- search_knowledge、after_sale_triage（坏果/过生/过熟/物流/重量/预售/退款）
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.aftersale.triage import format_after_sale_reply, triage_after_sale
from src.graph.builder import build_graph
from src.router.intent_router import _extract_order_id

# ── 完整榴莲 Agent（LangGraph Studio 侧边栏：durian_agent）──
graph = build_graph()


# ── 售后分诊专用图（LangGraph Studio 侧边栏：after_sale_triage）──
class AfterSaleState(TypedDict):
    user_message: str
    order_id: str | None
    after_sale: dict[str, Any]
    reply_text: str


def _triage_node(state: AfterSaleState) -> dict:
    """售后闭环：问题分类 → 规则命中 → 缺失凭证 → 处理建议 → 客服话术 → 转人工。"""
    message = state["user_message"]
    order_id = state.get("order_id") or _extract_order_id(message)
    triage = triage_after_sale(message, order_id=order_id)
    return {
        "order_id": order_id,
        "after_sale": triage.model_dump(),
        "reply_text": format_after_sale_reply(triage),
    }


_after_sale_builder = StateGraph(AfterSaleState)
_after_sale_builder.add_node("triage", _triage_node)
_after_sale_builder.add_edge(START, "triage")
_after_sale_builder.add_edge("triage", END)

after_sale_graph = _after_sale_builder.compile()
