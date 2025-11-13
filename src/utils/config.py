from pydantic import ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

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


settings = Settings()
