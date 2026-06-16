from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

from src.config.settings import get_settings
from src.models.schemas import SessionContext


def _url() -> str:
    return get_settings().database_url


def _now() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def get_conn():
    conn = psycopg.connect(_url(), row_factory=dict_row, connect_timeout=10)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                user_id      TEXT,
                context_json JSONB NOT NULL,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at   TIMESTAMPTZ
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          BIGSERIAL PRIMARY KEY,
                session_id  TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                intent      TEXT,
                cards_json  JSONB DEFAULT '[]',
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS events (
                id           BIGSERIAL PRIMARY KEY,
                session_id   TEXT,
                event_name   TEXT NOT NULL,
                payload_json JSONB DEFAULT '{}',
                created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id          TEXT PRIMARY KEY,
                taste_tags       JSONB DEFAULT '[]',
                budget_min       INTEGER,
                budget_max       INTEGER,
                favorite_variety TEXT,
                notes            TEXT DEFAULT '',
                updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS batch_experiences (
                id          BIGSERIAL PRIMARY KEY,
                user_id     TEXT NOT NULL,
                trace_code  TEXT,
                batch_id    TEXT,
                variety     TEXT,
                rating      SMALLINT,
                note        TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS user_memories (
                id         BIGSERIAL PRIMARY KEY,
                user_id    TEXT NOT NULL,
                memory_type TEXT NOT NULL DEFAULT 'fact',
                content    TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_events_name ON events(event_name);
            CREATE INDEX IF NOT EXISTS idx_batch_exp_user ON batch_experiences(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_memories_user ON user_memories(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

            CREATE TABLE IF NOT EXISTS trace_batches (
                trace_code TEXT PRIMARY KEY,
                payload    JSONB NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                payload    JSONB NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                user_id  TEXT NOT NULL,
                payload  JSONB NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
            """
        )


def save_session(ctx: SessionContext) -> None:
    settings = get_settings()
    now = _now()
    expires = now + timedelta(hours=settings.session_ttl_hours)
    payload = ctx.model_dump(mode="json")

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO sessions (session_id, user_id, context_json, created_at, updated_at, expires_at)
            VALUES (%s, %s, %s::jsonb, %s, %s, %s)
            ON CONFLICT (session_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                context_json = EXCLUDED.context_json,
                updated_at = EXCLUDED.updated_at,
                expires_at = EXCLUDED.expires_at
            """,
            (
                ctx.session_id,
                ctx.user_id,
                json.dumps(payload, ensure_ascii=False),
                now,
                now,
                expires,
            ),
        )


def load_session(session_id: str) -> SessionContext | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT context_json FROM sessions WHERE session_id = %s",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    data = row["context_json"]
    if isinstance(data, str):
        data = json.loads(data)
    return SessionContext.model_validate(data)


def save_message(
    session_id: str,
    role: str,
    content: str,
    intent: str | None = None,
    cards: list | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO messages (session_id, role, content, intent, cards_json, created_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                session_id,
                role,
                content,
                intent,
                json.dumps(cards or [], ensure_ascii=False),
                _now(),
            ),
        )


def get_messages(session_id: str, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT role, content, intent, cards_json, created_at
            FROM messages WHERE session_id = %s
            ORDER BY id DESC LIMIT %s
            """,
            (session_id, limit),
        ).fetchall()

    items = []
    for row in reversed(rows):
        cards = row["cards_json"] or []
        if isinstance(cards, str):
            cards = json.loads(cards)
        created = row["created_at"]
        items.append(
            {
                "role": row["role"],
                "content": row["content"],
                "intent": row["intent"],
                "cards": cards,
                "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created),
            }
        )
    return items


def log_event(session_id: str | None, event_name: str, payload: dict | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO events (session_id, event_name, payload_json, created_at)
            VALUES (%s, %s, %s::jsonb, %s)
            """,
            (session_id, event_name, json.dumps(payload or {}, ensure_ascii=False), _now()),
        )


def get_stats() -> dict:
    with get_conn() as conn:
        sessions = conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"]
        messages = conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"]
        profiles = conn.execute("SELECT COUNT(*) AS c FROM user_profiles").fetchone()["c"]
        events = conn.execute(
            "SELECT event_name, COUNT(*) AS c FROM events GROUP BY event_name"
        ).fetchall()
        products = conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
        trace_batches = conn.execute("SELECT COUNT(*) AS c FROM trace_batches").fetchone()["c"]
        orders = conn.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"]
    return {
        "sessions": sessions,
        "messages": messages,
        "user_profiles": profiles,
        "products": products,
        "trace_batches": trace_batches,
        "orders": orders,
        "events": {row["event_name"]: row["c"] for row in events},
    }


def get_user_profile(user_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = %s",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def upsert_user_profile(
    user_id: str,
    taste_tags: list[str] | None = None,
    budget_min: int | None = None,
    budget_max: int | None = None,
    favorite_variety: str | None = None,
    notes: str | None = None,
) -> None:
    existing = get_user_profile(user_id)
    tags = taste_tags if taste_tags is not None else (existing or {}).get("taste_tags") or []
    if isinstance(tags, str):
        tags = json.loads(tags)

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_profiles (
                user_id, taste_tags, budget_min, budget_max, favorite_variety, notes, updated_at
            ) VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                taste_tags = COALESCE(EXCLUDED.taste_tags, user_profiles.taste_tags),
                budget_min = COALESCE(EXCLUDED.budget_min, user_profiles.budget_min),
                budget_max = COALESCE(EXCLUDED.budget_max, user_profiles.budget_max),
                favorite_variety = COALESCE(EXCLUDED.favorite_variety, user_profiles.favorite_variety),
                notes = COALESCE(EXCLUDED.notes, user_profiles.notes),
                updated_at = EXCLUDED.updated_at
            """,
            (
                user_id,
                json.dumps(tags, ensure_ascii=False),
                budget_min,
                budget_max,
                favorite_variety,
                notes,
                _now(),
            ),
        )


def get_batch_experiences(user_id: str, limit: int = 5) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT trace_code, batch_id, variety, rating, note, created_at
            FROM batch_experiences WHERE user_id = %s
            ORDER BY id DESC LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def add_user_memory(user_id: str, content: str, memory_type: str = "fact") -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_memories (user_id, memory_type, content, created_at)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, memory_type, content, _now()),
        )


def get_user_memories(user_id: str, limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT memory_type, content, created_at
            FROM user_memories WHERE user_id = %s
            ORDER BY id DESC LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def list_user_sessions(user_id: str, limit: int = 30) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                s.session_id,
                s.created_at,
                s.updated_at,
                (
                    SELECT content FROM messages m
                    WHERE m.session_id = s.session_id AND m.role = 'user'
                    ORDER BY m.id ASC LIMIT 1
                ) AS preview,
                (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id) AS message_count
            FROM sessions s
            WHERE s.user_id = %s AND EXISTS (
                SELECT 1 FROM messages m WHERE m.session_id = s.session_id
            )
            ORDER BY s.updated_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()
    items = []
    for row in rows:
        preview = (row["preview"] or "新对话").replace("\n", " ")[:48]
        items.append(
            {
                "session_id": row["session_id"],
                "preview": preview,
                "message_count": row["message_count"],
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
            }
        )
    return items


def delete_session(session_id: str, user_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id FROM sessions WHERE session_id = %s",
            (session_id,),
        ).fetchone()
        if not row:
            return False
        if row["user_id"] and row["user_id"] != user_id:
            return False
        conn.execute("DELETE FROM events WHERE session_id = %s", (session_id,))
        conn.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
    return True


def delete_all_user_sessions(user_id: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM sessions WHERE user_id = %s",
            (user_id,),
        ).fetchone()
        count = row["c"] if row else 0
        if count:
            conn.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
    return count


def clear_user_long_term_memory(user_id: str) -> dict[str, int]:
    with get_conn() as conn:
        profiles = conn.execute(
            "DELETE FROM user_profiles WHERE user_id = %s RETURNING user_id",
            (user_id,),
        ).rowcount
        experiences = conn.execute(
            "DELETE FROM batch_experiences WHERE user_id = %s RETURNING id",
            (user_id,),
        ).rowcount
        memories = conn.execute(
            "DELETE FROM user_memories WHERE user_id = %s RETURNING id",
            (user_id,),
        ).rowcount
    return {"profiles": profiles, "experiences": experiences, "memories": memories}


def _row_payload(row: dict, id_key: str) -> dict:
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return {id_key: row[id_key], **payload}


def get_trace_batch(trace_code: str) -> dict | None:
    code = trace_code.strip().upper()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT trace_code, payload FROM trace_batches WHERE trace_code = %s",
            (code,),
        ).fetchone()
    if not row:
        return None
    return _row_payload(row, "trace_code")


def list_products() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT product_id, payload FROM products ORDER BY product_id"
        ).fetchall()
    return [_row_payload(r, "product_id") for r in rows]


def get_product(product_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT product_id, payload FROM products WHERE product_id = %s",
            (product_id,),
        ).fetchone()
    if not row:
        return None
    return _row_payload(row, "product_id")


def get_order(order_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT order_id, user_id, payload FROM orders WHERE order_id = %s",
            (order_id,),
        ).fetchone()
    if not row:
        return None
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return {"order_id": row["order_id"], "user_id": row["user_id"], **payload}


def seed_demo_catalog() -> dict[str, int]:
    """将演示商品/批次/订单写入 PostgreSQL（表为空时执行）。"""
    from src.storage.seed_data import ORDERS, PRODUCTS, TRACE_BATCHES

    with get_conn() as conn:
        existing = conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
        if existing:
            return {"trace_batches": 0, "products": 0, "orders": 0, "skipped": True}

        tb = 0
        for code, data in TRACE_BATCHES.items():
            conn.execute(
                """
                INSERT INTO trace_batches (trace_code, payload)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (trace_code) DO NOTHING
                """,
                (code, json.dumps(data, ensure_ascii=False)),
            )
            tb += 1

        pc = 0
        for pid, data in PRODUCTS.items():
            conn.execute(
                """
                INSERT INTO products (product_id, payload)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (product_id) DO NOTHING
                """,
                (pid, json.dumps(data, ensure_ascii=False)),
            )
            pc += 1

        oc = 0
        for oid, data in ORDERS.items():
            user_id = data["user_id"]
            payload = {k: v for k, v in data.items() if k not in ("order_id", "user_id")}
            conn.execute(
                """
                INSERT INTO orders (order_id, user_id, payload)
                VALUES (%s, %s, %s::jsonb)
                ON CONFLICT (order_id) DO NOTHING
                """,
                (oid, user_id, json.dumps(payload, ensure_ascii=False)),
            )
            oc += 1

    return {"trace_batches": tb, "products": pc, "orders": oc, "skipped": False}
