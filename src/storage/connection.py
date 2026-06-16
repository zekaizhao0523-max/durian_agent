from __future__ import annotations

from src.config.settings import get_settings


def assert_postgres_url() -> None:
    """启动时校验 DATABASE_URL 必须为 PostgreSQL。"""
    url = get_settings().database_url
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return
    raise RuntimeError(
        "本项目仅支持 PostgreSQL。请在 .env 设置例如：\n"
        "DATABASE_URL=postgresql://postgres:密码@localhost:5432/durian_agent"
    )


def database_label() -> str:
    return "postgresql"
