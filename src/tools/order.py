"""订单工具：按订单号查询购后信息，并校验用户归属权限。"""

from __future__ import annotations

import time

from src.models.schemas import ToolResult
from src.storage.db import get_order


def _normalize_order_id(order_id: str) -> str:
    """将用户输入的订单号统一为 ORD_123 格式。"""
    oid = order_id.strip().upper()
    if oid.startswith("ORD_"):
        return oid
    if oid.startswith("ORD"):
        return oid.replace("ORD", "ORD_", 1)
    return f"ORD_{oid}"


def get_order_detail(order_id: str, user_id: str | None = None) -> ToolResult:
    """查询当前用户本人的订单详情，主要用于售后场景。

    安全要求：必须传入服务端可信的 user_id（由 invoke_tool 从 configurable 注入），
    订单归属不一致时拒绝访问，防止模型在参数中伪造用户查他人订单。

    Args:
        order_id: 订单号，支持 ORD_10001、ORD10001 等写法。
        user_id: 当前登录用户 ID；为空返回 ORDER_AUTH_REQUIRED。

    Returns:
        成功时 data 含 status、items、trace_codes、total_amount 等；
        失败时 error_code 为 ORDER_NOT_FOUND / ORDER_AUTH_REQUIRED / ORDER_ACCESS_DENIED。
    """
    start = time.perf_counter()
    oid = _normalize_order_id(order_id)
    order = get_order(oid)

    if not order:
        return ToolResult(
            success=False,
            source="order_service",
            error_code="ORDER_NOT_FOUND",
            data={"order_id": oid},
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    if not user_id:
        return ToolResult(
            success=False,
            source="order_service",
            error_code="ORDER_AUTH_REQUIRED",
            data={"order_id": oid},
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    if order.get("user_id") != user_id:
        return ToolResult(
            success=False,
            source="order_service",
            error_code="ORDER_ACCESS_DENIED",
            data={"order_id": oid},
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    return ToolResult(
        success=True,
        source="order_service",
        data=order,
        latency_ms=int((time.perf_counter() - start) * 1000),
    )
