from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str = Field(..., description="Telegram Bot Token from BotFather")
    youtube_api_key: str = Field(..., description="YouTube Data API v3 Key")
    database_url: str = Field(default="sqlite+aiosqlite:///./bot.db", description="Database URL")
    webhook_host: str = Field(
        default="localhost", description="Webhook host for receiving notifications"
    )
    webhook_port: int = Field(default=8000, description="Webhook port")
    webhook_path: str = Field(default="/webhook", description="Webhook path")
    log_level: str = Field(default="INFO", description="Logging level")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
