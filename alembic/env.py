import asyncio
from logging.config import fileConfig
import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

from alembic import context

from models.base import LocalBase, OnlineBase

load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

target = "local"

cmd_opts = context.config.cmd_opts
if cmd_opts and hasattr(cmd_opts, 'x') and cmd_opts.x is not None:
    opts = cmd_opts.x
    for opt in opts:
        if opt.startswith("target="):
            target = opt.split("=")[1]
            break

if target == "local":
    DB_URL = os.getenv("LOCAL_DB_URL")
    target_metadata = LocalBase.metadata
    version_table = "alembic_version_local"
    context.script.__dict__.pop('_version_locations', None)  # type: ignore
    context.script.version_locations = ["alembic/versions/local"]
else:
    DB_URL = os.getenv("DB_URL")
    target_metadata = OnlineBase.metadata
    version_table = "alembic_version"
    context.script.__dict__.pop('_version_locations', None)  # type: ignore
    context.script.version_locations = ["alembic/versions/online"]

print(context.script.version_locations)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=DB_URL,
        target_metadata=target_metadata,
        version_table=version_table,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, version_table=version_table, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = DB_URL  # type: ignore
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online():
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
