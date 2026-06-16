"""LangGraph invoke 静态上下文（configurable）读取工具。"""

from __future__ import annotations

from langchain_core.runnables.config import RunnableConfig


def graph_context(config: RunnableConfig | None) -> dict:
    """读取 invoke 时传入的 configurable 字典。

    典型键：user_id、session_id。节点通过此函数获取服务端注入的上下文，
    避免将用户身份放入 AgentState 供模型可见或篡改。
    """
    if not config:
        return {}
    return dict(config.get("configurable") or {})


def user_id_from_config(config: RunnableConfig | None) -> str | None:
    """从 configurable 提取当前请求的用户 ID，用于订单查询权限校验。"""
    value = graph_context(config).get("user_id")
    return str(value) if value else None


def session_id_from_config(config: RunnableConfig | None) -> str | None:
    """从 configurable 提取当前会话 ID（图内节点较少直接使用）。"""
    value = graph_context(config).get("session_id")
    return str(value) if value else None
