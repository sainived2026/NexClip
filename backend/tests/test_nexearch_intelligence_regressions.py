from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"

for path in (str(ROOT), str(BACKEND_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


from nexearch.api.v1 import analyze as analyze_api
from nexearch.api.v1 import intelligence as intelligence_api
from nexearch.api.v1 import data_explorer as data_api
import nexearch.main as nexearch_main


def test_client_intelligence_aggregates_platform_stats_and_dna(monkeypatch):
    class FakeSystemMeta:
        def get_client(self, client_id: str):
            return {"name": "Client A"}

    class FakeStore:
        def __init__(self, client_id: str):
            self.client_id = client_id
            self.base_dir = ROOT / "fake_client"

        def get_manifest(self):
            return {
                "platforms": {
                    "instagram": {"tier_distribution": {"s_tier": 3, "a_tier": 2, "b_tier": 1, "c_tier": 0}},
                    "youtube": {"tier_distribution": {"s_tier": 1, "a_tier": 0, "b_tier": 4, "c_tier": 2}},
                }
            }

        def get_platform_dna(self, platform: str):
            if platform == "instagram":
                return {"version": 2, "dna": {"hook_style": "fast", "cta": "strong"}}
            return None

    monkeypatch.setattr("nexearch.api.v1.intelligence.SystemMeta", FakeSystemMeta)
    monkeypatch.setattr("nexearch.api.v1.intelligence.ClientDataStore", FakeStore)
    monkeypatch.setattr(
        "nexearch.api.v1.intelligence._collect_client_evolution_logs",
        lambda _store: [{"platform": "instagram", "change_summary": "Improved hooks", "timestamp": "2026-04-01T00:00:00+00:00"}],
    )

    payload = asyncio.run(intelligence_api.get_client_intelligence("client_a"))

    assert payload["name"] == "Client A"
    assert payload["stats"] == {"s_tier": 4, "a_tier": 2, "b_tier": 5, "c_tier": 2}
    assert payload["dna"]["version"] == 2
    assert payload["dna"]["brand_guidelines"]["hook_style"] == "fast"
    assert payload["evolution_logs"][0]["change_summary"] == "Improved hooks"


def test_data_explorer_evolution_endpoint_returns_log_entries(monkeypatch):
    class FakeStore:
        def __init__(self, client_id: str):
            self.base_dir = ROOT / "fake_client"

    monkeypatch.setattr("nexearch.api.v1.data_explorer.ClientDataStore", FakeStore)
    monkeypatch.setattr(
        "nexearch.api.v1.data_explorer._load_client_evolution_data",
        lambda _store, platform: {"platform": platform, "entries": [{"cycle_id": "123"}]},
    )

    payload = asyncio.run(data_api.get_client_evolution("client_a", "instagram"))

    assert payload["platform"] == "instagram"
    assert payload["entries"][0]["cycle_id"] == "123"


def test_nexearch_status_reports_threads_and_buffer_capabilities(monkeypatch):
    class FakeSystemMeta:
        def get_all_client_summaries(self):
            return []

        def get_system_status(self):
            return {"ok": True}

    monkeypatch.setattr("nexearch.data.system_meta.SystemMeta", FakeSystemMeta)

    payload = asyncio.run(nexearch_main.system_status())

    assert "threads" in payload["capabilities"]["platforms"]
    assert "buffer" in payload["capabilities"]["scraping_methods"]
    assert "buffer" in payload["capabilities"]["publishing_methods"]


def test_pipeline_status_payload_surfaces_progress_meta():
    payload = analyze_api._status_payload(
        task_id="task-1",
        status="PROGRESS",
        info={
            "stage": "scrape",
            "progress": 18,
            "message": "Scraping posts...",
            "scrape_total": 12,
        },
    )

    assert payload["current_stage"] == "scrape"
    assert payload["progress"] == 18
    assert payload["message"] == "Scraping posts..."
    assert payload["scrape_total"] == 12
    assert payload["analysis_total"] is None
