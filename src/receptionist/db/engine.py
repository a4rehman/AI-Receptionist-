import ssl

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from receptionist.config import get_settings

_settings = get_settings()


def _build_tidb_url() -> str:
    return (
        f"mysql+aiomysql://{_settings.tidb_user}:{_settings.tidb_password}"
        f"@{_settings.tidb_host}:{_settings.tidb_port}"
        f"/{_settings.tidb_database}"
    )


def _build_ssl_context() -> ssl.SSLContext | None:
    if not _settings.tidb_ssl_mode or _settings.tidb_ssl_mode == "disabled":
        return None
    context = ssl.create_default_context(cafile=_settings.tidb_ca_path or None)
    if _settings.tidb_ssl_mode == "preferred":
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def _get_engine_kwargs() -> dict:
    kwargs: dict = {
        "echo": _settings.is_development,
        "pool_size": 20,
        "max_overflow": 10,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "connect_args": {"connect_timeout": 10},
    }
    if _settings.tidb_host:
        ssl_context = _build_ssl_context()
        if ssl_context:
            kwargs["connect_args"]["ssl"] = ssl_context
    return kwargs


engine = create_async_engine(
    _settings.database_url_async,
    **_get_engine_kwargs(),
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
