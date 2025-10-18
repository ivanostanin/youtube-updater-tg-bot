from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    subscriptions = relationship("Subscription", back_populates="user")


class YouTubeChannel(Base):
    __tablename__ = "youtube_channels"

    id = Column(Integer, primary_key=True)
    channel_id = Column(String, unique=True, nullable=False, index=True)
    channel_name = Column(String, nullable=False)
    channel_url = Column(String, nullable=False)
    feed_url = Column(String, nullable=True)
    last_checked = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    subscriptions = relationship("Subscription", back_populates="channel")
    videos = relationship("Video", back_populates="channel")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("youtube_channels.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    notification_enabled = Column(Boolean, default=True)

    user = relationship("User", back_populates="subscriptions")
    channel = relationship("YouTubeChannel", back_populates="subscriptions")


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)
    video_id = Column(String, unique=True, nullable=False, index=True)
    channel_id = Column(Integer, ForeignKey("youtube_channels.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String, nullable=False)
    published_at = Column(DateTime, nullable=False)
    thumbnail_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    channel = relationship("YouTubeChannel", back_populates="videos")
    notifications = relationship("Notification", back_populates="video")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    message_id = Column(String, nullable=True)

    video = relationship("Video", back_populates="notifications")
