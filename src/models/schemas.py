from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Intent(str, Enum):
    """Agent 支持的业务意图集合。"""

    CONSULT_VARIETY = "consult_variety"
    CONSULT_BUDGET = "consult_budget"
    CONSULT_EVALUATE = "consult_evaluate"
    TRACE_QUERY = "trace_query"
    PURCHASE_INTENT = "purchase_intent"
    AFTER_SALE = "after_sale"
    POST_PURCHASE = "post_purchase"
    CHITCHAT = "chitchat"
    HUMAN_HANDOFF = "human_handoff"


class SessionSlots(BaseModel):
    """会话中逐轮累积的业务槽位。"""

    budget: list[int] | None = None
    variety: str | None = None
    taste_tags: list[str] = Field(default_factory=list)
    trace_code: str | None = None
    batch_id: str | None = None
    order_id: str | None = None


class SessionContext(BaseModel):
    """短期会话状态，跨轮保存但通常不跨用户长期沉淀。"""

    session_id: str
    user_id: str | None = None
    turn_count: int = 0
    current_intent: Intent | None = None
    slots: SessionSlots = Field(default_factory=SessionSlots)
    shown_trace_tip: bool = False
    recommended_products: list[str] = Field(default_factory=list)
    unclear_count: int = 0


class ChatRequest(BaseModel):
    """聊天接口入参。"""

    message: str
    session_id: str | None = None
    user_id: str | None = None
    trace_code: str | None = None


class TtsRequest(BaseModel):
    """语音合成入参。"""

    text: str
    voice: str | None = None


class CardType(str, Enum):
    """前端可渲染的结构化卡片类型。"""

    TRACE_BATCH = "trace_batch"
    PRODUCT_RECOMMEND = "product_recommend"
    PURCHASE_LINK = "purchase_link"
    ORDER_INFO = "order_info"


class Card(BaseModel):
    """结构化卡片，payload 按 type 约定字段。"""

    type: CardType
    payload: dict[str, Any]


class AfterSaleTriage(BaseModel):
    """售后分诊结构化结果（简历/客服系统可对接）。"""

    problem_type: str
    problem_label: str
    priority: str
    missing_evidence: list[str] = Field(default_factory=list)
    matched_rules: list[str] = Field(default_factory=list)
    handling_advice: str
    suggested_reply: str
    escalate_to_human: bool = False
    order_id: str | None = None
    order_status: str | None = None


class ChatResponse(BaseModel):
    """Agent 对外统一响应结构。"""

    session_id: str
    reply_text: str
    conclusion: str | None = None
    reasons: list[str] = Field(default_factory=list)
    next_action: str | None = None
    cards: list[Card] = Field(default_factory=list)
    intent: Intent | None = None
    after_sale: AfterSaleTriage | None = None


class ToolResult(BaseModel):
    """工具层统一返回结构，屏蔽 mock/http 等来源差异。"""

    success: bool
    source: str
    data: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    latency_ms: int = 0
