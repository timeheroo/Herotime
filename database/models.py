"""Database models for the Telegram management system."""
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, CheckConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    """Base class for all database models."""

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class AdminPermission(Base):
    __tablename__ = "admin_permissions"
    __table_args__ = (UniqueConstraint("user_id", "permission", name="uq_admin_user_permission"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    permission: Mapped[str] = mapped_column(String(80), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class Channel(Base):
    __tablename__ = "channels"
    __table_args__ = (UniqueConstraint("username", name="uq_channels_username"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    chat_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chat_type: Mapped[str] = mapped_column(String(30), default="channel", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class TelegramAccount(Base):
    """Metadata only; do not store plaintext session secrets."""
    __tablename__ = "telegram_accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    telegram_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    secret_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class BotTokenRecord(Base):
    """Encrypted bot-token metadata. Never expose encrypted_token via public schemas."""
    __tablename__ = "bot_token_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    telegram_bot_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    encrypted_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class ServiceSetting(Base):
    """Per-channel service target and duration; not observed activity."""
    __tablename__ = "service_settings"
    __table_args__ = (
        UniqueConstraint("channel_id", "service_type", name="uq_service_channel_type"),
        CheckConstraint("configured_quantity >= 0", name="ck_service_quantity_nonnegative"),
        CheckConstraint("duration_hours > 0", name="ck_service_duration_positive"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True, nullable=False)
    service_type: Mapped[str] = mapped_column(String(40), nullable=False)
    configured_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    custom_settings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class ReactionConfig(Base):
    """Reaction preferences; does not generate artificial reactions."""
    __tablename__ = "reaction_configs"
    __table_args__ = (
        UniqueConstraint("channel_id", "emoji", name="uq_reaction_channel_emoji"),
        CheckConstraint("configured_quantity >= 0", name="ck_reaction_quantity_nonnegative"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True, nullable=False)
    emoji: Mapped[str] = mapped_column(String(32), nullable=False)
    configured_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class MonitoringSession(Base):
    """Monitoring sessions and configured targets."""
    __tablename__ = "monitoring_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="stopped", nullable=False)
    configured_target: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class AnalyticsRecord(Base):
    """Observed metrics; unknown values remain NULL."""
    __tablename__ = "analytics_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="telegram", nullable=False)
    metric_name: Mapped[str] = mapped_column(String(80), nullable=False)
    metric_value: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
