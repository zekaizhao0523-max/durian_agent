from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """LangGraph 图内节点间传递的可变状态。

    用户身份（user_id）和会话（session_id）不放在此处，而是通过 invoke 的
    config["configurable"] 注入，见 graph/context.py。
    """

    messages: Annotated[list, add_messages]  # 多轮对话消息（System/Human/AI/Tool）
    trace_code: str | None  # 用户提供的批次溯源码
    shown_trace_tip: bool  # 是否已展示「一批一品类一码」提示
    tool_results: list[dict[str, Any]]  # 本轮工具调用记录
    cards: list[dict[str, Any]]  # 前端结构化卡片（format_node 填充）
    conclusion: str | None  # 结论摘要
    reasons: list[str]  # 理由列表
    next_action: str | None  # 建议的下一步操作
    intent: str | None  # 业务意图字符串
    reply_text: str  # 最终回复正文
    after_sale: dict[str, Any] | None  # 售后分诊结构化结果
