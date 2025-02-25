# circ_toolbox_project/circ_toolbox/backend/database/migrations/env.py
from logging.config import fileConfig
import sys
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
import fastapi_users_db_sqlalchemy
import fastapi_users_db_sqlalchemy.generics
_ = fastapi_users_db_sqlalchemy.generics.GUID  # Force resolution of GUID

from sqlalchemy.ext.compiler import compiles
from fastapi_users_db_sqlalchemy.generics import GUID

# Custom render function for our custom GUID type.
def render_item(type_, obj, autogen_context):
    if type_ == "type" and isinstance(obj, GUID):
        # Instead of returning "GUID()", return SQLAlchemy's UUID type.
        return "sa.dialects.postgresql.UUID()"
    # Fallback: use the default rendering.
    return False


from circ_toolbox.config import DATABASE_URL  # Import the database URL from your config.py
from circ_toolbox.backend.database.base import Base
from sqlalchemy import create_engine
from circ_toolbox.backend.database.models import *

# Check if using SQLite async driver and replace for migration
if "sqlite+aiosqlite" in DATABASE_URL:
    sync_db_url = DATABASE_URL.replace("sqlite+aiosqlite", "sqlite")
    print("🔄 Switching to synchronous SQLite driver for migrations")
else:
    sync_db_url = DATABASE_URL


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
# target_metadata = None
target_metadata = Base.metadata  # Link Alembic to your models

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.
# Set the database URL dynamically from config.py or fallback to alembic.ini
current_url = config.get_main_option("sqlalchemy.url")

if not current_url or current_url == "driver://user:pass@localhost/dbname":
    print("⚠️ DATABASE_URL not found in alembic.ini, using fallback from config.py")
    print(sync_db_url)
    if "asyncpg" in DATABASE_URL:
        sync_db_url = DATABASE_URL.replace("asyncpg", "psycopg2")
        print("🔄 Using synchronous psycopg2 driver for migrations")
    else:
        sync_db_url = DATABASE_URL
    config.set_main_option("sqlalchemy.url", sync_db_url)

print(f"✅ Using database URL: {config.get_main_option('sqlalchemy.url')}")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    print("🔧 Running migrations in offline mode.")

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item  # Use our custom renderer
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a synchronous engine."""
    print("🔧 Running migrations in online mode.")

    # Convert the async DB URL to sync (if async is detected)
    sync_db_url = DATABASE_URL.replace("asyncpg", "psycopg2") if "asyncpg" in DATABASE_URL else DATABASE_URL

    # Create a synchronous engine explicitly
    connectable = create_engine(
        sync_db_url,
        poolclass=pool.NullPool,
        echo=False  # Enable SQL logging for debugging
    )

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,  # Detect type changes in columns
                render_item=render_item  # Use our custom renderer
            )
            with context.begin_transaction():
                print("🟢 Running migrations...")
                context.run_migrations()
                print("✅ Migrations completed successfully.")
    except Exception as e:
        print(f"❌ Migration failed: {e}")

print("ℹ️ Checking Alembic migration mode...")

if context.is_offline_mode():
    print("ℹ️ Running offline migrations...")
    run_migrations_offline()
else:
    print("ℹ️ Running online migrations...")
    run_migrations_online()












'''
alembic -c circ_toolbox/backend/database/alembic.ini revision --autogenerate -m "Initial migration"
alembic -c circ_toolbox/backend/database/alembic.ini upgrade head


Modify env.py:

If needed, dynamically set the URL as a fallback:

'''