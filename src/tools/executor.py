"""工具执行入口：按名称分发到当前配置的 ToolAdapter。"""

from __future__ import annotations

from typing import Any

from src.models.schemas import ToolResult
from src.tools.adapters.factory import get_tool_adapter

_adapter = get_tool_adapter()


def execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
    """按工具名调用业务工具，返回统一的 ToolResult。

    LangGraph 节点、规则编排器、图内 invoke_tool 均通过此函数访问数据，
    避免上层直接依赖 mock 或 HTTP 实现。

    Args:
        tool_name: 工具标识，如 search_products、query_trace_code。
        params: 工具参数字典，字段因工具而异。

    Returns:
        包含 success、data、error_code、latency_ms 的标准结果。
    """
    return _adapter.execute(tool_name, params)
