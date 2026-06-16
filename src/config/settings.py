from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8080

    # mock | http（http 尚未对接真实系统，会自动回退 mock）
    tool_adapter: str = "mock"

    trace_api_base_url: str = ""
    mall_api_base_url: str = ""
    order_api_base_url: str = ""

    database_url: str = "postgresql://postgres:postgres@localhost:5432/durian_agent"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    llm_enabled: bool = False

    # langgraph（默认）| rules（无 API Key 时回退）
    agent_mode: str = "langgraph"
    graph_recursion_limit: int = 12
    max_history_turns: int = 10

    session_ttl_hours: int = 24

    # 为 true 时开放 /stats、/users/.../profile 等调试接口详情
    expose_debug_api: bool = False

    # 前端未指定用户时使用的默认 user_id（记忆、历史、订单权限均按此隔离）
    default_user_id: str = "demo_user"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.openai_api_key:
        settings.llm_enabled = True
    return settings


def effective_agent_mode() -> str:
    settings = get_settings()
    if settings.agent_mode == "langgraph" and settings.openai_api_key:
        return "langgraph"
    return "rules"
