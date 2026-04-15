"""
NexClip — Storage Abstraction Layer
Implements the Provider pattern so local/S3 can be swapped via config.
"""

import os
import uuid
import shutil
import aiofiles
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, BinaryIO
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class StorageProvider(ABC):
    """Abstract storage interface. All file access goes through this."""

    @abstractmethod
    async def save_file(self, file_data: bytes, directory: str, filename: str) -> str:
        """Save file and return storage path/key."""
        ...

    @abstractmethod
    async def save_upload(self, upload_file, directory: str, filename: Optional[str] = None) -> str:
        """Save an UploadFile (FastAPI) and return storage path."""
        ...

    @abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """Delete a file. Returns True on success."""
        ...

    @abstractmethod
    def get_file_url(self, file_path: str) -> str:
        """Get a serveable URL/path for a stored file."""
        ...

    @abstractmethod
    def get_absolute_path(self, file_path: str) -> str:
        """Get the absolute filesystem path (for local processing)."""
        ...

    @abstractmethod
    async def ensure_directory(self, directory: str) -> None:
        """Ensure a directory exists."""
        ...


class LocalStorageProvider(StorageProvider):
    """Stores files on the local filesystem under STORAGE_LOCAL_ROOT."""

    def __init__(self):
        configured_root = Path(settings.STORAGE_LOCAL_ROOT)
        if configured_root.is_absolute():
            self.root = configured_root.resolve()
        else:
            backend_root = Path(__file__).resolve().parents[2]
            self.root = (backend_root / configured_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorageProvider initialized at {self.root}")

    async def save_file(self, file_data: bytes, directory: str, filename: str) -> str:
        dir_path = self.root / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / filename
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_data)
        # Return relative path from root
        return str(file_path.relative_to(self.root))

    async def save_upload(self, upload_file, directory: str, filename: Optional[str] = None) -> str:
        if filename is None:
            ext = Path(upload_file.filename).suffix if upload_file.filename else ".mp4"
            filename = f"{uuid.uuid4().hex}{ext}"

        dir_path = self.root / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / filename

        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await upload_file.read(1024 * 1024):  # 1MB chunks
                await f.write(chunk)

        return str(file_path.relative_to(self.root))

    async def delete_file(self, file_path: str) -> bool:
        abs_path = self.root / file_path
        try:
            if abs_path.is_file():
                abs_path.unlink()
                return True
            elif abs_path.is_dir():
                shutil.rmtree(abs_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete {file_path}: {e}")
            return False

    def get_file_url(self, file_path: str) -> str:
        return f"/static/storage/{file_path}"

    def get_absolute_path(self, file_path: str) -> str:
        return str(self.root / file_path)

    async def ensure_directory(self, directory: str) -> None:
        (self.root / directory).mkdir(parents=True, exist_ok=True)

    async def clean_temp(self) -> None:
        pass # Optional temp cleanup, could be removed or adjusted.

    def enforce_storage_limit(self, max_bytes: int = 100 * 1024**3) -> None:
        """Enforces a strict size limit by deleting the oldest project folders."""
        while True:
            # Calculate total storage size
            total_size = sum(f.stat().st_size for f in self.root.rglob('*') if f.is_file())
            if total_size <= max_bytes:
                break
                
            # Find project directories (all direct subdirectories)
            project_dirs = [d for d in self.root.iterdir() if d.is_dir()]
            if not project_dirs:
                break # Nothing to delete
                
            # Sort by modification time (oldest first)
            oldest_dir = min(project_dirs, key=lambda d: d.stat().st_mtime)
            logger.info(f"Storage limit exceeded ({total_size / 1024**3:.2f}GB / {max_bytes / 1024**3:.2f}GB). Deleting oldest project: {oldest_dir.name}")
            shutil.rmtree(oldest_dir, ignore_errors=True)


# ── Factory ──────────────────────────────────────────────────────

_storage_instance: Optional[StorageProvider] = None


def get_storage() -> StorageProvider:
    """Factory — returns the active storage provider singleton."""
    global _storage_instance
    if _storage_instance is None:
        if settings.STORAGE_MODE == "s3":
            # Future: return S3StorageProvider()
            raise NotImplementedError("S3 storage not yet implemented. Set STORAGE_MODE=local.")
        _storage_instance = LocalStorageProvider()
    return _storage_instance
