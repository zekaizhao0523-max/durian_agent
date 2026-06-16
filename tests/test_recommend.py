from __future__ import annotations

from src.services.recommend import rank_products


def test_rank_products_prefers_higher_sales_score() -> None:
    items = [
        {
            "product_id": "a",
            "price": 268,
            "stock": 45,
            "taste_tags": ["偏甜", "气味适中"],
            "sales_score": 92,
            "variety": "金枕",
            "batch_summary": {"origin": "泰国"},
        },
        {
            "product_id": "b",
            "price": 198,
            "stock": 32,
            "taste_tags": ["偏甜", "气味适中"],
            "sales_score": 78,
            "variety": "金枕",
            "batch_summary": {},
        },
    ]
    ranked = rank_products(items, budget=[240, 360], taste_tags=["偏甜", "气味适中"], variety="金枕")

    assert ranked[0]["product_id"] == "a"
    assert ranked[0]["recommend_score"] >= ranked[1]["recommend_score"]
    assert ranked[0]["recommend_reasons"]
