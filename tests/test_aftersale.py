from __future__ import annotations

import os

os.environ["AGENT_MODE"] = "rules"
os.environ["OPENAI_API_KEY"] = ""

from src.aftersale.triage import triage_after_sale


def test_classifies_after_sale_problem_types() -> None:
    bad_fruit = triage_after_sale("榴莲收到就烂了，有照片")
    assert bad_fruit.problem_type == "bad_fruit"
    assert bad_fruit.priority == "P0"

    assert triage_after_sale("果子太生了，夹生").problem_type == "unripe"
    assert (
        triage_after_sale("快递太慢了，物流延迟怎么办", order_id="ORD_10001").problem_type
        == "logistics_delay"
    )
    assert triage_after_sale("称重不够，缺斤少两").problem_type == "weight_short"
    assert triage_after_sale("预售什么时候发货").problem_type == "presale_ship"


def test_after_sale_missing_evidence_and_rule_match() -> None:
    assert "订单号" in triage_after_sale("榴莲坏了").missing_evidence

    triage = triage_after_sale("榴莲收到就烂了，有照片")
    assert any("24小时" in rule or "图片" in rule for rule in triage.matched_rules)
