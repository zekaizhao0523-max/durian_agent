"""验证 durian_demo LangGraph 入口与售后分诊图。"""
from __future__ import annotations

import os

os.environ["AGENT_MODE"] = "rules"
os.environ["OPENAI_API_KEY"] = ""

from langchain_core.messages import AIMessage, HumanMessage

from durian_demo.graph import after_sale_graph, graph
from src.graph.nodes import format_node
from src.graph.tools import after_sale_triage


def test_after_sale_triage_tool_is_callable() -> None:
    raw = after_sale_triage.invoke({"message": "榴莲坏了，有照片", "order_id": ""})

    assert "problem_type" in raw


def test_after_sale_graph_returns_structured_triage() -> None:
    result = after_sale_graph.invoke(
        {"user_message": "订单号 ORD_10001，果子过熟坏了，昨天签收的，有照片"}
    )

    assert "问题类型" in result["reply_text"]
    assert "是否转人工" in result["reply_text"]
    assert result["after_sale"]["order_id"] == "ORD_10001"


def test_durian_agent_graph_compiles() -> None:
    assert graph is not None


def test_format_node_recognizes_after_sale_tool_result() -> None:
    formatted = format_node(
        {
            "messages": [HumanMessage(content="榴莲过生了要退款"), AIMessage(content="处理中")],
            "tool_results": [
                {
                    "name": "after_sale_triage",
                    "args": {"message": "榴莲过生了要退款"},
                    "result": after_sale_triage.invoke({"message": "榴莲过生了要退款"}),
                }
            ],
            "shown_trace_tip": False,
        }
    )

    assert formatted["intent"] == "after_sale"
    assert formatted["after_sale"] is not None
    assert "问题类型" in formatted["reply_text"]
