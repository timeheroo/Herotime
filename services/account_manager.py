
from asyncpg import UniqueViolationError

from database import get_pool
from utils.credential_security import (
    encrypt_api_hash,
    decrypt_api_hash,
)


async def add_api_config(
    name: str,
    api_id: int,
    api_hash: str,
    created_by: int,
) -> int:
    name = name.strip()

    if not name:
        raise ValueError("Configuration name cannot be empty.")

    if api_id <= 0:
        raise ValueError("API ID must be a positive number.")

    if not api_hash.strip():
        raise ValueError("API Hash cannot be empty.")

    encrypted_hash = encrypt_api_hash(api_hash)

    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO api_configs
                (name, api_id, api_hash_encrypted, is_active, created_by)
            VALUES ($1, $2, $3, TRUE, $4)
            RETURNING id
            """,
            name,
            api_id,
            encrypted_hash,
            created_by,
        )

    return row["id"]


async def list_api_configs():
    pool = await get_pool()

    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT id, name, api_id, is_active, created_at, updated_at
            FROM api_configs
            ORDER BY id DESC
            """
        )


async def get_api_config(config_id: int):
    pool = await get_pool()

    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT id, name, api_id, api_hash_encrypted,
                   is_active, created_at, updated_at
            FROM api_configs
            WHERE id = $1
            """,
            config_id,
        )


async def get_decrypted_api_hash(config_id: int) -> str:
    row = await get_api_config(config_id)

    if row is None:
        raise ValueError("API configuration not found.")

    return decrypt_api_hash(row["api_hash_encrypted"])


async def rename_api_config(config_id: int, new_name: str) -> bool:
    new_name = new_name.strip()

    if not new_name:
        raise ValueError("New configuration name cannot be empty.")

    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE api_configs
            SET name = $1, updated_at = NOW()
            WHERE id = $2
            """,
            new_name,
            config_id,
        )

    return result == "UPDATE 1"


async def set_api_config_status(
    config_id: int,
    is_active: bool,
) -> bool:
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE api_configs
            SET is_active = $1, updated_at = NOW()
            WHERE id = $2
            """,
            is_active,
            config_id,
        )

    return result == "UPDATE 1"


async def remove_api_config(config_id: int) -> bool:
    pool = await get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM api_configs
            WHERE id = $1
            """,
            config_id,
        )

    return result == "DELETE 1"


async def get_active_api_configs():
    pool = await get_pool()

    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT id, name, api_id, api_hash_encrypted
            FROM api_configs
            WHERE is_active = TRUE
            ORDER BY id ASC
            """
        )
