"""
Bakes 18 MP4 Video Previews for Caption Styles Gallery
Takes 9 existing 16:9 clips, cuts 5-8 seconds using existing word_timestamps,
and applies 2 distinct styles per clip without re-running STT.
Saves finally to backend/app/captions/caption_previews.
"""

import os
import shutil
import logging
import json
from sqlalchemy.orm import sessionmaker

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.models import Clip
from app.db.database import get_db, engine
from app.captions.style_registry import get_all_styles
from app.core.config import get_settings
from app.core.binaries import get_ffmpeg_path
import subprocess

settings = get_settings()

STORAGE_ROOT = os.path.abspath(settings.STORAGE_LOCAL_ROOT)
TEMP_PREVIEW_DIR = "previews/temp_caption_baking"
ABS_TEMP_PREVIEW_DIR = os.path.join(STORAGE_ROOT, "previews", "temp_caption_baking")
FINAL_DEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "captions", "caption_previews"))

# Wipe and recreate temp staging
if os.path.exists(ABS_TEMP_PREVIEW_DIR):
    shutil.rmtree(ABS_TEMP_PREVIEW_DIR, ignore_errors=True)
os.makedirs(ABS_TEMP_PREVIEW_DIR, exist_ok=True)
os.makedirs(FINAL_DEST_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    SessionItem = sessionmaker(bind=engine)
    db = SessionItem()

    styles = get_all_styles()
    style_ids = [s.style_id for s in styles]
    
    if len(style_ids) < 18:
        while len(style_ids) < 18:
            style_ids.extend(style_ids[:18 - len(style_ids)])
    elif len(style_ids) > 18:
        style_ids = style_ids[:18]

    # Find clips that have 16:9 variants and have existing word timestamps
    all_clips = db.query(Clip).filter(Clip.file_path_landscape != None, Clip.word_timestamps != "[]", Clip.word_timestamps != None).all()
    all_clips.reverse() # Start from most recent projects

    from app.captions.caption_pipeline import apply_caption_style

    success_count = 0
    
    # We need 9 successful base clips
    for clip in all_clips:
        if success_count >= 9:
            break

        input_path = os.path.join(STORAGE_ROOT, clip.file_path_landscape)
        if not os.path.exists(input_path) or os.path.getsize(input_path) < 100000:
            continue

        try:
            full_transcript = json.loads(clip.word_timestamps)
        except:
            continue
            
        # extract words up to max 8 seconds
        preview_words = []
        for w in full_transcript:
            if w.get("end", 0) <= 8.0:
                preview_words.append(w)
            else:
                break
                
        # we need at least 3 words to show a good caption preview
        if len(preview_words) < 3:
            continue
            
        cut_duration = preview_words[-1]["end"]
        # min 3 sec to look good looping
        if cut_duration < 3.0:
            continue

        style_1 = style_ids[success_count * 2]
        style_2 = style_ids[success_count * 2 + 1]

        relative_trimmed = f"{TEMP_PREVIEW_DIR}/trimmed_{success_count}.mp4"
        absolute_trimmed = os.path.join(STORAGE_ROOT, relative_trimmed)
        
        logger.info(f"Trimming {input_path} down to {cut_duration}s for caption preview...")
        trim_cmd = [
            get_ffmpeg_path(), "-y", "-i", input_path,
            "-ss", "00:00:00", "-t", str(cut_duration),
            "-c:v", "libx264", "-c:a", "aac", absolute_trimmed
        ]
        
        try:
            subprocess.run(trim_cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to trim clip: {e.stderr.decode()[-200:]}")
            continue

        def make_styled_clip(style_id):
            final_out = os.path.join(FINAL_DEST_DIR, f"{style_id}_preview.mp4")
            if os.path.exists(final_out):
                logger.info(f"Preview {final_out} already exists. Skipping.")
                return

            relative_out = f"{TEMP_PREVIEW_DIR}/{style_id}_preview.mp4"
            absolute_out = os.path.join(STORAGE_ROOT, relative_out)

            logger.info(f"Baking {style_id} over clip {success_count}...")
            
            # Use caption engine pipeline directly with existing real words!
            res = apply_caption_style(
                input_video_path=absolute_trimmed,
                word_timestamps=preview_words,
                style_id=style_id,
                output_path=absolute_out
            )

            if res.get("success", False) and os.path.exists(absolute_out):
                shutil.move(absolute_out, final_out)
                logger.info(f"Successfully baked and moved {style_id} to {final_out}")
            else:
                logger.error(f"Failed to generate {style_id}")

        make_styled_clip(style_1)
        make_styled_clip(style_2)
        
        success_count += 1

    logger.info(f"🎉 Baked previews using {success_count} valid clips!")

if __name__ == "__main__":
    main()
