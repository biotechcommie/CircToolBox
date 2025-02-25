# circ_toolbox_project/circ_toolbox/backend/scripts/init_db.py
import asyncio
from circ_toolbox.backend.database.base import Base, engine
from circ_toolbox.backend.database.models import *
from alembic.config import Config
from alembic import command
from circ_toolbox.config import ALEMBIC_INI_PATH, ALEMBIC_MIGRATION_VERSION_PATH
import os
import logging

logger = logging.getLogger(__name__)

async def drop_all_tables():
    """
    Drop all tables from the database.
    WARNING: This will delete all data!
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("⚠️  All database tables dropped.")

def clean_migrations():
    """
    Remove the Alembic migrations folder contents to reset migration history.
    """
    if os.path.exists(ALEMBIC_MIGRATION_VERSION_PATH):
        for file in os.listdir(ALEMBIC_MIGRATION_VERSION_PATH):
            file_path = os.path.join(ALEMBIC_MIGRATION_VERSION_PATH, file)
            os.remove(file_path)
        print("⚠️  Migration history cleaned.")

async def init_db():
    """
    Initialize the database schema using SQLAlchemy models.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database schema initialized successfully.")

def generate_initial_migration():
    """Generate an initial migration if no migration history exists."""
    migration_dir = ALEMBIC_MIGRATION_VERSION_PATH
    if not os.path.exists(migration_dir) or not os.listdir(migration_dir):
        logger.warning("⚠️ No migration history found. Generating initial migration...")
        alembic_cfg = Config(ALEMBIC_INI_PATH)
        
        # Create a migration script without applying it
        command.revision(alembic_cfg, autogenerate=True, message="Initial migration")
        logger.info("✅ Initial migration created. Please review it before applying.")

        # Instruction for the user
        print("\n⚠️  Review the migration file generated in:")
        print(f"   {ALEMBIC_MIGRATION_VERSION_PATH}")
        print("\n🚀 Once reviewed, apply the migration using:")
        print(f"   alembic -c {ALEMBIC_INI_PATH} upgrade head")
        print("✅ Migration will be applied successfully.")

async def reset_database():
    """Completely reset the database and migration history."""
    await drop_all_tables()
    clean_migrations()
    await init_db()
    generate_initial_migration()
    print("✅ Database has been reset successfully.")
    print("\n🚀 To apply the migration, run:")
    print(f"   alembic -c {ALEMBIC_INI_PATH} upgrade head")
    print("✅ Migration will be applied successfully.")

async def setup_database():
    """Handle database initialization without applying migrations."""
    logger.info("Starting database initialization...")
    await init_db()
    logger.info("Database schema created.")
    # generate_initial_migration()
    print("✅ Database setup completed successfully.")
    print("\n🚀 Next steps:")
    print("1. Review the generated migration file in:")
    print(f"   {ALEMBIC_MIGRATION_VERSION_PATH}")
    print("2. Apply it manually using:")
    print(f"   alembic -c {ALEMBIC_INI_PATH} upgrade head")
    print("✅ Database is now ready for use.")
    

# ----- # 

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        asyncio.run(reset_database())
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--dropdown":
        asyncio.run(drop_all_tables())
    
    else:
        asyncio.run(setup_database())  # Unified call for database setup





'''

POSTGRES_HOST=localhost (use 127.0.0.1 for direct host access).

If using Docker, the host should be the service name defined in docker-compose.yml, e.g.:

ini
Copiar
Editar
POSTGRES_HOST=db  # Referring to the database container


'''
'''


import asyncio
import psycopg2
from urllib.parse import urlparse
from circ_toolbox.config import DATABASE_URL
from circ_toolbox.backend.database.base import Base, engine
from circ_toolbox.backend.database.models import *  # Ensure models are loaded

# Extract connection params for PostgreSQL management operations
db_url = urlparse(DATABASE_URL)
db_name = db_url.path[1:]  # Remove leading '/'
db_user = db_url.username
db_pass = db_url.password
db_host = db_url.hostname
db_port = db_url.port

def create_database_if_not_exists():
    """
    Connects to PostgreSQL and creates the database if it does not exist.
    """
    try:
        with psycopg2.connect(
            dbname="postgres", user=db_user, password=db_pass, host=db_host, port=db_port
        ) as conn:
            conn.autocommit = True
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
                exists = cursor.fetchone()
                if not exists:
                    cursor.execute(f'CREATE DATABASE {db_name}')
                    print(f"✅ Database '{db_name}' created successfully.")
                else:
                    print(f"ℹ️ Database '{db_name}' already exists.")
    except Exception as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")

async def init_db():
    """
    Initialize the database by creating all tables defined in the models.
    """

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database schema initialized successfully.")

if __name__ == "__main__":
    create_database_if_not_exists()
    asyncio.run(init_db())


'''





'''
# THE CODE BELLOW IS FOR SQlite USAGE.

from circ_toolbox.backend.database.base import Base, engine
from circ_toolbox.backend.database.models import *  # Import all models to ensure proper dependency loading
# from circ_toolbox.config import DATABASE_DIR, DATABASE_FILENAME # only for SQLite
import os
import asyncio

async def init_db():
    """
    Initialize the database by creating all tables defined in the models.
    """
    # Ensure the database directory exists
    os.makedirs(DATABASE_DIR, exist_ok=True)
    db_path = os.path.join(DATABASE_DIR, DATABASE_FILENAME)

    if not os.path.exists(db_path):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print(f"Database initialized successfully at {db_path}.")
    else:
        print(f"Database already exists at {db_path}.")

if __name__ == "__main__":
    asyncio.run(init_db())

'''    



'''
Run the Script
From your project root, run the script to initialize the database:

bash
Copiar
python circ_toolbox/backend/database/init_db.py
This will create the resources.db file and the resources table based on your SQLAlchemy model.



Testing Initialization
Run init_db.py to ensure the database schema is created:

bash
Copiar
python circ_toolbox/backend/database/init_db.py
Inspect the SQLite database to verify the schema:

bash
Copiar
sqlite3 resources.db
.tables

'''


'''
python circ_toolbox/backend/scripts/init_db.py


sqlite3 circ_toolbox/backend/database/resources.db ".tables"

python circ_toolbox/backend/scripts/create_admin_user.py


'''