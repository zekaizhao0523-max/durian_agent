"""LangGraph 节点实现：路由、业务分支、LLM 循环与响应格式化。"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables.config import RunnableConfig
from langchain_openai import ChatOpenAI

from src.config.settings import get_settings
from src.graph.cards_from_tools import build_cards_from_tool_results, infer_intent
from src.graph.context import user_id_from_config
from src.graph.state import AgentState
from src.graph.tools import ALL_TOOLS, invoke_tool
from src.guardrails.guard import ensure_trace_tip, sanitize_reply
from src.models.schemas import AfterSaleTriage, Intent
from src.aftersale.triage import format_after_sale_reply
from src.router.intent_router import route_intent

CONCLUSION_RE = re.compile(r"【结论】\s*(.+?)(?:\n|$)")
RECOMMEND_RE = re.compile(r"【推荐】\s*(.+?)(?:\n|$)")
NEXT_ACTION_RE = re.compile(r"【下一步】\s*\n?\s*[-·]?\s*(.+?)(?:\n|$)")
REASONS_RE = re.compile(r"【理由】\s*\n((?:\s*\d+\.\s*.+\n?)+)")


def create_llm():
    """创建绑定业务工具（ALL_TOOLS）的 ChatOpenAI 实例。

    模型、API Key、Base URL 从 settings 读取；temperature 固定为 0.3。
    """
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.3,
    )
    return llm.bind_tools(ALL_TOOLS)


def _latest_user_message(state: AgentState) -> str:
    """从 messages 中倒序取最近一条用户（Human）消息文本。"""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    return ""


def _parse_tool_payload(raw: str) -> dict[str, Any]:
    """解析工具返回的 JSON 字符串，仅提取 success=true 时的 data 字段。"""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not payload.get("success"):
        return {}
    return payload.get("data", {})


def _append_tool_result(
    state: AgentState,
    name: str,
    args: dict[str, Any],
    *,
    config: RunnableConfig | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """调用工具并追加到 tool_results，返回（原始 JSON 结果, 更新后的列表）。"""
    content = invoke_tool(name, args, user_id_from_config(config))
    tool_results = list(state.get("tool_results", []))
    tool_results.append({"name": name, "args": args, "result": content})
    return content, tool_results


def router_node(state: AgentState) -> dict:
    """入口路由节点：识别本轮业务意图，写入 state.intent。

    若 state 中已有 trace_code，优先判定为验真意图。
    """
    message = _latest_user_message(state)
    if state.get("trace_code"):
        return {"intent": Intent.TRACE_QUERY.value}
    route = route_intent(message)
    return {"intent": route.intent.value}


def route_after_router(state: AgentState) -> Literal["recommend", "knowledge", "trace", "after_sale", "agent"]:
    """条件边：将细分意图映射到四个平级业务节点，其余走 LLM agent 循环。"""
    intent = state.get("intent")
    if intent in {Intent.CONSULT_BUDGET.value, Intent.CONSULT_EVALUATE.value, Intent.PURCHASE_INTENT.value}:
        return "recommend"
    if intent in {Intent.CONSULT_VARIETY.value, Intent.POST_PURCHASE.value}:
        return "knowledge"
    if intent == Intent.TRACE_QUERY.value:
        return "trace"
    if intent in {Intent.AFTER_SALE.value, Intent.HUMAN_HANDOFF.value}:
        return "after_sale"
    return "agent"


def recommend_node(state: AgentState) -> dict:
    """榴莲推荐节点：按槽位搜索商品，生成【推荐】格式回复与 tool_results。"""
    message = _latest_user_message(state)
    route = route_intent(message)
    args: dict[str, Any] = {}
    if route.slots.variety:
        args["variety"] = route.slots.variety
    if route.slots.budget:
        args["price_min"], args["price_max"] = route.slots.budget
    if route.slots.taste_tags:
        args["taste_tags"] = ",".join(route.slots.taste_tags)

    content, tool_results = _append_tool_result(state, "search_products", args)
    data = _parse_tool_payload(content)
    items = data.get("items", [])

    if items:
        top = items[0]
        reasons = top.get("recommend_reasons") or [f"综合推荐分 {top.get('recommend_score', '-')}"]
        reply = f"【推荐】{top['name']}（¥{top['price']}）\n\n【理由】\n"
        for idx, reason in enumerate(reasons[:5], 1):
            reply += f"{idx}. {reason}\n"
        reply += "\n【下一步】\n- 查看下方商品卡片"
        conclusion = top["name"]
    else:
        reply = "目前没有在售商品完全匹配你的条件，可以放宽预算、口味或品种限制，我再帮你综合推荐。"
        conclusion = "暂无合适商品"

    return {
        "messages": [AIMessage(content=reply)],
        "tool_results": tool_results,
        "intent": Intent.CONSULT_BUDGET.value,
        "conclusion": conclusion,
    }


def knowledge_node(state: AgentState) -> dict:
    """榴莲知识节点：检索 FAQ，返回百科内容与结论标题。"""
    message = _latest_user_message(state)
    content, tool_results = _append_tool_result(state, "search_knowledge", {"query": message})
    data = _parse_tool_payload(content)
    chunks = data.get("chunks", [])

    if chunks:
        chunk = chunks[0]
        reply = f"【结论】{chunk.get('title', '榴莲知识')}\n\n{chunk.get('content', '')}\n\n【下一步】\n- 继续补充预算或口味，我可以帮你选具体商品"
        conclusion = chunk.get("title")
    else:
        reply = "这个问题我暂时没有检索到明确知识。你可以换个问法，比如品种区别、保存方式或开果建议。"
        conclusion = "需补充问题"

    return {
        "messages": [AIMessage(content=reply)],
        "tool_results": tool_results,
        "intent": Intent.CONSULT_VARIETY.value,
        "conclusion": conclusion,
    }


def trace_node(state: AgentState) -> dict:
    """榴莲验真节点：查询批次溯源码，生成批次说明与是否可买结论。"""
    message = _latest_user_message(state)
    route = route_intent(message)
    trace_code = route.slots.trace_code or state.get("trace_code")
    if not trace_code:
        return {
            "messages": [AIMessage(content="请提供或扫描包装上的批次溯源码，我帮你查验这批货的来源信息。")],
            "intent": Intent.TRACE_QUERY.value,
            "conclusion": "需验批次",
            "next_action": "输入溯源码",
        }

    content, tool_results = _append_tool_result(state, "query_trace_code", {"trace_code": trace_code})
    data = _parse_tool_payload(content)
    if data.get("valid"):
        reply = (
            "【结论】可以买\n\n"
            f"【批次信息】\n· 品种：{data.get('variety')} {data.get('grade', '')}级\n"
            f"· 产地：{data.get('origin')}\n"
            f"· 采摘：{data.get('pick_date')} · 入库：{data.get('stock_in_date')}\n"
            f"· 成熟度区间：{data.get('ripeness_range')}\n\n"
            "【下一步】\n- 查看下方溯源卡片"
        )
        conclusion = "可以买"
    else:
        reply = f"未查询到有效批次信息（码：{trace_code}），请核对输入或联系官方客服人工核验。"
        conclusion = "不建议"

    return {
        "messages": [AIMessage(content=reply)],
        "tool_results": tool_results,
        "intent": Intent.TRACE_QUERY.value,
        "conclusion": conclusion,
    }


def after_sale_node(state: AgentState, config: RunnableConfig) -> dict:
    """售后咨询节点：可选查订单，执行 after_sale_triage 分诊并写入 after_sale。"""
    message = _latest_user_message(state)
    route = route_intent(message)
    tool_results = list(state.get("tool_results", []))

    if route.slots.order_id:
        _, tool_results = _append_tool_result(
            {**state, "tool_results": tool_results},
            "get_order_detail",
            {"order_id": route.slots.order_id},
            config=config,
        )

    triage_content, tool_results = _append_tool_result(
        {**state, "tool_results": tool_results},
        "after_sale_triage",
        {"message": message, "order_id": route.slots.order_id or ""},
    )
    data = _parse_tool_payload(triage_content)
    triage = AfterSaleTriage.model_validate(data) if data else None
    reply = format_after_sale_reply(triage) if triage else "请提供订单号并描述问题，我会按售后规则帮你处理。"

    return {
        "messages": [AIMessage(content=reply)],
        "tool_results": tool_results,
        "intent": Intent.AFTER_SALE.value,
        "after_sale": triage.model_dump() if triage else None,
    }


async def agent_node(state: AgentState) -> dict:
    """通用 LLM 节点：异步等待模型响应或 tool_calls。"""
    llm = create_llm()
    response = await llm.ainvoke(state["messages"])
    return {"messages": [response]}


def tools_node(state: AgentState, config: RunnableConfig) -> dict:
    """工具执行节点：执行 AIMessage 中的 tool_calls，追加 ToolMessage 与 tool_results。"""
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {}

    tool_results = list(state.get("tool_results", []))
    new_messages: list[ToolMessage] = []
    user_id = user_id_from_config(config)

    for call in last.tool_calls:
        name = call["name"]
        args = call.get("args", {})
        content = invoke_tool(name, args, user_id)
        tool_results.append({"name": name, "args": args, "result": content})
        new_messages.append(ToolMessage(content=content, tool_call_id=call["id"]))

    return {"messages": new_messages, "tool_results": tool_results}


def _parse_reasons(text: str) -> list[str]:
    """从【理由】段落解析编号列表，用于结构化响应 reasons 字段。"""
    match = REASONS_RE.search(text)
    if not match:
        return []
    block = match.group(1)
    return [line.strip().lstrip("1234567890.").strip() for line in block.splitlines() if line.strip()]


def _extract_after_sale_from_tools(tool_results: list) -> AfterSaleTriage | None:
    """从 tool_results 中解析 after_sale_triage 工具返回的结构化分诊对象。"""
    for record in reversed(tool_results):
        if record.get("name") != "after_sale_triage":
            continue
        raw = record.get("result", {})
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                continue
        data = raw.get("data") if isinstance(raw, dict) else None
        if data:
            return AfterSaleTriage.model_validate(data)
    return None


def format_node(state: AgentState) -> dict:
    """终态格式化节点：汇总 reply_text、卡片、意图、售后分诊与合规处理。

    从最后一条 AIMessage 与 tool_results 生成 API 所需的全部结构化字段。
    """
    last_ai = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            last_ai = msg
            break

    reply_text = str(last_ai.content) if last_ai and last_ai.content else "抱歉，我暂时无法回答，请稍后再试。"

    conclusion_match = CONCLUSION_RE.search(reply_text)
    recommend_match = RECOMMEND_RE.search(reply_text)
    next_match = NEXT_ACTION_RE.search(reply_text)
    if recommend_match:
        conclusion = recommend_match.group(1).strip()
    elif conclusion_match:
        conclusion = conclusion_match.group(1).strip()
    else:
        conclusion = None
    next_action = next_match.group(1).strip() if next_match else None
    reasons = _parse_reasons(reply_text)

    tool_results = state.get("tool_results", [])
    after_sale = _extract_after_sale_from_tools(tool_results)
    cards = build_cards_from_tool_results(tool_results)
    intent_str = infer_intent(tool_results) if tool_results else state.get("intent")
    if intent_str == Intent.CHITCHAT.value and state.get("intent"):
        intent_str = state.get("intent")

    if after_sale:
        reply_text = format_after_sale_reply(after_sale)
        conclusion = after_sale.problem_label
        next_action = "转人工客服" if after_sale.escalate_to_human else "补充凭证材料"
        reasons = after_sale.matched_rules
        intent_str = "after_sale"

    show_tip = not state.get("shown_trace_tip", False) and any(
        r.get("name") == "query_trace_code" for r in tool_results
    )
    if show_tip or "溯源" in reply_text or "批次" in reply_text:
        reply_text = ensure_trace_tip(reply_text, show_tip)

    reply_text = sanitize_reply(reply_text)

    return {
        "reply_text": reply_text,
        "conclusion": conclusion,
        "next_action": next_action,
        "reasons": reasons,
        "cards": [c.model_dump() for c in cards],
        "intent": intent_str,
        "shown_trace_tip": state.get("shown_trace_tip", False) or show_tip,
        "after_sale": after_sale.model_dump() if after_sale else None,
    }


def route_after_agent(state: AgentState) -> Literal["tools", "format"]:
    """条件边：AIMessage 含 tool_calls 则进入 tools，否则进入 format 结束循环。"""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "format"
