from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from src.config.settings import effective_agent_mode, get_settings
from src.models.schemas import ChatRequest, ChatResponse, TtsRequest
from src.orchestrator.orchestrator import orchestrator
from src.services.tts import synthesize_speech
from src.storage.connection import database_label
from src.storage.db import (
    clear_user_long_term_memory,
    delete_all_user_sessions,
    delete_session,
    get_messages,
    get_stats,
    get_user_profile,
    list_user_sessions,
    load_session,
)
from src.storage.memory import build_long_term_context

router = APIRouter()


@router.get("/app-config")
async def app_config() -> dict:
    """前端启动配置：默认用户名等。"""
    settings = get_settings()
    return {
        "default_user_id": settings.default_user_id,
        "service": "durian-agent",
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """异步聊天接口：返回完整 ChatResponse。"""
    return await orchestrator.handle(
        message=request.message,
        session_id=request.session_id,
        user_id=request.user_id,
        trace_code=request.trace_code,
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """SSE 聊天接口：先推增量文本，最后推完整响应对象。"""

    async def generate():
        async for event in orchestrator.stream(
            message=request.message,
            session_id=request.session_id,
            user_id=request.user_id,
            trace_code=request.trace_code,
        ):
            payload = dict(event)
            if payload.get("type") == "done" and "response" in payload:
                response = payload["response"]
                payload["response"] = json.loads(response.model_dump_json())
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/tts")
async def text_to_speech(request: TtsRequest) -> Response:
    """将 Agent 回复转为语音，供前端数字人播报。"""
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="文本不能为空")
    try:
        audio = await synthesize_speech(text, voice=request.voice or "zh-CN-XiaoxiaoNeural")
    except Exception:
        raise HTTPException(status_code=500, detail="语音合成失败，请稍后重试") from None
    if not audio:
        raise HTTPException(status_code=400, detail="没有可朗读的内容")
    return Response(content=audio, media_type="audio/mpeg")


@router.get("/users/{user_id}/profile")
async def user_profile(user_id: str) -> dict:
    """查看用户画像（调试接口，默认关闭内部 prompt 上下文）。"""
    settings = get_settings()
    profile = get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="用户画像不存在")
    payload: dict = {"user_id": user_id, "profile": profile}
    if settings.expose_debug_api:
        payload["long_term_context"] = build_long_term_context(user_id)
    return payload


@router.get("/users/{user_id}/sessions")
async def user_sessions(user_id: str, limit: int = 30) -> dict:
    """列出用户的历史对话会话（按最近更新排序）。"""
    items = list_user_sessions(user_id, limit=limit)
    return {"user_id": user_id, "items": items}


@router.delete("/sessions/{session_id}")
async def remove_session(session_id: str, user_id: str) -> dict:
    """删除单条历史对话（含消息与埋点）。"""
    if not delete_session(session_id, user_id):
        raise HTTPException(status_code=404, detail="会话不存在或无权删除")
    return {"deleted": True, "session_id": session_id}


@router.delete("/users/{user_id}/sessions")
async def remove_all_sessions(user_id: str) -> dict:
    """清空该用户的全部历史对话。"""
    count = delete_all_user_sessions(user_id)
    return {"deleted": count, "user_id": user_id}


@router.delete("/users/{user_id}/memory")
async def remove_user_memory(user_id: str) -> dict:
    """清空用户长期记忆：画像、批次体验、记住的事实。"""
    cleared = clear_user_long_term_memory(user_id)
    return {"cleared": True, "user_id": user_id, **cleared}


@router.get("/sessions/{session_id}/history")
async def session_history(session_id: str, user_id: str | None = None, limit: int = 50) -> dict:
    """返回会话历史，用于前端刷新后恢复上下文。"""
    ctx = load_session(session_id)
    if ctx and ctx.user_id and user_id and ctx.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问该会话")
    messages = get_messages(session_id, limit=limit)
    if not messages:
        raise HTTPException(status_code=404, detail="会话不存在或暂无历史")
    return {"session_id": session_id, "messages": messages}


@router.get("/trace/{trace_code}")
async def get_trace(trace_code: str) -> dict:
    """便捷溯源查询接口，绕过 Agent 直接调用工具层。"""
    from src.tools.executor import execute

    result = execute("query_trace_code", {"trace_code": trace_code})
    return result.model_dump()


@router.get("/products")
async def list_products_api() -> dict:
    from src.storage.db import list_products

    return {"items": list_products()}


@router.get("/knowledge")
async def knowledge_catalog() -> dict:
    """榴莲知识模块：小知识、品种对比、送礼、保存等结构化内容。"""
    from src.knowledge.data import get_knowledge_catalog

    return get_knowledge_catalog()


@router.get("/stats")
async def stats() -> dict:
    """运行统计；生产环境仅返回聚合数据。"""
    settings = get_settings()
    base = get_stats()
    if not settings.expose_debug_api:
        return {"sessions": base.get("sessions", 0), "messages": base.get("messages", 0)}
    return {
        **base,
        "database": database_label(),
        "tool_adapter": settings.tool_adapter,
        "agent_mode": effective_agent_mode(),
        "llm_enabled": settings.llm_enabled,
    }


@router.get("/health")
async def health() -> dict:
    """健康检查，不访问外部依赖。"""
    settings = get_settings()
    if not settings.expose_debug_api:
        return {"status": "ok", "service": "durian-agent"}
    base = get_stats()
    return {
        "status": "ok",
        "service": "durian-agent",
        "version": "0.4.0",
        "database": database_label(),
        "tool_adapter": settings.tool_adapter,
        "agent_mode": effective_agent_mode(),
        "llm_enabled": settings.llm_enabled,
        "trace_batches": base.get("trace_batches", 0),
        "products": base.get("products", 0),
        "orders": base.get("orders", 0),
    }
