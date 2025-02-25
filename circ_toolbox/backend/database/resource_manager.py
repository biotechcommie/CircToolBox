# circ_toolbox/backend/database/resource_manager.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from circ_toolbox.backend.database.models import Resource
from circ_toolbox.backend.database.user_manager import UserManager
from circ_toolbox.backend.utils.logging_config import get_logger, log_runtime
from circ_toolbox.backend.database.base import get_session, get_session_instance
from datetime import datetime
from typing import List, Optional, Set
from uuid import UUID
import os
from circ_toolbox.backend.database.user_manager import get_user_manager  # Import user manager

# Import custom exceptions for resource handling
from circ_toolbox.backend.exceptions import (
    ResourceNotFoundError,
    ResourceValidationError,
    ResourceUnexpectedDatabaseError,
    UnauthorizedActionError,
)

class ResourceManager:
    """
    Manages database operations related to resources.

    This class provides methods for:
      - Registering a new resource.
      - Listing resources with optional filters and pagination.
      - Fetching a resource by its ID.
      - Updating and deleting resources.
      - Retrieving unique species from stored resources.

    Attributes:
        logger (Logger): The logger instance for this module.
    """

    def __init__(self):
        """Initializes the ResourceManager with a logger."""
        self.logger = get_logger("resource_manager")

    # ===========================
    # INTERNAL SESSION HANDLING
    # ===========================
    @log_runtime("resource_manager")
    async def _get_session(self, session: Optional[AsyncSession]) -> tuple[AsyncSession, bool]:
        """
        Ensures that an active database session is available for execution.

        This method follows a structured logic to determine session handling:
        - If a session is provided as an argument, it is reused, and `close_session` is set to False.
        - If the method runs within the FastAPI context, it attempts to retrieve a session using FastAPI's dependency injection.
        - If FastAPI is unavailable (e.g., during CLI execution or background tasks), a new session is manually created using `get_session_instance()`, and `close_session` is set to True.

        Args:
            session (Optional[AsyncSession]): An externally provided SQLAlchemy async session.
                                            If None, attempts to retrieve or create a session.

        Returns:
            tuple[AsyncSession, bool]: A tuple containing:
                - The active SQLAlchemy async session.
                - A boolean indicating whether the session should be closed after the operation 
                (`True` if created internally, `False` otherwise).
        """
        if session is None:
            try:
                # If running in FastAPI, retrieve session via dependency injection
                async for fastapi_session in get_session():
                    return fastapi_session, False  # FastAPI manages session closure
            except RuntimeError:
                # If FastAPI context is unavailable, create a standalone session
                standalone_session = await get_session_instance()
                return standalone_session, True  # Must be manually closed later
        return session, False  # Session provided externally, do not close



    # ------------------------------------------------------------------------------
    # Register new resource
    # ------------------------------------------------------------------------------
    @log_runtime("resource_manager")
    async def register_resource(self, resource: Resource, session: Optional[AsyncSession] = None):
        """
        Register a new resource in the database.

        Args:
            resource (Resource): The resource object to be added.

        Raises:
            ResourceValidationError: If the resource already exists.
            ResourceUnexpectedDatabaseError: If the registration operation fails.
        """
        session, close_session = await self._get_session(session)

        try:
            stmt = select(Resource).filter_by(name=resource.name)
            result = await session.execute(stmt)
            existing_resource = result.scalar_one_or_none()

            if existing_resource:
                self.logger.warning(f"Resource '{resource.name}' already exists.")
                raise ResourceValidationError(f"Resource '{resource.name}' already exists.")

            session.add(resource)

            # Flush the session to persist the resource (so that auto-generated fields like id are set)
            await session.flush()
            # Refresh the resource from the database to obtain the generated id and other fields.
            await session.refresh(resource)

            # ✅ Always commit the session (since our sessions are raw and do not autocommit)
            await session.commit()

            self.logger.info(f"Resource '{resource.id}' registered successfully.")


        except ResourceValidationError as rve:
            await session.rollback()
            raise rve
        except Exception as e:
            await session.rollback()
            self.logger.error(f"Failed to register resource '{resource.name}': {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to register resource: {e}")
        finally:
            if close_session:
                await session.close()


    # ------------------------------------------------------------------------------
    # List resources with pagination and filters
    # ------------------------------------------------------------------------------
    @log_runtime("resource_manager")
    async def list_resources(
        self, limit: int, offset: int, filters: Optional[dict] = None, session: Optional[AsyncSession] = None
    ) -> list[Resource]:

        """
        List all resources or filter with pagination.

        Args:
            limit (int): Number of resources to retrieve.
            offset (int): Offset for pagination.
            filters (dict, optional): Filters for resource type, species, or date range.

        Returns:
            List[Resource]: Filtered and paginated list of resources.

        Raises:
            ResourceUnexpectedDatabaseError: If listing resources fails.
        """
        self.logger.info(f"Listing resources with limit={limit}, offset={offset}, filters={filters}")
        
        session, close_session = await self._get_session(session)

        try:
            stmt = select(Resource).order_by(Resource.date_added.desc()).limit(limit).offset(offset)

            if "resource_type" in filters:
                stmt = stmt.filter(Resource.resource_type == filters["resource_type"])
            if "species" in filters:
                stmt = stmt.filter(Resource.species == filters["species"])

            result = await session.execute(stmt)
            resources = result.scalars().all()
            self.logger.info(f"Retrieved {len(resources)} resources.")
            return resources

        except Exception as e:
            await session.rollback()
            self.logger.error(f"Failed to list resources: {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to list resources: {e}")
        finally:
            if close_session:
                await session.close()


    # ------------------------------------------------------------------------------
    # Get resource by ID
    # ------------------------------------------------------------------------------
    @log_runtime("resource_manager")
    async def get_resource_by_id(self, resource_id: UUID, session: Optional[AsyncSession] = None) -> Optional[Resource]:
        """
        Retrieve a single resource by its ID.

        Args:
            resource_id (UUID): The unique identifier of the resource.
            session (Optional[AsyncSession]): The database session.

        Returns:
            Resource: The resource if found.

        Raises:
            ResourceNotFoundError: If the resource is not found.
            ResourceUnexpectedDatabaseError: If fetching the resource fails.
        """
        session, close_session = await self._get_session(session)


        try:
            stmt = select(Resource).filter(Resource.id == resource_id)
            result = await session.execute(stmt)
            resource = result.scalar_one_or_none()

            if not resource:
                self.logger.warning(f"Resource '{resource_id}' not found.")
                raise ResourceNotFoundError(detail=f"Resource '{resource_id}' not found.")

            return resource

        except ResourceNotFoundError as rfe:
            # Propagate our own validation errors
            await session.rollback()
            raise rfe
        
        except Exception as e:
            await session.rollback()
            self.logger.error(f"Failed to fetch resource '{resource_id}': {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to fetch resource: {e}")
        finally:
            if close_session:
                await session.close()


    # ------------------------------------------------------------------------------
    # Update resource
    # ------------------------------------------------------------------------------
    @log_runtime("resource_manager")
    async def update_resource(self, resource_id: UUID, update_data: dict, user_id: UUID, user_manager: UserManager, session: Optional[AsyncSession] = None):
        """
        Update a resource's details in the database.

        Args:
            resource_id (UUID): The unique ID of the resource.
            update_data (dict): The fields to update.
            user_id (UUID): The ID of the user attempting the update.
            user_manager (UserManager): The injected UserManager instance.
            session (Optional[AsyncSession]): The database session.

        Returns:
            dict: Success message.

        Raises:
            ResourceNotFoundError: If the resource is not found.
            UnauthorizedActionError: If the user lacks permissions.
            ResourceUnexpectedDatabaseError: If the update fails.
        """
        self.logger.info(f"Updating resource '{resource_id}' with data: {update_data}")
        
        session, close_session = await self._get_session(session)

        try:
            stmt = select(Resource).where(Resource.id == resource_id)
            result = await session.execute(stmt)
            resource = result.scalar_one_or_none()

            if not resource:
                raise ResourceNotFoundError(f"Resource '{resource_id}' not found.")

            # ✅ Correctly call `user_manager.user_is_admin()` (await it)
            is_admin = await user_manager.user_is_admin(user_id, session)

            # Check if user is the owner OR is an admin
            if resource.uploaded_by != user_id and not is_admin:
                raise UnauthorizedActionError("User is not allowed to update this resource.")

            for key, value in update_data.items():
                setattr(resource, key, value)

            await session.refresh(resource)
            await session.commit()

            self.logger.info(f"Resource '{resource_id}' updated successfully.")

        except ResourceNotFoundError as rfe:
            # Propagate our own validation errors
            await session.rollback()
            raise rfe
        except UnauthorizedActionError as e:
            await session.rollback()
            raise e
        except Exception as e:
            await session.rollback()
            self.logger.error(f"Failed to update resource '{resource_id}': {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to update resource: {e}")
        finally:
            if close_session:
                await session.close()


    # ------------------------------------------------------------------------------
    # Delete resource
    # ------------------------------------------------------------------------------
    @log_runtime("resource_manager")
    async def delete_resource(self, resource_id: UUID, session: Optional[AsyncSession] = None):
        """
        Delete a resource from the database.

        Args:
            resource_id (UUID): The unique ID of the resource to delete.
            session (Optional[AsyncSession]): The database session.

        Returns:
            dict: A success message.

        Raises:
            ResourceNotFoundError: If the resource is not found.
            ResourceUnexpectedDatabaseError: If the deletion fails.
        """
        session, close_session = await self._get_session(session)

        try:
            stmt = select(Resource).where(Resource.id == resource_id)
            result = await session.execute(stmt)
            resource = result.scalar_one_or_none()

            if not resource:
                raise ResourceNotFoundError(f"Resource '{resource_id}' not found.")

            # Store file path before deletion
            file_path = resource.file_path

            # Delete from database
            await session.delete(resource)
            # ✅ Always commit the session (since our sessions are raw and do not autocommit)
            await session.commit()

            # Delete the file from storage # in the future: (Option 2: Keep files, only delete metadata (For audit logging)
                                                            # This is used when you want to retain files for recovery or logging purposes.
                                                            # But the file might accumulate, so implement a cleanup job.)
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"Deleted file '{file_path}' after resource deletion.")

            self.logger.info(f"Resource '{resource_id}' deleted successfully.")

        except ResourceNotFoundError as rfe:
            # Propagate our own validation errors
            await session.rollback()
            raise rfe
        
        except Exception as e:
            await session.rollback()
            self.logger.error(f"Failed to delete resource '{resource_id}': {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to delete resource: {e}")
        finally:
            if close_session:
                await session.close()


    # ------------------------------------------------------------------------------
    # List unique species
    # ------------------------------------------------------------------------------
    @log_runtime("resource_manager")
    async def list_unique_species(self, session: Optional[AsyncSession] = None) -> List[str]:
        """
        Retrieve a sorted list of unique species from the resources.

        Args:
            session (Optional[AsyncSession]): The database session.

        Returns:
            List[str]: A sorted list of unique species.

        Raises:
            ResourceUnexpectedDatabaseError: If fetching the species list fails.
        """

        session, close_session = await self._get_session(session)

        try:
            stmt = select(Resource.species).distinct()
            result = await session.execute(stmt)
            species_list = [row[0] for row in result.all() if row[0]]

            self.logger.info(f"Retrieved {len(species_list)} unique species.")
            return species_list

        except Exception as e:
            await session.rollback()
            self.logger.error(f"Failed to fetch species list: {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to fetch species list: {e}")
        finally:
            if close_session:
                await session.close()



    @log_runtime("resource_manager")
    async def get_resource_path(self, resource_id: str, session: Optional[AsyncSession] = None) -> str:
        """
        Get the file path of a resource based on its resource_id.

        Args:
            resource_id (str): The resource identifier (not the primary key ID).
            session (Optional[AsyncSession]): The database session.

        Returns:
            str: The file path of the resource if found, else an empty string.

        Raises:
            ResourceNotFoundError: If the resource is not found.
            ResourceUnexpectedDatabaseError: If there is a failure in fetching the resource.
        """
        session, close_session = await self._get_session(session)
        try:
            stmt = select(Resource).filter_by(id=resource_id)
            result = await session.execute(stmt)
            resource = result.scalar_one_or_none()
            if not resource:
                self.logger.warning(f"Resource '{resource_id}' not found.")
                raise ResourceNotFoundError(detail=f"Resource '{resource_id}' not found.")
            self.logger.info(f"File path for resource '{resource_id}': {resource.file_path}")
            return resource.file_path
        except ResourceNotFoundError as rne:
            await session.rollback()
            raise rne
        except Exception as e:
            await session.rollback()
            self.logger.error(f"Failed to fetch file path for resource '{resource_id}': {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to fetch file path: {e}")
        finally:
            if close_session:
                await session.close()


    @log_runtime("resource_manager")
    async def get_existing_resource_ids(self, resource_ids: List[UUID], session: Optional[AsyncSession] = None) -> Set[UUID]:
        """
        Returns a set of resource IDs that exist in the database from the provided list.

        Args:
            resource_ids (List[UUID]): A list of resource IDs to check.
            session (Optional[AsyncSession]): The database session.

        Returns:
            Set[UUID]: A set of resource IDs that exist in the database.
        """
        if not resource_ids:
            return set()

        session, close_session = await self._get_session(session)
        try:
            stmt = select(Resource.id).where(Resource.id.in_(resource_ids))
            result = await session.execute(stmt)
            existing_ids = {row[0] for row in result.all()}
            return existing_ids
        except Exception as e:
            await session.rollback()
            self.logger.error(f"Failed to fetch existing resource IDs: {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to fetch existing resource IDs: {e}")
        finally:
            if close_session:
                await session.close()


