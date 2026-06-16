"""根据工具调用结果生成前端卡片，并从工具序列推断业务意图。"""

from __future__ import annotations

import json
from typing import Any

from src.cards.builder import (
    build_order_card,
    build_product_cards,
    build_purchase_card,
    build_trace_card,
)
from src.models.schemas import Card, CardType


def _parse_tool_data(record: dict[str, Any]) -> dict[str, Any]:
    """解析单条 tool_result 的 result 字段，仅保留 success=true 的 data。"""
    raw = record.get("result", {})
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    if not raw.get("success"):
        return {}
    return raw.get("data", {})


def _merge_product_and_purchase_cards(cards: list[Card]) -> list[Card]:
    """合并同一商品的推荐卡与购买链接卡，避免前端出现重复商品卡片。"""
    links_by_product: dict[str, str] = {}
    for card in cards:
        if card.type == CardType.PURCHASE_LINK:
            pid = card.payload.get("product_id")
            url = card.payload.get("url")
            if pid and url:
                links_by_product[pid] = url

    merged: list[Card] = []
    recommended_products: set[str] = set()

    for card in cards:
        if card.type == CardType.PRODUCT_RECOMMEND:
            pid = card.payload.get("product_id")
            payload = dict(card.payload)
            if pid and pid in links_by_product:
                payload["purchase_url"] = links_by_product[pid]
            if pid:
                recommended_products.add(pid)
            merged.append(Card(type=card.type, payload=payload))
        elif card.type == CardType.PURCHASE_LINK:
            pid = card.payload.get("product_id")
            if pid and pid in recommended_products:
                continue
            merged.append(card)
        else:
            merged.append(card)

    return merged


def build_cards_from_tool_results(tool_results: list[dict[str, Any]]) -> list[Card]:
    """根据工具调用结果生成前端可渲染的结构化卡片列表。

    卡片字段来自可信工具返回值，不由 LLM 直接编造。最多返回 5 张，按业务 id 去重。
    """
    cards: list[Card] = []
    seen_products: set[str] = set()

    for record in tool_results:
        name = record.get("name")
        data = _parse_tool_data(record)

        if name == "query_trace_code" and data.get("valid"):
            payload = {"trace_code": record.get("args", {}).get("trace_code"), **data}
            cards.append(build_trace_card(payload))

        elif name == "search_products":
            items = []
            for item in data.get("items", [])[:3]:
                pid = item.get("product_id")
                if pid and pid not in seen_products:
                    seen_products.add(pid)
                    items.append(item)
            if items:
                cards.extend(build_product_cards(items))

        elif name == "get_product_detail" and data.get("product_id"):
            pid = data["product_id"]
            if pid not in seen_products:
                seen_products.add(pid)
                cards.extend(build_product_cards([data]))

        elif name == "get_purchase_link" and data.get("url"):
            product_id = record.get("args", {}).get("product_id", "")
            cards.append(build_purchase_card(product_id, data))

        elif name == "get_order_detail" and data.get("order_id"):
            cards.append(build_order_card(data))

    cards = _merge_product_and_purchase_cards(cards)
    unique: list[Card] = []
    seen: set[str] = set()
    for card in cards:
        key = f"{card.type}:{card.payload.get('product_id') or card.payload.get('trace_code') or card.payload.get('order_id')}"
        if key not in seen:
            seen.add(key)
            unique.append(card)
    return unique[:5]


def infer_intent(tool_results: list[dict[str, Any]]) -> str | None:
    """根据本轮调用了哪些工具，粗略反推业务意图（用于埋点与响应元数据）。"""
    names = [r.get("name") for r in tool_results]
    if "after_sale_triage" in names or "get_order_detail" in names:
        return "after_sale"
    if "query_trace_code" in names:
        return "trace_query"
    if "get_purchase_link" in names:
        return "purchase_intent"
    if "search_products" in names or "get_product_detail" in names:
        return "consult_budget"
    if "search_knowledge" in names:
        return "consult_variety"
    return "chitchat"
