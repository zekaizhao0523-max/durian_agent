"""Mock 适配器：默认实现，直接调用本地 PostgreSQL 演示数据。"""

from __future__ import annotations

from src.models.schemas import ToolResult
from src.tools.adapters.base import ToolAdapter
from src.tools.mall import get_product_detail, get_purchase_link, search_products
from src.tools.order import get_order_detail
from src.tools.trace import query_trace_code


class MockToolAdapter(ToolAdapter):
    """本地演示适配器。

    将 ToolAdapter 协议转发到 trace.py / mall.py / order.py，
    数据来源于 storage/seed_data 写入的 PostgreSQL 表。
    配置 TOOL_ADAPTER=mock（默认）时使用。
    """

    def query_trace_code(self, trace_code: str) -> ToolResult:
        """转发至 trace.query_trace_code。"""
        return query_trace_code(trace_code)

    def search_products(
        self,
        variety: str | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        taste_tags: list[str] | None = None,
    ) -> ToolResult:
        """转发至 mall.search_products。"""
        return search_products(variety, price_min, price_max, taste_tags)

    def get_product_detail(self, product_id: str) -> ToolResult:
        """转发至 mall.get_product_detail。"""
        return get_product_detail(product_id)

    def get_purchase_link(self, product_id: str, channel: str = "web") -> ToolResult:
        """转发至 mall.get_purchase_link。"""
        return get_purchase_link(product_id, channel)

    def get_order_detail(self, order_id: str, user_id: str | None = None) -> ToolResult:
        """转发至 order.get_order_detail。"""
        return get_order_detail(order_id, user_id)
