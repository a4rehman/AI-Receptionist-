import asyncio
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from receptionist.config import get_settings
from receptionist.db.models import Base

_settings = get_settings()
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    ssl_context = None
    if _settings.tidb_ca_path:
        import ssl
        ssl_context = ssl.create_default_context(cafile=_settings.tidb_ca_path)
        if _settings.tidb_ssl_mode == "preferred":
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

    connectable = create_async_engine(
        _settings.database_url_async,
        poolclass=pool.NullPool,
        connect_args={"ssl": ssl_context} if ssl_context else {},
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
