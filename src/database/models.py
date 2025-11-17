from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy models."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    first_name: Mapped[str | None] = mapped_column(String, nullable=True)
    last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    chats: Mapped[list[Chat]] = relationship("Chat", back_populates="user")
    channel_admin_links: Mapped[list[ChannelAdminLink]] = relationship(
        "ChannelAdminLink",
        back_populates="admin",
        cascade="all, delete-orphan",
    )


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    chat_type: Mapped[str] = mapped_column(String(32), nullable=False)
    preferred_locale: Mapped[str | None] = mapped_column(String(5), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    active_channel_chat_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("chats.id"), nullable=True
    )
    active_channel_selected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active_channel_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User | None] = relationship("User", back_populates="chats")
    subscriptions: Mapped[list[Subscription]] = relationship(
        "Subscription", back_populates="chat", cascade="all, delete-orphan"
    )
    notifications: Mapped[list[Notification]] = relationship(
        "Notification", back_populates="chat", cascade="all, delete-orphan"
    )
    active_channel: Mapped[Chat | None] = relationship(
        "Chat",
        remote_side="Chat.id",
        uselist=False,
        foreign_keys=[active_channel_chat_id],
    )
    linked_admins: Mapped[list[ChannelAdminLink]] = relationship(
        "ChannelAdminLink",
        back_populates="channel",
        cascade="all, delete-orphan",
        foreign_keys="ChannelAdminLink.channel_chat_id",
    )


class YouTubeChannel(Base):
    __tablename__ = "youtube_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    channel_name: Mapped[str] = mapped_column(String, nullable=False)
    channel_url: Mapped[str] = mapped_column(String, nullable=False)
    feed_url: Mapped[str | None] = mapped_column(String, nullable=True)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    webhook_callback_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    webhook_lease_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    webhook_lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    webhook_last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    subscriptions: Mapped[list[Subscription]] = relationship(
        "Subscription", back_populates="channel"
    )
    videos: Mapped[list[Video]] = relationship("Video", back_populates="channel")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey("chats.id"), nullable=False)
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("youtube_channels.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    webhook_url: Mapped[str | None] = mapped_column(String, nullable=True)

    chat: Mapped[Chat] = relationship("Chat", back_populates="subscriptions")
    channel: Mapped[YouTubeChannel] = relationship("YouTubeChannel", back_populates="subscriptions")


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("youtube_channels.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    channel: Mapped[YouTubeChannel] = relationship("YouTubeChannel", back_populates="videos")
    notifications: Mapped[list[Notification]] = relationship("Notification", back_populates="video")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey("chats.id"), nullable=False)
    video_id: Mapped[int] = mapped_column(Integer, ForeignKey("videos.id"), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    message_id: Mapped[str | None] = mapped_column(String, nullable=True)

    chat: Mapped[Chat] = relationship("Chat", back_populates="notifications")
    video: Mapped[Video] = relationship("Video", back_populates="notifications")


class ChannelAdminLink(Base):
    __tablename__ = "channel_admin_links"
    __table_args__ = (
        UniqueConstraint("channel_chat_id", "admin_user_id", name="uq_channel_admin_link"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_chat_id: Mapped[int] = mapped_column(Integer, ForeignKey("chats.id"), nullable=False)
    admin_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    channel: Mapped[Chat | None] = relationship(
        "Chat",
        back_populates="linked_admins",
        foreign_keys=[channel_chat_id],
    )
    admin: Mapped[User] = relationship("User", back_populates="channel_admin_links")
