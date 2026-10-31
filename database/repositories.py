"""Async database repository functions for the Telegram management system.

These functions operate on the SQLAlchemy models in database/models.py.
They persist configuration and observed metrics separately. They do not perform
Telegram automation or generate artificial engagement.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    AdminPermission,
    AnalyticsRecord,
    BotTokenRecord,
    Channel,
    MonitoringSession,
    ReactionConfig,
    ServiceSetting,
    TelegramAccount,
    User,
)


# ---------------------------------------------------------------------------
# Users and permissions
# ---------------------------------------------------------------------------

async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    display_name: Optional[str] = None,
) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user:
        user.username = username
        user.display_name = display_name
        await session.flush()
        return user

    user = User(
        telegram_id=telegram_id,
        username=username,
        display_name=display_name,
    )
    session.add(user)
    await session.flush()
    return user


async def get_user_by_telegram_id(
    session: AsyncSession, telegram_id: int
) -> Optional[User]:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def list_users(session: AsyncSession, limit: int = 100) -> list[User]:
    result = await session.scalars(select(User).order_by(User.id.desc()).limit(limit))
    return list(result.all())


async def set_user_role(
    session: AsyncSession, user_id: int, role: str
) -> Optional[User]:
    if role not in {"user", "admin"}:
        raise ValueError("role must be 'user' or 'admin'")
    user = await session.get(User, user_id)
    if user:
        user.role = role
        await session.flush()
    return user


async def set_user_active(
    session: AsyncSession, user_id: int, is_active: bool
) -> Optional[User]:
    user = await session.get(User, user_id)
    if user:
        user.is_active = is_active
        await session.flush()
    return user


async def list_admin_permissions(
    session: AsyncSession, user_id: int
) -> list[AdminPermission]:
    result = await session.scalars(
        select(AdminPermission)
        .where(AdminPermission.user_id == user_id)
        .order_by(AdminPermission.permission)
    )
    return list(result.all())


async def set_admin_permission(
    session: AsyncSession,
    user_id: int,
    permission: str,
    is_enabled: bool = True,
) -> AdminPermission:
    item = await session.scalar(
        select(AdminPermission).where(
            AdminPermission.user_id == user_id,
            AdminPermission.permission == permission,
        )
    )
    if item:
        item.is_enabled = is_enabled
    else:
        item = AdminPermission(
            user_id=user_id, permission=permission, is_enabled=is_enabled
        )
        session.add(item)
    await session.flush()
    return item


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

async def add_channel(
    session: AsyncSession,
    title: str,
    username: Optional[str] = None,
    telegram_chat_id: Optional[int] = None,
    chat_link: Optional[str] = None,
    chat_type: str = "channel",
    created_by_user_id: Optional[int] = None,
) -> Channel:
    channel = Channel(
        title=title,
        username=username.lstrip("@") if username else None,
        telegram_chat_id=telegram_chat_id,
        chat_link=chat_link,
        chat_type=chat_type,
        created_by_user_id=created_by_user_id,
        is_active=True,
    )
    session.add(channel)
    await session.flush()
    return channel


async def get_channel(session: AsyncSession, channel_id: int) -> Optional[Channel]:
    return await session.get(Channel, channel_id)


async def get_channel_by_username(
    session: AsyncSession, username: str
) -> Optional[Channel]:
    username = username.strip().removeprefix("@")
    return await session.scalar(select(Channel).where(Channel.username == username))


async def list_channels(
    session: AsyncSession, active_only: bool = True
) -> list[Channel]:
    query = select(Channel).order_by(Channel.title)
    if active_only:
        query = query.where(Channel.is_active.is_(True))
    result = await session.scalars(query)
    return list(result.all())


async def set_channel_active(
    session: AsyncSession, channel_id: int, is_active: bool
) -> Optional[Channel]:
    channel = await session.get(Channel, channel_id)
    if channel:
        channel.is_active = is_active
        await session.flush()
    return channel


async def remove_channel(session: AsyncSession, channel_id: int) -> bool:
    """Soft-remove a channel so its history is retained."""
    return (await set_channel_active(session, channel_id, False)) is not None


# ---------------------------------------------------------------------------
# Telegram account metadata (no plaintext session secrets)
# ---------------------------------------------------------------------------

async def add_telegram_account(
    session: AsyncSession,
    label: str,
    telegram_user_id: Optional[int] = None,
    username: Optional[str] = None,
    secret_reference: Optional[str] = None,
    status: str = "pending",
) -> TelegramAccount:
    account = TelegramAccount(
        label=label,
        telegram_user_id=telegram_user_id,
        username=username,
        secret_reference=secret_reference,
        status=status,
        is_active=True,
    )
    session.add(account)
    await session.flush()
    return account


async def get_telegram_account(
    session: AsyncSession, account_id: int
) -> Optional[TelegramAccount]:
    return await session.get(TelegramAccount, account_id)


async def list_telegram_accounts(
    session: AsyncSession, active_only: bool = True
) -> list[TelegramAccount]:
    query = select(TelegramAccount).order_by(TelegramAccount.id.desc())
    if active_only:
        query = query.where(TelegramAccount.is_active.is_(True))
    result = await session.scalars(query)
    return list(result.all())


async def rename_telegram_account(
    session: AsyncSession, account_id: int, label: str
) -> Optional[TelegramAccount]:
    account = await session.get(TelegramAccount, account_id)
    if account:
        account.label = label
        await session.flush()
    return account


async def set_telegram_account_status(
    session: AsyncSession,
    account_id: int,
    status: str,
    is_active: Optional[bool] = None,
) -> Optional[TelegramAccount]:
    account = await session.get(TelegramAccount, account_id)
    if account:
        account.status = status
        if is_active is not None:
            account.is_active = is_active
        await session.flush()
    return account


async def remove_telegram_account(session: AsyncSession, account_id: int) -> bool:
    account = await session.get(TelegramAccount, account_id)
    if not account:
        return False
    account.is_active = False
    account.status = "removed"
    await session.flush()
    return True


# ---------------------------------------------------------------------------
# Bot token records (store encrypted tokens only)
# ---------------------------------------------------------------------------

async def add_bot_token_record(
    session: AsyncSession,
    label: str,
    encrypted_token: str,
    token_fingerprint: str,
    telegram_bot_id: Optional[int] = None,
    username: Optional[str] = None,
    created_by_user_id: Optional[int] = None,
    status: str = "pending",
) -> BotTokenRecord:
    record = BotTokenRecord(
        label=label,
        encrypted_token=encrypted_token,
        token_fingerprint=token_fingerprint,
        telegram_bot_id=telegram_bot_id,
        username=username,
        created_by_user_id=created_by_user_id,
        status=status,
        is_active=True,
    )
    session.add(record)
    await session.flush()
    return record


async def list_bot_token_records(
    session: AsyncSession, active_only: bool = True
) -> list[BotTokenRecord]:
    query = select(BotTokenRecord).order_by(BotTokenRecord.id.desc())
    if active_only:
        query = query.where(BotTokenRecord.is_active.is_(True))
    result = await session.scalars(query)
    return list(result.all())


async def get_bot_token_record(
    session: AsyncSession, record_id: int
) -> Optional[BotTokenRecord]:
    return await session.get(BotTokenRecord, record_id)


async def rename_bot_token_record(
    session: AsyncSession, record_id: int, label: str
) -> Optional[BotTokenRecord]:
    record = await session.get(BotTokenRecord, record_id)
    if record:
        record.label = label
        await session.flush()
    return record


async def update_bot_token_status(
    session: AsyncSession,
    record_id: int,
    status: str,
    is_active: Optional[bool] = None,
    last_checked_at: Optional[datetime] = None,
) -> Optional[BotTokenRecord]:
    record = await session.get(BotTokenRecord, record_id)
    if record:
        record.status = status
        if is_active is not None:
            record.is_active = is_active
        record.last_checked_at = last_checked_at or datetime.now(timezone.utc)
        await session.flush()
    return record


async def remove_bot_token_record(session: AsyncSession, record_id: int) -> bool:
    record = await session.get(BotTokenRecord, record_id)
    if not record:
        return False
    record.is_active = False
    record.status = "removed"
    await session.flush()
    return True


# ---------------------------------------------------------------------------
# Service configuration and reaction preferences
# ---------------------------------------------------------------------------

async def get_service_setting(
    session: AsyncSession, channel_id: int, service_type: str
) -> Optional[ServiceSetting]:
    return await session.scalar(
        select(ServiceSetting).where(
            ServiceSetting.channel_id == channel_id,
            ServiceSetting.service_type == service_type,
        )
    )


async def upsert_service_setting(
    session: AsyncSession,
    channel_id: int,
    service_type: str,
    configured_quantity: Optional[int] = None,
    duration_hours: Optional[int] = None,
    is_enabled: Optional[bool] = None,
    custom_settings: Optional[dict[str, Any]] = None,
    updated_by_user_id: Optional[int] = None,
) -> ServiceSetting:
    setting = await get_service_setting(session, channel_id, service_type)
    if setting is None:
        setting = ServiceSetting(
            channel_id=channel_id,
            service_type=service_type,
            configured_quantity=0 if configured_quantity is None else configured_quantity,
            duration_hours=24 if duration_hours is None else duration_hours,
            is_enabled=False if is_enabled is None else is_enabled,
            custom_settings=custom_settings,
            updated_by_user_id=updated_by_user_id,
        )
        session.add(setting)
    else:
        if configured_quantity is not None:
            setting.configured_quantity = configured_quantity
        if duration_hours is not None:
            setting.duration_hours = duration_hours
        if is_enabled is not None:
            setting.is_enabled = is_enabled
        if custom_settings is not None:
            setting.custom_settings = custom_settings
        if updated_by_user_id is not None:
            setting.updated_by_user_id = updated_by_user_id
    await session.flush()
    return setting


async def list_service_settings(
    session: AsyncSession, channel_id: Optional[int] = None
) -> list[ServiceSetting]:
    query = select(ServiceSetting).order_by(ServiceSetting.channel_id, ServiceSetting.service_type)
    if channel_id is not None:
        query = query.where(ServiceSetting.channel_id == channel_id)
    result = await session.scalars(query)
    return list(result.all())


async def set_reaction_config(
    session: AsyncSession,
    channel_id: int,
    emoji: str,
    configured_quantity: int,
    is_enabled: bool = True,
) -> ReactionConfig:
    config = await session.scalar(
        select(ReactionConfig).where(
            ReactionConfig.channel_id == channel_id,
            ReactionConfig.emoji == emoji,
        )
    )
    if config:
        config.configured_quantity = configured_quantity
        config.is_enabled = is_enabled
    else:
        config = ReactionConfig(
            channel_id=channel_id,
            emoji=emoji,
            configured_quantity=configured_quantity,
            is_enabled=is_enabled,
        )
        session.add(config)
    await session.flush()
    return config


async def list_reaction_configs(
    session: AsyncSession, channel_id: Optional[int] = None
) -> list[ReactionConfig]:
    query = select(ReactionConfig).order_by(ReactionConfig.channel_id, ReactionConfig.emoji)
    if channel_id is not None:
        query = query.where(ReactionConfig.channel_id == channel_id)
    result = await session.scalars(query)
    return list(result.all())


# ---------------------------------------------------------------------------
# Monitoring and observed analytics
# ---------------------------------------------------------------------------

async def start_monitoring_session(
    session: AsyncSession,
    channel_id: int,
    configured_target: Optional[int] = None,
    notes: Optional[str] = None,
) -> MonitoringSession:
    item = MonitoringSession(
        channel_id=channel_id,
        status="running",
        configured_target=configured_target,
        started_at=datetime.now(timezone.utc),
        notes=notes,
    )
    session.add(item)
    await session.flush()
    return item


async def stop_monitoring_session(
    session: AsyncSession, session_id: int, notes: Optional[str] = None
) -> Optional[MonitoringSession]:
    item = await session.get(MonitoringSession, session_id)
    if item:
        item.status = "stopped"
        item.stopped_at = datetime.now(timezone.utc)
        if notes is not None:
            item.notes = notes
        await session.flush()
    return item


async def list_monitoring_sessions(
    session: AsyncSession,
    channel_id: Optional[int] = None,
    limit: int = 100,
) -> list[MonitoringSession]:
    query = select(MonitoringSession).order_by(MonitoringSession.id.desc()).limit(limit)
    if channel_id is not None:
        query = query.where(MonitoringSession.channel_id == channel_id)
    result = await session.scalars(query)
    return list(result.all())


async def record_analytics(
    session: AsyncSession,
    channel_id: int,
    metric_name: str,
    metric_value: Optional[int],
    source: str = "telegram",
    details: Optional[dict[str, Any]] = None,
    observed_at: Optional[datetime] = None,
) -> AnalyticsRecord:
    record = AnalyticsRecord(
        channel_id=channel_id,
        metric_name=metric_name,
        metric_value=metric_value,
        source=source,
        details=details,
        observed_at=observed_at or datetime.now(timezone.utc),
    )
    session.add(record)
    await session.flush()
    return record


async def list_analytics(
    session: AsyncSession,
    channel_id: Optional[int] = None,
    metric_name: Optional[str] = None,
    limit: int = 100,
) -> list[AnalyticsRecord]:
    query = select(AnalyticsRecord).order_by(desc(AnalyticsRecord.observed_at)).limit(limit)
    if channel_id is not None:
        query = query.where(AnalyticsRecord.channel_id == channel_id)
    if metric_name is not None:
        query = query.where(AnalyticsRecord.metric_name == metric_name)
    result = await session.scalars(query)
    return list(result.all())
