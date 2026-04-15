"""
Nexearch — Configuration Module
Enterprise-grade settings for the self-evolving social media intelligence system.
Loads from the shared NexClip .env file with Nexearch-specific prefixed variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import List
from functools import lru_cache
from pathlib import Path
import os

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_ROOT = _REPO_ROOT / "backend"
_DEFAULT_SECRET_KEY = "change-me-to-a-secure-random-string"
_DEFAULT_NEXEARCH_CLIENTS_DIR = str((_REPO_ROOT / "nexearch_data").resolve())
_DEFAULT_CHROMA_DIR = str((_REPO_ROOT / "nexearch_chroma_db").resolve())
_DEFAULT_ARC_MEMORY_DIR = str((_REPO_ROOT / "nexearch_arc_memory").resolve())
_DEFAULT_ARC_TOOLS_DIR = str((_REPO_ROOT / "nexearch_arc_tools").resolve())
_DEFAULT_BACKEND_DB_URL = f"sqlite:///{(_BACKEND_ROOT / 'nexclip.db').resolve().as_posix()}"


def _resolve_repo_relative_path(raw_value: str, *, anchor: Path = _REPO_ROOT) -> str:
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
        return _DEFAULT_BACKEND_DB_URL

    if not value.startswith("sqlite:///"):
        return value

    sqlite_path = value[len("sqlite:///"):]
    if sqlite_path == ":memory:":
        return value

    path = Path(sqlite_path)
    if path.is_absolute():
        return f"sqlite:///{path.resolve().as_posix()}"

    return f"sqlite:///{(_BACKEND_ROOT / path).resolve().as_posix()}"


class NexearchSettings(BaseSettings):
    """
    All Nexearch configuration. Shares NexClip's .env file.
    Nexearch-specific vars are prefixed with NEXEARCH_ or service-specific prefixes.
    """

    # ──────────────────────────────────────────────────────────────
    # Core App Settings
    # ──────────────────────────────────────────────────────────────
    APP_NAME: str = "Nexearch"
    APP_ENV: str = "development"
    SECRET_KEY: str = _DEFAULT_SECRET_KEY
    DATABASE_URL: str = _DEFAULT_BACKEND_DB_URL
    REDIS_URL: str = "redis://localhost:6379/0"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ──────────────────────────────────────────────────────────────
    # LLM Configuration (same configurable priority chain as NexClip)
    # ──────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20250315"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite-preview"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "qwen/qwen3.6-plus:free"
    LLM_PROVIDER_PRIORITY: str = "anthropic,openai,gemini,openrouter"

    LLM_TIMEOUT: int = 600
    LLM_MAX_TOKENS: int = 32000
    LLM_TEMPERATURE: float = 0.3

    # ──────────────────────────────────────────────────────────────
    # Metricool Publishing API
    # ──────────────────────────────────────────────────────────────
    METRICOOL_API_TOKEN: str = ""
    METRICOOL_BASE_URL: str = "https://app.metricool.com/api"

    # ──────────────────────────────────────────────────────────────
    # Platform API Keys (per-client overridable, these are defaults)
    # ──────────────────────────────────────────────────────────────
    INSTAGRAM_APP_ID: str = ""
    INSTAGRAM_APP_SECRET: str = ""
    YOUTUBE_API_KEY: str = ""
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    TIKTOK_CLIENT_KEY: str = ""
    TIKTOK_CLIENT_SECRET: str = ""
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    TWITTER_API_KEY: str = ""
    TWITTER_API_SECRET: str = ""
    TWITTER_BEARER_TOKEN: str = ""
    FACEBOOK_APP_ID: str = ""
    FACEBOOK_APP_SECRET: str = ""
    THREADS_APP_ID: str = ""
    THREADS_APP_SECRET: str = ""

    # ──────────────────────────────────────────────────────────────
    # Buffer API (Beta)
    # ──────────────────────────────────────────────────────────────
    BUFFER_ACCESS_TOKEN: str = ""
    BUFFER_BASE_URL: str = "https://api.bufferapp.com/1"

    # ──────────────────────────────────────────────────────────────
    # Scraping Configuration
    # ──────────────────────────────────────────────────────────────
    APIFY_API_KEY: str = ""
    PROXY_URL: str = ""
    SCRAPER_DELAY_MIN_SECONDS: float = 2.0
    SCRAPER_DELAY_MAX_SECONDS: float = 5.0
    CRAWLEE_HEADLESS: bool = True
    CRAWLEE_MAX_CONCURRENCY: int = 3
    CRAWLEE_REQUEST_TIMEOUT_SECONDS: int = 60

    # ──────────────────────────────────────────────────────────────
    # Vector Database
    # ──────────────────────────────────────────────────────────────
    CHROMA_PERSIST_DIRECTORY: str = _DEFAULT_CHROMA_DIR
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "nexearch-signals"

    # ──────────────────────────────────────────────────────────────
    # Embeddings
    # ──────────────────────────────────────────────────────────────
    EMBEDDING_PROVIDER: str = "local"  # "local" or "openai"
    # local = all-MiniLM-L6-v2 (free, CPU)
    # openai = text-embedding-3-small

    # ──────────────────────────────────────────────────────────────
    # Nexearch Core Settings
    # ──────────────────────────────────────────────────────────────
    NEXEARCH_RESCRAPE_INTERVAL_HOURS: int = 24
    NEXEARCH_PERFORMANCE_POLL_WINDOWS: str = "24,48,168"  # hours (168 = 7 days)
    NEXEARCH_MIN_POSTS_FOR_DIRECTIVE: int = 20
    NEXEARCH_REQUIRE_PUBLISH_APPROVAL: bool = True
    NEXEARCH_MAX_CONCURRENT_SCRAPES: int = 3
    NEXEARCH_ANALYSIS_BATCH_SIZE: int = 10
    NEXEARCH_MAX_POSTS_PER_SCRAPE: int = 500

    # ──────────────────────────────────────────────────────────────
    # Arc Agent Settings
    # ──────────────────────────────────────────────────────────────
    ARC_AGENT_ENABLED: bool = True
    ARC_AGENT_MEMORY_PATH: str = _DEFAULT_ARC_MEMORY_DIR
    ARC_AGENT_MAX_SUB_AGENTS: int = 10
    ARC_AGENT_SKILLS_PATH: str = ".agent/skills"
    ARC_AGENT_CUSTOM_TOOLS_PATH: str = _DEFAULT_ARC_TOOLS_DIR

    # ──────────────────────────────────────────────────────────────
    # Client Config Storage
    # ──────────────────────────────────────────────────────────────
    NEXEARCH_CLIENTS_DIR: str = _DEFAULT_NEXEARCH_CLIENTS_DIR

    # ──────────────────────────────────────────────────────────────
    # Encryption (for storing client credentials at rest)
    # ──────────────────────────────────────────────────────────────
    NEXEARCH_FERNET_KEY: str = ""  # Generate with: from cryptography.fernet import Fernet; Fernet.generate_key()

    # ──────────────────────────────────────────────────────────────
    # Nex Agent Integration
    # ──────────────────────────────────────────────────────────────
    NEX_AGENT_ENABLED: bool = True
    NEX_AGENT_BASE_URL: str = "http://localhost:8001"
    NEX_AGENT_MEMORY_PATH: str = "./nex_agent_memory"

    # ──────────────────────────────────────────────────────────────
    # Computed Properties
    # ──────────────────────────────────────────────────────────────

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
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def has_secure_secret_key(self) -> bool:
        return bool(self.SECRET_KEY) and self.SECRET_KEY != _DEFAULT_SECRET_KEY and len(self.SECRET_KEY) >= 32

    @property
    def performance_poll_windows(self) -> List[int]:
        return [int(w.strip()) for w in self.NEXEARCH_PERFORMANCE_POLL_WINDOWS.split(",")]

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
    def has_openrouter(self) -> bool:
        return bool(self.OPENROUTER_API_KEY)

    @property
    def has_metricool(self) -> bool:
        return bool(self.METRICOOL_API_TOKEN)

    @property
    def has_apify(self) -> bool:
        return bool(self.APIFY_API_KEY)

    @property
    def has_instagram_api(self) -> bool:
        return bool(self.INSTAGRAM_APP_ID) and bool(self.INSTAGRAM_APP_SECRET)

    @property
    def has_youtube_api(self) -> bool:
        return bool(self.YOUTUBE_API_KEY)

    @property
    def has_tiktok_api(self) -> bool:
        return bool(self.TIKTOK_CLIENT_KEY)

    @property
    def has_twitter_api(self) -> bool:
        return bool(self.TWITTER_BEARER_TOKEN) or bool(self.TWITTER_API_KEY)

    @property
    def has_linkedin_api(self) -> bool:
        return bool(self.LINKEDIN_CLIENT_ID)

    @property
    def has_facebook_api(self) -> bool:
        return bool(self.FACEBOOK_APP_ID)

    @property
    def has_threads_api(self) -> bool:
        return bool(self.THREADS_APP_ID)

    @property
    def has_buffer(self) -> bool:
        return bool(self.BUFFER_ACCESS_TOKEN)

    @property
    def chroma_persist_path(self) -> Path:
        return Path(self.CHROMA_PERSIST_DIRECTORY)

    @property
    def arc_memory_path(self) -> Path:
        return Path(self.ARC_AGENT_MEMORY_PATH)

    @property
    def clients_dir_path(self) -> Path:
        return Path(self.NEXEARCH_CLIENTS_DIR)

    @property
    def skills_path(self) -> Path:
        return Path(self.ARC_AGENT_SKILLS_PATH)

    @property
    def custom_tools_path(self) -> Path:
        return Path(self.ARC_AGENT_CUSTOM_TOOLS_PATH)

    @field_validator(
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "ANTHROPIC_MODEL",
        "OPENAI_MODEL",
        "GEMINI_MODEL",
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

    @field_validator("NEXEARCH_CLIENTS_DIR", mode="before")
    @classmethod
    def _resolve_clients_dir(cls, value):
        raw = str(value or "").strip()
        if not raw:
            return _DEFAULT_NEXEARCH_CLIENTS_DIR
        return _resolve_repo_relative_path(raw)

    @field_validator(
        "CHROMA_PERSIST_DIRECTORY",
        "ARC_AGENT_MEMORY_PATH",
        "ARC_AGENT_CUSTOM_TOOLS_PATH",
        mode="before",
    )
    @classmethod
    def _resolve_local_directories(cls, value):
        return _resolve_repo_relative_path(str(value or ""))

    @field_validator("ARC_AGENT_SKILLS_PATH", mode="before")
    @classmethod
    def _resolve_skills_path(cls, value):
        return _resolve_repo_relative_path(str(value or ""), anchor=_REPO_ROOT)

    @model_validator(mode="after")
    def _apply_runtime_guards(self):
        return self

    model_config = SettingsConfigDict(
        env_file=[".env", "backend/.env", "../backend/.env", str(Path(__file__).resolve().parent.parent / "backend" / ".env")],
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_nexearch_settings() -> NexearchSettings:
    """Factory — returns the Nexearch settings singleton."""
    return NexearchSettings()
