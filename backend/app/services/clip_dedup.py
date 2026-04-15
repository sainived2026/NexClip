from __future__ import annotations

from typing import Any, Iterable, List


def _clip_value(clip: Any, field: str) -> Any:
    if isinstance(clip, dict):
        return clip.get(field)
    return getattr(clip, field, None)


def _clip_identity(clip: Any) -> tuple:
    rank = _clip_value(clip, "rank")
    if rank is not None:
        return ("rank", int(rank))

    file_path = _clip_value(clip, "file_path") or ""
    landscape_path = _clip_value(clip, "file_path_landscape") or ""
    start = _clip_value(clip, "start") or _clip_value(clip, "start_time") or 0
    end = _clip_value(clip, "end") or _clip_value(clip, "end_time") or 0
    return ("path", file_path, landscape_path, float(start), float(end))


def _clip_completeness_score(clip: Any) -> int:
    fields = (
        "file_path",
        "file_path_landscape",
        "captioned_video_url",
        "captioned_video_url_landscape",
        "hook_text",
        "title_suggestion",
    )
    return sum(1 for field in fields if _clip_value(clip, field))


def _merge_clip_dicts(current: dict, incoming: dict) -> dict:
    merged = dict(current)
    for key, value in incoming.items():
        if value not in (None, "", [], {}):
            merged[key] = value
    return merged


def dedupe_clip_dicts(clips: Iterable[dict]) -> List[dict]:
    deduped: dict[tuple, dict] = {}

    for clip in clips:
        key = _clip_identity(clip)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = dict(clip)
            continue

        merged = _merge_clip_dicts(existing, clip)
        if _clip_completeness_score(clip) > _clip_completeness_score(existing):
            deduped[key] = merged
        else:
            deduped[key] = _merge_clip_dicts(clip, existing)

    return sorted(deduped.values(), key=lambda clip: (_clip_value(clip, "rank") is None, _clip_value(clip, "rank") or 0))


def dedupe_clip_records(clips: Iterable[Any]) -> List[Any]:
    deduped: dict[tuple, Any] = {}

    for clip in clips:
        key = _clip_identity(clip)
        existing = deduped.get(key)
        if existing is None or _clip_completeness_score(clip) > _clip_completeness_score(existing):
            deduped[key] = clip

    return sorted(deduped.values(), key=lambda clip: (_clip_value(clip, "rank") is None, _clip_value(clip, "rank") or 0))
