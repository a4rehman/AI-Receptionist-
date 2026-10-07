from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from receptionist.config import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url_async,
    echo=_settings.is_development,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
