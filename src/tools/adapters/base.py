"""工具适配器基类：定义业务工具协议与按名称分发的 execute 入口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from src.models.schemas import ToolResult


class ToolAdapter(ABC):
    """业务工具的适配器协议。

    Agent 只依赖这些抽象方法，不直接关心数据来自本地 mock、HTTP 服务，
    还是以后替换成 RPC/数据库查询。
    """

    @abstractmethod
    def query_trace_code(self, trace_code: str) -> ToolResult:
        """查询批次溯源码。"""

    @abstractmethod
    def search_products(
        self,
        variety: str | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        taste_tags: list[str] | None = None,
    ) -> ToolResult:
        """搜索在售商品并排序。"""

    @abstractmethod
    def get_product_detail(self, product_id: str) -> ToolResult:
        """获取商品详情。"""

    @abstractmethod
    def get_purchase_link(self, product_id: str, channel: str = "web") -> ToolResult:
        """获取购买链接。"""

    @abstractmethod
    def get_order_detail(self, order_id: str, user_id: str | None = None) -> ToolResult:
        """查询订单（需 user_id 权限校验）。"""

    def search_knowledge(self, query: str) -> ToolResult:
        """检索榴莲百科 FAQ。

        默认走本地 knowledge.search；HTTP 适配器可按需覆盖为远程知识服务。
        """
        from src.knowledge.search import search_knowledge

        chunks = search_knowledge(query)
        return ToolResult(success=True, source="knowledge_service", data={"chunks": chunks})

    def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """按工具名统一分发，供 executor.execute 与 LangGraph 共用。

        支持的工具名：query_trace_code、search_products、get_product_detail、
        get_purchase_link、search_knowledge、get_order_detail。
        after_sale_triage 由 graph/tools.py 直接调用售后模块，不经此分发。

        Args:
            tool_name: 工具标识字符串。
            params: 各工具所需参数字典。

        Returns:
            成功或失败的 ToolResult；未知工具返回 UNKNOWN_TOOL。
        """
        mapping: dict[str, Callable[[], ToolResult]] = {
            "query_trace_code": lambda: self.query_trace_code(params["trace_code"]),
            "search_products": lambda: self.search_products(
                variety=params.get("variety"),
                price_min=params.get("price_min"),
                price_max=params.get("price_max"),
                taste_tags=params.get("taste_tags"),
            ),
            "get_product_detail": lambda: self.get_product_detail(params["product_id"]),
            "get_purchase_link": lambda: self.get_purchase_link(
                params["product_id"], params.get("channel", "web")
            ),
            "search_knowledge": lambda: self.search_knowledge(params["query"]),
            "get_order_detail": lambda: self.get_order_detail(
                params["order_id"], params.get("user_id")
            ),
        }
        handler = mapping.get(tool_name)
        if not handler:
            return ToolResult(success=False, source="tool_adapter", error_code="UNKNOWN_TOOL")
        try:
            return handler()
        except KeyError as exc:
            return ToolResult(
                success=False, source="tool_adapter", error_code=f"MISSING_PARAM:{exc}"
            )
