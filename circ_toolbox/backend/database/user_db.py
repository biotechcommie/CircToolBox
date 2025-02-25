# circ_toolbox_project/circ_toolbox/backend/database/user_db.py
"""
Database utilities for user management in CircToolbox.

Provides dependency injection for:
- `get_user_db`: Used in FastAPI routes to interact with users in an async session.
- `get_user_db_manual`: Used for database seeding (admin creation).
"""

from fastapi import Depends
from circ_toolbox.backend.database.base import get_session
from circ_toolbox.backend.database.models.user_model import Users
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID


async def get_user_db(session: AsyncSession = Depends(get_session)):
    """
    Dependency injection to provide the user database instance.

    Args:
        session (AsyncSession): Async database session.

    Yields:
        SQLAlchemyUserDatabase: A FastAPI Users-compatible database adapter.
    """
    yield SQLAlchemyUserDatabase(session, Users)


async def get_user_db_manual():
    """
    Helper function for direct database access (e.g., admin user creation during startup).

    NOTE: This should only be used in the database seeding process.
    
    Yields:
        SQLAlchemyUserDatabase: A FastAPI Users-compatible database adapter.
    """
    async for session in get_session():  
        try:
            yield SQLAlchemyUserDatabase(session, Users)
            await session.commit()  # Ensure changes persist
        except Exception as e:
            await session.rollback()  # Rollback on failure
            raise e
        finally:
            await session.close()  # Always close the session
            
'''
async def get_user_db_manual():
    async for session in get_session():  # Correct async handling
        try:
            yield SQLAlchemyUserDatabase(session, User)
            await session.commit()  # Ensure commits happen before session closes
        finally:
            await session.close()  # Ensure proper session closure




from circ_toolbox.backend.database.base import Base, get_session
from circ_toolbox.backend.database.models.user import User
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from uuid import UUID


async def get_user_db():
    async for session in get_session():
        yield SQLAlchemyUserDatabase(session, User)

'''

'''
async def get_user_db():
    async for session in get_session():
        yield SQLAlchemyUserDatabase[User, UUID](session=session, user_table=User)



async def get_user_by_id(db: AsyncSession, user_id: UUID):
    user = await db.get(User, user_id)
    if user:
        await db.refresh(user)  # Ensure all fields are loaded
        return UserRead.from_orm(user)
    return None

    
'''


'''


from fastapi_users.exceptions import UserAlreadyExists

async def create_user_manually(email: str, password: str, is_superuser: bool = False):
    async for user_manager in get_user_manager():
        try:
            user = await user_manager.create(
                UserCreate(email=email, password=password, is_superuser=is_superuser)
            )
            print(f"User created {user}")
        except UserAlreadyExists:
            print(f"User {email} already exists")

'''