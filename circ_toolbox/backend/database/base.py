# circ_toolbox_project/circ_toolbox/backend/database/base.py
"""
Async database connection and session management.

Provides:
- `get_session`: Dependency injection for async FastAPI routes.
- `create_db_and_tables`: Function to initialize tables.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from circ_toolbox.config import DATABASE_URL
# from sqlalchemy.orm import registry

# Create the declarative base for models
Base = declarative_base()

# Async database engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Async session factory
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)



# ✅ Corrected `get_session()` without auto-commit/close
async def get_session():
    """
    Yields an async session for database transactions.

    Used as a dependency in FastAPI routes.
    
    Yields:
        AsyncSession: A SQLAlchemy async session.
    """
    async with SessionLocal() as session:
        try:
            yield session  # ✅ Dependency-injected session
        except Exception as e:
            await session.rollback()  # ✅ Rollback only if error  - Probabilidade de ser problemático pois 'async with' já pode ter fechado (close) a sessão antes de chegar aqui - depuração necessária.
            raise


async def get_session_instance():
    session = SessionLocal()
    try:
        return session
    except Exception as e:
        await session.rollback()
        raise
#    finally:
#        await session.close()


# Function to create database tables (for testing and local development)
async def create_db_and_tables():
    """Creates database tables asynchronously (for initial setup)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


'''

# Dependency to get an async session for FastAPI
async def get_session():
    """
    Yields an async session for database transactions.

    Used as a dependency in FastAPI routes.

    Yields:
        AsyncSession: A SQLAlchemy async session.
    """
    async with SessionLocal() as session: # ✅ Opens session
        try:
            yield session  # ✅ Dependency-injected session # Let the calling function handle commit/rollback
            await session.commit()  # ✅ Commits automatically # Ensure transactions are committed
        except Exception as e:
            await session.rollback() # ✅ Rolls back on error # Rollback in case of error
            raise
        finally:
            await session.close() # ✅ Closes session # Always close the session

'''


'''
    

# Dependency to get an async session
async def get_session():
    session = SessionLocal()
    try:
        yield session
        await session.commit()  # Ensure data persistence
    finally:
        await session.close()


async def get_session():
    session = SessionLocal()
    try:
        yield session  # Let handlers control commit/rollback
    finally:
        await session.close()


async def get_session():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()  # Ensure transactions are committed
        except Exception as e:
            await session.rollback()  # Rollback in case of error
            raise
        finally:
            await session.close()  # Always close session


async def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.commit()  # Ensure session commits changes before closing
        await session.close()


async def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.close()


# Dependency to get an async session
async def get_session():
    async with SessionLocal() as session:
        yield session

        

async def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.close()


        
2. Environment Configuration:
The DATABASE_URL is hardcoded. It would be better to use environment variables for flexibility:
python
Copiar
import os
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./resources.db")
3. Error Handling:
If the database connection fails, it might result in unhandled exceptions. You could add a try-except block during engine creation or session initialization.

'''