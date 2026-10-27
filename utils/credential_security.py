
from cryptography.fernet import Fernet, InvalidToken

from config import CREDENTIAL_ENCRYPTION_KEY


def _get_fernet() -> Fernet:
    """Create a Fernet encryption handler using the configured key."""
    if not CREDENTIAL_ENCRYPTION_KEY:
        raise RuntimeError(
            "CREDENTIAL_ENCRYPTION_KEY Railway variable is missing."
        )

    try:
        return Fernet(CREDENTIAL_ENCRYPTION_KEY.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError(
            "CREDENTIAL_ENCRYPTION_KEY is invalid. "
            "Generate a valid Fernet key."
        ) from exc


def encrypt_api_hash(api_hash: str) -> str:
    """Encrypt an API Hash before saving it to the database."""
    if not isinstance(api_hash, str) or not api_hash.strip():
        raise ValueError("API Hash cannot be empty.")

    encrypted = _get_fernet().encrypt(
        api_hash.strip().encode("utf-8")
    )
    return encrypted.decode("utf-8")


def decrypt_api_hash(encrypted_api_hash: str) -> str:
    """Decrypt an API Hash retrieved from the database."""
    if not isinstance(encrypted_api_hash, str) or not encrypted_api_hash:
        raise ValueError("Encrypted API Hash cannot be empty.")

    try:
        decrypted = _get_fernet().decrypt(
            encrypted_api_hash.encode("utf-8")
        )
        return decrypted.decode("utf-8")
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise ValueError(
            "API Hash decryption failed. Check the encryption key "
            "and stored database value."
        ) from exc
