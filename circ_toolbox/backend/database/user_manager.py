# circ_toolbox/backend/database/user_manager.py
"""
User Management Service for CircToolbox API.

This module implements a custom `UserManager` using FastAPI Users
for authentication, user management, and role-based access control.

It provides:
- User registration hooks
- User deletion with superuser protection
- User listing with pagination
- User updates (both admin and self-management)

The class integrates FastAPI's dependency injection and SQLAlchemy for 
async database interactions, ensuring proper session management.
"""

import uuid
from typing import Optional, List
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from circ_toolbox.backend.database.models import Users
from circ_toolbox.backend.database.user_db import get_user_db
from circ_toolbox.backend.database.base import get_session, get_session_instance
from circ_toolbox.config import SECRET_KEY
from circ_toolbox.backend.utils.logging_config import get_logger, log_runtime
from circ_toolbox.backend.api.schemas.user_schemas import UserUpdate, UserCreate
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from circ_toolbox.backend.exceptions import UserAlreadyExistsError, UserNotFoundError, LastSuperuserError, UnexpectedDatabaseError



class UserManager(UUIDIDMixin, BaseUserManager[Users, uuid.UUID]):
    """
    Custom UserManager for handling user-related operations.

    This class extends `BaseUserManager` from FastAPI Users and adds:
    - Logging hooks for user actions.
    - Superuser protection to prevent accidental deletion.
    - Support for listing users with pagination.
    - Update methods for both admin and regular users.

    Attributes:
        reset_password_token_secret (str): Secret key for password reset tokens.
        verification_token_secret (str): Secret key for email verification tokens.
    """

    reset_password_token_secret = SECRET_KEY
    verification_token_secret = SECRET_KEY

    def __init__(self, user_db: SQLAlchemyUserDatabase[Users, uuid.UUID]):  # ✅ Expect `user_db`
        """
        Initialize the `UserManager` with the necessary dependencies.

        Args:
            user_db (SQLAlchemyUserDatabase[Users, uuid.UUID]): The database instance for user management.
        """
        super().__init__(user_db)  # ✅ Call parent constructor
        self.logger = get_logger("user_manager")  # ✅ Keep logging

    @log_runtime("user_manager")
    async def on_after_register(self, user: Users, request: Optional[Request] = None):
        """
        Hook triggered after a new user is registered.

        Args:
            user (Users): The newly registered user.
            request (Optional[Request]): The request object (if applicable).
        """
        self.logger.info(f"User {user.email} has registered.")

    @log_runtime("user_manager")
    async def on_after_forgot_password(self, user: Users, token: str, request: Optional[Request] = None):
        """
        Hook triggered when a user requests a password reset.

        Args:
            user (Users): The user requesting a password reset.
            token (str): The generated reset token.
            request (Optional[Request]): The request object (if applicable).
        """
        self.logger.info(f"User {user.email} forgot their password. Reset token: {token}")

    @log_runtime("user_manager")
    async def on_after_request_verify(self, user: Users, token: str, request: Optional[Request] = None):
        """
        Hook triggered when a user requests email verification.

        Args:
            user (Users): The user requesting verification.
            token (str): The generated verification token.
            request (Optional[Request]): The request object (if applicable).
        """
        self.logger.info(f"Verification requested for user {user.email}.")

    # ===========================
    # INTERNAL SESSION HANDLING
    # ===========================

    @log_runtime("user_manager")
    async def _get_session(self, session: Optional[AsyncSession]) -> tuple[AsyncSession, bool]:
        """
        Ensures that the UserManager has an active database session.

        Args:
            session (Optional[AsyncSession]): The provided session.

        Returns:
            Tuple[AsyncSession, bool]: The active session and a flag indicating if we should close it.
        """
        if session is None:
            try:
                # ✅ If running in FastAPI, use its session (dependency injection)
                async for fastapi_session in get_session():  
                    return fastapi_session, False  # ✅ FastAPI will close it automatically
            except RuntimeError:
                # ✅ If FastAPI context is not available, fallback to manual session (CLI or script)
                standalone_session = await get_session_instance()
                return standalone_session, True  # ✅ We must manually close it later

        return session, False  # ✅ If session was provided externally, do NOT close manually

   
    # ===========================
    # USER MANAGEMENT METHODS
    # ===========================

    @log_runtime("user_manager")
    async def has_any_admin(self, session: Optional[AsyncSession] = None) -> bool:
        """
        Check if at least one admin (superuser) exists.

        Args:
            session (Optional[AsyncSession]): The database session.

        Returns:
            bool: True if at least one admin exists, False otherwise.

        Raises:
            UnexpectedDatabaseError: If a database error occurs while retrieving users.
        """
        session, close_session = await self._get_session(session)  # ✅ Get session, handle FastAPI or manual calls
        try:
            result = await session.execute(select(Users).where(Users.is_superuser == True))
            admins = result.scalars().all()
            has_admin = len(admins) > 0  # ✅ Return True if at least one admin exists

            # ✅ DO NOT COMMIT - is a read-only database operation

            return has_admin
        except SQLAlchemyError as e:
            self.logger.error(f"Database error checking admin existence: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))
        
        except Exception as e:
            self.logger.error(f"Unexpected error checking admin existence: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))

        finally:
            if close_session:
                await session.close()
                
    @log_runtime("user_manager")
    async def create_user(self, user_create: UserCreate, session: Optional[AsyncSession] = None) -> Users:
        """
        Create a new user, ensuring unique constraints.

        Args:
            user_create (UserCreate): User creation data.
            session (Optional[AsyncSession]): Database session.

        Returns:
            Users: The created user.

        Raises:
            UserAlreadyExistsError: If the user already exists.
            UnexpectedDatabaseError: If an unexpected database error occurs.
        """
        session, close_session = await self._get_session(session)  # ✅ Get session
        try:

            existing_user = await session.execute(
                select(Users).where(
                    (Users.email == user_create.email) | (Users.username == user_create.username)
                )
            )
            if existing_user.scalars().first():
                self.logger.warning(f"User creation blocked: Email={user_create.email}, Username={user_create.username} already exists")
                raise UserAlreadyExistsError() # ✅ KEEP IT AS VALUEERROR


            # ✅ Attempt user creation
            new_user = await self.create(user_create)  # ✅ Use inherited FastAPI Users `create()`

            # if close_session:
                # await session.commit()  # DO NOT COMMIT BECAUSE THE SQLAlchemyUserDatabase create method already does it. # ✅ Commit only if we created the session

            return new_user
        

        except UserAlreadyExistsError as e:
            if close_session:
                await session.rollback()
            raise e  # Propagate to higher layers

        except IntegrityError:
            if close_session:
                await session.rollback()  # ✅ Rollback only if we created the session
            self.logger.error("IntegrityError: Duplicate user creation attempted - User creation failed: Email or username already exists")
            raise UserAlreadyExistsError()  # ✅ Raise meaningful error

        except SQLAlchemyError as e:
            if close_session:
                await session.rollback()
            self.logger.error(f"Database error creating user: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))  # ✅ Properly return 500

        except Exception as e:
            if close_session:
                await session.rollback()  # ✅ Ensure rollback on unexpected failure
            self.logger.error(f"Unexpected error creating user: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e)) # ✅ Raise generic error

        finally:
            if close_session:
                await session.close()  # ✅ Always close session if we created it

    @log_runtime("user_manager")
    async def delete_user(self, user_id: uuid.UUID, session: Optional[AsyncSession] = None) -> None:
        """
        Delete a user but prevent deletion of the last superuser.

        Args:
            user_id (uuid.UUID): The user ID to delete.
            session (Optional[AsyncSession]): The database session.

        Raises:
            UserNotFoundError: If the user does not exist.
            LastSuperuserError: If attempting to delete the last superuser.
            UnexpectedDatabaseError: If an unexpected database error occurs.
        """
        session, close_session = await self._get_session(session)
        try:
            user = await session.get(Users, user_id)
            if not user:
                self.logger.warning(f"Attempted to delete non-existent user: {user_id}")
                raise UserNotFoundError() # ✅ Passed to Orchestrator

            # ✅ Check if this is the last superuser
            result = await session.execute(select(Users).where(Users.is_superuser == True))
            superuser_count = len(result.scalars().all())

            if user.is_superuser and superuser_count <= 1:
                self.logger.warning(f"Attempted to delete the last superuser. Remaining superusers: {superuser_count}")
                raise LastSuperuserError()  # ✅ Prevent last admin deletion

            await self.delete(user)  # ✅ Calls inherited `delete()`

            # if close_session:
                # await session.commit()  # ✅ Commit only if we created the session
            
        except UserNotFoundError as e:
            if close_session:
                await session.rollback()
            raise e  # Propagate to higher layers

        except LastSuperuserError as e:
            if close_session:
                await session.rollback()
            raise e  # Propagate to higher layers


        except SQLAlchemyError as e:
            if close_session:
                await session.rollback()
            self.logger.error(f"Database error deleting user {user_id}: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))
        except Exception as e:
            if close_session:
                await session.rollback()  # ✅ Ensure rollback on failure
            self.logger.error(f"Unexpected error deleting user {user_id}: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))
        
        finally:
            if close_session:
                await session.close()

    @log_runtime("user_manager")
    async def list_all_users(self, skip: int, limit: int, session: Optional[AsyncSession] = None) -> List[Users]:
        """
        Retrieve a paginated list of users.

        Args:
            skip (int): Number of users to skip.
            limit (int): Maximum number of users to return.
            session (Optional[AsyncSession]): The database session.

        Returns:
            List[Users]: A list of user records.

        Raises:
            UnexpectedDatabaseError: If a database error occurs while retrieving users.
        """
        session, close_session = await self._get_session(session)
        try:
            result = await session.execute(select(Users).offset(skip).limit(limit))
            users = result.scalars().all()
            return users
            
        except SQLAlchemyError as e:
            if close_session:
                await session.rollback()
            self.logger.error(f"Database error retrieving user list: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))

        except Exception as e:
            if close_session:
                await session.rollback()
            self.logger.error(f"Unexpected error retrieving user list: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))

        finally:
            if close_session:
                await session.close()

    @log_runtime("user_manager")
    async def get_user_by_id(self, user_id: uuid.UUID, session: Optional[AsyncSession] = None) -> Optional[Users]:
        """
        Fetch a user by ID.

        Args:
            user_id (uuid.UUID): The ID of the user to fetch.
            session (Optional[AsyncSession]): The database session.

        Returns:
            Optional[Users]: The user ORM model if found.

        Raises:
            UserNotFoundError: If the user does not exist.
            UnexpectedDatabaseError: If a database error occurs.
        """
        session, close_session = await self._get_session(session)
        try:
            user = await session.get(Users, user_id)
            # ✅ DO NOT COMMIT - Read-only operation
            if not user:
                self.logger.warning(f"User with ID {user_id} not found")
                raise UserNotFoundError()  # ✅ GOOD: Raise a meaningful error

            return user

        except UserNotFoundError as e:
            if close_session:
                await session.rollback()
            raise e  # Propagate to higher layers

        except SQLAlchemyError as e:
            if close_session:
                await session.rollback()
            self.logger.error(f"Database error retrieving user {user_id}: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))

        except Exception as e:
            if close_session:
                await session.rollback()
            self.logger.error(f"Unexpected error retrieving user {user_id}: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))

        finally:
            if close_session:
                await session.close()

    @log_runtime("user_manager")
    async def update_user_by_id(self, user_id: uuid.UUID, update_data: UserUpdate, session: Optional[AsyncSession] = None) -> Users:
        """
        Update a user's profile by ID.

        Args:
            user_id (uuid.UUID): The ID of the user to update.
            update_data (UserUpdate): The fields to update (validated via Pydantic).
            session (Optional[AsyncSession]): The database session.

        Returns:
            Users: The updated user record.

        Raises:
            UserNotFoundError: If the user does not exist.
            UnexpectedDatabaseError: If a database error occurs.
        """
        session, close_session = await self._get_session(session)

        try:
            user = await self.get_user_by_id(user_id, session)  # ✅ Fetch user first
            if not user:
                raise UserNotFoundError()  # ✅ Ensure user exists

            existing_user = await session.execute(
                select(Users).where(
                    (((Users.email == update_data.email) | (Users.username == update_data.username)) &
                    (Users.id != user_id))
                )
            )

            if existing_user.scalars().first():
                self.logger.warning(f"User update blocked: Email={update_data.email}, Username={update_data.username} already exists")
                raise UserAlreadyExistsError() # ✅ KEEP IT AS VALUEERROR
            
            updated_user = await self.update(update_data, user, safe=False)  # ✅ Admin can update all fields

            # if close_session:
                # await session.commit()  # ✅ Commit only if we created the session

            return updated_user

        except UserNotFoundError as e:
            if close_session:
                await session.rollback()
            raise e  # Propagate to higher layers
        except UserAlreadyExistsError as e:
            if close_session:
                await session.rollback()
            raise e  # Propagate to higher layers



        except SQLAlchemyError as e:
            if close_session:
                await session.rollback()
            self.logger.error(f"Database error retrieving user {user_id}: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))

        except Exception as e:
            if close_session:
                await session.rollback()
            self.logger.error(f"Unexpected error retrieving user {user_id}: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))


        finally:
            if close_session:
                await session.close()    # ✅ Close session if we created it


    @log_runtime("user_manager")
    async def user_is_admin(self, user_id: uuid.UUID, session: Optional[AsyncSession] = None) -> bool:
        """
        Check if a user is an admin.

        Args:
            user_id (UUID): The user ID to check.
            session (AsyncSession): The database session.

        Returns:
            bool: True if the user is an admin, False otherwise.
        """
        session, close_session = await self._get_session(session)  # ✅ Get session

        try:
            stmt = select(Users.is_superuser).where(Users.id == user_id)
            result = await session.execute(stmt)
            is_admin = result.scalar_one_or_none()

            return bool(is_admin)  # ✅ Ensure it returns True/False

        except SQLAlchemyError as e:
            self.logger.error(f"Database error checking admin status for user {user_id}: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))

        except Exception as e:
            self.logger.error(f"Unexpected error checking admin status for user {user_id}: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))

        finally:
            if close_session:
                await session.close()

# ===========================
# Dependency Injection for UserManager
# ===========================
async def get_user_manager(
    user_db: SQLAlchemyUserDatabase[Users, uuid.UUID] = Depends(get_user_db),
):
    """
    Provides an instance of `UserManager` for dependency injection.

    Args:
        user_db (SQLAlchemyUserDatabase[Users, uuid.UUID]): The user database dependency.

    Yields:
        UserManager: The user management service.
    """
    yield UserManager(user_db) # ✅ Now `UserManager` correctly expects `user_db`

