
"""Database repository functions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    AdminPermission,
    AnalyticsRecord,
    Channel,
    MonitoringSession,
    ReactionConfig,
    TelegramAccount,
    User,
)


# -------------------------
# Users
# -------------------------

async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int,
) -> User | None:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


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
        await session.commit()
        await session.refresh(user)
        return user

    user = User(
        telegram_id=telegram_id,
        username=username,
        display_name=display_name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# -------------------------
# Channels
# -------------------------

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
    await session.commit()
    await session.refresh(channel)
    return channel


async def deactivate_channel(
    session: AsyncSession,
    channel_id: int,
) -> bool:
    channel = await get_channel(session, channel_id)

    if channel is None:
        return False

    channel.is_active = False
    await session.commit()
    return True


# -------------------------
# Telegram account metadata
# -------------------------

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


# -------------------------
# Admin permissions
# -------------------------

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


# -------------------------
# Reaction configuration
# -------------------------

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


# -------------------------
# Monitoring history
# -------------------------

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


# -------------------------
# Observed analytics
# -------------------------

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
