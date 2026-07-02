from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

engine_options = {}
if settings.db_supports_schema and settings.db_schema:
    engine_options["schema_translate_map"] = {None: settings.db_schema}

engine_kwargs = {
    "echo": settings.debug,
    "pool_pre_ping": True,
    "execution_options": engine_options,
}

if "sqlite" not in settings.engine_str:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
    })

engine: AsyncEngine = create_async_engine(
    settings.engine_str,
    **engine_kwargs,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


__all__ = [
    "engine",
    "async_session_factory",
    "get_db_session",
]