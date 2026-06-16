from __future__ import annotations

import asyncio
import os

import pytest

os.environ["AGENT_MODE"] = "rules"
os.environ["OPENAI_API_KEY"] = ""
os.environ["LLM_ENABLED"] = "false"


@pytest.fixture
def agent_handle():
    """在同步测试中调用异步 orchestrator.handle。"""
    from src.orchestrator.orchestrator import orchestrator

    def _call(message: str, **kwargs):
        return asyncio.run(orchestrator.handle(message, **kwargs))

    return _call
