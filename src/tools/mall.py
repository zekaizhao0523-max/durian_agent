"""商城工具：商品搜索、详情与购买链接（数据来自 PostgreSQL 演示目录）。"""

from __future__ import annotations

import time

from src.models.schemas import ToolResult
from src.services.recommend import rank_products
from src.storage.db import get_product, list_products


def search_products(
    variety: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    taste_tags: list[str] | None = None,
) -> ToolResult:
    """搜索在售榴莲商品并按综合得分排序。

    过滤逻辑：品种名匹配 → 价格区间 → 口味标签 → 库存 > 0；
    排序由 services.recommend.rank_products 完成（预算、口味、热度、库存等）。

    Args:
        variety: 品种关键词，如金枕、猫山王、黑刺。
        price_min: 最低价格（元），可选。
        price_max: 最高价格（元），可选。
        taste_tags: 口味偏好标签列表，如 ["偏甜", "气味适中"]。

    Returns:
        data.items 为排序后的商品列表，通常取前 3 个做推荐。
    """
    start = time.perf_counter()
    items = list_products()

    if variety:
        items = [p for p in items if variety in p["variety"] or variety in p["name"]]

    if price_min is not None:
        items = [p for p in items if p["price"] >= price_min]
    if price_max is not None:
        items = [p for p in items if p["price"] <= price_max]

    if taste_tags:
        for tag in taste_tags:
            items = [
                p
                for p in items
                if any(tag in t or t in tag for t in p.get("taste_tags", []))
            ]

    items = [p for p in items if p["stock"] > 0]
    budget = None
    if price_min is not None or price_max is not None:
        budget = [price_min or 0, price_max or 99999]
    items = rank_products(items, budget=budget, taste_tags=taste_tags, variety=variety)

    return ToolResult(
        success=True,
        source="mall_service",
        data={"items": items},
        latency_ms=int((time.perf_counter() - start) * 1000),
    )


def get_product_detail(product_id: str) -> ToolResult:
    """获取单个 SKU 的完整商品信息。

    Args:
        product_id: 商品 ID，如 sku_101。

    Returns:
        成功时 data 为商品 dict（含价格、库存、trace_code、batch_summary 等）；
        不存在时 error_code=PRODUCT_NOT_FOUND。
    """
    start = time.perf_counter()
    product = get_product(product_id)
    if not product:
        return ToolResult(
            success=False,
            source="mall_service",
            error_code="PRODUCT_NOT_FOUND",
            latency_ms=int((time.perf_counter() - start) * 1000),
        )
    return ToolResult(
        success=True,
        source="mall_service",
        data=product,
        latency_ms=int((time.perf_counter() - start) * 1000),
    )


def get_purchase_link(product_id: str, channel: str = "web") -> ToolResult:
    """生成商品购买链接及前端卡片所需参数。

    演示环境 URL 为占位域名；对接真实商城时可由 HTTP 适配器覆盖。

    Args:
        product_id: 商品 ID。
        channel: 渠道标识，默认 web。

    Returns:
        data.url 为购买链接；data.card_params 含 title、price、image。
    """
    start = time.perf_counter()
    product = get_product(product_id)
    if not product:
        return ToolResult(
            success=False,
            source="mall_service",
            error_code="PRODUCT_NOT_FOUND",
            latency_ms=int((time.perf_counter() - start) * 1000),
        )
    return ToolResult(
        success=True,
        source="mall_service",
        data={
            "url": f"https://shop.example.com/buy/{product_id}?channel={channel}",
            "card_params": {
                "title": product["name"],
                "price": product["price"],
                "image": product.get("image", ""),
            },
        },
        latency_ms=int((time.perf_counter() - start) * 1000),
    )
