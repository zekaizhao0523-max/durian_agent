from __future__ import annotations

from src.aftersale.classifier import classify_problem, detect_provided_evidence, problem_label
from src.aftersale.rules import AFTER_SALE_RULES, EVIDENCE_LABELS
from src.models.schemas import AfterSaleTriage


def _match_rules(problem_type: str, message: str) -> list[dict]:
    matched: list[dict] = []
    for rule in AFTER_SALE_RULES:
        if problem_type in rule["problem_types"] or problem_type == "general":
            if any(kw in message for kw in rule.get("keywords", [])):
                matched.append(rule)
        elif problem_type in rule["problem_types"]:
            matched.append(rule)
    if not matched:
        for rule in AFTER_SALE_RULES:
            if problem_type in rule["problem_types"]:
                matched.append(rule)
                break
    if not matched and problem_type == "general":
        matched.append(AFTER_SALE_RULES[-1])
    seen: set[str] = set()
    unique: list[dict] = []
    for rule in matched:
        if rule["id"] not in seen:
            seen.add(rule["id"])
            unique.append(rule)
    return unique[:4]


def _priority(rules: list[dict], problem_type: str) -> str:
    if not rules:
        return "P2"
    order = {"P0": 0, "P1": 1, "P2": 2}
    best = min(rules, key=lambda r: order.get(r["priority"], 9))
    return best["priority"]


def _missing_evidence(rules: list[dict], provided: set[str], has_order: bool) -> list[str]:
    required: set[str] = set()
    if not has_order:
        required.add("order_id")
    for rule in rules:
        required.update(rule.get("required_evidence", []))
    missing = required - provided
    return [EVIDENCE_LABELS.get(k, k) for k in sorted(missing)]


def _handling_advice(rules: list[dict], missing: list[str]) -> str:
    parts = [r["handling"] for r in rules[:2]]
    if missing:
        parts.append(f"当前还需用户补充：{'、'.join(missing)}。")
    return " ".join(parts)


def _suggested_reply(rules: list[dict], missing: list[str], problem_type: str) -> str:
    if rules:
        base = rules[0]["cs_reply"]
    else:
        base = "请提供订单号并描述问题，我会按售后规则帮您处理。"
    if missing:
        base += f" 另外还需要您补充：{'、'.join(missing)}。"
    return base


def _escalate(rules: list[dict], missing: list[str], priority: str) -> bool:
    if any(r.get("escalate") for r in rules):
        return True
    if priority == "P0" and missing:
        return True
    return False


def triage_after_sale(
    message: str,
    *,
    order_id: str | None = None,
    order_status: str | None = None,
) -> AfterSaleTriage:
    """售后分诊：分类、命中规则、缺失凭证、处理建议与客服话术。"""
    has_order = bool(order_id)
    problem_type = classify_problem(message)
    rules = _match_rules(problem_type, message)
    provided = detect_provided_evidence(message, has_order)
    missing = _missing_evidence(rules, provided, has_order)
    priority = _priority(rules, problem_type)
    escalate = _escalate(rules, missing, priority)

    return AfterSaleTriage(
        problem_type=problem_type,
        problem_label=problem_label(problem_type),
        priority=priority,
        missing_evidence=missing,
        matched_rules=[r["title"] for r in rules],
        handling_advice=_handling_advice(rules, missing),
        suggested_reply=_suggested_reply(rules, missing, problem_type),
        escalate_to_human=escalate,
        order_id=order_id,
        order_status=order_status,
    )


def format_after_sale_reply(triage: AfterSaleTriage) -> str:
    """生成面向用户的自然语言回复（含结构化摘要）。"""
    lines = [
        f"问题类型：{triage.problem_label}",
        f"优先级：{triage.priority}",
    ]
    if triage.matched_rules:
        lines.append(f"命中规则：{'；'.join(triage.matched_rules)}")
    if triage.missing_evidence:
        lines.append(f"待补充凭证：{'、'.join(triage.missing_evidence)}")
    lines.append(f"处理建议：{triage.handling_advice}")
    lines.append(f"推荐客服回复：{triage.suggested_reply}")
    lines.append(f"是否转人工：{'是' if triage.escalate_to_human else '否'}")
    return "\n".join(lines)


def enrich_after_sale_response(message: str, response, order_id: str | None = None, order_status: str | None = None):
    """为 ChatResponse 附加售后分诊结果。"""
    triage = triage_after_sale(message, order_id=order_id, order_status=order_status)
    response.after_sale = triage
    if response.intent and response.intent.value == "after_sale":
        response.reply_text = format_after_sale_reply(triage)
        response.conclusion = triage.problem_label
        response.next_action = "转人工客服" if triage.escalate_to_human else "补充凭证材料"
        response.reasons = triage.matched_rules
    return response
