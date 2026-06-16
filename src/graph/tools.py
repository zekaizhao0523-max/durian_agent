"""LangChain 工具定义：供大模型 tool-calling 使用，内部转发至 src/tools/。"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from src.tools.executor import execute


def _dump(result) -> str:
    """将 ToolResult 序列化为 JSON 字符串，供 LLM 读取工具返回值。"""
    return json.dumps(result.model_dump(), ensure_ascii=False)


@tool
def query_trace_code(trace_code: str) -> str:
    """查询我方自主生成的批次溯源码（按产地与批次编码），返回产地、入库日期、成熟度区间、批次状态等。"""
    return _dump(execute("query_trace_code", {"trace_code": trace_code}))


@tool
def search_products(
    variety: str = "",
    price_min: int = 0,
    price_max: int = 9999,
    taste_tags: str = "",
) -> str:
    """搜索在售榴莲商品，按特征/价格/偏好/销售热度综合排序。variety 如金枕/猫山王；taste_tags 逗号分隔如偏甜,气味适中。"""
    tags = [t.strip() for t in taste_tags.split(",") if t.strip()] if taste_tags else None
    return _dump(
        execute(
            "search_products",
            {
                "variety": variety or None,
                "price_min": price_min or None,
                "price_max": price_max if price_max < 9999 else None,
                "taste_tags": tags,
            },
        )
    )


@tool
def get_product_detail(product_id: str) -> str:
    """获取商品详情，含价格、库存、关联批次摘要。"""
    return _dump(execute("get_product_detail", {"product_id": product_id}))


@tool
def get_purchase_link(product_id: str, channel: str = "web") -> str:
    """获取商品购买链接。"""
    return _dump(execute("get_purchase_link", {"product_id": product_id, "channel": channel}))


@tool
def search_knowledge(query: str) -> str:
    """检索榴莲百科：品种对比、保存、开果、售后规则、批次码说明等。"""
    return _dump(execute("search_knowledge", {"query": query}))


@tool
def get_order_detail(order_id: str) -> str:
    """查询当前用户本人的订单详情，用于售后。"""
    return _dump(execute("get_order_detail", {"order_id": order_id}))


@tool
def after_sale_triage(message: str, order_id: str = "") -> str:
    """榴莲售后分诊：对坏果、过生、过熟、物流延迟、重量不足、预售发货、退款赔付等问题分类，命中规则知识库，检查缺失凭证，输出优先级、处理建议、客服话术、是否转人工。"""
    from src.aftersale.triage import triage_after_sale as run_triage

    triage = run_triage(message, order_id=order_id or None)
    return json.dumps(
        {"success": True, "data": triage.model_dump(), "source": "after_sale_rules"},
        ensure_ascii=False,
    )


ALL_TOOLS = [
    query_trace_code,
    search_products,
    get_product_detail,
    get_purchase_link,
    search_knowledge,
    get_order_detail,
    after_sale_triage,
]

TOOL_NAME_MAP = {t.name: t for t in ALL_TOOLS}


def invoke_tool(name: str, args: dict, user_id: str | None = None) -> str:
    """按名称执行工具，返回 JSON 字符串。

    get_order_detail 强制注入服务端 user_id，防止模型在参数中伪造用户身份越权查单。
    未知工具名返回 success=false 的 JSON。
    """
    if name == "get_order_detail":
        return _dump(
            execute(
                "get_order_detail",
                {"order_id": args.get("order_id", ""), "user_id": user_id},
            )
        )
    tool_fn = TOOL_NAME_MAP.get(name)
    if tool_fn:
        return tool_fn.invoke(args)
    return json.dumps({"success": False, "error_code": "UNKNOWN_TOOL"}, ensure_ascii=False)
