import logging

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

from app.config import settings


logger = logging.getLogger(__name__)

Base = declarative_base()

engine = None
AsyncSessionLocal = None

if settings.analytics_enabled:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.is_development,
        future=True,
    )
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
else:
    logger.warning("DATABASE_URL is not set; analytics and cost tracking are disabled.")


async def get_db():
    """FastAPI dependency: yield an async DB session."""
    if AsyncSessionLocal is None:
        raise RuntimeError("Database is not configured")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_db_optional():
    """FastAPI dependency: yield a session or None when analytics are disabled."""
    if AsyncSessionLocal is None:
        yield None
        return
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create tables on startup."""
    if engine is None:
        logger.warning("Skipping DB table creation: no database configured")
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")
