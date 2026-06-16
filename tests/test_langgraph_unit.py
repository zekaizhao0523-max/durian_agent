from __future__ import annotations

import os

os.environ["AGENT_MODE"] = "rules"
os.environ["OPENAI_API_KEY"] = ""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.graph.cards_from_tools import build_cards_from_tool_results, infer_intent
from src.graph.nodes import format_node, route_after_agent
from src.graph.tools import query_trace_code


def test_query_trace_tool_invoke() -> None:
    raw = query_trace_code.invoke({"trace_code": "TR20260609002"})
    assert "金枕" in raw


def test_build_cards_from_trace_tool() -> None:
    raw = query_trace_code.invoke({"trace_code": "TR20260609002"})
    tool_results = [
        {
            "name": "query_trace_code",
            "args": {"trace_code": "TR20260609002"},
            "result": raw,
        }
    ]
    cards = build_cards_from_tool_results(tool_results)
    assert len(cards) == 1
    assert cards[0].type.value == "trace_batch"
    assert infer_intent(tool_results) == "trace_query"


def test_merge_duplicate_product_cards() -> None:
    tool_results = [
        {
            "name": "search_products",
            "args": {},
            "result": (
                '{"success": true, "data": {"items": [{"product_id": "sku_101", '
                '"name": "金枕榴莲", "price": 268, "stock": 45, "ship_time": "明日达", '
                '"variety": "金枕"}]}}'
            ),
        },
        {
            "name": "get_purchase_link",
            "args": {"product_id": "sku_101"},
            "result": (
                '{"success": true, "data": {"url": "https://shop.example.com/buy/sku_101", '
                '"card_params": {"title": "金枕榴莲", "price": 268}}}'
            ),
        },
    ]
    cards = build_cards_from_tool_results(tool_results)
    assert len(cards) == 1
    assert cards[0].type.value == "product_recommend"
    assert cards[0].payload.get("purchase_url") == "https://shop.example.com/buy/sku_101"


def test_format_node_parses_recommendation() -> None:
    raw = query_trace_code.invoke({"trace_code": "TR20260609002"})
    state = {
        "messages": [
            SystemMessage(content="sys"),
            HumanMessage(content="hello"),
            AIMessage(
                content="【推荐】金枕榴莲 A级 5-6斤（¥268）\n\n【理由】\n1. 测试\n\n【下一步】\n- 查看商品"
            ),
        ],
        "tool_results": [
            {
                "name": "query_trace_code",
                "args": {"trace_code": "TR20260609002"},
                "result": raw,
            }
        ],
        "shown_trace_tip": False,
    }
    assert route_after_agent(state) == "format"
    formatted = format_node(state)
    assert formatted["conclusion"] == "金枕榴莲 A级 5-6斤（¥268）"
    assert "批次" in formatted["reply_text"] or len(formatted["cards"]) > 0
