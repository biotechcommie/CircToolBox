# circ_toolbox/manage.py
import click
import asyncio
from alembic.config import Config
from alembic import command
from circ_toolbox.config import ALEMBIC_INI_PATH
from circ_toolbox.backend.scripts.create_admin_user import create_admin_user
from circ_toolbox.backend.scripts.init_db import setup_database
from sqlalchemy.orm import configure_mappers

# Ensure SQLAlchemy ORM is fully configured before using models
configure_mappers()

@click.group()
def cli():
    """Management commands for CircToolbox."""
    pass

@cli.command()
def migrate():
    """Run Alembic migrations (upgrade to head)."""
    alembic_cfg = Config(ALEMBIC_INI_PATH)
    click.echo("Running migrations...")
    command.upgrade(alembic_cfg, "head")
    click.echo("Migrations applied successfully.")

@cli.command()
def seed():
    """Seed the database (e.g., create the initial admin user)."""
    click.echo("Seeding database...")
    asyncio.run(create_admin_user())
    click.echo("Database seeded successfully.")

@cli.command()
def initdb():
    """Initialize the database schema and run migrations."""
    click.echo("Setting up the database...")
    asyncio.run(setup_database())
    click.echo("Database schema created.")
    # Optionally, run migrations automatically:
    alembic_cfg = Config(ALEMBIC_INI_PATH)
    command.upgrade(alembic_cfg, "head")
    click.echo("Migrations applied successfully.")
    # Then seed the database.
    asyncio.run(create_admin_user())
    click.echo("Database seeded successfully.")

if __name__ == "__main__":
    cli()



'''
With this CLI script you can run, for example:

python manage.py initdb
to initialize the schema, run migrations, and seed the database.
python manage.py migrate
to apply new migrations.
python manage.py seed
to run the seeding process (which creates the admin user).

'''