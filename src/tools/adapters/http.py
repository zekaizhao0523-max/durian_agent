"""HTTP 适配器：对接真实溯源/商城/订单 API 的预留实现。"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from src.config.settings import get_settings
from src.models.schemas import ToolResult
from src.tools.adapters.base import ToolAdapter

logger = logging.getLogger(__name__)


class HttpToolAdapter(ToolAdapter):
    """真实外部 API 适配器。

    通过 httpx 调用配置的 base_url；未配置对应 URL 时返回 NOT_CONFIGURED，
    由 FallbackToolAdapter 决定是否回退到 Mock。
    """

    def __init__(self) -> None:
        """读取 settings 中的各服务 base_url，设置请求超时。"""
        self.settings = get_settings()
        self.timeout = 10.0

    def _request(self, base_url: str, path: str, params: dict[str, Any] | None = None) -> ToolResult:
        """发起 GET 请求并将 JSON 响应包装为 ToolResult。

        Args:
            base_url: 服务根地址，为空则直接返回 NOT_CONFIGURED。
            path: 接口路径，如 /trace/TR20260609002。
            params: 查询参数字典。

        Returns:
            成功时 data 为响应 JSON；失败时 error_code 为 NOT_CONFIGURED 或 HTTP_ERROR。
        """
        start = time.perf_counter()
        if not base_url:
            return ToolResult(
                success=False,
                source="http_adapter",
                error_code="NOT_CONFIGURED",
                latency_ms=int((time.perf_counter() - start) * 1000),
            )
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{base_url.rstrip('/')}{path}", params=params)
                resp.raise_for_status()
                return ToolResult(
                    success=True,
                    source="http_adapter",
                    data=resp.json(),
                    latency_ms=int((time.perf_counter() - start) * 1000),
                )
        except Exception as exc:
            logger.warning("HTTP tool call failed: %s", exc)
            return ToolResult(
                success=False,
                source="http_adapter",
                error_code="HTTP_ERROR",
                data={"detail": str(exc)},
                latency_ms=int((time.perf_counter() - start) * 1000),
            )

    def query_trace_code(self, trace_code: str) -> ToolResult:
        """GET {TRACE_API_BASE_URL}/trace/{trace_code}。"""
        return self._request(
            self.settings.trace_api_base_url,
            f"/trace/{trace_code}",
        )

    def search_products(
        self,
        variety: str | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        taste_tags: list[str] | None = None,
    ) -> ToolResult:
        """GET {MALL_API_BASE_URL}/products/search。"""
        return self._request(
            self.settings.mall_api_base_url,
            "/products/search",
            {
                "variety": variety,
                "price_min": price_min,
                "price_max": price_max,
                "taste_tags": ",".join(taste_tags or []),
            },
        )

    def get_product_detail(self, product_id: str) -> ToolResult:
        """GET {MALL_API_BASE_URL}/products/{product_id}。"""
        return self._request(self.settings.mall_api_base_url, f"/products/{product_id}")

    def get_purchase_link(self, product_id: str, channel: str = "web") -> ToolResult:
        """GET {MALL_API_BASE_URL}/products/{product_id}/purchase-link。"""
        return self._request(
            self.settings.mall_api_base_url,
            f"/products/{product_id}/purchase-link",
            {"channel": channel},
        )

    def get_order_detail(self, order_id: str, user_id: str | None = None) -> ToolResult:
        """GET {ORDER_API_BASE_URL}/orders/{order_id}，附带 user_id 查询参数。"""
        return self._request(
            self.settings.order_api_base_url,
            f"/orders/{order_id}",
            {"user_id": user_id},
        )
