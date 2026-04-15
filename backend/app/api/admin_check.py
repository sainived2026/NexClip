"""
NexClip — Admin Check Endpoint
===================================
Returns whether the authenticated user is an admin.
Does NOT throw 403 — simply returns {is_admin: true/false}.
Used by the frontend sidebar to conditionally render admin pages.
"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from app.api.auth import get_current_user
from app.db.models import User

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/admin-check")
def admin_check(current_user: User = Depends(get_current_user)):
    """Check if the current user has admin privileges (always true now)."""
    return {"is_admin": True, "email": current_user.email}
