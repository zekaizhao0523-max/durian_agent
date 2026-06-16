from __future__ import annotations

from src.cards.builder import (
    build_order_card,
    build_product_cards,
    build_purchase_card,
    build_trace_card,
)
from src.guardrails.guard import ensure_trace_tip, sanitize_reply
from src.models.schemas import Card, ChatResponse, Intent, SessionContext
from src.router.intent_router import route_intent
from src.services.analytics import track
from src.services.llm import polish_reply
from src.session.manager import session_manager
from src.storage.db import save_message
from src.storage.memory import extract_memories_from_message, sync_slots_to_profile
from src.aftersale.triage import format_after_sale_reply, triage_after_sale
from src.knowledge.compare import format_comparison_reply, is_compare_question
from src.tools.executor import execute


class RuleOrchestrator:
    """无 LLM 或演示环境下的规则编排器。

    它用关键词/正则识别意图，再进入对应业务 handler。handler 仍然走统一
    工具层，所以规则模式和 LangGraph 模式拿到的数据来源保持一致。
    """

    def handle(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        trace_code: str | None = None,
    ) -> ChatResponse:
        """完成一次规则模式对话：识别意图、调用工具、生成回复并持久化。"""
        ctx = session_manager.get_or_create(session_id, user_id)
        ctx.turn_count += 1

        if trace_code:
            ctx.slots.trace_code = trace_code.strip().upper()

        track(ctx.session_id, "consult_start", message_preview=message[:80])
        save_message(ctx.session_id, "user", message)

        # 路由会在识别意图的同时更新槽位，保留跨轮补充信息。
        route = route_intent(message, ctx.slots)
        ctx.current_intent = route.intent
        ctx.slots = route.slots

        handlers = {
            Intent.TRACE_QUERY: self._handle_trace,
            Intent.CONSULT_EVALUATE: self._handle_variety_evaluate,
            Intent.CONSULT_BUDGET: self._handle_consult_budget,
            Intent.CONSULT_VARIETY: self._handle_consult_variety,
            Intent.PURCHASE_INTENT: self._handle_purchase,
            Intent.AFTER_SALE: self._handle_after_sale,
            Intent.POST_PURCHASE: self._handle_post_purchase,
            Intent.HUMAN_HANDOFF: self._handle_human_handoff,
            Intent.CHITCHAT: self._handle_chitchat,
        }

        handler = handlers.get(route.intent, self._handle_chitchat)
        response = handler(ctx, message)
        response.intent = route.intent
        response.session_id = ctx.session_id

        tool_facts = "\n".join(response.reasons) if response.reasons else ""

        # 如果配置了 LLM，可只做“润色”，事实仍以 handler 和工具结果为准。
        polished = polish_reply(
            response.reply_text,
            response.intent.value if response.intent else None,
            tool_facts,
            message,
        )
        if polished:
            response.reply_text = polished

        response.reply_text = sanitize_reply(response.reply_text)

        save_message(
            ctx.session_id,
            "assistant",
            response.reply_text,
            intent=response.intent.value if response.intent else None,
            cards=[c.model_dump() for c in response.cards],
        )
        track(
            ctx.session_id,
            "consult_end",
            intent=response.intent.value if response.intent else None,
            conclusion=response.conclusion,
            card_count=len(response.cards),
        )
        if route.intent == Intent.TRACE_QUERY and ctx.slots.trace_code:
            track(
                ctx.session_id,
                "trace_query",
                trace_code=ctx.slots.trace_code,
                conclusion=response.conclusion,
            )
        if response.cards and any(c.type.value == "product_recommend" for c in response.cards):
            track(ctx.session_id, "product_expose", count=len(response.cards))

        sync_slots_to_profile(user_id, ctx.slots)
        extract_memories_from_message(user_id, message, ctx.slots)

        session_manager.save(ctx)
        return response

    def _handle_trace(self, ctx: SessionContext, message: str) -> ChatResponse:
        """处理批次溯源码验真，并在有在售 SKU 时附带商品推荐。"""
        code = ctx.slots.trace_code
        if not code:
            return ChatResponse(
                session_id=ctx.session_id,
                reply_text="请提供或扫描包装上的批次溯源码（我方按产地与批次生成，格式如 TR20260609002），我帮你查验这批货的来源信息。",
                conclusion="需验批次",
                next_action="输入溯源码",
            )

        result = execute("query_trace_code", {"trace_code": code})
        if not result.success or not result.data.get("valid"):
            return ChatResponse(
                session_id=ctx.session_id,
                reply_text=(
                    f"未查询到有效批次信息（码：{code}）。\n"
                    "请核对包装上的溯源码是否输入正确，或联系官方客服人工核验。"
                ),
                conclusion="不建议",
                reasons=["溯源码无效或不存在"],
                next_action="联系客服",
            )

        data = result.data
        ctx.slots.batch_id = data.get("batch_id")
        show_tip = not ctx.shown_trace_tip
        ctx.shown_trace_tip = True

        reply = (
            f"【结论】可以买\n\n"
            f"【码说明】该溯源码为我方根据产地与批次自主生成，对应以下批次档案。\n\n"
            f"【批次信息】\n"
            f"· 品种：{data.get('variety')} {data.get('grade', '')}级\n"
            f"· 产地：{data.get('origin')}\n"
            f"· 采摘：{data.get('pick_date')} · 入库：{data.get('stock_in_date')}\n"
            f"· 规格：{data.get('weight_range')} · 成熟度区间：{data.get('ripeness_range')}\n"
            f"· 批次状态：{_status_label(data.get('batch_status'))}\n\n"
            f"【食用建议】按该批次成熟度区间，到货后 1-2 天内通常达最佳食用期。"
        )
        reply = ensure_trace_tip(reply, show_tip)

        cards: list[Card] = [build_trace_card(data)]
        listing_ids = data.get("listing_ids", [])
        if listing_ids and data.get("batch_status") == "on_sale":
            products = []
            for pid in listing_ids[:3]:
                detail = execute("get_product_detail", {"product_id": pid})
                if detail.success:
                    products.append(detail.data)
            if products:
                cards.extend(build_product_cards(products))
                reply += "\n\n【下一步】同款商品在售，可查看下方推荐卡片。"

        return ChatResponse(
            session_id=ctx.session_id,
            reply_text=reply,
            conclusion="可以买",
            reasons=[
                f"批次 {data.get('batch_name', data.get('batch_id'))} 验真通过",
                f"成熟度区间 {data.get('ripeness_range')}",
                f"产地 {data.get('origin')}",
            ],
            next_action="查看推荐商品" if listing_ids else "到货后开果",
            cards=cards,
        )

    def _handle_variety_evaluate(self, ctx: SessionContext, message: str) -> ChatResponse:
        """用户点名某品种，结合预算/口味判断该品种是否适合。"""
        variety = ctx.slots.variety or "该品种"
        params: dict = {"variety": variety}
        if ctx.slots.budget:
            params["price_min"], params["price_max"] = ctx.slots.budget
        if ctx.slots.taste_tags:
            params["taste_tags"] = ctx.slots.taste_tags

        knowledge = execute("search_knowledge", {"query": f"{variety} {message}"})
        all_products = execute("search_products", {"variety": variety})
        matched = execute("search_products", params)

        all_items = all_products.data.get("items", []) if all_products.success else []
        matched_items = matched.data.get("items", []) if matched.success else []

        eval_reasons: list[str] = []
        cards: list[Card] = []
        next_action = "告诉我更具体偏好"
        conclusion = "需进一步确认"

        if not all_items:
            conclusion = "不建议"
            eval_reasons.append(f"当前暂无在售的{variety}商品")
        else:
            reference = matched_items[0] if matched_items else all_items[0]
            price = reference["price"]
            product_tags = reference.get("taste_tags", [])
            price_ok = True
            taste_ok = True

            if ctx.slots.budget:
                if price > ctx.slots.budget[1]:
                    price_ok = False
                    eval_reasons.append(
                        f"{variety}在售约 ¥{price}，超出预算 {ctx.slots.budget[0]}-{ctx.slots.budget[1]} 元"
                    )
                else:
                    eval_reasons.append(
                        f"¥{price} 落在预算 {ctx.slots.budget[0]}-{ctx.slots.budget[1]} 元内"
                    )

            user_wants_mild = any(t in ctx.slots.taste_tags for t in ["气味适中"])
            if user_wants_mild and "气味浓郁" in product_tags:
                taste_ok = False
                eval_reasons.append(f"{variety}气味通常较浓郁，与「气味不要太重」的偏好不太匹配")

            user_wants_sweet = any(t in ctx.slots.taste_tags for t in ["偏甜"])
            if user_wants_sweet and "苦甜" in product_tags and "偏甜" not in product_tags:
                taste_ok = False
                eval_reasons.append(f"{variety}偏苦甜风格，与「要甜一点」的偏好有差异")

            if knowledge.success and knowledge.data.get("chunks"):
                eval_reasons.append(knowledge.data["chunks"][0]["content"][:100])

            if not price_ok or not taste_ok:
                conclusion = "不建议"
            elif matched_items:
                conclusion = "可以买"
            else:
                conclusion = "再等等"
                eval_reasons.append("按当前条件筛选后暂无完全匹配的在售商品")

            if conclusion == "可以买":
                ctx.recommended_products = [i["product_id"] for i in matched_items[:3]]
                cards = build_product_cards(matched_items)
                next_action = "查看匹配商品"
            elif conclusion == "不建议":
                alternatives = execute(
                    "search_products",
                    {
                        "price_min": ctx.slots.budget[0] if ctx.slots.budget else None,
                        "price_max": ctx.slots.budget[1] if ctx.slots.budget else None,
                        "taste_tags": ctx.slots.taste_tags or None,
                    },
                )
                alt_items = alternatives.data.get("items", [])[:2] if alternatives.success else []
                alt_names = [i["variety"] for i in alt_items if i.get("variety") != variety]
                if alt_names:
                    eval_reasons.append(f"同条件下可考虑：{'、'.join(dict.fromkeys(alt_names))}")
                next_action = "查看更匹配的品种推荐"
            else:
                next_action = "放宽口味条件或查看在售商品"

        reply = f"【结论】{conclusion}\n\n【理由】\n"
        for i, reason in enumerate(eval_reasons[:5], 1):
            reply += f"{i}. {reason}\n"
        reply += f"\n【下一步】\n- {next_action}"

        return ChatResponse(
            session_id=ctx.session_id,
            reply_text=reply,
            conclusion=conclusion,
            reasons=eval_reasons[:5],
            next_action=next_action,
            cards=cards,
            intent=Intent.CONSULT_EVALUATE,
        )

    def _handle_consult_budget(self, ctx: SessionContext, message: str) -> ChatResponse:
        """榴莲推荐：综合特征、价格、食客偏好与销售热度。"""
        params: dict = {}
        if ctx.slots.budget:
            params["price_min"], params["price_max"] = ctx.slots.budget
        if ctx.slots.variety:
            params["variety"] = ctx.slots.variety
        if ctx.slots.taste_tags:
            params["taste_tags"] = ctx.slots.taste_tags

        knowledge = execute("search_knowledge", {"query": message})
        products = execute("search_products", params)

        reasons = []
        if knowledge.success and knowledge.data.get("chunks"):
            chunk = knowledge.data["chunks"][0]
            reasons.append(chunk["content"][:80] + "...")

        items = products.data.get("items", []) if products.success else []
        if not items:
            return ChatResponse(
                session_id=ctx.session_id,
                reply_text="目前没有在售商品完全匹配你的条件，可以放宽预算、口味或品种限制，我再帮你综合推荐。",
                conclusion="暂无合适商品",
                next_action="补充偏好或放宽条件",
                intent=Intent.CONSULT_BUDGET,
            )

        ctx.recommended_products = [i["product_id"] for i in items[:3]]
        top = items[0]
        rec_reasons = list(top.get("recommend_reasons") or [])
        if not rec_reasons:
            rec_reasons = [f"综合推荐分 {top.get('recommend_score', '-')}"]

        reply = f"【推荐】{top['name']}（¥{top['price']}）\n\n【理由】\n"
        reply += "综合特征、价格、你的偏好与销售热度，首推这一款：\n"
        for i, reason in enumerate(rec_reasons[:5], 1):
            reply += f"{i}. {reason}\n"

        if len(items) > 1:
            reply += f"\n另有 {min(len(items), 3) - 1} 款备选，见下方卡片。\n"

        reply += "\n【下一步】\n- 点击下方商品卡片查看详情并购买"

        return ChatResponse(
            session_id=ctx.session_id,
            reply_text=reply,
            conclusion=top["name"],
            reasons=reasons or rec_reasons[:3],
            next_action="查看推荐商品",
            cards=build_product_cards(items),
            intent=Intent.CONSULT_BUDGET,
        )

    def _handle_consult_variety(self, ctx: SessionContext, message: str) -> ChatResponse:
        """回答品种对比类问题，并尝试补充同品种在售商品。"""
        knowledge = execute("search_knowledge", {"query": message})
        chunks = knowledge.data.get("chunks", []) if knowledge.success else []
        reasons: list[str] = []

        products = execute(
            "search_products",
            {"variety": ctx.slots.variety} if ctx.slots.variety else {},
        )
        items = products.data.get("items", []) if products.success else []
        cards = build_product_cards(items) if items else []

        if is_compare_question(message):
            chunk = chunks[0] if chunks else None
            product_hint = items[0]["name"] if items else None
            reply = format_comparison_reply(message, chunk, product_hint)
            if chunk:
                reasons.append(chunk["title"])
            return ChatResponse(
                session_id=ctx.session_id,
                reply_text=reply,
                conclusion=chunk["title"] if chunk else "品种对比",
                reasons=reasons,
                next_action="查看推荐商品" if items else "补充偏好继续聊",
                cards=cards,
                intent=Intent.CONSULT_VARIETY,
            )

        reply = "【推荐】"
        if items:
            reply += f"首推 {items[0]['name']}"
        elif chunks:
            reply += chunks[0]["title"]
        else:
            reply += "建议先明确你的偏好再选品种"
        reply += "\n"

        if chunks:
            reply += f"\n{chunks[0]['content']}"
            reasons.append(chunks[0]["title"])

        if items:
            reply += "\n\n【理由】\n1. 下方为对应该品种的在售商品，可直接选购"
            reply += "\n\n【下一步】\n- 查看下方商品卡片"
        else:
            reply += "\n\n【下一步】\n- 告诉我你的预算和口味偏好，我帮你精确推荐"

        return ChatResponse(
            session_id=ctx.session_id,
            reply_text=reply,
            conclusion=items[0]["name"] if items else (chunks[0]["title"] if chunks else "待明确偏好"),
            reasons=reasons,
            next_action="查看推荐商品" if items else "补充预算偏好",
            cards=cards,
            intent=Intent.CONSULT_VARIETY,
        )

    def _handle_purchase(self, ctx: SessionContext, message: str) -> ChatResponse:
        """处理购买链接请求；缺少明确商品时回到推荐流程。"""
        if ctx.recommended_products and any(k in message for k in ["第", "这个", "那个", "链接"]):
            idx = 0
            for i, ch in enumerate(["一", "二", "三", "1", "2", "3"]):
                if f"第{ch}" in message or f"{ch}个" in message:
                    idx = i if i < 3 else i - 3
                    break
            product_id = ctx.recommended_products[min(idx, len(ctx.recommended_products) - 1)]
            link = execute("get_purchase_link", {"product_id": product_id})
            detail = execute("get_product_detail", {"product_id": product_id})
            if link.success and detail.success:
                return ChatResponse(
                    session_id=ctx.session_id,
                    reply_text=(
                        f"【结论】可以买。\n\n"
                        f"为你生成 {detail.data['name']} 的购买链接，价格 ¥{detail.data['price']}。\n"
                        f"发货：{detail.data.get('ship_time', '尽快发货')}\n\n"
                        f"【说明】每颗榴莲包装附批次溯源码，到货可扫码验真。"
                    ),
                    conclusion="可以买",
                    reasons=[f"库存 {detail.data['stock']}", detail.data.get("ship_time", "")],
                    next_action="点击购买",
                    cards=[build_purchase_card(product_id, link.data)],
                )

        return self._handle_consult_budget(ctx, message)

    def _handle_after_sale(self, ctx: SessionContext, message: str) -> ChatResponse:
        """售后分诊：分类、规则命中、凭证检查、处理建议与客服话术。"""
        order_id = ctx.slots.order_id
        order = None
        cards: list[Card] = []

        if order_id:
            result = execute(
                "get_order_detail",
                {"order_id": order_id, "user_id": ctx.user_id},
            )
            if result.success:
                order = result.data
                cards.append(build_order_card(order))

        triage = triage_after_sale(
            message,
            order_id=order_id,
            order_status=order.get("status") if order else None,
        )

        return ChatResponse(
            session_id=ctx.session_id,
            reply_text=format_after_sale_reply(triage),
            conclusion=triage.problem_label,
            reasons=triage.matched_rules,
            next_action="转人工客服" if triage.escalate_to_human else "补充凭证材料",
            cards=cards,
            intent=Intent.AFTER_SALE,
            after_sale=triage,
        )

    def _handle_post_purchase(self, ctx: SessionContext, message: str) -> ChatResponse:
        """处理开果、保存、到货后食用建议。"""
        knowledge = execute("search_knowledge", {"query": message})
        chunks = knowledge.data.get("chunks", []) if knowledge.success else []

        ripeness_hint = ""
        cards: list[Card] = []
        if ctx.slots.trace_code:
            trace = execute("query_trace_code", {"trace_code": ctx.slots.trace_code})
            if trace.success and trace.data.get("valid"):
                ripeness_hint = f"\n\n你查询的批次成熟度区间为 {trace.data.get('ripeness_range')}。"
                cards.append(build_trace_card(trace.data))

        content = chunks[0]["content"] if chunks else "建议结合手感、气味与轻微裂纹综合判断是否可以开果。"
        reply = f"【结论】可以参考以下指南。{ripeness_hint}\n\n{content}"
        reply = ensure_trace_tip(reply, bool(ctx.slots.trace_code and not ctx.shown_trace_tip))
        if ctx.slots.trace_code:
            ctx.shown_trace_tip = True

        return ChatResponse(
            session_id=ctx.session_id,
            reply_text=reply,
            conclusion="可以参考",
            reasons=[chunks[0]["title"]] if chunks else ["通用开果保存指南"],
            next_action="到货后按指南开果",
            cards=cards,
        )

    def _handle_human_handoff(self, ctx: SessionContext, message: str) -> ChatResponse:
        """转人工兜底。"""
        return ChatResponse(
            session_id=ctx.session_id,
            reply_text=(
                "非常抱歉给你带来不好的体验。我已记录你的问题，"
                "正在为你转接人工客服，请稍候。\n\n"
                "转接时将同步本次对话摘要，方便客服快速处理。"
            ),
            conclusion="转人工",
            next_action="等待人工客服",
        )

    def _handle_chitchat(self, ctx: SessionContext, message: str) -> ChatResponse:
        """闲聊/未识别意图兜底，连续不清晰时转人工。"""
        ctx.unclear_count += 1
        if ctx.unclear_count >= 2:
            return self._handle_human_handoff(ctx, message)

        return ChatResponse(
            session_id=ctx.session_id,
            reply_text=(
                "嗨，我是小榴，帮你挑榴莲、验批次、聊保存和售后～\n"
                "你可以直接说「300左右要甜一点的推荐」，扫溯源码验真，"
                "或者拿订单号来问售后。"
            ),
            conclusion="欢迎咨询",
            next_action="开始咨询或扫码",
        )


def _status_label(status: str | None) -> str:
    mapping = {
        "on_sale": "在售",
        "in_stock": "在库",
        "sold_out": "售罄",
        "off_shelf": "已下架",
    }
    return mapping.get(status or "", status or "未知")


rule_orchestrator = RuleOrchestrator()
