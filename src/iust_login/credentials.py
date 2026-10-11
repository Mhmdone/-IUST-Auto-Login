"""Secure credential management for IUST Auto Login.

Credentials are stored using the system keyring when available,
with an encrypted file fallback. Passwords are NEVER logged or
stored in plaintext.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SERVICE_NAME = "iust-auto-login"
USERNAME_KEY = "username"


def _secure_write_text(filepath: Path, content: str) -> None:
    """Write text to a file with secure permissions from creation.

    Uses os.open with O_CREAT to set 0o600 permissions atomically,
    avoiding TOCTOU race conditions.
    """
    fd = os.open(str(filepath), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, content.encode("utf-8"))
    finally:
        os.close(fd)


def _secure_write_bytes(filepath: Path, content: bytes) -> None:
    """Write bytes to a file with secure permissions from creation."""
    fd = os.open(str(filepath), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, content)
    finally:
        os.close(fd)


class CredentialStore:
    """Manages secure storage and retrieval of user credentials."""

    def __init__(self, config_dir: Path = None):
        if config_dir is None:
            config_dir = Path.home() / ".config" / "iust-login"
        self.config_dir = config_dir
        self._username_file = self.config_dir / ".username"
        self._key_file = self.config_dir / ".key"
        self._cred_file = self.config_dir / ".credentials"
        self._use_keyring = self._check_keyring()

    @staticmethod
    def _check_keyring() -> bool:
        """Check if system keyring is available and functional."""
        try:
            import keyring
            from keyring.backends.fail import Keyring as FailKeyring

            backend = keyring.get_keyring()
            if isinstance(backend, FailKeyring):
                return False
            # Try a test operation
            keyring.get_password(SERVICE_NAME, "__test__")
            return True
        except Exception:
            return False

    def save(self, username: str, password: str) -> None:
        """Save credentials securely."""
        self.config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Save username to file
        _secure_write_text(self._username_file, username)

        if self._use_keyring:
            self._save_keyring(password)
        else:
            self._save_encrypted(password)

        logger.info("Credentials saved successfully")

    def load(self) -> tuple:
        """Load credentials. Returns (username, password) or raises."""
        if not self._username_file.exists():
            raise FileNotFoundError("No credentials found. Run 'iust-login setup' first.")

        username = self._username_file.read_text(encoding="utf-8").strip()

        if self._use_keyring:
            password = self._load_keyring()
        else:
            password = self._load_encrypted()

        if not password:
            raise ValueError("Could not retrieve password. Run 'iust-login setup' again.")

        return username, password

    def delete(self) -> None:
        """Delete all stored credentials."""
        # Remove username file
        if self._username_file.exists():
            self._username_file.unlink()

        # Remove keyring entry
        if self._use_keyring:
            try:
                import keyring
                keyring.delete_password(SERVICE_NAME, USERNAME_KEY)
            except Exception:
                pass

        # Remove encrypted files
        for f in [self._key_file, self._cred_file]:
            if f.exists():
                f.unlink()

        logger.info("Credentials deleted")

    def exists(self) -> bool:
        """Check if credentials are stored."""
        if not self._username_file.exists():
            return False
        if self._use_keyring:
            try:
                import keyring
                return keyring.get_password(SERVICE_NAME, USERNAME_KEY) is not None
            except Exception:
                return False
        else:
            return self._cred_file.exists()

    # --- Keyring backend ---

    def _save_keyring(self, password: str) -> None:
        import keyring
        keyring.set_password(SERVICE_NAME, USERNAME_KEY, password)
        logger.debug("Password saved to system keyring")

    def _load_keyring(self) -> str:
        import keyring
        password = keyring.get_password(SERVICE_NAME, USERNAME_KEY)
        return password

    # --- Encrypted file fallback ---

    def _get_or_create_key(self) -> bytes:
        """Derive encryption key from system machine-id."""
        import hashlib
        import base64
        
        machine_id = "default-iust-login-salt"
        try:
            if Path("/etc/machine-id").exists():
                machine_id = Path("/etc/machine-id").read_text().strip()
            elif Path("/var/lib/dbus/machine-id").exists():
                machine_id = Path("/var/lib/dbus/machine-id").read_text().strip()
        except Exception:
            pass
            
        # Derive a 32-byte url-safe base64 key suitable for Fernet
        key = hashlib.sha256(machine_id.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(key)

    def _save_encrypted(self, password: str) -> None:
        from cryptography.fernet import Fernet

        key = self._get_or_create_key()
        f = Fernet(key)
        encrypted = f.encrypt(password.encode("utf-8"))

        _secure_write_bytes(self._cred_file, encrypted)
        logger.debug("Password saved to encrypted file")

    def _load_encrypted(self) -> str:
        from cryptography.fernet import Fernet

        if not self._cred_file.exists():
            return None

        key = self._get_or_create_key()
        f = Fernet(key)
        encrypted = self._cred_file.read_bytes()

        try:
            return f.decrypt(encrypted).decode("utf-8")
        except Exception:
            logger.error("Failed to decrypt credentials")
            return None
