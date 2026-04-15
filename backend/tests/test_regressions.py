from __future__ import annotations

import sys
import json
import shutil
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"

for path in (str(ROOT), str(BACKEND_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


from app.services.clip_dedup import dedupe_clip_dicts
from app.services.llm_service import LLMService
from app.admin.routes import _restartable_services
from app.admin.routes import _get_service_specs
from app.api.projects import _normalize_project_status_message
from app.api.auth import get_current_user
from app.core.config import Settings
from app.workers.celery_app import celery_app, _ensure_worker_import_paths
from app.schemas import ClipResponse, ProjectResponse, ProjectStatusResponse
from app.services.storage_service import LocalStorageProvider
from app.services.transcription_service import TranscriptionService
from app.workers.tasks import (
    ProjectTaskLock,
    _build_completion_project_update,
    _build_completion_status_message,
)
from app.db.models import User
from nex_agent.llm_provider import _load_env_value, _sanitize_env_value as sanitize_nex_agent_env_value
from nex_agent.conversation_engine import ConversationEngine
from nex_agent.tools.video_tools import _send_proactive_chat
from nexearch.arc.tools.arc_tools import _resolve_playwright_credentials
from nexearch.config import NexearchSettings
from nexearch.tools.llm_router import NexearchLLMRouter
from app.admin.routes import _sanitize_env_value as sanitize_admin_env_value


def test_dedupe_clip_dicts_collapses_duplicate_ranks():
    clips = [
        {"rank": 1, "file_path": "project/clip_01.mp4", "file_path_landscape": ""},
        {"rank": 2, "file_path": "project/clip_02.mp4", "file_path_landscape": "project/clip_02_16x9.mp4"},
        {"rank": 1, "file_path": "project/clip_01.mp4", "file_path_landscape": "project/clip_01_16x9.mp4"},
    ]

    deduped = dedupe_clip_dicts(clips)

    assert [clip["rank"] for clip in deduped] == [1, 2]
    assert deduped[0]["file_path_landscape"] == "project/clip_01_16x9.mp4"


def test_normalize_project_status_message_uses_deduped_clip_count():
    status_message = "Complete! 24 clips generated in 1325s (transcribe=882s, AI=145s, speaker=94s, render=148s)"
    normalized = _normalize_project_status_message(status_message, 12)

    assert normalized.startswith("Complete! 12 clips generated")
    assert "1325s" in normalized


def test_build_completion_status_message_defaults_missing_stage_times_to_zero():
    message = _build_completion_status_message(
        clip_count=12,
        total_time=1325.0,
        transcribe_time=None,
        ai_time=None,
        speaker_time=94.0,
        clip_gen_time=148.0,
    )

    assert message == (
        "Complete! 12 clips generated in 1325s "
        "(transcribe=0s, AI=0s, speaker=94s, render=148s)"
    )


def test_build_completion_project_update_clears_stale_error_message():
    payload = _build_completion_project_update(
        clip_count=12,
        total_time=1325.0,
        transcribe_time=None,
        ai_time=None,
        speaker_time=94.0,
        clip_gen_time=148.0,
    )

    assert payload["status"].value == "COMPLETED"
    assert payload["progress"] == 100
    assert payload["error_message"] is None
    assert payload["status_message"].startswith("Complete! 12 clips generated")


def test_project_task_lock_blocks_duplicate_workers():
    scratch_dir = ROOT / "runtime_test_artifacts" / f"project-lock-{uuid.uuid4().hex}"
    lock_path = scratch_dir / "_pipeline.lock"
    first = ProjectTaskLock(str(lock_path), owner_id="task-1")
    second = ProjectTaskLock(str(lock_path), owner_id="task-2")

    try:
        assert first.acquire() is True
        assert second.acquire() is False

        first.release()
        assert second.acquire() is True
    finally:
        second.release()
        first.release()
        shutil.rmtree(scratch_dir, ignore_errors=True)


def test_project_task_lock_clears_dead_owner_pid():
    scratch_dir = ROOT / "runtime_test_artifacts" / f"project-lock-dead-{uuid.uuid4().hex}"
    lock_path = scratch_dir / "_pipeline.lock"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(
            {
                "owner_id": "dead-task",
                "created_at": "2099-01-01T00:00:00+00:00",
                "pid": 999999,
            }
        ),
        encoding="utf-8",
    )

    lock = ProjectTaskLock(str(lock_path), owner_id="new-task")
    try:
        assert lock.acquire() is True
        assert lock_path.exists() is True
    finally:
        lock.release()
        shutil.rmtree(scratch_dir, ignore_errors=True)


def test_local_whisper_slot_serializes_transcriptions(monkeypatch):
    gate = threading.BoundedSemaphore(value=1)
    monkeypatch.setattr("app.services.transcription_service._local_whisper_gate", gate)
    service = TranscriptionService()
    entered = threading.Event()
    finished = threading.Event()

    def contender():
        with service._local_transcription_slot():
            entered.set()
        finished.set()

    with service._local_transcription_slot():
        thread = threading.Thread(target=contender)
        thread.start()
        time.sleep(0.2)
        assert entered.is_set() is False

    thread.join(timeout=2)
    assert entered.is_set() is True
    assert finished.is_set() is True


def test_project_response_accepts_null_error_message():
    payload = ProjectResponse.model_validate(
        {
            "id": "project_1",
            "title": "Demo",
            "description": "",
            "status": "COMPLETED",
            "progress": 100,
            "status_message": "Complete!",
            "error_message": None,
            "clip_count": 12,
            "created_at": "2026-04-02T00:00:00",
            "updated_at": "2026-04-02T00:00:00",
            "owner_id": "user_1",
            "client_id": None,
        }
    )

    assert payload.error_message is None


def test_project_status_response_accepts_null_error_message():
    payload = ProjectStatusResponse.model_validate(
        {
            "project_id": "project_1",
            "status": "COMPLETED",
            "progress": 100,
            "status_message": "Complete!",
            "error_message": None,
        }
    )

    assert payload.error_message is None


def test_clip_response_accepts_sfcs_metrics_from_pipeline_payload():
    payload = ClipResponse.model_validate(
        {
            "id": "clip_1",
            "rank": 1,
            "start_time": 0,
            "end_time": 30,
            "duration": 30,
            "viral_score": 88,
            "title_suggestion": "Title",
            "hook_text": "Hook",
            "reason": "Reason",
            "file_path": "project/clip_01.mp4",
            "file_path_landscape": "project/clip_01_16x9.mp4",
            "scores_json": "{}",
            "sfcs_version": "director_v4",
            "sfcs_faces_detected": 2,
            "sfcs_frames_with_speaker": 16,
            "sfcs_fallback_frames": 1,
            "caption_style_id": "",
            "caption_status": "none",
            "captioned_video_url": "",
            "captioned_video_url_landscape": "",
            "word_timestamps": "[]",
            "created_at": "2026-04-02T00:00:00",
        }
    )

    assert payload.sfcs_version == "director_v4"
    assert payload.sfcs_faces_detected == 2
    assert payload.sfcs_frames_with_speaker == 16
    assert payload.sfcs_fallback_frames == 1


def test_admin_restart_service_registry_includes_all_agent_services():
    assert set(_restartable_services()) >= {
        "backend",
        "celery",
        "nex_agent",
        "nexearch",
        "arc_agent",
        "all",
    }


def test_admin_celery_restart_spec_listens_on_all_runtime_queues():
    celery_command = _get_service_specs()["celery"]["command"]
    assert "-Q" in celery_command
    assert "video,captions,nexearch,celery" in celery_command


def test_celery_includes_nexearch_pipeline_tasks():
    include = set(celery_app.conf.include or [])
    assert "nexearch.tasks.pipeline" in include


def test_celery_worker_bootstrap_adds_repo_and_backend_to_sys_path(monkeypatch):
    fake_sys_path = ["existing"]
    monkeypatch.setattr("app.workers.celery_app.sys.path", fake_sys_path)
    monkeypatch.setattr(
        "app.workers.celery_app.Path.resolve",
        lambda self: ROOT / "backend" / "app" / "workers" / "celery_app.py",
    )

    _ensure_worker_import_paths()

    assert str(ROOT) in fake_sys_path
    assert str(BACKEND_ROOT) in fake_sys_path


def test_admin_sanitize_env_value_strips_inline_comments_and_quotes():
    raw = " 'AIzaSy-demo-key'   # previous key kept as comment "
    assert sanitize_admin_env_value(raw) == "AIzaSy-demo-key"


def test_nex_agent_load_env_value_sanitizes_os_environ(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", " 'AIzaSy-demo-key'   # old value ")
    assert _load_env_value("GEMINI_API_KEY") == "AIzaSy-demo-key"
    assert sanitize_nex_agent_env_value(" 'https://openrouter.ai/api/v1' ") == "https://openrouter.ai/api/v1"


def test_backend_settings_strip_inline_comments_from_llm_values():
    settings = Settings(
        GEMINI_API_KEY="AIzaSy-demo-key # stale comment",
        OPENROUTER_API_KEY=" 'sk-or-demo-key' ",
        LLM_PROVIDER_PRIORITY=" anthropic , openai , gemini , gemini ",
    )

    assert settings.GEMINI_API_KEY == "AIzaSy-demo-key"
    assert settings.OPENROUTER_API_KEY == "sk-or-demo-key"
    assert settings.llm_provider_priority_list == ["anthropic", "openai", "gemini", "openrouter"]


def test_backend_settings_treat_ved_suffix_on_elevenlabs_key_as_disabled():
    settings = Settings(ELEVENLABS_API_KEY="sk_demo_validlooking_key---Ved")
    assert settings.has_elevenlabs is False


def test_nexearch_settings_strip_inline_comments_from_llm_values():
    settings = NexearchSettings(
        GEMINI_API_KEY=" 'AIzaSy-demo-key' # stale comment ",
        OPENROUTER_API_KEY=" sk-or-demo-key ",
    )

    assert settings.GEMINI_API_KEY == "AIzaSy-demo-key"
    assert settings.OPENROUTER_API_KEY == "sk-or-demo-key"


def test_llm_service_respects_configured_provider_priority(monkeypatch):
    custom_settings = Settings(
        GEMINI_API_KEY="gemini-key",
        OPENROUTER_API_KEY="router-key",
        ANTHROPIC_API_KEY="anthropic-key",
        OPENAI_API_KEY="openai-key",
        LLM_PROVIDER_PRIORITY="anthropic,openai,gemini,openrouter",
    )
    monkeypatch.setattr("app.services.llm_service.settings", custom_settings)

    service = LLMService()

    assert [provider["name"] for provider in service._providers] == [
        "Anthropic",
        "OpenAI",
        "Gemini",
        "OpenRouter",
    ]


def test_nex_agent_provider_respects_llm_priority(monkeypatch):
    values = {
        "GEMINI_API_KEY": "gemini-key",
        "GEMINI_MODEL": "gemini-3.1-flash-lite-preview",
        "OPENROUTER_API_KEY": "router-key",
        "OPENROUTER_MODEL": "openrouter/model",
        "ANTHROPIC_API_KEY": "anthropic-key",
        "ANTHROPIC_MODEL": "claude",
        "OPENAI_API_KEY": "openai-key",
        "OPENAI_MODEL": "gpt",
        "LLM_PROVIDER_PRIORITY": "anthropic,openai,gemini,openrouter",
    }
    monkeypatch.setattr(
        "nex_agent.llm_provider._load_env_value",
        lambda key, default="": values.get(key, default),
    )

    from nex_agent.llm_provider import LLMProvider

    provider = LLMProvider()

    assert [item["name"] for item in provider.providers] == [
        "anthropic",
        "openai",
        "gemini",
        "openrouter",
    ]


def test_get_current_user_prefers_authenticated_token_subject(monkeypatch):
    user = User(
        id="user_clip_aura",
        email="clipaura@example.com",
        username="clip_aura",
        hashed_password="hashed",
        full_name="Clip Aura",
        is_active=True,
    )

    class FakeQuery:
        def __init__(self, result):
            self._result = result

        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return self._result

    class FakeDB:
        def query(self, _model):
            return FakeQuery(user)

    monkeypatch.setattr("app.api.auth.decode_access_token", lambda token: {"sub": "user_clip_aura"})

    current_user = get_current_user(token="jwt-token", db=FakeDB())

    assert current_user.id == "user_clip_aura"


def test_local_storage_provider_defaults_to_backend_storage(monkeypatch):
    monkeypatch.chdir(ROOT)
    provider = LocalStorageProvider()

    assert provider.root == (BACKEND_ROOT / "storage").resolve()


def test_nexearch_llm_router_chat_delegates_to_generate():
    class FakeLLM:
        def generate(self, **kwargs):
            assert kwargs["system_prompt"] == "system"
            assert kwargs["user_message"] == "user"
            return "hello"

    router = object.__new__(NexearchLLMRouter)
    router._llm = FakeLLM()

    assert router.chat(system_prompt="system", user_message="user") == "hello"


def test_nexearch_llm_router_chat_with_tools_formats_tool_calls(monkeypatch):
    class FakeResponse:
        text = ""
        finish_reason = "tool_calls"
        provider = "fake"
        model = "fake-model"
        tool_calls = [
            {"id": "call_1", "name": "arc_nexclip_upload_clips", "arguments": {"client_id": "client_1"}}
        ]

    class FakeProvider:
        def generate_with_tools(self, **kwargs):
            assert kwargs["tools"][0]["function"]["name"] == "arc_nexclip_upload_clips"
            return FakeResponse()

    monkeypatch.setattr("nex_agent.llm_provider.get_llm_provider", lambda: FakeProvider())

    router = object.__new__(NexearchLLMRouter)
    router._llm = None
    result = router.chat_with_tools(
        messages=[{"role": "user", "content": "upload clips"}],
        tools=[{"type": "function", "function": {"name": "arc_nexclip_upload_clips", "parameters": {"type": "object"}}}],
    )

    assert result["tool_calls"][0]["function"]["name"] == "arc_nexclip_upload_clips"
    assert '"client_id": "client_1"' in result["tool_calls"][0]["function"]["arguments"]


def test_extract_json_repairs_truncated_markdown_fenced_payload():
    payload = """```json
{
  "tier": "C",
  "total_score": 57,
  "engagement_score": 0
"""

    assert LLMService.extract_json(payload) == {
        "tier": "C",
        "total_score": 57,
        "engagement_score": 0,
    }


def test_extract_json_repairs_truncated_payload_with_dangling_key():
    payload = """{
  "tier": "C",
  "total_score": 67,
  "engagement_score": 0,
  "hook_"""

    assert LLMService.extract_json(payload) == {
        "tier": "C",
        "total_score": 67,
        "engagement_score": 0,
    }


def test_nex_conversation_engine_chat_returns_only_final_text(monkeypatch):
    engine = ConversationEngine()

    def fake_chat_stream(_user_message: str):
        yield json.dumps({"type": "status", "content": "Executing tool"})
        yield json.dumps({"type": "tool_call", "name": "nexearch_arc_status", "arguments": {}, "result": {"status": "online"}})
        yield json.dumps({"type": "token", "content": "Arc "})
        yield json.dumps({"type": "token", "content": "is healthy."})
        yield json.dumps({"type": "done"})

    monkeypatch.setattr(engine, "chat_stream", fake_chat_stream)

    assert engine.chat("Check Arc") == "Arc is healthy."


def test_resolve_playwright_credentials_prefers_client_upload_config(monkeypatch):
    client_id = "client_123"
    scratch_root = ROOT / "sandbox-fixture-root"
    expected_path = scratch_root / "clients" / client_id / "upload_methods.json"
    payload = """
    {
      "instagram": {
        "method": "playwright",
        "playwright": {
          "username": "local-user",
          "password": "local-pass"
        }
      }
    }
    """.strip()

    monkeypatch.setattr(
        "nexearch.arc.tools.arc_tools.Path.resolve",
        lambda self: scratch_root / "nexearch" / "arc" / "tools" / "arc_tools.py",
    )
    monkeypatch.setattr(
        "pathlib.Path.exists",
        lambda self: self == expected_path,
    )
    monkeypatch.setattr(
        "pathlib.Path.read_text",
        lambda self, encoding="utf-8": payload if self == expected_path else "",
    )

    assert _resolve_playwright_credentials(client_id, "instagram") == {
        "username": "local-user",
        "password": "local-pass",
        "platform": "instagram",
    }


def test_resolve_playwright_credentials_falls_back_to_vault(monkeypatch):
    monkeypatch.setattr(
        "nexearch.tools.credential_vault.get_credentials",
        lambda platform: {"username": "env-user", "password": "env-pass", "platform": platform},
    )

    credentials = _resolve_playwright_credentials("missing_client", "instagram")
    assert credentials["username"] == "env-user"
    assert credentials["platform"] == "instagram"


def test_send_proactive_chat_persists_and_dispatches_to_target_conversation(monkeypatch):
    saved_messages = []
    dispatched = []

    class FakeStreamingManager:
        def save_assistant_message(self, message_id, conversation_id, user_id, content, rich_type="", rich_data=None):
            saved_messages.append({
                "message_id": message_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "content": content,
                "rich_type": rich_type,
                "rich_data": rich_data,
            })

    class FakeAgent:
        streaming_manager = FakeStreamingManager()

    monkeypatch.setattr("nex_agent.core.get_nex_agent", lambda: FakeAgent())
    monkeypatch.setattr(
        "nex_agent.websocket.ws_manager.dispatch_to_user",
        lambda user_id, payload: dispatched.append((user_id, payload)),
    )

    _send_proactive_chat(
        "Clips generated successfully.",
        target_context={"user_id": "user_1", "conversation_id": "conv_1"},
    )

    assert saved_messages[0]["conversation_id"] == "conv_1"
    assert saved_messages[0]["user_id"] == "user_1"
    assert saved_messages[0]["content"] == "Clips generated successfully."
    assert dispatched[0][0] == "user_1"
    assert dispatched[0][1]["content"] == "Clips generated successfully."
