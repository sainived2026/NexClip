from __future__ import annotations

from pathlib import Path
import sys

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
for path in (str(ROOT), str(BACKEND_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.api import auth
from app.core.config import Settings
from nexearch.config import NexearchSettings


def test_backend_settings_resolve_relative_paths_and_guard_production_defaults():
    settings = Settings(
        APP_ENV="production",
        SECRET_KEY="x" * 40,
        DATABASE_URL="sqlite:///./custom.db",
        STORAGE_LOCAL_ROOT="./custom_storage",
        FONTS_DIR="backend/fonts",
        ALLOW_DEV_AUTH_BYPASS=True,
        CORS_ORIGINS="http://localhost:3000, http://localhost:3000/, http://127.0.0.1:3000",
    )

    assert settings.DATABASE_URL.endswith("/backend/custom.db")
    assert settings.storage_root_path == (Path.cwd() / "backend" / "custom_storage").resolve()
    assert settings.fonts_dir_path == (Path.cwd() / "backend" / "fonts").resolve()
    assert settings.ALLOW_DEV_AUTH_BYPASS is False
    assert settings.has_secure_secret_key is True
    assert settings.cors_origins_list == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_backend_settings_flags_placeholder_secret_in_production():
    settings = Settings(APP_ENV="production")

    assert settings.has_secure_secret_key is False
    assert settings.ALLOW_DEV_AUTH_BYPASS is False


def test_nexearch_settings_resolve_relative_dirs_and_db_url():
    settings = NexearchSettings(
        APP_ENV="production",
        SECRET_KEY="y" * 40,
        DATABASE_URL="sqlite:///./nexearch.db",
        NEXEARCH_CLIENTS_DIR="./tenant_data",
        CHROMA_PERSIST_DIRECTORY="./vector_db",
        ARC_AGENT_MEMORY_PATH="./arc_memory",
        ARC_AGENT_CUSTOM_TOOLS_PATH="./arc_tools",
        CORS_ORIGINS="http://localhost:3000, http://localhost:3000/",
    )

    repo_root = Path.cwd()
    assert settings.DATABASE_URL.endswith("/backend/nexearch.db")
    assert settings.clients_dir_path == (repo_root / "tenant_data").resolve()
    assert settings.chroma_persist_path == (repo_root / "vector_db").resolve()
    assert settings.arc_memory_path == (repo_root / "arc_memory").resolve()
    assert settings.custom_tools_path == (repo_root / "arc_tools").resolve()
    assert settings.has_secure_secret_key is True
    assert settings.cors_origins_list == ["http://localhost:3000"]


class _FakeQuery:
    def __init__(self, user=None):
        self._user = user

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._user


class _FakeSession:
    def __init__(self, existing_user=None):
        self.existing_user = existing_user
        self.added_user = None

    def query(self, model):
        return _FakeQuery(self.existing_user)

    def add(self, user):
        self.added_user = user
        self.existing_user = user

    def commit(self):
        return None

    def refresh(self, user):
        return None


def test_get_current_user_requires_auth_when_dev_bypass_disabled(monkeypatch):
    fake_db = _FakeSession(existing_user=None)
    monkeypatch.setattr(auth.settings, "ALLOW_DEV_AUTH_BYPASS", False)

    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(token=None, db=fake_db)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Authentication required"


def test_get_current_user_bootstraps_dev_admin_with_hashed_password(monkeypatch):
    fake_db = _FakeSession(existing_user=None)
    monkeypatch.setattr(auth.settings, "ALLOW_DEV_AUTH_BYPASS", True)

    user = auth.get_current_user(token=None, db=fake_db)

    assert user.email == "admin@nexclip.local"
    assert fake_db.added_user is not None
    assert fake_db.added_user.hashed_password != "pwd"
    assert fake_db.added_user.hashed_password.startswith("$2")
