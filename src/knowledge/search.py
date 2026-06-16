"""知识库关键词检索。"""

from __future__ import annotations

from src.knowledge.data import DURIAN_TIPS, FAQ_ENTRIES, VARIETY_PROFILES


def _keyword_score(query: str, *, keywords: list[str], content: str, varieties: list[str] | None = None, tags: list[str] | None = None) -> float:
    """按关键词、品种、标签与正文重合度打分。"""
    query_lower = query.lower()
    score = 0.0
    for kw in keywords:
        if kw in query or kw.lower() in query_lower:
            score += 2.0
    for variety in varieties or []:
        if variety in query:
            score += 2.5
    for tag in tags or []:
        if tag in query:
            score += 0.5
    for char in query:
        if char in content:
            score += 0.01
    return score


def _variety_profile_entry(profile: dict) -> dict:
    """把品种档案转为可检索条目。"""
    variety = profile["variety"]
    aliases = profile.get("aliases") or []
    content = (
        f"{variety}榴莲品种档案。"
        f"别名：{'、'.join(aliases)}。"
        f"主产地：{profile.get('origin', '')}。"
        f"口感：{profile.get('taste', '')}。"
        f"质地：{profile.get('texture', '')}。"
        f"气味：{profile.get('aroma', '')}。"
        f"价位带：{profile.get('price_tier', '')}。"
        f"适合：{profile.get('best_for', '')}。"
        f"不太适合：{profile.get('not_for', '')}。"
    )
    return {
        "id": profile["id"],
        "title": f"{variety}品种档案",
        "content": content,
        "comparison": None,
        "keywords": [variety, *aliases],
        "varieties": [variety],
        "tags": ["品种百科"],
    }


def _iter_search_entries() -> list[dict]:
    """汇总 FAQ、小贴士与品种档案为统一检索列表。"""
    entries: list[dict] = []
    for entry in FAQ_ENTRIES:
        entries.append(
            {
                "id": entry["id"],
                "title": entry["title"],
                "content": entry["content"],
                "comparison": entry.get("comparison"),
                "keywords": list(entry.get("keywords") or []),
                "varieties": list(entry.get("varieties") or []),
                "tags": list(entry.get("tags") or []),
            }
        )
    for tip in DURIAN_TIPS:
        prompt = tip.get("prompt") or ""
        entries.append(
            {
                "id": tip["id"],
                "title": "榴莲小贴士",
                "content": tip["text"],
                "comparison": None,
                "keywords": [prompt] if prompt else [],
                "varieties": [],
                "tags": ["小贴士"],
            }
        )
    for profile in VARIETY_PROFILES:
        entries.append(_variety_profile_entry(profile))
    return entries


def search_knowledge(query: str, top_k: int = 3) -> list[dict]:
    """检索榴莲百科与售后知识，返回按相关度排序的切片列表。"""
    scored: list[tuple[float, dict]] = []
    for entry in _iter_search_entries():
        score = _keyword_score(
            query,
            keywords=entry["keywords"],
            content=entry["content"],
            varieties=entry.get("varieties"),
            tags=entry.get("tags"),
        )
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda item: item[0], reverse=True)
    results: list[dict] = []
    for score, entry in scored[:top_k]:
        results.append(
            {
                "id": entry["id"],
                "title": entry["title"],
                "content": entry["content"],
                "comparison": entry.get("comparison"),
                "score": round(score, 2),
            }
        )
    return results
