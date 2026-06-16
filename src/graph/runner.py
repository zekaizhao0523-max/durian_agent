"""LangGraph 运行器：组装消息、invoke/ainvoke 图、流式输出与会话持久化。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.config.settings import Settings, get_settings
from src.graph.builder import build_graph
from src.graph.nodes import create_llm, format_node
from src.graph.tools import invoke_tool
from src.models.schemas import Card, ChatResponse, Intent, AfterSaleTriage
from src.services.analytics import track
from src.session.manager import session_manager
from src.storage.db import get_messages, save_message
from src.storage.memory import build_long_term_context, extract_memories_from_message, sync_slots_to_profile


def _graph_invoke_config(
    *,
    session_id: str,
    user_id: str | None,
    settings: Settings,
) -> dict[str, Any]:
    """构造 LangGraph invoke 的 config 参数。

    user_id / session_id 放在 configurable 中，不写入 AgentState。
    recursion_limit 限制 agent↔tools 最大循环次数。
    """
    return {
        "configurable": {
            "user_id": user_id,
            "session_id": session_id,
        },
        "recursion_limit": settings.graph_recursion_limit,
    }


class LangGraphRunner:
    """LangGraph 模式的运行器。

    负责把 HTTP 层输入转换为 LangGraph state，并在图执行完成后回写会话、
    埋点和长期记忆。对外仅提供异步 `handle` 与 `stream`。
    """

    def __init__(self) -> None:
        """加载系统提示词并编译 LangGraph（build_graph 结果缓存）。"""
        self._system_prompt = (
            Path(__file__).parent.parent.joinpath("prompts", "agent_system.txt").read_text(encoding="utf-8")
        )
        self._graph = build_graph()

    def _missing_key_response(self, session_id: str | None) -> ChatResponse:
        """未配置 API Key 时的统一提示。"""
        return ChatResponse(
            session_id=session_id or "unconfigured",
            reply_text=(
                "当前为 LangGraph 大模型模式，但未配置 OPENAI_API_KEY。\n"
                "请在项目根目录创建 .env 并填写：\n"
                "OPENAI_API_KEY=你的密钥\n"
                "OPENAI_BASE_URL=兼容接口地址（可选）\n"
                "OPENAI_MODEL=模型名称\n\n"
                "或设置 AGENT_MODE=rules 使用规则模式（无需 API Key）。"
            ),
            conclusion="需配置",
            next_action="配置 API Key",
        )

    def _prepare_turn(
        self,
        message: str,
        session_id: str | None,
        user_id: str | None,
        trace_code: str | None,
        *,
        mode: str,
    ) -> tuple[Any, dict[str, Any], Settings, dict[str, Any]] | ChatResponse:
        """加载会话、写入用户消息并构造 initial_state；缺 Key 时直接返回提示响应。"""
        settings = get_settings()
        if not settings.openai_api_key:
            return self._missing_key_response(session_id)

        ctx = session_manager.get_or_create(session_id, user_id)
        ctx.turn_count += 1
        if trace_code:
            ctx.slots.trace_code = trace_code.strip().upper()

        track(ctx.session_id, "consult_start", message_preview=message[:80], mode=mode)
        save_message(ctx.session_id, "user", message)

        user_content = message
        if trace_code:
            user_content += f"\n[用户提供了批次溯源码: {trace_code.strip().upper()}]"

        system_content = self._system_prompt
        ltm = build_long_term_context(user_id)
        if ltm:
            system_content += f"\n\n## 用户长期记忆（跨会话）\n{ltm}"

        messages = [SystemMessage(content=system_content)]
        messages.extend(self._load_history(ctx.session_id, settings.max_history_turns))
        messages.append(HumanMessage(content=user_content))

        initial_state = {
            "messages": messages,
            "trace_code": ctx.slots.trace_code,
            "shown_trace_tip": ctx.shown_trace_tip,
            "tool_results": [],
            "cards": [],
            "conclusion": None,
            "reasons": [],
            "next_action": None,
            "intent": None,
            "reply_text": "",
            "after_sale": None,
        }
        invoke_config = _graph_invoke_config(
            session_id=ctx.session_id,
            user_id=user_id,
            settings=settings,
        )
        return ctx, initial_state, settings, invoke_config

    def _finalize_turn(
        self,
        ctx: Any,
        message: str,
        user_id: str | None,
        final_state: dict[str, Any],
        *,
        mode: str,
    ) -> ChatResponse:
        """根据图终态写库、同步画像并返回 ChatResponse。"""
        cards = [Card.model_validate(c) for c in final_state.get("cards", [])]
        intent_str = final_state.get("intent")
        intent = None
        if intent_str:
            try:
                intent = Intent(intent_str)
            except ValueError:
                intent = None

        if intent:
            ctx.current_intent = intent
        if final_state.get("shown_trace_tip"):
            ctx.shown_trace_tip = True

        product_ids = [
            c.payload.get("product_id")
            for c in cards
            if c.type.value == "product_recommend" and c.payload.get("product_id")
        ]
        if product_ids:
            ctx.recommended_products = product_ids

        after_sale_data = final_state.get("after_sale")
        after_sale = AfterSaleTriage.model_validate(after_sale_data) if after_sale_data else None

        response = ChatResponse(
            session_id=ctx.session_id,
            reply_text=final_state.get("reply_text", ""),
            conclusion=final_state.get("conclusion"),
            reasons=final_state.get("reasons", []),
            next_action=final_state.get("next_action"),
            cards=cards,
            intent=intent,
            after_sale=after_sale,
        )

        save_message(
            ctx.session_id,
            "assistant",
            response.reply_text,
            intent=intent.value if intent else None,
            cards=[c.model_dump() for c in cards],
        )
        track(
            ctx.session_id,
            "consult_end",
            intent=intent.value if intent else None,
            conclusion=response.conclusion,
            card_count=len(cards),
            mode=mode,
        )
        if intent == Intent.TRACE_QUERY and ctx.slots.trace_code:
            track(ctx.session_id, "trace_query", trace_code=ctx.slots.trace_code, conclusion=response.conclusion)
        if cards and any(c.type.value == "product_recommend" for c in cards):
            track(ctx.session_id, "product_expose", count=len(cards))

        sync_slots_to_profile(user_id, ctx.slots)
        extract_memories_from_message(user_id, message, ctx.slots)

        session_manager.save(ctx)
        return response

    async def handle(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        trace_code: str | None = None,
    ) -> ChatResponse:
        """异步执行完整对话：ainvoke 图并返回 ChatResponse。"""
        prepared = await asyncio.to_thread(
            self._prepare_turn,
            message,
            session_id,
            user_id,
            trace_code,
            mode="langgraph",
        )
        if isinstance(prepared, ChatResponse):
            return prepared
        ctx, initial_state, _settings, invoke_config = prepared
        final_state = await self._graph.ainvoke(initial_state, config=invoke_config)
        return await asyncio.to_thread(
            self._finalize_turn,
            ctx,
            message,
            user_id,
            final_state,
            mode="langgraph",
        )

    async def stream(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        trace_code: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """异步流式对话：astream LLM token，供 SSE 接口使用。"""
        prepared = await asyncio.to_thread(
            self._prepare_turn,
            message,
            session_id,
            user_id,
            trace_code,
            mode="langgraph_stream",
        )
        if isinstance(prepared, ChatResponse):
            async for event in _stream_response(prepared):
                yield event
            return

        ctx, initial_state, settings, _invoke_config = prepared
        messages = list(initial_state["messages"])
        tool_results: list[dict[str, Any]] = []
        streamed_text = ""
        llm = create_llm()

        for _ in range(settings.graph_recursion_limit):
            full_chunk = None

            async for chunk in llm.astream(messages):
                full_chunk = chunk if full_chunk is None else full_chunk + chunk
                piece = _content_to_text(chunk.content)
                if piece and not getattr(chunk, "tool_call_chunks", None):
                    streamed_text += piece
                    yield {"type": "text", "content": piece}

            if full_chunk is None:
                break

            ai_message = _chunk_to_ai_message(full_chunk)
            messages.append(ai_message)
            tool_calls = getattr(ai_message, "tool_calls", []) or []
            if not tool_calls:
                break

            for call in tool_calls:
                name = call["name"]
                args = call.get("args", {})
                content = await asyncio.to_thread(invoke_tool, name, args, user_id)
                tool_results.append({"name": name, "args": args, "result": content})
                messages.append(ToolMessage(content=content, tool_call_id=call["id"]))

        final_state = {
            "messages": messages,
            "trace_code": ctx.slots.trace_code,
            "shown_trace_tip": ctx.shown_trace_tip,
            "tool_results": tool_results,
            "cards": [],
            "conclusion": None,
            "reasons": [],
            "next_action": None,
            "intent": None,
            "reply_text": "",
            "after_sale": None,
        }
        formatted = format_node(final_state)

        reply_text = formatted.get("reply_text", "")
        if reply_text and not streamed_text:
            async for event in _stream_text(reply_text):
                yield event

        cards = [Card.model_validate(c) for c in formatted.get("cards", [])]
        intent_str = formatted.get("intent")
        intent = None
        if intent_str:
            try:
                intent = Intent(intent_str)
            except ValueError:
                intent = None

        if intent:
            ctx.current_intent = intent
        if formatted.get("shown_trace_tip"):
            ctx.shown_trace_tip = True

        product_ids = [
            c.payload.get("product_id")
            for c in cards
            if c.type.value == "product_recommend" and c.payload.get("product_id")
        ]
        if product_ids:
            ctx.recommended_products = product_ids

        after_sale_data = formatted.get("after_sale")
        after_sale = AfterSaleTriage.model_validate(after_sale_data) if after_sale_data else None

        response = ChatResponse(
            session_id=ctx.session_id,
            reply_text=reply_text,
            conclusion=formatted.get("conclusion"),
            reasons=formatted.get("reasons", []),
            next_action=formatted.get("next_action"),
            cards=cards,
            intent=intent,
            after_sale=after_sale,
        )

        await asyncio.to_thread(
            save_message,
            ctx.session_id,
            "assistant",
            response.reply_text,
            intent.value if intent else None,
            [c.model_dump() for c in cards],
        )
        await asyncio.to_thread(
            lambda: track(
                ctx.session_id,
                "consult_end",
                intent=intent.value if intent else None,
                conclusion=response.conclusion,
                card_count=len(cards),
                mode="langgraph_stream",
            )
        )
        if intent == Intent.TRACE_QUERY and ctx.slots.trace_code:
            await asyncio.to_thread(
                lambda: track(
                    ctx.session_id,
                    "trace_query",
                    trace_code=ctx.slots.trace_code,
                    conclusion=response.conclusion,
                )
            )
        if cards and any(c.type.value == "product_recommend" for c in cards):
            await asyncio.to_thread(
                lambda: track(ctx.session_id, "product_expose", count=len(cards))
            )

        await asyncio.to_thread(sync_slots_to_profile, user_id, ctx.slots)
        await asyncio.to_thread(extract_memories_from_message, user_id, message, ctx.slots)
        await asyncio.to_thread(session_manager.save, ctx)
        yield {"type": "done", "response": response}

    def _load_history(self, session_id: str, limit: int) -> list:
        """从数据库加载会话历史，转为 LangChain HumanMessage / AIMessage 列表。

        排除本轮刚写入的用户消息，避免与当前 HumanMessage 重复。
        """
        history = get_messages(session_id, limit=limit * 2)
        if not history:
            return []
        pairs = history[:-1] if history and history[-1]["role"] == "user" else history
        lc_messages = []
        for item in pairs:
            if item["role"] == "user":
                lc_messages.append(HumanMessage(content=item["content"]))
            else:
                lc_messages.append(AIMessage(content=item["content"]))
        return lc_messages[-limit * 2 :]


def _content_to_text(content: Any) -> str:
    """将 LLM 流式 chunk 的 content（str 或多模态 list）统一提取为纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return ""


def _chunk_to_ai_message(chunk: Any) -> AIMessage:
    """将流式累积的 chunk 转为 AIMessage，保留 content 与 tool_calls。"""
    if hasattr(chunk, "to_message"):
        message = chunk.to_message()
        if isinstance(message, AIMessage):
            return message
    return AIMessage(
        content=getattr(chunk, "content", "") or "",
        tool_calls=getattr(chunk, "tool_calls", []) or [],
    )


async def _stream_text(text: str) -> AsyncIterator[dict[str, str]]:
    """将完整文本按固定长度切片，生成 type=text 的 SSE 事件序列。"""
    chunk_size = 6
    for i in range(0, len(text), chunk_size):
        yield {"type": "text", "content": text[i : i + chunk_size]}


async def _stream_response(response: ChatResponse) -> AsyncIterator[dict[str, Any]]:
    """将完整 ChatResponse 转为异步 SSE 事件序列。"""
    async for event in _stream_text(response.reply_text):
        yield event
    yield {"type": "done", "response": response}


langgraph_runner = LangGraphRunner()
