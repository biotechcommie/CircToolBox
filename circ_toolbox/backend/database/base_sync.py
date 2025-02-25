# circ_toolbox_project/circ_toolbox/backend/database/base_sync.py
"""
Synchronous database session management.

This is used for Celery tasks and background jobs that need sync database access.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from circ_toolbox.config import DATABASE_URL
from circ_toolbox.backend.database.base import Base  # Reuse the same Base


# DO NOT DO: - Create the declarative base for models (you can reuse the same Base if desired)
# Base = declarative_base()

# Create a synchronous engine
sync_engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=0,
    pool_recycle=1800,
    pool_pre_ping=True,
    echo=False  # Set to False in production.
)

# Synchronous session factory
SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False
)

def get_sync_session():
    """
    Creates and returns a new synchronous SQLAlchemy session.

    Used in Celery tasks and other synchronous contexts.

    Returns:
        Session: SQLAlchemy session object.
    """
    return SyncSessionLocal()
