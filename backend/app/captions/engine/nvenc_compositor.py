"""
NexRenderer Engine — FFmpeg Hardware Compositor
Pipes raw Pillow RGBA canvases into FFmpeg's overlay filter with hardware NVENC encoding.
Extremely fast, entirely bypassing disk I/O.
"""

import os
import time
import subprocess
import logging
import cv2
from typing import List
from app.captions.engine.pillow_renderer import PillowRenderer
from app.captions.models import CaptionStyle, CaptionSegment
from app.core.binaries import get_ffmpeg_path

logger = logging.getLogger(__name__)

class NexRenderer:
    def __init__(self, style: CaptionStyle, width: int, height: int):
        self.style = style
        self.width = width
        self.height = height
        self.pillow_renderer = PillowRenderer(style, width, height)

    def generate(self, input_video: str, output_video: str, segments: List[CaptionSegment]) -> dict:
        """
        Orchestrates frame generation and FFmpeg overlay.
        Args:
            input_video: Absolute path to the source video.
            output_video: Absolute path to the destination video.
            segments: List of CaptionSegments with timing data.
        Returns:
            dict containing success state and runtime metrics.
        """
        t0 = time.perf_counter()

        cap = cv2.VideoCapture(input_video)
        if not cap.isOpened():
            return {"success": False, "error": f"Could not decode video {input_video}"}

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            total_frames = 150 # default 5s
            
        cap.release()

        ffmpeg = get_ffmpeg_path()
        
        # Build the brutal hardware FFmpeg pipe!
        # [0:v] is the main video.
        # [1:v] is our raw RGBA byte-stream pipe from Python.
        cmd = [
            ffmpeg,
            '-y',
            '-i', input_video,
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', f'{self.width}x{self.height}',
            '-pix_fmt', 'rgba',
            '-r', str(fps),
            '-i', '-',  # Pipe stdin
            '-filter_complex', '[0:v][1:v]overlay=format=auto,format=yuv420p',
            '-c:v', 'h264_nvenc', # GPU Encoding!
            '-cq', '20',
            '-preset', 'p6',
            '-c:a', 'copy', # Audio is identical, DO NOT touch!
            output_video
        ]
        
        logger.info(f"Booting NexRenderer Pipeline ({total_frames} frames)...")

        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

        frame_dur_ms = 1000.0 / fps
        empty_frame = None

        rendered_count = 0
        
        # Sort segments to iterate efficiently
        segments = sorted(segments, key=lambda s: s.segment_start_ms)
        
        for frame_idx in range(total_frames):
            current_ms = int(frame_idx * frame_dur_ms)
            
            # Find Active Segment
            active_segment = None
            for seg in segments:
                if seg.segment_start_ms <= current_ms <= seg.segment_end_ms + 200: # 200ms padding for fade outs
                    active_segment = seg
                    break

            if active_segment:
                # Render vivid CSS canvas
                canvas = self.pillow_renderer.render_frame(active_segment, current_ms)
                frame_bytes = canvas.tobytes()
            else:
                # Cache an empty transparent frame to save CPU
                if empty_frame is None:
                    from PIL import Image
                    empty_img = Image.new("RGBA", (self.width, self.height), (0,0,0,0))
                    empty_frame = empty_img.tobytes()
                frame_bytes = empty_frame
            
            try:
                process.stdin.write(frame_bytes)
                rendered_count += 1
            except BrokenPipeError:
                break
                
        # Flush and shutdown
        if process.stdin:
            process.stdin.close()
            
        _, stderr_out = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"NexRenderer FFmpeg crashed: {stderr_out.decode()[-500:]}")
            return {"success": False, "error": "FFmpeg crash", "frames": rendered_count}
            
        elapsed = time.perf_counter() - t0
        logger.info(f"NexRenderer completed {rendered_count} frames seamlessly in {elapsed:.2f}s!")

        return {
            "success": True,
            "elapsed_seconds": round(elapsed, 2),
            "style_id": self.style.style_id,
            "frames_processed": rendered_count
        }
