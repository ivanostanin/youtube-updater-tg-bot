from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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

    subscriptions: Mapped[list[Subscription]] = relationship("Subscription", back_populates="user")


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

    subscriptions: Mapped[list[Subscription]] = relationship("Subscription", back_populates="channel")
    videos: Mapped[list[Video]] = relationship("Video", back_populates="channel")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("youtube_channels.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[User] = relationship("User", back_populates="subscriptions")
    channel: Mapped[YouTubeChannel] = relationship("YouTubeChannel", back_populates="subscriptions")


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("youtube_channels.id"), nullable=False)
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
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    video_id: Mapped[int] = mapped_column(Integer, ForeignKey("videos.id"), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    message_id: Mapped[str | None] = mapped_column(String, nullable=True)

    video: Mapped[Video] = relationship("Video", back_populates="notifications")
