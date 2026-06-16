"""工具适配器工厂：按配置实例化 Mock 或 HTTP+回退 实现。"""

from __future__ import annotations

from collections.abc import Callable

from src.config.settings import get_settings
from src.models.schemas import ToolResult
from src.tools.adapters.base import ToolAdapter
from src.tools.adapters.http import HttpToolAdapter
from src.tools.adapters.mock import MockToolAdapter


class FallbackToolAdapter(ToolAdapter):
    """HTTP 优先、Mock 回退的复合适配器。

    当 TOOL_ADAPTER=http 时使用：若对应 base_url 未配置或返回 NOT_CONFIGURED，
    自动改用本地 PostgreSQL 演示数据，保证开发环境始终可跑通。
    真实 HTTP 业务错误（HTTP_ERROR）不会静默回退，便于排查对接问题。
    """

    def __init__(self) -> None:
        """初始化 HTTP 与 Mock 两个子适配器及全局配置。"""
        self.http = HttpToolAdapter()
        self.mock = MockToolAdapter()
        self.settings = get_settings()

    def _pick(self, http_result: ToolResult, mock_call: Callable[[], ToolResult]) -> ToolResult:
        """在 HTTP 结果与 Mock 调用之间选择返回值。

        HTTP 成功 → 用 HTTP；仅 NOT_CONFIGURED → 回退 Mock；其他错误 → 原样返回。
        """
        if http_result.success:
            return http_result
        if http_result.error_code == "NOT_CONFIGURED":
            return mock_call()
        return http_result

    def query_trace_code(self, trace_code: str) -> ToolResult:
        """未配置 TRACE_API_BASE_URL 时直接用 Mock。"""
        if not self.settings.trace_api_base_url:
            return self.mock.query_trace_code(trace_code)
        return self._pick(
            self.http.query_trace_code(trace_code),
            lambda: self.mock.query_trace_code(trace_code),
        )

    def search_products(
        self,
        variety: str | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        taste_tags: list[str] | None = None,
    ) -> ToolResult:
        """未配置 MALL_API_BASE_URL 时直接用 Mock。"""
        if not self.settings.mall_api_base_url:
            return self.mock.search_products(variety, price_min, price_max, taste_tags)
        return self._pick(
            self.http.search_products(variety, price_min, price_max, taste_tags),
            lambda: self.mock.search_products(variety, price_min, price_max, taste_tags),
        )

    def get_product_detail(self, product_id: str) -> ToolResult:
        """未配置 MALL_API_BASE_URL 时直接用 Mock。"""
        if not self.settings.mall_api_base_url:
            return self.mock.get_product_detail(product_id)
        return self._pick(
            self.http.get_product_detail(product_id),
            lambda: self.mock.get_product_detail(product_id),
        )

    def get_purchase_link(self, product_id: str, channel: str = "web") -> ToolResult:
        """未配置 MALL_API_BASE_URL 时直接用 Mock。"""
        if not self.settings.mall_api_base_url:
            return self.mock.get_purchase_link(product_id, channel)
        return self._pick(
            self.http.get_purchase_link(product_id, channel),
            lambda: self.mock.get_purchase_link(product_id, channel),
        )

    def get_order_detail(self, order_id: str, user_id: str | None = None) -> ToolResult:
        """未配置 ORDER_API_BASE_URL 时直接用 Mock。"""
        if not self.settings.order_api_base_url:
            return self.mock.get_order_detail(order_id, user_id)
        return self._pick(
            self.http.get_order_detail(order_id, user_id),
            lambda: self.mock.get_order_detail(order_id, user_id),
        )


def get_tool_adapter() -> ToolAdapter:
    """根据 TOOL_ADAPTER 配置创建适配器实例。

    Returns:
        mock → MockToolAdapter（纯本地 PostgreSQL）；
        http → FallbackToolAdapter（HTTP 优先，未配置则回退 Mock）。
    """
    settings = get_settings()
    if settings.tool_adapter == "http":
        return FallbackToolAdapter()
    return MockToolAdapter()
