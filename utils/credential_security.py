
"""
API credential security helpers.

Encryption is disabled because no encryption key is configured.
API Hash values must not be stored or logged in plaintext.
"""

def encrypt_api_hash(api_hash: str) -> str:
    raise RuntimeError(
        "API Hash storage is disabled. "
        "Configure secure encryption before adding API credentials."
    )


def decrypt_api_hash(encrypted_api_hash: str) -> str:
    raise RuntimeError(
        "API Hash decryption is disabled. "
        "Configure secure encryption before using API credentials."
    )
