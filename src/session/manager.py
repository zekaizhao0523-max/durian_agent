from __future__ import annotations

import uuid

from src.models.schemas import SessionContext
from src.storage.db import load_session, save_session


class SessionManager:
    """会话上下文的轻量门面。

    它负责把 API 传入的 session_id 映射到持久化的 SessionContext；
    找不到时创建新会话，避免编排层关心存储细节。
    """

    def get_or_create(self, session_id: str | None, user_id: str | None = None) -> SessionContext:
        """优先加载已有会话；没有 session_id 或找不到时创建新会话。"""
        if session_id:
            ctx = load_session(session_id)
            if ctx:
                if user_id and ctx.user_id and ctx.user_id != user_id:
                    raise PermissionError("会话与用户不匹配")
                if user_id and not ctx.user_id:
                    ctx.user_id = user_id
                return ctx

        new_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        ctx = SessionContext(session_id=new_id, user_id=user_id)
        save_session(ctx)
        return ctx

    def save(self, ctx: SessionContext) -> None:
        """保存最新会话槽位、意图和推荐状态。"""
        save_session(ctx)


session_manager = SessionManager()