# ------------------------------------------------------------------------------
# Dependency Injection for ResourceManager
# ------------------------------------------------------------------------------
async def get_resource_manager(
    session: AsyncSession = Depends(get_session)
):
    """
    Provides an instance of ResourceManager for dependency injection.

    Args:
        session (AsyncSession): The database session dependency.

    Yields:
        ResourceManager: The resource management service.
    """
    # Here, we simply yield a new instance of ResourceManager.
    yield ResourceManager()















'''
        
        try:
            # ✅ Never commit the session os inherited methods.
            pass 
        except Exception as e:
            # ✅ Ensure rollback on unexpected failure
            # Only we created session.
            if close_session:   
                
                await session.rollback()  
        finally:
            if close_session:
                # ✅ Always close session if we created it.
                await session.close()  


            # ✅ Always commit the session (since our sessions are raw and do not autocommit)
            # WE ONLY DO NOT COMMIT ON USER MANAGER INHERITHED METHODS SINCE THEY HANDLE COMMIT INTERNALLY.
            await session.commit()
'''













'''
    @log_runtime("resource_manager")
    async def get_resource_path(self, resource_id: str) -> str:
        """
        Get the file path of a resource based on its ID.
        """
        self.logger.info(f"Fetching file path for resource ID: {resource_id}")
        stmt = select(Resource).filter_by(resource_id=resource_id)
        result = await self.session.execute(stmt)
        resource = result.scalar_one_or_none()

        if resource:
            self.logger.info(f"File path for resource '{resource_id}': {resource.file_path}")
        else:
            self.logger.warning(f"Resource '{resource_id}' not found.")
        return resource.file_path if resource else None

'''
