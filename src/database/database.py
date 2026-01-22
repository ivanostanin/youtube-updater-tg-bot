import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..utils.config import settings
from .models import Base


logger = logging.getLogger(__name__)


engine = create_async_engine(
    settings.database_url,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _build_alembic_config(
    *, ini_path: Path | None = None, script_location: Path | None = None
) -> Config:
    """Create an Alembic Config that works even when alembic.ini is absent."""
    script_location = script_location or Path(__file__).resolve().parent / "migrations"
    ini_path = ini_path or (Path(__file__).resolve().parents[2] / "alembic.ini")

    if ini_path.exists():
        config = Config(str(ini_path))
    else:
        logger.warning(
            "Alembic configuration file missing; using in-memory defaults",
            extra={"path": str(ini_path)},
        )
        config = Config()

    # Always disable Alembic's logging configuration so our setup controls handlers
    config.attributes["configure_logger"] = False

    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    config.attributes["db_url"] = settings.database_url
    return config


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    """Run database migrations to ensure schema is up to date."""

    def _upgrade() -> None:
        config = _build_alembic_config()
        command.upgrade(config, "head")

    await asyncio.to_thread(_upgrade)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
