from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from src.config.settings import effective_agent_mode
from src.graph.runner import langgraph_runner
from src.guardrails.guard import guard_user_message, sanitize_reply
from src.models.schemas import ChatResponse, Intent
from src.orchestrator.rule_orchestrator import rule_orchestrator
from src.session.manager import session_manager
from src.aftersale.triage import enrich_after_sale_response
from src.router.intent_router import route_intent


class Orchestrator:
    """Agent 的统一门面。

    上层 API 不关心当前运行的是 LangGraph 还是规则引擎；这里根据配置
    选择实际编排器，并保证普通响应和流式响应拥有一致的对外结构。
    """

    def _apply_after_sale_enrichment(
        self,
        message: str,
        response: ChatResponse,
        user_id: str | None,
    ) -> ChatResponse:
        if response.after_sale is not None:
            if response.intent is None:
                response.intent = Intent.AFTER_SALE
            return response

        route = route_intent(message)
        is_after_sale = response.intent == Intent.AFTER_SALE or route.intent == Intent.AFTER_SALE
        if not is_after_sale:
            return response
        ctx = session_manager.get_or_create(response.session_id, user_id)
        order_id = ctx.slots.order_id or route.slots.order_id
        order_status = None
        if order_id:
            from src.tools.executor import execute

            detail = execute("get_order_detail", {"order_id": order_id, "user_id": user_id})
            if detail.success:
                order_status = detail.data.get("status")
        response = enrich_after_sale_response(
            message, response, order_id=order_id, order_status=order_status
        )
        if response.intent is None and route.intent == Intent.AFTER_SALE:
            response.intent = Intent.AFTER_SALE
        response.reply_text = sanitize_reply(response.reply_text)
        return response

    async def handle(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        trace_code: str | None = None,
    ) -> ChatResponse:
        """返回一次完整的对话结果。"""
        blocked = guard_user_message(message)
        if blocked:
            return ChatResponse(
                session_id=session_id or "blocked",
                reply_text=blocked,
                conclusion="无法处理",
                next_action="咨询榴莲相关问题",
            )

        try:
            mode = effective_agent_mode()
            if mode == "langgraph":
                response = await langgraph_runner.handle(message, session_id, user_id, trace_code)
            else:
                response = await asyncio.to_thread(
                    rule_orchestrator.handle,
                    message,
                    session_id,
                    user_id,
                    trace_code,
                )
        except PermissionError:
            return ChatResponse(
                session_id=session_id or "denied",
                reply_text="当前会话和账号对不上，刷新一下页面再试试哈～",
                conclusion="无权访问",
                next_action="刷新页面",
            )

        response.reply_text = sanitize_reply(response.reply_text)
        return self._apply_after_sale_enrichment(message, response, user_id)

    async def stream(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        trace_code: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """返回 SSE 可消费的事件流。

        事件约定：
        - text：增量文本片段
        - done：最终 ChatResponse，用于前端渲染卡片、结论和会话 id
        """
        blocked = guard_user_message(message)
        if blocked:
            response = ChatResponse(
                session_id=session_id or "blocked",
                reply_text=blocked,
                conclusion="无法处理",
                next_action="咨询榴莲相关问题",
            )
            chunk_size = 8
            for i in range(0, len(response.reply_text), chunk_size):
                yield {"type": "text", "content": response.reply_text[i : i + chunk_size]}
            yield {"type": "done", "response": response}
            return

        try:
            mode = effective_agent_mode()
            if mode == "langgraph":
                events = langgraph_runner.stream(message, session_id, user_id, trace_code)
            else:
                response = await asyncio.to_thread(
                    rule_orchestrator.handle,
                    message,
                    session_id,
                    user_id,
                    trace_code,
                )
                response.reply_text = sanitize_reply(response.reply_text)

                async def _rule_events() -> AsyncIterator[dict[str, Any]]:
                    chunk_size = 6
                    for i in range(0, len(response.reply_text), chunk_size):
                        yield {"type": "text", "content": response.reply_text[i : i + chunk_size]}
                    yield {"type": "done", "response": response}

                events = _rule_events()

            async for event in events:
                if event.get("type") == "done" and "response" in event:
                    resp = event["response"]
                    resp.reply_text = sanitize_reply(resp.reply_text)
                    event["response"] = self._apply_after_sale_enrichment(
                        message, resp, user_id
                    )
                yield event
        except PermissionError:
            response = ChatResponse(
                session_id=session_id or "denied",
                reply_text="当前会话和账号对不上，刷新一下页面再试试哈～",
                conclusion="无权访问",
                next_action="刷新页面",
            )
            yield {"type": "done", "response": response}


orchestrator = Orchestrator()
