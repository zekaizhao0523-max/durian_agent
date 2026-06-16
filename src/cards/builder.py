from __future__ import annotations

from src.models.schemas import Card, CardType


def build_trace_card(data: dict) -> Card:
    return Card(
        type=CardType.TRACE_BATCH,
        payload={
            "trace_code": data.get("trace_code"),
            "valid": data.get("valid", False),
            "batch_id": data.get("batch_id"),
            "batch_name": data.get("batch_name"),
            "variety": data.get("variety"),
            "grade": data.get("grade"),
            "origin": data.get("origin"),
            "pick_date": data.get("pick_date"),
            "stock_in_date": data.get("stock_in_date"),
            "weight_range": data.get("weight_range"),
            "ripeness_range": data.get("ripeness_range"),
            "batch_status": data.get("batch_status"),
            "granularity_tip": "我方按产地与批次自主生成的品类溯源码，非单果唯一码",
        },
    )


def build_product_cards(items: list[dict], limit: int = 3) -> list[Card]:
    cards = []
    for item in items[:limit]:
        cards.append(
            Card(
                type=CardType.PRODUCT_RECOMMEND,
                payload={
                    "product_id": item["product_id"],
                    "name": item["name"],
                    "price": item["price"],
                    "stock": item["stock"],
                    "ship_time": item.get("ship_time"),
                    "batch_summary": item.get("batch_summary", {}),
                    "match_reasons": item.get("recommend_reasons") or _build_match_reasons(item),
                },
            )
        )
    return cards


def build_purchase_card(product_id: str, link_data: dict) -> Card:
    return Card(
        type=CardType.PURCHASE_LINK,
        payload={
            "product_id": product_id,
            "url": link_data.get("url"),
            **link_data.get("card_params", {}),
        },
    )


def build_order_card(order: dict) -> Card:
    return Card(
        type=CardType.ORDER_INFO,
        payload={
            "order_id": order["order_id"],
            "status": order["status"],
            "items": order["items"],
            "trace_codes": order.get("trace_codes", []),
            "created_at": order.get("created_at"),
            "total_amount": order.get("total_amount"),
        },
    )


def _build_match_reasons(item: dict) -> list[str]:
    reasons = []
    if item.get("variety"):
        reasons.append(f"品种：{item['variety']}")
    if item.get("price"):
        reasons.append(f"价格 ¥{item['price']}")
    batch = item.get("batch_summary", {})
    if batch.get("origin"):
        reasons.append(f"产地：{batch['origin']}")
    if batch.get("ripeness_range"):
        reasons.append(f"成熟度区间：{batch['ripeness_range']}")
    return reasons[:3]
