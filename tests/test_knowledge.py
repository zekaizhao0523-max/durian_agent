from __future__ import annotations

from src.knowledge.data import FAQ_ENTRIES, get_knowledge_catalog
from src.knowledge.search import search_knowledge
from src.models.schemas import Intent
from src.storage.seed_data import PRODUCTS, TRACE_BATCHES


def test_heici_faq_entries_exist() -> None:
    heici_faqs = [e for e in FAQ_ENTRIES if "黑刺" in e["title"] or "黑刺" in e.get("keywords", [])]
    assert len(heici_faqs) >= 4
    titles = {e["title"] for e in heici_faqs}
    assert "黑刺榴莲特点" in titles
    assert "黑刺与猫山王区别" in titles


def test_heici_seed_catalog_data() -> None:
    assert "sku_401" in PRODUCTS
    assert PRODUCTS["sku_401"]["variety"] == "黑刺"
    assert "TR20260610004" in TRACE_BATCHES
    assert TRACE_BATCHES["TR20260610004"]["variety"] == "黑刺"


def test_search_knowledge_finds_heici() -> None:
    hits = search_knowledge("黑刺榴莲有什么特点", top_k=3)
    assert hits
    assert any("黑刺" in hit["title"] for hit in hits)


def test_search_knowledge_heici_compare() -> None:
    hits = search_knowledge("黑刺和猫山王哪个更好", top_k=2)
    assert hits
    assert hits[0].get("comparison") or "黑刺" in hits[0]["content"]


def test_knowledge_catalog_has_heici_prompts() -> None:
    catalog = get_knowledge_catalog()
    prompts = catalog["prompts"]
    assert any("黑刺" in p for p in prompts)


def test_orchestrator_heici_compare_reply(agent_handle) -> None:
    response = agent_handle("黑刺和猫山王有什么区别")
    assert response.intent == Intent.CONSULT_VARIETY
    assert "黑刺" in response.reply_text
    assert "我会从" in response.reply_text or "首先" in response.reply_text
