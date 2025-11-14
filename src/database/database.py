import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..utils.config import settings


engine = create_async_engine(
    settings.database_url,
    echo=settings.log_level.upper() == "DEBUG",
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Run database migrations to ensure schema is up to date."""

    def _upgrade() -> None:
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        script_location = Path(__file__).resolve().parent / "migrations"
        config.set_main_option("script_location", str(script_location))
        config.set_main_option("sqlalchemy.url", settings.database_url)
        # Propagate database URL for env.py access
        config.attributes["db_url"] = settings.database_url
        command.upgrade(config, "head")

    await asyncio.to_thread(_upgrade)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
