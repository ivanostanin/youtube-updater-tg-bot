from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .locale_codes import SUPPORTED_LOCALES, normalize_locale_code


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    telegram_bot_token: str = Field(default="", description="Telegram Bot Token from BotFather")
    youtube_api_key: str = Field(default="", description="YouTube Data API v3 Key")
    database_url: str = Field(default="sqlite+aiosqlite:///./bot.db", description="Database URL")
    webhook_host: str = Field(
        default="localhost", description="Webhook host for receiving notifications"
    )
    webhook_port: int = Field(default=8000, description="Webhook port")
    webhook_path: str = Field(default="/webhook/youtube", description="Webhook path")
    webhook_callback_url: str = Field(
        default="http://localhost:8000/webhook/youtube",
        description="Full callback URL for YouTube webhook notifications (publicly accessible)",
    )
    log_level: str = Field(default="INFO", description="Logging level")
    default_locale: str = Field(
        default="en",
        description="Default locale to use when a chat has not selected a language",
    )
    pubsub_lease_renewal_interval: int = Field(
        default=3600,
        description="Interval (seconds) between lease refresher runs",
    )
    pubsub_lease_renewal_threshold: int = Field(
        default=21_600,
        description="Window (seconds) before expiry when leases should be renewed",
    )
    pubsub_lease_renewal_batch_limit: int | None = Field(
        default=50,
        description="Maximum number of channels to renew per cycle (None for unlimited)",
    )
    dm_channel_context_ttl_minutes: int = Field(
        default=60,
        description="Minutes a DM channel selection remains active before expiring",
    )

    @field_validator("webhook_callback_url")
    @classmethod
    def validate_https_for_production(cls, v: str) -> str:
        """Validate that production URLs use HTTPS."""
        if v and not v.startswith("http://localhost") and not v.startswith("https://"):
            raise ValueError(
                "Production webhook callback URL must use HTTPS. "
                "Only localhost URLs are allowed to use HTTP."
            )
        return v

    @field_validator("default_locale", mode="before")
    @classmethod
    def validate_default_locale(cls, v: str | None) -> str:
        """Ensure DEFAULT_LOCALE stays within the supported catalog."""
        normalized = normalize_locale_code(v) if v else None
        if normalized:
            return normalized
        allowed = ", ".join(SUPPORTED_LOCALES)
        raise ValueError(f"DEFAULT_LOCALE must be one of: {allowed}")

    @field_validator(
        "pubsub_lease_renewal_interval",
        "pubsub_lease_renewal_threshold",
        mode="after",
    )
    @classmethod
    def validate_positive_interval(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Lease renewal intervals must be positive integers.")
        return value

    @field_validator("pubsub_lease_renewal_batch_limit", mode="after")
    @classmethod
    def validate_batch_limit(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value <= 0:
            raise ValueError("Lease renewal batch limit must be positive when provided.")
        return value

    @field_validator("dm_channel_context_ttl_minutes", mode="after")
    @classmethod
    def validate_channel_context_ttl(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("DM channel context TTL must be a positive number of minutes.")
        return value


settings = Settings()
