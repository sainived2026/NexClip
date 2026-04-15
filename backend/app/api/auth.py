"""
NexClip auth API endpoints.

AUTH MODE: DISABLED
All requests are automatically authenticated as the dev admin.
No token required. No 401s. Re-enable by setting AUTH_DISABLED=False.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    oauth2_scheme,
    verify_password,
)
from app.db.database import get_db
from app.db.models import User
from app.schemas import TokenResponse, UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
settings = get_settings()

# ── Dev admin singleton (cached to avoid repeated DB hits) ─────────
_DEV_ADMIN_CACHE: User | None = None


def _get_or_create_dev_admin(db: Session) -> User:
    """Return the first user (dev admin), creating one if needed."""
    global _DEV_ADMIN_CACHE
    if _DEV_ADMIN_CACHE is not None:
        return _DEV_ADMIN_CACHE

    user = db.query(User).first()
    if not user:
        user = User(
            email="admin@nexclip.local",
            username="admin",
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            full_name="NexClip Admin",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    _DEV_ADMIN_CACHE = user
    return user


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    AUTH DISABLED — always returns the dev admin.
    No token validation, no 401s, zero auth overhead.
    """
    return _get_or_create_dev_admin(db)



@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name or "",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": user.id})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
