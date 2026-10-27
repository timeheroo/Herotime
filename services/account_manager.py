
"""
API configuration manager.

API Hash storage is disabled until secure encryption is configured.
Never save API Hash values in plaintext.
"""


async def add_api_config(name, api_id, api_hash, created_by):
    raise RuntimeError(
        "API configuration is disabled because secure API Hash "
        "encryption has not been configured."
    )


async def list_api_configs():
    """Return an empty list while API configuration is disabled."""
    return []


async def get_api_config(config_id):
    """API configuration retrieval is disabled."""
    return None


async def get_decrypted_api_hash(config_id):
    raise RuntimeError(
        "API Hash access is disabled until secure encryption is configured."
    )


async def rename_api_config(config_id, new_name):
    return False


async def set_api_config_status(config_id, is_active):
    return False


async def remove_api_config(config_id):
    return False


async def get_active_api_configs():
    """No active API configurations are available."""
    return []
