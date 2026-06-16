from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

from src.graph.context import session_id_from_config, user_id_from_config
from src.graph.nodes import tools_node


def test_user_id_from_invoke_config() -> None:
    config = {"configurable": {"user_id": "demo_user", "session_id": "sess_abc"}}
    assert user_id_from_config(config) == "demo_user"
    assert session_id_from_config(config) == "sess_abc"


def test_tools_node_reads_user_id_from_config() -> None:
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_order_detail",
                        "args": {"order_id": "ORD_10001"},
                        "id": "call_1",
                        "type": "tool_call",
                    }
                ],
            )
        ],
        "tool_results": [],
    }
    config = {"configurable": {"user_id": "demo_user", "session_id": "sess_test"}}

    result = tools_node(state, config)

    assert result["tool_results"]
    assert '"success": true' in result["tool_results"][0]["result"]
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], ToolMessage)
