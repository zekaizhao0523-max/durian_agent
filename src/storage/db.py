from __future__ import annotations

from src.models.schemas import SessionContext
from src.storage import postgres_store as store
from src.storage.connection import assert_postgres_url, database_label


def init_db() -> None:
    """初始化 PostgreSQL 表结构并写入演示商品/订单数据。"""
    assert_postgres_url()
    store.init_db()
    store.seed_demo_catalog()


def save_session(ctx: SessionContext) -> None:
    store.save_session(ctx)


def load_session(session_id: str) -> SessionContext | None:
    return store.load_session(session_id)


def save_message(
    session_id: str,
    role: str,
    content: str,
    intent: str | None = None,
    cards: list | None = None,
) -> None:
    store.save_message(session_id, role, content, intent, cards)


def get_messages(session_id: str, limit: int = 50) -> list[dict]:
    return store.get_messages(session_id, limit)


def log_event(session_id: str | None, event_name: str, payload: dict | None = None) -> None:
    store.log_event(session_id, event_name, payload)


def get_stats() -> dict:
    stats = store.get_stats()
    stats["database"] = database_label()
    return stats


def get_user_profile(user_id: str) -> dict | None:
    return store.get_user_profile(user_id)


def upsert_user_profile(
    user_id: str,
    taste_tags: list[str] | None = None,
    budget_min: int | None = None,
    budget_max: int | None = None,
    favorite_variety: str | None = None,
    notes: str | None = None,
) -> None:
    store.upsert_user_profile(
        user_id, taste_tags, budget_min, budget_max, favorite_variety, notes
    )


def get_batch_experiences(user_id: str, limit: int = 5) -> list[dict]:
    return store.get_batch_experiences(user_id, limit)


def add_user_memory(user_id: str, content: str, memory_type: str = "fact") -> None:
    store.add_user_memory(user_id, content, memory_type)


def get_user_memories(user_id: str, limit: int = 10) -> list[dict]:
    return store.get_user_memories(user_id, limit)


def list_user_sessions(user_id: str, limit: int = 30) -> list[dict]:
    return store.list_user_sessions(user_id, limit)


def delete_session(session_id: str, user_id: str) -> bool:
    return store.delete_session(session_id, user_id)


def delete_all_user_sessions(user_id: str) -> int:
    return store.delete_all_user_sessions(user_id)


def clear_user_long_term_memory(user_id: str) -> dict[str, int]:
    return store.clear_user_long_term_memory(user_id)


def get_trace_batch(trace_code: str) -> dict | None:
    return store.get_trace_batch(trace_code)


def list_products() -> list[dict]:
    return store.list_products()


def get_product(product_id: str) -> dict | None:
    return store.get_product(product_id)


def get_order(order_id: str) -> dict | None:
    return store.get_order(order_id)


def seed_demo_catalog() -> dict[str, int]:
    return store.seed_demo_catalog()
