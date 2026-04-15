from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"

for path in (str(ROOT), str(BACKEND_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


from app.services.speaker_detection_service import FaceTrack, SpeakerDetectionService, SpeakerKeyframe
from app.services.ffmpeg_service import FFmpegService


def _build_track(
    face_id: int,
    home_x: int,
    home_y: int,
    face_w: int,
    face_h: int,
    duration: float,
    lip_pattern: list[float],
    sample_step: float = 0.5,
) -> FaceTrack:
    timestamps = [round(i * sample_step, 3) for i in range(len(lip_pattern))]
    track = FaceTrack(face_id=face_id)
    track.timestamps = timestamps
    track.lip_ratios = lip_pattern
    track.face_centers_x = [home_x] * len(lip_pattern)
    track.face_centers_y = [home_y] * len(lip_pattern)
    track.face_widths = [face_w] * len(lip_pattern)
    track.face_heights = [face_h] * len(lip_pattern)
    track.home_x = home_x
    track.home_y = home_y
    track.home_face_w = face_w
    track.home_face_h = face_h
    return track


def test_rejects_edge_only_track_when_visible_speaker_exists():
    service = SpeakerDetectionService()
    duration = 8.0

    visible_speaker = _build_track(
        face_id=0,
        home_x=980,
        home_y=360,
        face_w=230,
        face_h=280,
        duration=duration,
        lip_pattern=[0.03, 0.06, 0.03, 0.06, 0.03, 0.06, 0.03, 0.06],
    )
    edge_false_positive = _build_track(
        face_id=1,
        home_x=1025,
        home_y=54,
        face_w=220,
        face_h=270,
        duration=duration,
        lip_pattern=[0.01, 0.10, 0.01, 0.10, 0.01, 0.10, 0.01, 0.10],
    )

    timeline = service._build_speaker_timeline(
        [visible_speaker, edge_false_positive],
        start=0.0,
        duration=duration,
        sample_fps=2,
    )

    assert all(face_id != 1 for _, _, face_id in timeline)


def test_rejects_side_edge_track_when_visible_speaker_exists():
    service = SpeakerDetectionService()
    duration = 8.0

    visible_speaker = _build_track(
        face_id=0,
        home_x=960,
        home_y=360,
        face_w=230,
        face_h=280,
        duration=duration,
        lip_pattern=[0.03, 0.06, 0.03, 0.06, 0.03, 0.06, 0.03, 0.06],
    )
    side_edge_false_positive = _build_track(
        face_id=1,
        home_x=1870,
        home_y=362,
        face_w=220,
        face_h=270,
        duration=duration,
        lip_pattern=[0.01, 0.10, 0.01, 0.10, 0.01, 0.10, 0.01, 0.10],
    )

    timeline = service._build_speaker_timeline(
        [visible_speaker, side_edge_false_positive],
        start=0.0,
        duration=duration,
        sample_fps=2,
        src_height=1080,
    )

    assert all(face_id != 1 for _, _, face_id in timeline)


def test_holds_current_speaker_when_challenger_is_only_marginally_stronger():
    service = SpeakerDetectionService()
    duration = 6.0

    current_speaker = _build_track(
        face_id=0,
        home_x=860,
        home_y=390,
        face_w=250,
        face_h=300,
        duration=duration,
        lip_pattern=[0.03, 0.07, 0.03, 0.06, 0.03, 0.06],
    )
    challenger = _build_track(
        face_id=1,
        home_x=1320,
        home_y=392,
        face_w=238,
        face_h=290,
        duration=duration,
        lip_pattern=[0.03, 0.075, 0.03, 0.065, 0.03, 0.065],
    )

    timeline = service._build_speaker_timeline(
        [current_speaker, challenger],
        start=0.0,
        duration=duration,
        sample_fps=2,
    )

    assert len({face_id for _, _, face_id in timeline}) == 1
    assert timeline[0][2] == 0


def test_repeated_near_threshold_challenges_do_not_create_flip_flopping_timeline():
    service = SpeakerDetectionService()
    duration = 10.0

    anchor = _build_track(
        face_id=0,
        home_x=900,
        home_y=380,
        face_w=248,
        face_h=295,
        duration=duration,
        lip_pattern=[0.03, 0.07, 0.03, 0.068, 0.03, 0.069, 0.03, 0.068, 0.03, 0.069],
    )
    challenger = _build_track(
        face_id=1,
        home_x=1290,
        home_y=382,
        face_w=240,
        face_h=288,
        duration=duration,
        lip_pattern=[0.03, 0.071, 0.03, 0.069, 0.03, 0.070, 0.03, 0.069, 0.03, 0.070],
    )

    timeline = service._build_speaker_timeline(
        [anchor, challenger],
        start=0.0,
        duration=duration,
        sample_fps=2,
        src_height=1080,
    )

    assert len(timeline) == 1
    assert timeline[0][2] == 0


def test_short_clip_visible_track_is_still_viable():
    service = SpeakerDetectionService()
    short_visible_track = _build_track(
        face_id=0,
        home_x=960,
        home_y=370,
        face_w=220,
        face_h=270,
        duration=1.0,
        lip_pattern=[0.03, 0.07],
    )

    score = service._track_visibility_score(short_visible_track, 1920, 1080)

    assert score >= service.MIN_TRACK_VISIBILITY_SCORE


def test_invalid_clip_tracks_fall_back_to_cached_face(monkeypatch):
    service = SpeakerDetectionService()
    invalid_edge_track = _build_track(
        face_id=99,
        home_x=1010,
        home_y=36,
        face_w=220,
        face_h=260,
        duration=4.0,
        lip_pattern=[0.02, 0.09, 0.02, 0.09],
    )
    borrowed = SpeakerKeyframe(
        timestamp=0.0,
        center_x=940,
        center_y=360,
        face_top=120,
        face_bottom=660,
        face_width=240,
        face_height=280,
        end_time=4.0,
    )

    monkeypatch.setattr(service.storage, "get_absolute_path", lambda video_path: video_path)
    monkeypatch.setattr(service, "_get_clip_face_tracks", lambda *args, **kwargs: [invalid_edge_track])
    monkeypatch.setattr(service, "_yolo_fallback", lambda *args, **kwargs: [])
    monkeypatch.setattr(service, "_borrow_nearest_face_from_cache", lambda *args, **kwargs: borrowed)

    keyframes = service.detect_active_speaker(
        video_path="demo.mp4",
        start=0.0,
        duration=4.0,
        src_width=1920,
        src_height=1080,
    )

    assert len(keyframes) == 1
    assert keyframes[0].center_x == borrowed.center_x
    assert keyframes[0].center_y == borrowed.center_y


def test_filter_tracks_for_short_clip_keeps_two_detection_face_track():
    service = SpeakerDetectionService()
    short_track = FaceTrack(face_id=7)
    short_track.timestamps = [10.0, 10.5]
    short_track.face_centers_x = [940, 948]
    short_track.face_centers_y = [365, 368]
    short_track.face_widths = [220, 224]
    short_track.face_heights = [270, 274]
    short_track.lip_ratios = [0.03, 0.07]
    short_track.home_x = 944
    short_track.home_y = 366
    short_track.home_face_w = 222
    short_track.home_face_h = 272

    filtered = service._filter_tracks_for_clip(
        [short_track],
        clip_start=10.0,
        clip_duration=1.0,
    )

    assert len(filtered) == 1
    assert filtered[0].home_x == 944


def test_detect_active_speaker_with_metadata_counts_short_clip_face_frames(monkeypatch):
    service = SpeakerDetectionService()
    short_track = FaceTrack(face_id=7)
    short_track.timestamps = [10.0, 10.5]
    short_track.face_centers_x = [940, 948]
    short_track.face_centers_y = [365, 368]
    short_track.face_widths = [220, 224]
    short_track.face_heights = [270, 274]
    short_track.lip_ratios = [0.03, 0.07]
    short_track.home_x = 944
    short_track.home_y = 366
    short_track.home_face_w = 222
    short_track.home_face_h = 272

    monkeypatch.setattr(service, "_get_clip_face_tracks", lambda *args, **kwargs: [short_track])

    result = service.detect_active_speaker_with_metadata(
        video_path="videos/test.mp4",
        start=10.0,
        duration=1.0,
        src_width=1920,
        src_height=1080,
    )

    assert result.sfcs_version == "director_v4"
    assert result.sfcs_faces_detected == 1
    assert result.sfcs_frames_with_speaker == 2
    assert result.sfcs_fallback_frames == 0
    assert len(result.keyframes) == 1


def test_detect_active_speaker_with_metadata_marks_fallback_when_no_tracks(monkeypatch):
    service = SpeakerDetectionService()

    monkeypatch.setattr(service, "_get_clip_face_tracks", lambda *args, **kwargs: [])
    monkeypatch.setattr(service, "_yolo_fallback", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        service,
        "_build_presence_fallback_keyframes",
        lambda *args, **kwargs: [
            SpeakerKeyframe(
                timestamp=0.0,
                center_x=960,
                center_y=360,
                face_top=0,
                face_bottom=640,
                face_width=320,
                face_height=360,
                end_time=1.0,
            )
        ],
    )

    result = service.detect_active_speaker_with_metadata(
        video_path="videos/test.mp4",
        start=0.0,
        duration=1.0,
        src_width=1920,
        src_height=1080,
    )

    assert result.sfcs_faces_detected == 0
    assert result.sfcs_frames_with_speaker == 0
    assert result.sfcs_fallback_frames > 0
    assert len(result.keyframes) == 1


def test_window_local_fallback_prefers_visible_person_when_previous_speaker_disappears():
    service = SpeakerDetectionService()

    first_speaker = _build_track(
        face_id=0,
        home_x=860,
        home_y=385,
        face_w=250,
        face_h=300,
        duration=6.0,
        lip_pattern=[0.03, 0.08, 0.03, 0.08, 0.03],
    )
    first_speaker.timestamps = [0.0, 0.5, 1.0, 1.5, 2.0]

    visible_listener = FaceTrack(face_id=1)
    visible_listener.timestamps = [2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5]
    visible_listener.face_centers_x = [1320] * len(visible_listener.timestamps)
    visible_listener.face_centers_y = [395] * len(visible_listener.timestamps)
    visible_listener.face_widths = [230] * len(visible_listener.timestamps)
    visible_listener.face_heights = [280] * len(visible_listener.timestamps)
    visible_listener.lip_ratios = []
    visible_listener.home_x = 1320
    visible_listener.home_y = 395
    visible_listener.home_face_w = 230
    visible_listener.home_face_h = 280

    timeline = service._build_speaker_timeline(
        [first_speaker, visible_listener],
        start=0.0,
        duration=6.0,
        sample_fps=2,
    )

    assert timeline[0][2] == 0
    assert timeline[-1][2] == 1


def test_portrait_crop_keeps_face_inside_safe_bounds():
    ffmpeg = FFmpegService()

    class Keyframe:
        center_x = 1680
        center_y = 360
        face_width = 240
        face_height = 280
        face_top = 80
        face_bottom = 640

    crop_w = int(1080 * (ffmpeg.output_width / ffmpeg.output_height))
    crop_h = 1080

    crop_x, crop_y = ffmpeg._compute_smart_crop_position(
        Keyframe(),
        crop_w=crop_w,
        crop_h=crop_h,
        src_width=1920,
        src_height=1080,
        src_ratio=1920 / 1080,
        target_ratio=ffmpeg.output_width / ffmpeg.output_height,
    )

    face_left = Keyframe.center_x - Keyframe.face_width // 2
    face_right = Keyframe.center_x + Keyframe.face_width // 2
    assert crop_y == 0
    assert face_left >= crop_x
    assert face_right <= crop_x + crop_w


def test_turn_local_face_bounds_prevent_edge_face_clipping():
    service = SpeakerDetectionService()
    ffmpeg = FFmpegService()

    anchor = _build_track(
        face_id=0,
        home_x=760,
        home_y=380,
        face_w=240,
        face_h=290,
        duration=6.0,
        lip_pattern=[0.03, 0.07, 0.03, 0.07, 0.03, 0.07],
    )

    leaning_speaker = FaceTrack(face_id=1)
    leaning_speaker.timestamps = [0.0, 0.5, 1.0, 2.0, 2.5, 3.0, 3.5, 4.0]
    leaning_speaker.face_centers_x = [1490, 1500, 1505, 1660, 1680, 1695, 1700, 1688]
    leaning_speaker.face_centers_y = [385, 386, 386, 392, 394, 396, 395, 394]
    leaning_speaker.face_widths = [176, 180, 182, 296, 304, 310, 306, 300]
    leaning_speaker.face_heights = [238, 240, 242, 324, 332, 336, 334, 330]
    leaning_speaker.lip_ratios = [0.02, 0.02, 0.02, 0.07, 0.08, 0.08, 0.07, 0.07]
    leaning_speaker.home_x = 1500
    leaning_speaker.home_y = 390
    leaning_speaker.home_face_w = 180
    leaning_speaker.home_face_h = 240

    timeline = [(0.0, 2.0, 0), (2.0, 4.0, 1)]
    keyframes = service._timeline_to_smooth_keyframes(
        timeline=timeline,
        tracks=[anchor, leaning_speaker],
        clip_start=0.0,
        clip_duration=4.0,
        src_width=1920,
        src_height=1080,
    )

    leaning_keyframe = next(kf for kf in keyframes if abs(kf.timestamp - 2.0) < 1e-6)

    crop_w = int(1080 * (ffmpeg.output_width / ffmpeg.output_height))
    crop_h = 1080
    crop_x, crop_y = ffmpeg._compute_smart_crop_position(
        leaning_keyframe,
        crop_w=crop_w,
        crop_h=crop_h,
        src_width=1920,
        src_height=1080,
        src_ratio=1920 / 1080,
        target_ratio=ffmpeg.output_width / ffmpeg.output_height,
    )

    actual_turn_center_x = 1688
    actual_turn_face_w = 306
    actual_face_left = actual_turn_center_x - actual_turn_face_w // 2
    actual_face_right = actual_turn_center_x + actual_turn_face_w // 2

    assert crop_y == 0
    assert actual_face_left >= crop_x
    assert actual_face_right <= crop_x + crop_w
