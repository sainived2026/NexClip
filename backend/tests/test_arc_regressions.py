from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"

for path in (str(ROOT), str(BACKEND_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


from nexearch.arc import api as arc_api
from nexearch.arc.api import _collect_chat_stream_result
from nexearch.arc.conversation_engine import ArcConversationEngine
from nexearch.arc.streaming_manager import ArcStreamingManager


class _FakeAgent:
    def __init__(self, chunks):
        self._chunks = chunks

    def chat_stream(self, message: str, context=None):
        yield from self._chunks


class _FakeToolExecutor:
    def get_tools_for_llm(self):
        return []

    def get_tool_count(self):
        return 0

    def execute(self, tool_name: str, arguments):
        return {"ok": True}


def test_collect_chat_stream_result_aggregates_tokens_and_tool_calls():
    agent = _FakeAgent([
        json.dumps({"type": "tool_call", "name": "arc_search_tools", "arguments": {"query": "upload"}, "status": "executing"}),
        json.dumps({"type": "tool_call", "name": "arc_search_tools", "arguments": {"query": "upload"}, "result": {"tools": 1}, "status": "complete"}),
        json.dumps({"type": "token", "content": "Arc "}),
        json.dumps({"type": "token", "content": "ready"}),
        json.dumps({"type": "done", "tool_calls": 1}),
    ])

    result = _collect_chat_stream_result(agent, "hello")

    assert result["response"] == "Arc ready"
    assert "Executed `arc_search_tools`" in result["thinking_content"]
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["name"] == "arc_search_tools"


def test_arc_chat_route_persists_sync_response_text(monkeypatch):
    class FakeStreamingManager:
        def __init__(self):
            self.finalized = []

        def create_conversation(self, conversation_id: str, user_id: str = "admin"):
            return None

        def save_user_message(self, message_id: str, conversation_id: str, user_id: str, content: str):
            return None

        def create_stream(self, message_id: str, conversation_id: str, user_id: str):
            self.stream_id = message_id

        def finalize_stream(self, message_id: str, tool_calls=None, error=None, final_content=None, thinking_content=""):
            self.finalized.append((message_id, tool_calls, error, final_content, thinking_content))

    class FakeAgent:
        def __init__(self, streaming_manager):
            self.streaming_manager = streaming_manager

        def chat_stream(self, message: str, context=None):
            yield json.dumps({"type": "token", "content": "Arc "})
            yield json.dumps({"type": "token", "content": "ready"})
            yield json.dumps({"type": "done", "tool_calls": 0})

    fake_sm = FakeStreamingManager()
    fake_agent = FakeAgent(fake_sm)
    monkeypatch.setattr("nexearch.arc.core.get_arc_agent", lambda: fake_agent)

    response = asyncio.run(arc_api.chat(arc_api.ChatRequest(message="hello")))

    assert response.response == "Arc ready"
    assert fake_sm.finalized[0][0] == fake_sm.stream_id
    assert fake_sm.finalized[0][3] == "Arc ready"


def test_arc_streaming_manager_conversation_crud_and_message_shape():
    storage_root = ROOT / "backend" / "tests" / ".tmp" / f"arc-streams-{uuid.uuid4().hex}"
    storage_root.mkdir(parents=True, exist_ok=True)
    try:
        manager = ArcStreamingManager(storage_path=str(storage_root))
        conv_id = "conv_123"

        manager.create_conversation(conv_id, "admin")
        manager.save_user_message("user_1", conv_id, "admin", "hello arc")
        manager.create_stream("assistant_1", conv_id, "admin")
        manager.append_tokens("assistant_1", "hello back")
        manager.finalize_stream("assistant_1")

        conversations = manager.list_conversations()
        assert conversations[0]["id"] == conv_id
        assert conversations[0]["message_count"] == 2
        assert conversations[0]["title"].startswith("hello arc")

        messages = manager.get_conversation_messages(conv_id)
        assert messages[0]["id"] == "user_1"
        assert messages[0]["role"] == "user"
        assert messages[1]["id"] == "assistant_1"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "hello back"

        assert manager.delete_conversation(conv_id) is True
        assert manager.get_conversation_messages(conv_id) == []
    finally:
        shutil.rmtree(storage_root, ignore_errors=True)


def test_arc_conversation_engine_falls_back_to_generate_when_chat_method_missing(monkeypatch):
    class FakeRouter:
        def chat_with_tools(self, **kwargs):
            raise AttributeError("tool calling unavailable")

        def generate(self, **kwargs):
            return "Arc fallback works"

    monkeypatch.setattr("nexearch.tools.llm_router.get_nexearch_llm", lambda: FakeRouter())

    engine = ArcConversationEngine(tool_executor=_FakeToolExecutor(), memory=None)
    chunks = list(engine.chat_stream("Say something"))
    token_text = "".join(
        json.loads(chunk).get("content", "")
        for chunk in chunks
        if json.loads(chunk).get("type") == "token"
    )

    assert "Arc fallback works" in token_text
    assert json.loads(chunks[-1])["type"] == "done"


def test_arc_conversation_engine_preserves_tool_name_in_tool_result_messages(monkeypatch):
    class FakeRouter:
        def __init__(self):
            self.calls = 0

        def chat_with_tools(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "arc_list_sub_agents",
                                "arguments": "{}",
                            },
                        }
                    ],
                }

            tool_messages = [m for m in kwargs["messages"] if m.get("role") == "tool"]
            assert tool_messages[-1]["name"] == "arc_list_sub_agents"
            assert tool_messages[-1]["tool_call_id"] == "call_1"
            return {"content": "Arc is ready", "tool_calls": []}

    monkeypatch.setattr("nexearch.tools.llm_router.get_nexearch_llm", lambda: FakeRouter())

    engine = ArcConversationEngine(tool_executor=_FakeToolExecutor(), memory=None)
    chunks = list(engine.chat_stream("Check your sub-agents"))
    token_text = "".join(
        json.loads(chunk).get("content", "")
        for chunk in chunks
        if json.loads(chunk).get("type") == "token"
    )

    assert "Arc is ready" in token_text
