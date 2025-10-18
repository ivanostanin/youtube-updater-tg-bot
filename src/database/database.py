from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..utils.config import settings
from .models import Base


engine = create_async_engine(
    settings.database_url,
    echo=settings.log_level.upper() == "DEBUG",
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db_session() -> AsyncSession:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
