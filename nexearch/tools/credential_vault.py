"""
Nexearch — Credential Vault
================================
Encrypted credential manager for platform login (Playwright).
Loads credentials from .env, provides get_credentials(platform).
Credentials are stored in .env and loaded via os.environ.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from loguru import logger


# Platform credential key mapping
_CREDENTIAL_MAP = {
    "instagram": {
        "username_key": "PLATFORM_INSTAGRAM_USERNAME",
        "password_key": "PLATFORM_INSTAGRAM_PASSWORD",
        "login_url": "https://www.instagram.com/accounts/login/",
    },
    "tiktok": {
        "username_key": "PLATFORM_TIKTOK_USERNAME",
        "password_key": "PLATFORM_TIKTOK_PASSWORD",
        "login_url": "https://www.tiktok.com/login/phone-or-email/email",
    },
    "youtube": {
        "username_key": "PLATFORM_YOUTUBE_EMAIL",
        "password_key": "PLATFORM_YOUTUBE_PASSWORD",
        "login_url": "https://accounts.google.com/signin",
    },
    "linkedin": {
        "username_key": "PLATFORM_LINKEDIN_EMAIL",
        "password_key": "PLATFORM_LINKEDIN_PASSWORD",
        "login_url": "https://www.linkedin.com/login",
    },
    "twitter": {
        "username_key": "PLATFORM_TWITTER_USERNAME",
        "password_key": "PLATFORM_TWITTER_PASSWORD",
        "login_url": "https://twitter.com/i/flow/login",
    },
    "facebook": {
        "username_key": "PLATFORM_FACEBOOK_EMAIL",
        "password_key": "PLATFORM_FACEBOOK_PASSWORD",
        "login_url": "https://www.facebook.com/login",
    },
}


def get_credentials(platform: str) -> Dict[str, str]:
    """
    Get login credentials for a platform.
    Returns dict with 'username', 'password', 'login_url'.
    Raises ValueError if credentials are not set.
    """
    platform = platform.lower().strip()
    if platform not in _CREDENTIAL_MAP:
        raise ValueError(
            f"Unknown platform: {platform}. "
            f"Supported: {list(_CREDENTIAL_MAP.keys())}"
        )

    cred_info = _CREDENTIAL_MAP[platform]
    username = os.environ.get(cred_info["username_key"], "").strip()
    password = os.environ.get(cred_info["password_key"], "").strip()

    if not username or not password:
        raise ValueError(
            f"Credentials not set for {platform}. "
            f"Set {cred_info['username_key']} and {cred_info['password_key']} in .env"
        )

    return {
        "username": username,
        "password": password,
        "login_url": cred_info["login_url"],
        "platform": platform,
    }


def has_credentials(platform: str) -> bool:
    """Check if credentials are configured for a platform."""
    try:
        get_credentials(platform)
        return True
    except (ValueError, KeyError):
        return False


def get_all_configured_platforms() -> List[str]:
    """Return list of platforms that have credentials configured."""
    return [p for p in _CREDENTIAL_MAP if has_credentials(p)]


def get_supported_platforms() -> List[str]:
    """Return all supported platform names."""
    return list(_CREDENTIAL_MAP.keys())


def get_login_url(platform: str) -> str:
    """Get the login URL for a platform."""
    platform = platform.lower().strip()
    if platform not in _CREDENTIAL_MAP:
        raise ValueError(f"Unknown platform: {platform}")
    return _CREDENTIAL_MAP[platform]["login_url"]


def get_session_dir(platform: str) -> str:
    """Get the browser session storage directory for a platform."""
    base = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "arc", "arc_agent_memory", "browser_sessions", platform,
    )
    os.makedirs(base, exist_ok=True)
    return base
