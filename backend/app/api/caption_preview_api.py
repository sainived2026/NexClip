import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

PREVIEW_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "captions", "caption_previews"))

@router.get("/api/captions/preview/{style_id}")
async def get_caption_preview(style_id: str):
    """
    Returns a high-quality pre-rendered MP4 video preview of a caption style.
    Uses pre-generated 5-second video clips to preview actual animation and rendering quality.
    """
    preview_path = os.path.join(PREVIEW_DIR, f"{style_id}_preview.mp4")

    if not os.path.exists(preview_path):
        # Fallback if specific preview is missing
        fallback_path = os.path.join(PREVIEW_DIR, "bold_impact_preview.mp4")
        if os.path.exists(fallback_path):
            return FileResponse(fallback_path, media_type="video/mp4")
        raise HTTPException(status_code=404, detail=f"Preview video for {style_id} not found")

    # Serve the static MP4 directly, enabling Range headers for seamless browser looping
    return FileResponse(preview_path, media_type="video/mp4")
