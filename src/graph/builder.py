from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from src.graph.nodes import (
    after_sale_node,
    agent_node,
    format_node,
    knowledge_node,
    recommend_node,
    route_after_agent,
    route_after_router,
    router_node,
    tools_node,
    trace_node,
)
from src.graph.state import AgentState


@lru_cache
def build_graph():
    """构建并编译 LangGraph 状态机。

    流程概要：
    1. START → route：识别用户意图
    2. 四个平级业务分支（推荐/知识/验真/售后）→ format → END
    3. 其他复杂场景 → agent ↔ tools 循环 → format → END

    agent 节点为异步实现，供 ainvoke 与 durian_demo 使用。
    """
    graph = StateGraph(AgentState)
    graph.add_node("route", router_node)
    graph.add_node("recommend", recommend_node)
    graph.add_node("knowledge", knowledge_node)
    graph.add_node("trace", trace_node)
    graph.add_node("after_sale", after_sale_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("format", format_node)

    graph.add_edge(START, "route")
    graph.add_conditional_edges(
        "route",
        route_after_router,
        {
            "recommend": "recommend",
            "knowledge": "knowledge",
            "trace": "trace",
            "after_sale": "after_sale",
            "agent": "agent",
        },
    )
    graph.add_edge("recommend", "format")
    graph.add_edge("knowledge", "format")
    graph.add_edge("trace", "format")
    graph.add_edge("after_sale", "format")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "format": "format"})
    graph.add_edge("tools", "agent")
    graph.add_edge("format", END)

    return graph.compile()
