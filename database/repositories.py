
"""Database repository functions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import OWNER_ID
from database.models import (
    AdminPermission,
    AnalyticsRecord,
    Channel,
    MonitoringSession,
    ReactionConfig,
    TelegramAccount,
    User,
)


# -------------------- USERS --------------------

async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int,
) -> User | None:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_user(
    session: AsyncSession,
    user_id: int,
) -> User | None:
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def list_users(
    session: AsyncSession,
) -> list[User]:
    result = await session.execute(
        select(User).order_by(User.id.desc())
    )
    return list(result.scalars().all())


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    display_name: str | None = None,
) -> User:
    user = await get_user_by_telegram_id(session, telegram_id)

    if user is not None:
        user.username = username
        user.display_name = display_name
        if telegram_id == OWNER_ID:
            user.role = "admin"
    else:
        user = User(
            telegram_id=telegram_id,
            username=username,
            display_name=display_name,
            role="admin" if telegram_id == OWNER_ID else "user",
        )
        session.add(user)

    try:
        await session.commit()
        await session.refresh(user)
    except Exception:
        await session.rollback()
        raise

    return user


# -------------------- CHANNELS --------------------

async def list_channels(
    session: AsyncSession,
    active_only: bool = True,
) -> list[Channel]:
    query = select(Channel).order_by(Channel.id.desc())

    if active_only:
        query = query.where(Channel.is_active.is_(True))

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_channel(
    session: AsyncSession,
    channel_id: int,
) -> Channel | None:
    result = await session.execute(
        select(Channel).where(Channel.id == channel_id)
    )
    return result.scalar_one_or_none()


async def create_channel(
    session: AsyncSession,
    title: str,
    username: str | None = None,
    telegram_chat_id: int | None = None,
    chat_link: str | None = None,
    chat_type: str = "channel",
    created_by_user_id: int | None = None,
) -> Channel:
    channel = Channel(
        title=title,
        username=username,
        telegram_chat_id=telegram_chat_id,
        chat_link=chat_link,
        chat_type=chat_type,
        created_by_user_id=created_by_user_id,
    )
    session.add(channel)

    try:
        await session.commit()
        await session.refresh(channel)
    except Exception:
        await session.rollback()
        raise

    return channel


async def update_channel(
    session: AsyncSession,
    channel_id: int,
    title: str | None = None,
    username: str | None = None,
    chat_link: str | None = None,
) -> Channel | None:
    channel = await get_channel(session, channel_id)

    if channel is None:
        return None

    if title is not None:
        channel.title = title
    if username is not None:
        channel.username = username or None
    if chat_link is not None:
        channel.chat_link = chat_link or None

    try:
        await session.commit()
        await session.refresh(channel)
    except Exception:
        await session.rollback()
        raise

    return channel


async def deactivate_channel(
    session: AsyncSession,
    channel_id: int,
) -> bool:
    channel = await get_channel(session, channel_id)

    if channel is None:
        return False

    channel.is_active = False

    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return True


async def reactivate_channel(
    session: AsyncSession,
    channel_id: int,
) -> bool:
    channel = await get_channel(session, channel_id)

    if channel is None:
        return False

    channel.is_active = True

    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return True


# -------------------- TELEGRAM ACCOUNTS --------------------

async def list_accounts(
    session: AsyncSession,
    active_only: bool = True,
) -> list[TelegramAccount]:
    query = select(TelegramAccount).order_by(
        TelegramAccount.id.desc()
    )

    if active_only:
        query = query.where(TelegramAccount.is_active.is_(True))

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_account(
    session: AsyncSession,
    account_id: int,
) -> TelegramAccount | None:
    result = await session.execute(
        select(TelegramAccount).where(
            TelegramAccount.id == account_id
        )
    )
    return result.scalar_one_or_none()


async def update_account_status(
    session: AsyncSession,
    account_id: int,
    status: str,
    is_active: bool | None = None,
) -> TelegramAccount | None:
    account = await get_account(session, account_id)

    if account is None:
        return None

    account.status = status

    if is_active is not None:
        account.is_active = is_active

    try:
        await session.commit()
        await session.refresh(account)
    except Exception:
        await session.rollback()
        raise

    return account


# -------------------- ADMIN PERMISSIONS --------------------

async def get_admin_permissions(
    session: AsyncSession,
    user_id: int,
) -> list[AdminPermission]:
    result = await session.execute(
        select(AdminPermission)
        .where(AdminPermission.user_id == user_id)
        .order_by(AdminPermission.permission)
    )
    return list(result.scalars().all())


async def set_admin_permission(
    session: AsyncSession,
    user_id: int,
    permission: str,
    is_enabled: bool,
) -> AdminPermission:
    result = await session.execute(
        select(AdminPermission).where(
            AdminPermission.user_id == user_id,
            AdminPermission.permission == permission,
        )
    )
    record = result.scalar_one_or_none()

    if record is None:
        record = AdminPermission(
            user_id=user_id,
            permission=permission,
            is_enabled=is_enabled,
        )
        session.add(record)
    else:
        record.is_enabled = is_enabled

    try:
        await session.commit()
        await session.refresh(record)
    except Exception:
        await session.rollback()
        raise

    return record


# -------------------- REACTION CONFIGURATION --------------------

async def list_reaction_configs(
    session: AsyncSession,
    channel_id: int,
) -> list[ReactionConfig]:
    result = await session.execute(
        select(ReactionConfig)
        .where(ReactionConfig.channel_id == channel_id)
        .order_by(ReactionConfig.id)
    )
    return list(result.scalars().all())


async def set_reaction_config(
    session: AsyncSession,
    channel_id: int,
    emoji: str,
    configured_quantity: int,
    is_enabled: bool = True,
) -> ReactionConfig:
    if configured_quantity < 0:
        raise ValueError("Reaction quantity cannot be negative.")

    result = await session.execute(
        select(ReactionConfig).where(
            ReactionConfig.channel_id == channel_id,
            ReactionConfig.emoji == emoji,
        )
    )
    config = result.scalar_one_or_none()

    if config is None:
        config = ReactionConfig(
            channel_id=channel_id,
            emoji=emoji,
            configured_quantity=configured_quantity,
            is_enabled=is_enabled,
        )
        session.add(config)
    else:
        config.configured_quantity = configured_quantity
        config.is_enabled = is_enabled

    try:
        await session.commit()
        await session.refresh(config)
    except Exception:
        await session.rollback()
        raise

    return config


# -------------------- MONITORING HISTORY --------------------

async def list_monitoring_sessions(
    session: AsyncSession,
    channel_id: int,
    limit: int = 50,
) -> list[MonitoringSession]:
    limit = max(1, min(limit, 200))

    result = await session.execute(
        select(MonitoringSession)
        .where(MonitoringSession.channel_id == channel_id)
        .order_by(MonitoringSession.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# -------------------- OBSERVED ANALYTICS --------------------

async def list_analytics(
    session: AsyncSession,
    channel_id: int,
    limit: int = 100,
) -> list[AnalyticsRecord]:
    limit = max(1, min(limit, 500))

    result = await session.execute(
        select(AnalyticsRecord)
        .where(AnalyticsRecord.channel_id == channel_id)
        .order_by(AnalyticsRecord.observed_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
