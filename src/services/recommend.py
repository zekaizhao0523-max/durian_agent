from __future__ import annotations

from src.models.schemas import SessionSlots


def _taste_overlap(user_tags: list[str], product_tags: list[str]) -> tuple[float, list[str]]:
    if not user_tags:
        return 0.0, []
    matched = []
    for tag in user_tags:
        for pt in product_tags:
            if tag in pt or pt in tag:
                matched.append(pt)
                break
    if not matched:
        return 0.0, []
    ratio = len(matched) / len(user_tags)
    return ratio * 30, [f"口味匹配：{'、'.join(dict.fromkeys(matched))}"]


def _price_fit(price: int, budget: list[int] | None) -> tuple[float, list[str]]:
    if not budget:
        return 10.0, [f"售价 ¥{price}"]
    low, high = budget
    if low <= price <= high:
        center = (low + high) / 2
        closeness = 1 - min(abs(price - center) / max(center, 1), 1)
        return 15 + closeness * 10, [f"¥{price} 落在预算 {low}-{high} 元内"]
    if price < low:
        return 12.0, [f"¥{price} 低于预算上限，性价比突出"]
    over = price - high
    penalty = min(over / max(high, 1), 1) * 25
    return max(0, 8 - penalty), [f"¥{price} 略超预算 {low}-{high} 元"]


def _sales_heat(item: dict) -> tuple[float, list[str]]:
    score = float(item.get("sales_score", 50))
    normalized = min(score / 100, 1) * 25
    reasons = []
    if score >= 85:
        reasons.append(f"近期热销（热度 {int(score)}）")
    elif score >= 70:
        reasons.append(f"销售表现稳定（热度 {int(score)}）")
    return normalized, reasons


def _feature_fit(item: dict, variety: str | None) -> tuple[float, list[str]]:
    reasons = []
    score = 0.0
    tags = item.get("feature_tags") or item.get("taste_tags") or []
    if tags:
        reasons.append(f"特征：{'、'.join(tags[:3])}")
        score += 8
    batch = item.get("batch_summary", {})
    if batch.get("origin"):
        reasons.append(f"产地 {batch['origin']}")
        score += 4
    if variety and variety in (item.get("variety") or ""):
        score += 8
        reasons.insert(0, f"品种匹配：{variety}")
    return min(score, 15), reasons[:2]


def _stock_bonus(stock: int) -> tuple[float, list[str]]:
    if stock >= 40:
        return 10.0, ["库存充足，下单成功率高"]
    if stock >= 20:
        return 7.0, ["库存正常"]
    if stock > 0:
        return 4.0, ["库存偏紧，建议尽快下单"]
    return 0.0, []


def score_product(
    item: dict,
    *,
    budget: list[int] | None = None,
    taste_tags: list[str] | None = None,
    variety: str | None = None,
) -> tuple[float, list[str]]:
    """综合口味、价格、特征、销售热度与库存为商品打分。"""
    product_tags = item.get("taste_tags") or []
    parts: list[str] = []
    total = 0.0

    taste_s, taste_r = _taste_overlap(taste_tags or [], product_tags)
    total += taste_s
    parts.extend(taste_r)

    price_s, price_r = _price_fit(int(item.get("price", 0)), budget)
    total += price_s
    parts.extend(price_r)

    sales_s, sales_r = _sales_heat(item)
    total += sales_s
    parts.extend(sales_r)

    feat_s, feat_r = _feature_fit(item, variety)
    total += feat_s
    parts.extend(feat_r)

    stock_s, stock_r = _stock_bonus(int(item.get("stock", 0)))
    total += stock_s
    parts.extend(stock_r)

    return round(total, 2), parts[:5]


def rank_products(
    items: list[dict],
    *,
    budget: list[int] | None = None,
    taste_tags: list[str] | None = None,
    variety: str | None = None,
) -> list[dict]:
    """按综合推荐分排序，并为每个商品附加 recommend_score / recommend_reasons。"""
    ranked: list[dict] = []
    for item in items:
        score, reasons = score_product(
            item,
            budget=budget,
            taste_tags=taste_tags,
            variety=variety,
        )
        ranked.append(
            {
                **item,
                "recommend_score": score,
                "recommend_reasons": reasons,
            }
        )
    ranked.sort(key=lambda x: x["recommend_score"], reverse=True)
    return ranked


def rank_from_slots(items: list[dict], slots: SessionSlots) -> list[dict]:
    return rank_products(
        items,
        budget=slots.budget,
        taste_tags=slots.taste_tags or None,
        variety=slots.variety,
    )
