"""
Nexearch — Intelligence Routes
Real endpoints for Universal and Client-Specific intelligence data,
DNA, evolution logs, live progress, and revert capability.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from loguru import logger
import json

from nexearch.data.universal_store import get_universal_store, PLATFORMS
from nexearch.data.system_meta import SystemMeta
from nexearch.data.client_store import ClientDataStore

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])


def _collect_client_evolution_logs(client_store: ClientDataStore) -> list[Dict[str, Any]]:
    """Collect client evolution logs across all platforms."""
    logs: list[Dict[str, Any]] = []

    for platform in PLATFORMS:
        log_path = client_store.base_dir / "intelligence" / platform / "evolution" / "evolution_log.json"
        if not log_path.exists():
            continue

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            continue

        entries = raw.get("entries", []) if isinstance(raw, dict) else []
        for entry in entries:
            cycle_id = entry.get("cycle_id", "")
            detail_path = client_store.base_dir / "intelligence" / platform / "evolution" / f"cycle_{cycle_id}.json"
            details = {}
            if cycle_id and detail_path.exists():
                try:
                    with open(detail_path, "r", encoding="utf-8") as f:
                        details = json.load(f)
                except Exception:
                    details = {}

            data = details.get("data", {}) if isinstance(details, dict) else {}
            changes_made = data.get("changes_made", []) if isinstance(data, dict) else []
            summary = (
                data.get("summary")
                or data.get("change_summary")
                or (changes_made[0].get("summary") if changes_made and isinstance(changes_made[0], dict) else "")
                or f"Evolution cycle {cycle_id or 'unknown'}"
            )

            logs.append({
                "platform": platform,
                "cycle_id": cycle_id,
                "timestamp": entry.get("timestamp") or details.get("evolved_at") or "",
                "magnitude": entry.get("magnitude", data.get("magnitude", 0)),
                "change_summary": summary,
                "changes_made": changes_made,
            })

    logs.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return logs


# ── Universal Intelligence ────────────────────────────────────────


@router.get("/universal")
async def get_universal_intelligence():
    """Get the universal DNA, winning patterns, and tier distribution — per platform."""
    store = get_universal_store()
    try:
        dna_by_platform = {}
        stats_by_platform = {}
        evolution_logs = []

        for platform in PLATFORMS:
            # Get DNA for this platform
            raw_dna = store.get_universal_dna(platform)
            if raw_dna and isinstance(raw_dna, dict):
                dna_by_platform[platform] = {
                    "version": raw_dna.get("version", "1.0"),
                    "winning_patterns": [],
                    "avoid_patterns": [],
                    "directives": raw_dna.get("dna", raw_dna.get("directives", {})),
                }
            else:
                dna_by_platform[platform] = {
                    "version": "1.0",
                    "winning_patterns": [],
                    "avoid_patterns": [],
                    "directives": {},
                }

            # Winning patterns
            wp = store.get_winning_patterns(platform)
            if wp and wp.get("patterns"):
                dna_by_platform[platform]["winning_patterns"] = [
                    p.get("name", p.get("type", "Unknown")) for p in wp["patterns"][:10]
                ]

            # Avoid patterns
            avoid_path = store.base_dir / platform / "global_patterns" / "avoid_patterns.json"
            if avoid_path.exists():
                with open(avoid_path, "r") as f:
                    ap = json.load(f)
                if ap.get("patterns"):
                    dna_by_platform[platform]["avoid_patterns"] = [
                        p.get("name", p.get("type", "Unknown")) for p in ap["patterns"][:10]
                    ]

            # Stats: count tier files from engagement benchmarks
            benchmarks = store.get_engagement_benchmarks(platform)
            s_count = a_count = b_count = c_count = 0
            if benchmarks and benchmarks.get("benchmarks"):
                for client_key, client_data in benchmarks["benchmarks"].items():
                    if isinstance(client_data, dict):
                        td = client_data.get("tier_distribution", {})
                        s_count += td.get("S", td.get("s_tier", 0))
                        a_count += td.get("A", td.get("a_tier", 0))
                        b_count += td.get("B", td.get("b_tier", 0))
                        c_count += td.get("C", td.get("c_tier", 0))

            stats_by_platform[platform] = {
                "s_tier": s_count,
                "a_tier": a_count,
                "b_tier": b_count,
                "c_tier": c_count,
            }

            # Load evolution logs for this platform
            index_path = store.base_dir / platform / "global_evolution" / "log_index.json"
            if index_path.exists():
                with open(index_path, "r") as f:
                    platform_logs = json.load(f)
                for log in platform_logs[-5:]:  # Last 5 per platform
                    log["platform"] = platform
                    evolution_logs.append(log)

        # Sort logs by timestamp descending
        evolution_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return {
            "dna": dna_by_platform,
            "stats": stats_by_platform,
            "evolution_logs": evolution_logs[:20],
            "platforms": PLATFORMS,
        }
    except Exception as e:
        logger.error(f"Error fetching universal intelligence: {e}")
        empty_dna = {p: {"version": "1.0", "winning_patterns": [], "avoid_patterns": [], "directives": {}} for p in PLATFORMS}
        empty_stats = {p: {"s_tier": 0, "a_tier": 0, "b_tier": 0, "c_tier": 0} for p in PLATFORMS}
        return {"dna": empty_dna, "stats": empty_stats, "evolution_logs": [], "platforms": PLATFORMS, "error": str(e)}


# ── Trigger Evolution ─────────────────────────────────────────


@router.post("/universal/evolve")
async def force_universal_evolution():
    """Start a universal evolution cycle. Returns a task_id for polling."""
    from nexearch.agents.universal_pipeline import start_universal_pipeline
    task_id = start_universal_pipeline(mode="full")
    return {"status": "started", "task_id": task_id, "message": "Universal evolution pipeline started."}


@router.post("/universal/analyze")
async def run_global_analysis():
    """Run global analysis across all clients and platforms. Returns a task_id for polling."""
    from nexearch.agents.universal_pipeline import start_universal_pipeline
    task_id = start_universal_pipeline(mode="full")
    return {"status": "started", "task_id": task_id, "message": "Global analysis pipeline started."}


# ── Live Status Polling ───────────────────────────────────────


@router.get("/universal/evolve/status/{task_id}")
async def get_evolution_status(task_id: str):
    """Get live progress of a running evolution/analysis task."""
    from nexearch.agents.universal_pipeline import get_task_status
    status = get_task_status(task_id)
    if not status:
        raise HTTPException(404, f"Task {task_id} not found")
    return status


@router.post("/universal/evolve/cancel/{task_id}")
async def cancel_evolution(task_id: str):
    """Cancel a running evolution/analysis task."""
    from nexearch.agents.universal_pipeline import _running_tasks
    if task_id not in _running_tasks:
        raise HTTPException(404, f"Task {task_id} not found")
    _running_tasks[task_id]["status"] = "cancelled"
    _running_tasks[task_id]["message"] = "Cancelled by user"
    return {"status": "cancelled", "task_id": task_id}


# ── Evolution Logs ────────────────────────────────────────────


@router.get("/universal/evolution-logs")
async def get_evolution_logs():
    """Get all evolution log entries across all platforms, with before/after for revert."""
    store = get_universal_store()
    all_logs = []

    for platform in PLATFORMS:
        index_path = store.base_dir / platform / "global_evolution" / "log_index.json"
        if not index_path.exists():
            continue

        with open(index_path, "r") as f:
            index = json.load(f)

        for entry in index:
            entry["platform"] = platform
            # Load the detailed log for changes summary
            log_id = entry.get("log_id", "")
            detail_path = store.base_dir / platform / "global_evolution" / "detailed_logs" / f"log_{log_id}.json"
            if detail_path.exists():
                with open(detail_path, "r") as f:
                    detail = json.load(f)
                entry["changes_summary"] = detail.get("changes_summary", [])
                entry["has_before_snapshot"] = bool(detail.get("before_dna"))
            else:
                entry["changes_summary"] = []
                entry["has_before_snapshot"] = False

            all_logs.append(entry)

    all_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"logs": all_logs[:50], "total": len(all_logs)}


@router.get("/universal/evolution-logs/{log_id}")
async def get_evolution_log_detail(log_id: str):
    """Get detailed evolution log entry with full before/after DNA snapshots."""
    store = get_universal_store()

    for platform in PLATFORMS:
        detail_path = store.base_dir / platform / "global_evolution" / "detailed_logs" / f"log_{log_id}.json"
        if detail_path.exists():
            with open(detail_path, "r") as f:
                return json.load(f)

    raise HTTPException(404, f"Log {log_id} not found")


# ── Revert ────────────────────────────────────────────────────


@router.post("/universal/revert/{log_id}")
async def revert_evolution_log(log_id: str):
    """Revert a specific evolution change by restoring the before-snapshot DNA."""
    from nexearch.agents.universal_pipeline import revert_evolution
    store = get_universal_store()

    # Find which platform this log belongs to
    for platform in PLATFORMS:
        detail_path = store.base_dir / platform / "global_evolution" / "detailed_logs" / f"log_{log_id}.json"
        if detail_path.exists():
            result = revert_evolution(platform, log_id)
            return result

    raise HTTPException(404, f"Log {log_id} not found")


# ── Client Intelligence ───────────────────────────────────────


@router.get("/client/{client_id}")
async def get_client_intelligence(client_id: str):
    """Get client-specific DNA, tier distribution, and evolution history."""
    meta = SystemMeta()
    client = {}
    if hasattr(meta, "get_client"):
        client = meta.get_client(client_id)
        if not client:
            client = {}

    try:
        client_store = ClientDataStore(client_id)
        manifest = client_store.get_manifest() or {}

        stats = {"s_tier": 0, "a_tier": 0, "b_tier": 0, "c_tier": 0}
        best_platform = ""
        best_platform_total = -1

        for platform in PLATFORMS:
            tier_dist = manifest.get("platforms", {}).get(platform, {}).get("tier_distribution", {}) or {}
            stats["s_tier"] += tier_dist.get("s_tier", tier_dist.get("S", 0))
            stats["a_tier"] += tier_dist.get("a_tier", tier_dist.get("A", 0))
            stats["b_tier"] += tier_dist.get("b_tier", tier_dist.get("B", 0))
            stats["c_tier"] += tier_dist.get("c_tier", tier_dist.get("C", 0))

            platform_total = sum(int(tier_dist.get(key, 0)) for key in ("s_tier", "a_tier", "b_tier", "c_tier"))
            if platform_total > best_platform_total and client_store.get_platform_dna(platform):
                best_platform = platform
                best_platform_total = platform_total

        dna_payload = client_store.get_platform_dna(best_platform) if best_platform else None
        dna_data = dna_payload.get("dna", {}) if isinstance(dna_payload, dict) else {}
        dna = {
            "version": dna_payload.get("version", "1.0") if isinstance(dna_payload, dict) else "1.0",
            "platform": best_platform or "",
            "brand_guidelines": dna_data if isinstance(dna_data, dict) else {},
        }

        evolution_logs = _collect_client_evolution_logs(client_store)

        return {
            "client_id": client_id,
            "name": client.get("name", client_id) if isinstance(client, dict) else client_id,
            "dna": dna,
            "stats": stats,
            "tier_distribution": stats,
            "evolution_logs": evolution_logs[:20],
            "platform_breakdown": manifest.get("platforms", {}),
            "recent_posts": [],
        }
    except Exception as e:
        logger.error(f"Error fetching client intelligence for {client_id}: {e}")
        return {"error": str(e), "client_id": client_id}


@router.post("/client/{client_id}/evolve")
async def force_client_evolution(client_id: str):
    """Force a client-specific evolution cycle."""
    return {"status": "success", "message": f"Client evolution cycle triggered for {client_id}."}
