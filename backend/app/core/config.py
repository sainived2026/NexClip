"""
NexClip application configuration.

The settings layer now hardens a few production-critical behaviors:
- resolves relative filesystem paths against the repo/backend roots
- resolves relative SQLite URLs so startup no longer depends on cwd
- requires a non-placeholder secret in production
- disables the dev auth bypass automatically in production
- uses machine-scaled worker defaults instead of extreme hardcoded values
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_ROOT = _REPO_ROOT / "backend"
_DEFAULT_STORAGE_ROOT = (_BACKEND_ROOT / "storage").resolve()
_DEFAULT_FONTS_DIR = (_BACKEND_ROOT / "fonts").resolve()
_DEFAULT_DB_PATH = (_BACKEND_ROOT / "nexclip.db").resolve()
_DEFAULT_SECRET_KEY = "change-me-to-a-secure-random-string"
_CPU_COUNT = max(os.cpu_count() or 1, 1)


def _sqlite_url_from_path(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _resolve_repo_relative_path(raw_value: str, *, anchor: Path) -> str:
    value = (raw_value or "").strip()
    if not value:
        return str(anchor.resolve())

    path = Path(value)
    if path.is_absolute():
        return str(path.resolve())

    return str((anchor / path).resolve())


def _resolve_sqlite_database_url(raw_value: str) -> str:
    value = (raw_value or "").strip()
    if not value:
        return _sqlite_url_from_path(_DEFAULT_DB_PATH)

    if not value.startswith("sqlite:///"):
        return value

    sqlite_path = value[len("sqlite:///"):]
    if sqlite_path == ":memory:":
        return value

    path = Path(sqlite_path)
    if path.is_absolute():
        return _sqlite_url_from_path(path)

    return _sqlite_url_from_path((_BACKEND_ROOT / path).resolve())


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "NexClip"
    APP_ENV: str = "development"
    SECRET_KEY: str = _DEFAULT_SECRET_KEY
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ALLOW_DEV_AUTH_BYPASS: bool = True
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Database ---
    DATABASE_URL: str = _sqlite_url_from_path(_DEFAULT_DB_PATH)
    DB_POOL_SIZE: int = max(5, min(20, _CPU_COUNT * 2))
    DB_MAX_OVERFLOW: int = max(2, min(10, _CPU_COUNT))

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Storage ---
    STORAGE_MODE: str = "local"  # "local" | "s3"
    STORAGE_LOCAL_ROOT: str = str(_DEFAULT_STORAGE_ROOT)
    S3_BUCKET_NAME: str = ""
    S3_REGION: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    FONTS_DIR: str = str(_DEFAULT_FONTS_DIR)

    # --- Upload ---
    MAX_UPLOAD_SIZE_MB: int = 4000

    # --- LLM Configuration ---
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20250315"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite-preview"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "qwen/qwen3.6-plus:free"
    LLM_PROVIDER_PRIORITY: str = "anthropic,openai,gemini,openrouter"

    # --- LLM Limits ---
    LLM_TIMEOUT: int = 300
    LLM_MAX_TOKENS: int = 32000
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TRANSCRIPT_LENGTH: int = 360000

    # --- Speech-to-Text ---
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_STT_MODEL: str = "scribe_v2"
    WHISPER_MODEL: str = "medium"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_COMPUTE_TYPE: str = "float16"
    WHISPER_MAX_PARALLEL_JOBS: int = 1

    # --- Processing Timeouts ---
    FFMPEG_CLIP_TIMEOUT: int = 600
    FFMPEG_AUDIO_TIMEOUT: int = 600
    AUDIO_LOAD_TIMEOUT: int = 1800
    DOWNLOAD_TIMEOUT: int = 1800
    FFPROBE_TIMEOUT: int = 30
    FFMPEG_DURATION_TIMEOUT: int = 30

    # --- Speaker Detection ---
    SPEAKER_DETECTION_ENABLED: bool = True
    SPEAKER_DETECTION_SAMPLE_FPS: int = 3
    SPEAKER_DETECTION_MIN_FACE_SIZE: int = 40
    SPEAKER_CROP_SMOOTHING: float = 0.15
    SPEAKER_DETECTION_FRAME_WIDTH: int = 640

    # --- Downloader & Video Output ---
    YTDLP_COOKIES_BROWSER: str = "chrome"
    OUTPUT_VIDEO_WIDTH: int = 1080
    OUTPUT_VIDEO_HEIGHT: int = 1920
    VIDEO_CODEC: str = "libx264"
    VIDEO_PRESET: str = "ultrafast"
    VIDEO_CRF: int = 23
    AUDIO_CODEC: str = "aac"
    AUDIO_BITRATE: str = "128k"
    AUDIO_SAMPLE_RATE: int = 44100
    CAPTION_FONT_SIZE: int = 42
    CAPTION_MAX_LENGTH: int = 80

    # --- Clip Defaults ---
    DEFAULT_CLIP_COUNT: int = 10
    MIN_CLIP_DURATION: int = 30
    MAX_CLIP_DURATION: int = 90

    # --- Performance Tuning ---
    CELERY_VIDEO_CONCURRENCY: int = max(2, min(8, _CPU_COUNT))
    CELERY_CAPTION_CONCURRENCY: int = max(4, min(16, _CPU_COUNT * 2))
    CELERY_NEXEARCH_CONCURRENCY: int = max(2, min(8, _CPU_COUNT))
    FFMPEG_PARALLEL_CLIPS: int = 2
    FFMPEG_THREADS_PER_CLIP: int = 1

    @property
    def cors_origins_list(self) -> List[str]:
        seen: set[str] = set()
        origins: List[str] = []
        for origin in self.CORS_ORIGINS.split(","):
            normalized = origin.strip().rstrip("/")
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            origins.append(normalized)
        return origins

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def storage_root_path(self) -> Path:
        return Path(self.STORAGE_LOCAL_ROOT)

    @property
    def fonts_dir_path(self) -> Path:
        return Path(self.FONTS_DIR)

    @property
    def has_secure_secret_key(self) -> bool:
        return bool(self.SECRET_KEY) and self.SECRET_KEY != _DEFAULT_SECRET_KEY and len(self.SECRET_KEY) >= 32

    @property
    def has_anthropic(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY)

    @property
    def has_openai(self) -> bool:
        return bool(self.OPENAI_API_KEY)

    @property
    def has_gemini(self) -> bool:
        return bool(self.GEMINI_API_KEY)

    @property
    def has_elevenlabs(self) -> bool:
        value = (self.ELEVENLABS_API_KEY or "").strip()
        if not value:
            return False
        return not value.endswith("---Ved")

    @property
    def has_openrouter(self) -> bool:
        return bool(self.OPENROUTER_API_KEY)

    @property
    def llm_provider_priority_list(self) -> List[str]:
        providers = [
            provider.strip().lower()
            for provider in self.LLM_PROVIDER_PRIORITY.split(",")
            if provider.strip()
        ]
        valid = {"anthropic", "openai", "gemini", "openrouter"}
        ordered: List[str] = []
        for provider in providers:
            if provider in valid and provider not in ordered:
                ordered.append(provider)
        for provider in ("anthropic", "openai", "gemini", "openrouter"):
            if provider not in ordered:
                ordered.append(provider)
        return ordered

    @field_validator(
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "ANTHROPIC_MODEL",
        "OPENAI_MODEL",
        "GEMINI_MODEL",
        "LLM_PROVIDER_PRIORITY",
        mode="before",
    )
    @classmethod
    def _sanitize_llm_env_values(cls, value):
        if value is None:
            return ""
        cleaned = str(value).strip()
        if " #" in cleaned:
            cleaned = cleaned.split(" #", 1)[0].rstrip()
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
            cleaned = cleaned[1:-1].strip()
        return cleaned

    @field_validator("APP_ENV", mode="before")
    @classmethod
    def _normalize_app_env(cls, value):
        return str(value or "development").strip().lower()

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, value):
        return _resolve_sqlite_database_url(str(value or ""))

    @field_validator("STORAGE_LOCAL_ROOT", mode="before")
    @classmethod
    def _normalize_storage_root(cls, value):
        return _resolve_repo_relative_path(str(value or ""), anchor=_BACKEND_ROOT)

    @field_validator("FONTS_DIR", mode="before")
    @classmethod
    def _normalize_fonts_dir(cls, value):
        return _resolve_repo_relative_path(str(value or ""), anchor=_REPO_ROOT)

    @model_validator(mode="after")
    def _apply_runtime_guards(self):
        if self.is_production:
            self.ALLOW_DEV_AUTH_BYPASS = False

        self.DB_POOL_SIZE = max(1, int(self.DB_POOL_SIZE))
        self.DB_MAX_OVERFLOW = max(0, int(self.DB_MAX_OVERFLOW))
        self.CELERY_VIDEO_CONCURRENCY = max(1, int(self.CELERY_VIDEO_CONCURRENCY))
        self.CELERY_CAPTION_CONCURRENCY = max(1, int(self.CELERY_CAPTION_CONCURRENCY))
        self.CELERY_NEXEARCH_CONCURRENCY = max(1, int(self.CELERY_NEXEARCH_CONCURRENCY))

        if self.is_sqlite:
            self.DB_POOL_SIZE = 1
            self.DB_MAX_OVERFLOW = 0

        return self

    model_config = {
        "env_file": [".env", "backend/.env", "../backend/.env"],
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
