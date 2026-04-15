"""
Nexearch — Encryption Utility
Fernet encryption for client credentials stored at rest.
"""

from typing import Optional
from loguru import logger

from nexearch.config import get_nexearch_settings


class CredentialEncryptor:
    """Encrypts/decrypts client credentials using Fernet symmetric encryption."""

    def __init__(self):
        settings = get_nexearch_settings()
        self._key = settings.NEXEARCH_FERNET_KEY
        self._fernet = None

        if self._key:
            try:
                from cryptography.fernet import Fernet
                self._fernet = Fernet(self._key.encode() if isinstance(self._key, str) else self._key)
            except Exception as e:
                logger.warning(f"Fernet key invalid: {e}. Credential encryption disabled.")
        else:
            logger.info("No NEXEARCH_FERNET_KEY set — credentials stored in plaintext (dev mode)")

    @property
    def is_configured(self) -> bool:
        return self._fernet is not None

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string. Returns ciphertext or original if encryption unavailable."""
        if not plaintext:
            return ""
        if self._fernet:
            return self._fernet.encrypt(plaintext.encode()).decode()
        return plaintext  # Dev fallback: no encryption

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a string. Returns plaintext or original if decryption unavailable."""
        if not ciphertext:
            return ""
        if self._fernet:
            try:
                return self._fernet.decrypt(ciphertext.encode()).decode()
            except Exception:
                return ciphertext  # Already plaintext or corrupted
        return ciphertext


_encryptor: Optional[CredentialEncryptor] = None


def get_encryptor() -> CredentialEncryptor:
    global _encryptor
    if _encryptor is None:
        _encryptor = CredentialEncryptor()
    return _encryptor
