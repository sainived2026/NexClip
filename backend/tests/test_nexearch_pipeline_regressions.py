from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from celery import Celery

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"

for path in (str(ROOT), str(BACKEND_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


from nexearch.api.v1 import analyze as analyze_api
from nexearch.agents.agent_bridge import NexClipBridgeAgent
from nexearch.agents.agent_publish import PublisherAgent
from nexearch.agents.state import PipelineState
from nexearch.arc.sub_agents.manager import SubAgentRegistry
from nexearch.arc.tool_executor import ArcToolExecutor
from nexearch.config import NexearchSettings
from nexearch.arc.tools.arc_tools import (
    _resolve_playwright_credentials,
    metricool_accessible_accounts,
    nexclip_upload_clips,
    pipeline_trigger,
)
from nexearch.tasks import pipeline as pipeline_tasks
from nexearch.tools.metricool import get_metricool_client
from nexearch.tools.publishers.playwright_publisher import _describe_login_failure
from nexearch.tools.publishers.publisher import _compose_caption_text, create_publisher
from nexearch.tools.scrapers.crawlee_scraper import CrawleePlaywrightScraper


def test_resolve_pipeline_context_backfills_account_metadata(monkeypatch):
    class FakeStore:
        def __init__(self, client_id: str):
            self.client_id = client_id

        def get_manifest(self):
            return {"account_handle": "client_handle"}

        def get_credentials(self, platform: str):
            return {"account_url": "https://instagram.com/client_handle", "login_username": "user"}

    monkeypatch.setattr("nexearch.api.v1.analyze.ClientDataStore", FakeStore)

    resolved = analyze_api._resolve_pipeline_context({
        "client_id": "client_a",
        "platform": "instagram",
    })

    assert resolved["account_handle"] == "client_handle"
    assert resolved["account_url"] == "https://instagram.com/client_handle"
    assert resolved["credentials"]["login_username"] == "user"
    assert resolved["platform_credentials"]["instagram"]["account_url"] == "https://instagram.com/client_handle"


def test_bridge_uses_platform_evolution_when_flat_list_empty():
    class FakeLLM:
        def generate_json(self, **kwargs):
            user_message = kwargs["user_message"]
            assert "pattern shift" in user_message
            return {
                "writing_directives": {},
                "nexclip_system_prompt_injection": "bridge prompt",
            }

    agent = NexClipBridgeAgent()
    agent._llm = FakeLLM()
    state = PipelineState(
        account_handle="client_handle",
        platform="instagram",
        account_dna={"content_dna_summary": "Podcast clips"},
        tier_distribution={"S": 1, "A": 0, "B": 0, "C": 0},
        platform_evolution={
            "instagram": {
                "changes": {"change_reason": "pattern shift"},
                "cycle_id": "cycle-1",
                "mode": "client",
            }
        },
    )

    result = asyncio.run(agent.run(state))

    assert result.nexclip_system_prompt == "bridge prompt"
    assert result.directive_id


def test_resolve_playwright_credentials_prefers_client_store_logins(monkeypatch):
    class FakeStore:
        def __init__(self, client_id: str):
            self.client_id = client_id

        def get_credentials(self, platform: str):
            return {"login_username": "client-user", "login_password": "client-pass"}

    monkeypatch.setattr("nexearch.data.client_store.ClientDataStore", FakeStore)

    credentials = _resolve_playwright_credentials("client_a", "instagram")

    assert credentials == {
        "username": "client-user",
        "password": "client-pass",
        "platform": "instagram",
    }


def test_pipeline_trigger_resolves_account_context_before_queue(monkeypatch):
    class FakeStore:
        def __init__(self, client_id: str):
            self.client_id = client_id

        def get_manifest(self):
            return {"account_handle": "resolved_handle"}

        def get_credentials(self, platform: str):
            return {"account_url": "https://instagram.com/resolved_handle", "login_username": "user"}

    queued = {}

    class FakeTask:
        id = "task-123"

    class FakeCeleryTask:
        @staticmethod
        def delay(payload):
            queued["payload"] = payload
            return FakeTask()

    monkeypatch.setattr("nexearch.data.client_store.ClientDataStore", FakeStore)
    monkeypatch.setattr("nexearch.tasks.pipeline.run_pipeline_task", FakeCeleryTask())

    response = pipeline_trigger("client_a", "instagram", dry_run=False)

    assert response["task_id"] == "task-123"
    assert queued["payload"]["account_handle"] == "resolved_handle"
    assert queued["payload"]["account_url"] == "https://instagram.com/resolved_handle"
    assert queued["payload"]["platform_credentials"]["instagram"]["login_username"] == "user"


def test_count_evolution_entries_falls_back_to_platform_evolution():
    class FakeState:
        evolution_changes = []
        platform_evolution = {"instagram": {"changes": {}}}

    assert pipeline_tasks._count_evolution_entries(FakeState()) == 1


def test_publisher_agent_does_not_record_fake_publish_without_media_asset():
    class FakeLLM:
        def generate(self, **kwargs):
            return "generated"

    agent = PublisherAgent()
    agent._llm = FakeLLM()
    state = PipelineState(
        client_id="client_a",
        platform="instagram",
        account_handle="client",
        publishing_method="metricool",
        clip_directive={"writing_directives": {}},
        directive_id="directive-1",
        account_dna={"content_dna_summary": "Podcast clips"},
    )

    result = asyncio.run(agent.run(state))

    assert result.published_posts == []
    assert result.publish_errors == [
        "Publish stage skipped: no media asset was provided for this pipeline run"
    ]


def test_metricool_publisher_uses_client_specific_api_key(monkeypatch):
    observed = {}

    class FakeMetricoolClient:
        def __init__(self, api_token):
            self._token = api_token

        @property
        def is_configured(self):
            return bool(self._token)

        async def find_profile(self, **kwargs):
            observed["lookup"] = kwargs
            return {"id": "brand-42", "label": "brand-42", "userId": "user-42"}

        async def add_post(self, **kwargs):
            observed["token"] = self._token
            observed["brand_id"] = kwargs["brand_id"]
            observed["user_id"] = kwargs["user_id"]
            observed["network"] = kwargs["network"]
            return {"id": "metricool-post-1"}

    monkeypatch.setattr(
        "nexearch.tools.metricool.get_metricool_client",
        lambda access_token=None: FakeMetricoolClient(access_token),
    )

    publisher = create_publisher(
        "metricool",
        "instagram",
        "client_a",
        metricool_api_key="client-metricool-token",
    )

    assert asyncio.run(publisher.check_availability()) is True

    result = asyncio.run(
        publisher.publish(
            video_url="https://cdn.example.com/video.mp4",
            caption="caption",
            credentials={
                "metricool_api_key": "client-metricool-token",
                "account_url": "https://instagram.com/client_a",
            },
        )
    )

    assert result.success is True
    assert observed["lookup"]["account_url"] == "https://instagram.com/client_a"
    assert observed == {
        "lookup": {
            "account_url": "https://instagram.com/client_a",
            "account_handle": "client_a",
            "platform": "instagram",
        },
        "token": "client-metricool-token",
        "brand_id": "brand-42",
        "user_id": "user-42",
        "network": "instagram",
    }


def test_metricool_publisher_auto_resolves_matching_profile(monkeypatch):
    observed = {}

    class FakeMetricoolClient:
        def __init__(self, api_token):
            self._token = api_token

        @property
        def is_configured(self):
            return True

        async def find_profile(self, **kwargs):
            observed["lookup"] = kwargs
            return {"id": 6071644, "label": "clipaura2026", "userId": 4453754}

        async def add_post(self, **kwargs):
            observed["publish"] = kwargs
            return {"uuid": "scheduled-post-1"}

    monkeypatch.setattr(
        "nexearch.tools.metricool.get_metricool_client",
        lambda access_token=None: FakeMetricoolClient(access_token),
    )

    publisher = create_publisher("metricool", "instagram", "clip_aura", metricool_api_key="token-1")
    result = asyncio.run(
        publisher.publish(
            video_url="https://cdn.example.com/video.mp4",
            caption="caption",
            credentials={
                "metricool_api_key": "token-1",
                "account_url": "https://instagram.com/clipaura2026",
            },
        )
    )

    assert result.success is True
    assert result.metricool_post_id == "scheduled-post-1"
    assert observed["publish"]["brand_id"] == "6071644"
    assert observed["publish"]["user_id"] == "4453754"
    assert observed["lookup"]["platform"] == "instagram"
    assert observed["lookup"]["account_url"] == "https://instagram.com/clipaura2026"


def test_metricool_publisher_uploads_local_files_and_leads_with_title(monkeypatch):
    observed = {}
    local_clip = ROOT / "runtime_logs" / "test_metricool_local_clip.mp4"
    local_clip.parent.mkdir(parents=True, exist_ok=True)
    local_clip.write_bytes(b"video-bytes")

    class FakeMetricoolClient:
        @property
        def is_configured(self):
            return True

        async def find_profile(self, **kwargs):
            return {"id": 6071644, "label": "clipaura2026", "userId": 4453754}

        async def upload_media_file(self, file_path: str):
            observed["uploaded_path"] = file_path
            return "https://static.metricool.com/video/clip.mp4"

        async def add_post(self, **kwargs):
            observed["publish"] = kwargs
            return {"id": "metricool-post-2"}

    monkeypatch.setattr(
        "nexearch.tools.metricool.get_metricool_client",
        lambda access_token=None: FakeMetricoolClient(),
    )

    try:
        publisher = create_publisher("metricool", "instagram", "clip_aura", metricool_api_key="token-1")
        result = asyncio.run(
            publisher.publish(
                video_url=str(local_clip),
                title="Clip Title With Hook",
                caption="Longer supporting caption",
                hashtags=["space", "lesson"],
                credentials={
                    "metricool_api_key": "token-1",
                    "account_url": "https://instagram.com/clipaura2026",
                },
            )
        )
        assert result.success is True
        assert observed["uploaded_path"] == str(local_clip)
        assert observed["publish"]["video_url"] == "https://static.metricool.com/video/clip.mp4"
        assert observed["publish"]["text"].startswith("Clip Title With Hook")
        assert "#space #lesson" in observed["publish"]["text"]
    finally:
        local_clip.unlink(missing_ok=True)


def test_metricool_accessible_accounts_uses_client_metricool_key(monkeypatch):
    class FakeStore:
        def __init__(self, client_id: str):
            self.client_id = client_id

        def get_credentials(self, platform: str):
            if platform == "instagram":
                return {"metricool_api_key": "client-metricool-token"}
            return {}

    class FakeMetricoolClient:
        async def list_profiles(self):
            return [{"id": 6071644, "userId": 4453754, "label": "test", "instagram": "clipaura2026"}]

    monkeypatch.setattr("nexearch.data.client_store.ClientDataStore", FakeStore)
    monkeypatch.setattr(
        "nexearch.tools.metricool.get_metricool_client",
        lambda access_token=None: FakeMetricoolClient(),
    )

    result = metricool_accessible_accounts("clip_aura", "instagram")

    assert result["client_id"] == "clip_aura"
    assert result["accounts"][0]["profiles"][0]["instagram"] == "clipaura2026"


def test_compose_caption_text_strips_inline_hashtag_block_before_appending():
    composed = _compose_caption_text(
        platform="instagram",
        title="Specific Clip Hook",
        caption="This clip is about one exact insight.\n\n#generic #wrong",
        hashtags=["specific", "better"],
    )

    assert composed.startswith("Specific Clip Hook")
    assert "#generic #wrong" not in composed
    assert composed.endswith("#specific #better")


def test_metricool_client_factory_accepts_client_specific_tokens():
    default_client = get_metricool_client()
    custom_client = get_metricool_client(access_token="client-specific-token")

    assert default_client is get_metricool_client()
    assert custom_client._token == "client-specific-token"
    assert custom_client is get_metricool_client(access_token="client-specific-token")
    assert custom_client is not default_client


def test_nexearch_clients_dir_is_resolved_relative_to_backend_env_root():
    settings = NexearchSettings(NEXEARCH_CLIENTS_DIR="./nexearch_data")

    assert Path(settings.NEXEARCH_CLIENTS_DIR) == (ROOT / "nexearch_data").resolve()


def test_crawlee_linkedin_candidates_convert_to_raw_posts():
    scraper = CrawleePlaywrightScraper("linkedin", "client_a")

    posts = scraper._linkedin_posts_from_candidates(
        [
            {
                "href": "https://www.linkedin.com/posts/rajshamani_founders-need-distribution-activity-7314625257274079232-X6M7",
                "text": "Founders need distribution before they need more features.",
                "title": "",
            }
        ],
        max_posts=5,
        account_url="https://www.linkedin.com/in/rajshamani/",
    )

    assert len(posts) == 1
    assert posts[0].platform == "linkedin"
    assert posts[0].post_id == "rajshamani_founders-need-distribution-activity-7314625257274079232-X6M7"
    assert posts[0].account_id == "rajshamani"
    assert posts[0].caption.startswith("Founders need distribution")


def test_crawlee_facebook_candidates_convert_to_raw_posts():
    scraper = CrawleePlaywrightScraper("facebook", "client_a")

    posts = scraper._facebook_posts_from_candidates(
        [
            {
                "href": "https://www.facebook.com/rajshamani/posts/10161047000000000",
                "text": "If you can explain it simply, you understand it well.",
                "title": "",
            }
        ],
        max_posts=5,
        account_url="https://www.facebook.com/rajshamani/",
    )

    assert len(posts) == 1
    assert posts[0].platform == "facebook"
    assert posts[0].post_id == "10161047000000000"
    assert posts[0].account_id == "rajshamani"
    assert posts[0].format == "facebook_post"


def test_arc_tool_registration_exposes_threads_and_buffer_contracts():
    from nexearch.arc.tools.arc_tools import register_all_arc_tools

    executor = ArcToolExecutor()
    register_all_arc_tools(executor)

    pipeline_trigger_tool = executor.get_tool_info("arc_pipeline_trigger")
    scrape_only_tool = executor.get_tool_info("arc_pipeline_scrape_only")
    upload_tool = executor.get_tool_info("arc_nexclip_upload_clips")
    creds_tool = executor.get_tool_info("arc_check_credentials")
    metricool_accounts_tool = executor.get_tool_info("arc_metricool_accessible_accounts")

    assert "threads" in pipeline_trigger_tool["parameters"]["properties"]["platform"]["enum"]
    assert "buffer" in scrape_only_tool["parameters"]["properties"]["method"]["enum"]
    assert "crawlee_playwright" in scrape_only_tool["parameters"]["properties"]["method"]["enum"]
    assert "buffer" in upload_tool["parameters"]["properties"]["method"]["enum"]
    assert "threads" in creds_tool["parameters"]["properties"]["platform"]["enum"]
    assert metricool_accounts_tool["parameters"]["required"] == ["client_id"]


def test_arc_sub_agent_registry_reports_threads_and_buffer_capabilities():
    scrape = SubAgentRegistry.BUILT_IN_AGENTS["scrape_agent"]
    publisher = SubAgentRegistry.BUILT_IN_AGENTS["publisher_agent"]

    assert "threads" in scrape["platforms"]
    assert "buffer_scrape" in scrape["capabilities"]
    assert "buffer_publish" in publisher["capabilities"]


def test_arc_nexclip_upload_clips_accepts_string_clip_paths(monkeypatch):
    observed = {}

    def fake_playwright_upload(platform, clip_list, title, description, caption, client_id=""):
        observed["platform"] = platform
        observed["clip_list"] = clip_list
        observed["client_id"] = client_id
        return {"uploaded": len(clip_list), "results": [{"success": True}]}

    monkeypatch.setattr("nexearch.arc.tools.arc_tools._playwright_upload", fake_playwright_upload)

    result = nexclip_upload_clips(
        client_id="client_a",
        platform="instagram",
        clips='["C:/clips/clip1.mp4", "C:/clips/clip2.mp4"]',
        method="playwright",
    )

    assert result["uploaded"] == 2
    assert observed["platform"] == "instagram"
    assert observed["client_id"] == "client_a"
    assert observed["clip_list"] == [
        {"path": "C:/clips/clip1.mp4", "absolute_path": "C:/clips/clip1.mp4"},
        {"path": "C:/clips/clip2.mp4", "absolute_path": "C:/clips/clip2.mp4"},
    ]


def test_arc_nexclip_upload_clips_metricool_uses_generated_metadata_and_client_credentials(monkeypatch):
    observed = {}

    class FakePublisher:
        async def publish(self, **kwargs):
            observed["publish_kwargs"] = kwargs
            return type(
                "Result",
                (),
                {"success": True, "error_message": "", "raw_response": {}},
            )()

    async def fake_generate_publish_metadata(**kwargs):
        return {
            "title": "Generated Hook Title",
            "caption": "Generated polished caption",
            "description": "Generated description",
            "hashtags": ["clipaura", "viral"],
        }

    monkeypatch.setattr(
        "nexearch.arc.tools.arc_tools._load_client_platform_credentials",
        lambda client_id, platform: {
            "metricool_api_key": "client-token",
            "account_url": "https://instagram.com/clipaura2026",
        },
    )
    monkeypatch.setattr(
        "nexearch.arc.tools.arc_tools._generate_publish_metadata",
        fake_generate_publish_metadata,
    )
    monkeypatch.setattr(
        "nexearch.tools.publishers.publisher.create_publisher",
        lambda method, platform, client_id, **kwargs: FakePublisher(),
    )

    result = nexclip_upload_clips(
        client_id="clip_aura",
        platform="instagram",
        clips='["C:/clips/clip1.mp4"]',
        method="metricool",
    )

    assert result["uploaded"] == 1
    assert observed["publish_kwargs"]["credentials"]["metricool_api_key"] == "client-token"
    assert observed["publish_kwargs"]["title"] == "Generated Hook Title"
    assert observed["publish_kwargs"]["caption"] == "Generated polished caption"
    assert observed["publish_kwargs"]["hashtags"] == ["clipaura", "viral"]


def test_describe_login_failure_reports_platform_specific_states():
    assert _describe_login_failure(
        "instagram",
        "https://www.instagram.com/auth_platform/recaptcha/",
        "",
    ) == "Instagram login blocked by CAPTCHA/reCAPTCHA challenge"
    assert _describe_login_failure(
        "linkedin",
        "https://www.linkedin.com/login",
        "We've emailed a one-time link to your primary email address",
    ) == "LinkedIn requested an email-based verification step instead of a normal sign-in"
    assert _describe_login_failure(
        "threads",
        "https://www.threads.com/",
        "logged_out",
    ) == "Threads returned to a logged-out state after login submit"


def test_get_pipeline_status_handles_disabled_result_backend(monkeypatch):
    fake_app = Celery("nexearch-test")
    monkeypatch.setattr("nexearch.tasks.pipeline.celery_app", fake_app)

    result = asyncio.run(analyze_api.get_pipeline_status("task-123"))

    assert result["task_id"] == "task-123"
    assert result["status"] == "UNKNOWN"
    assert "disabled" in result["info"]["warning"].lower()
