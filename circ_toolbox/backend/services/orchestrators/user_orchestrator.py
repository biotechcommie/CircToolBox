# circ_toolbox/backend/services/orchestrators/user_orchestrator.py
"""
User Orchestrator.

This module serves as an intermediary between API routes and `UserManager`.

Responsibilities:
- Receives validated user input from API routes.
- Delegates actual database operations to `UserManager`.
- Implements business logic before interacting with `UserManager`.

This design follows the same pattern used in `PipelineOrchestrator`.
"""

import uuid
from typing import List
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from circ_toolbox.backend.database.models.user_model import Users
from circ_toolbox.backend.api.schemas.user_schemas import UserUpdate, UserCreate
from circ_toolbox.backend.database.user_manager import UserManager, get_user_manager
from circ_toolbox.backend.utils import get_logger, log_runtime
from circ_toolbox.backend.exceptions import UserAlreadyExistsError, UserNotFoundError, LastSuperuserError, UnexpectedDatabaseError

class UserOrchestrator:
    """
    Handles high-level user-related operations before calling `UserManager`.

    Responsibilities:
    - Implements business logic before delegating to `UserManager`.
    - Manages user CRUD operations and role-based access control.
    - Ensures proper error handling and logging.
    """

    def __init__(self, user_manager: UserManager):
        self.user_manager = user_manager
        self.logger = get_logger("user_orchestrator")

    # ===========================
    # COMMON USER ROUTES ORCHESTRATOR METHODS
    # ===========================

    async def update_user_profile(self, user: Users, update_data: dict, session: AsyncSession) -> Users:
        """
        Update the profile of the currently authenticated user.

        Args:
            user (Users): The authenticated user.
            update_data (dict): The fields to update.
                - Fields not provided remain unchanged (`exclude_unset=True`).
                - Validation is enforced through Pydantic.
            session (AsyncSession): The database session.

        Returns:
            Users: The updated user record.

        Raises:
            ValueError: If validation fails.
            UnexpectedDatabaseError: If an unexpected database error occurs.
        """
        try:
            user_update = UserUpdate(**update_data)  # ✅ Ensure correct schema type
            return await self.user_manager.update(user_update, user, safe=True) #  ✅ Safe update for non admin
        except ValueError as ve:
            self.logger.error(f"Validation error updating profile: {str(ve)}")
            raise ve  # ✅ Propagate meaningful validation errors
        except UnexpectedDatabaseError as e:
            raise e  # Propagate to higher layers
        except Exception as e:
            self.logger.error(f"Unexpected error updating profile for user {user.id}: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))
    
    # ===========================
    # ADMIN ROUTES ORCHESTRATOR METHODS
    # ===========================

    async def create_user(self, user_create: UserCreate, session: AsyncSession) -> Users:
        """
        Create a new user.

        Args:
            user_create (UserCreate): The new user's details.
            session (AsyncSession): The database session.

        Returns:
            Users: The created user record.

        Raises:
            UserAlreadyExistsError: If the user already exists.
            UnexpectedDatabaseError: If an unexpected database error occurs.
        """
        try:
            return await self.user_manager.create_user(user_create, session)  # ✅ Uses inherited FastAPI Users method

        except UserAlreadyExistsError as e:
            raise e  # Propagate to higher layers
        except UnexpectedDatabaseError as e:
            raise e  # Propagate to higher layers
        except Exception as e:
            self.logger.error(f"Unexpected error in orchestrator while creating user: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))

    async def list_all_users(self, skip: int, limit: int, session: AsyncSession) -> List[Users]:
        """
        Retrieve a paginated list of all users.

        Args:
            skip (int): The number of users to skip (pagination offset).
            limit (int): The maximum number of users to return.
            session (AsyncSession): The database session.

        Returns:
            List[Users]: A list of user records.

        Raises:
            UnexpectedDatabaseError: If an unexpected database error occurs.
        """
        try:
            users = await self.user_manager.list_all_users(skip, limit, session)
            return users

        except UnexpectedDatabaseError as e:
            raise e  # Propagate to higher layers
        except Exception as e:
            self.logger.error(f"Unexpected error listing users: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))

    async def get_user_by_id(self, user_id: uuid.UUID, session: AsyncSession) -> Users:
        """
        Retrieve a user by their ID.

        Args:
            user_id (uuid.UUID): The unique ID of the user.
            session (AsyncSession): The database session.

        Returns:
            Users: The requested user record.

        Raises:
            UserNotFoundError: If the user does not exist.
            UnexpectedDatabaseError: If an unexpected database error occurs.
        """
        try:
            return await self.user_manager.get_user_by_id(user_id, session)
    
        except UserNotFoundError as e:
            raise e  # Propagate to higher layers
        except UnexpectedDatabaseError as e:
            raise e  # Propagate to higher layers
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving user {user_id}: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))

    async def update_user_by_id(self, user_id: uuid.UUID, update_data: dict, session: AsyncSession) -> Users:
        """
        Allow an admin to update any user's profile.

        Args:
            user_id (uuid.UUID): The target user's ID.
            update_data (dict): The fields to update.
            session (AsyncSession): The database session.

        Returns:
            Users: The updated user record.

        Raises:
            UserNotFoundError: If the user does not exist.
            UnexpectedDatabaseError: If an unexpected error occurs.
        """
        try:
            # ✅ Convert raw dict into validated Pydantic `UserUpdate` model
            user_update = UserUpdate(**update_data)

            # ✅ Delegate update logic to UserManager
            return await self.user_manager.update_user_by_id(user_id, user_update, session)

        except UserAlreadyExistsError as e:
            raise e  # Propagate to higher layers
        except UserNotFoundError as e:
            raise e  # Propagate to higher layers
        except UnexpectedDatabaseError as e:
            raise e  # Propagate to higher layers
        except Exception as e:
            self.logger.error(f"Unexpected error updating user {user_id}: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))

    async def delete_user(self, user_id: uuid.UUID, session: AsyncSession) -> None:
        """
        Allow an admin to delete a user.

        Args:
            user_id (uuid.UUID): The target user's ID.
            session (AsyncSession): The database session.

        Returns:
            None.

        Raises:
            UserNotFoundError: If the user does not exist.
            LastSuperuserError: If attempting to delete the last superuser.
            UnexpectedDatabaseError: If an unexpected error occurs.
        """
        try:
            return await self.user_manager.delete_user(user_id, session)  # ✅ Delegate to User Manager
    
        except UserNotFoundError as e:
            raise e  # Propagate to higher layers
        except LastSuperuserError as e:
            raise e  # Propagate to higher layers
        except UnexpectedDatabaseError as e:
            raise e  # Propagate to higher layers
        except Exception as e:
            self.logger.error(f"Unexpected error deleting user {user_id}: {str(e)}")
            raise UnexpectedDatabaseError(detail=str(e))



# ===========================
# Dependency Injection for UserOrchestrator
# ===========================
async def get_user_orchestrator(
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Provides an instance of `UserOrchestrator` for dependency injection.

    Args:
        user_manager (UserManager): The user manager dependency.

    Yields:
        UserOrchestrator: The orchestrator instance.
    """
    yield UserOrchestrator(user_manager)
