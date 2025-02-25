# circ_toolbox/backend/services/orchestrators/resource_orchestrator.py
"""
Resource Orchestrator.

This module serves as an intermediary between the resource API routes and the underlying resource management logic.
It handles business logic for creating, listing, updating, deleting, and retrieving resources. Custom exceptions such as
ResourceNotFoundError, ResourcePermissionError, ResourceValidationError, and ResourceUnexpectedDatabaseError are used to
ensure consistent error handling and meaningful HTTP responses.

Usage:
    Endpoints in the resource routes depend on an instance of ResourceOrchestrator, which is provided via dependency
    injection using the `get_resource_orchestrator` function.
"""
import asyncio
from fastapi import Depends
from circ_toolbox.backend.services.resource_service import ResourceService, get_resource_service
from circ_toolbox.backend.database.resource_manager import ResourceManager, get_resource_manager
from circ_toolbox.backend.database.user_manager import UserManager, get_user_manager

from circ_toolbox.backend.api.schemas.resource_schemas import (
    ResourceCreate,
    ResourceUpdate,
    ResourceResponse,
    SpeciesListResponse,
)
from circ_toolbox.backend.utils.logging_config import get_logger, log_runtime
from circ_toolbox.backend.utils.validation import validate_file_path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Set
from uuid import UUID

# Import custom exceptions for resource handling
from circ_toolbox.backend.exceptions import (
    ResourceNotFoundError,
    ResourcePermissionError,
    ResourceValidationError,
    ResourceUnexpectedDatabaseError,
)

class ResourceOrchestrator:
    """
    Handles high-level resource operations by delegating to the ResourceManager and ResourceService.

    Responsibilities:
      - Validates additional business rules (e.g. file extension, resource_type consistency).
      - Offloads blocking file I/O (using asyncio.to_thread) via the ResourceService.
      - Delegates database operations (register, list, update, delete) to the ResourceManager.
    
    Attributes:
        resource_manager (ResourceManager): Manager for resource database operations.
        resource_service (ResourceService): Service layer for resource business logic (file I/O).
        logger: Logger instance.
    """

    def __init__(self, resource_manager: ResourceManager = None, resource_service: ResourceService = None, user_manager: UserManager = None):
        """
        Initialize the ResourceOrchestrator with optional dependencies.

        Args:
            resource_manager (Optional[ResourceManager]): Instance of ResourceManager; if not provided, a default is used.
            resource_service (Optional[ResourceService]): Instance of ResourceService; if not provided, a default is used.
        """
        self.resource_manager = resource_manager or ResourceManager()
        self.resource_service = resource_service or ResourceService()
        self.user_manager = user_manager or UserManager() # ✅ Injected UserManager
        self.logger = get_logger("resource_orchestrator")


    @log_runtime("resource_orchestrator")
    async def register_resource(self, resource_data: ResourceCreate, user, session: Optional[AsyncSession] = None) -> ResourceResponse:
        """
        Orchestrates the resource registration process.
        
        The process includes:
          - Injecting the authenticated user's ID into the resource data.
          - (Optionally) performing additional validation on the file via business logic.
          - Calling the ResourceService to offload the blocking file I/O (e.g. copying the file
            from its temporary upload location to the final destination).
          - Delegating database registration to the ResourceManager.
          - Converting the resulting ORM resource into a Pydantic ResourceResponse.
        
        Args:
            resource_data (ResourceCreate): Data for creating the resource.
            user: The authenticated user registering the resource.
            session (Optional[AsyncSession]): The database session.
        
        Returns:
            ResourceResponse: The details of the registered resource.
        
        Raises:
            ResourceValidationError: If resource data validation fails.
            ResourceUnexpectedDatabaseError: If a database error occurs during registration.
        """

        self.logger.info(f"Starting resource registration for user: {user.email}")

        try:
            # Inject user ID into resource data
            enriched_resource = resource_data.model_copy(update={"uploaded_by": user.id})


            async_or_sync = True # True = async | False = sync

            # OPTIONAL: You can perform additional business-level validations here.
            # For example, you might validate the resource_type further.
            # (Note: the Pydantic validator already checks file extension, so additional check of file_path is not needed.)

            if async_or_sync:

                # Offload blocking file I/O (copying the file) to the service layer.
                # Since copy_and_save_file is fully asynchronous now, we can await it directly.
                final_file_path, file_size = await self.resource_service.async_copy_and_save_file(
                    enriched_resource.file,
                    enriched_resource.resource_type,
                    enriched_resource.species,
                    enriched_resource.version,
                    enriched_resource.force_overwrite,
                )
            else:

                # Offload blocking file I/O (copying the file) to the service layer.
                # The service will move/copy the file from its temporary location to the final destination.
                final_file_path, file_size = await asyncio.to_thread(
                    self.resource_service.copy_and_save_file,
                    enriched_resource.file,
                    enriched_resource.resource_type,
                    enriched_resource.species,
                    enriched_resource.version,
                    enriched_resource.force_overwrite,
                )

            
            # Build a clean dictionary from the enriched resource,
            # excluding keys that are not needed by the ORM function.
            enriched_data = enriched_resource.dict(exclude={"file", "force_overwrite"})
            
            
            # Set the keys that the ORM creation function requires.
            enriched_data["file_path"] = final_file_path  # or "file_path" if you rename the parameter
            enriched_data["file_size"] = file_size

            # Optionally, update file_size if needed (the service can return it, e.g., via os.path.getsize).


            # Create the resource object (using the service to construct the Resource ORM instance)
            resource_obj = self.resource_service.create_resource_from_data(**enriched_data)
            
            # Save the resource record in the database via the manager.
            await self.resource_manager.register_resource(resource_obj, session)
            self.logger.info(f"Resource '{resource_obj.name}' registered successfully.")
            
            # Convert ORM resource to Pydantic response model.
            return ResourceResponse.from_orm(resource_obj)

        except (ValueError, ResourceValidationError) as rve:
            self.logger.warning(f"Validation error for resource registration: {rve}")
            raise ResourceValidationError(detail=str(rve))
        except ResourceUnexpectedDatabaseError as e:
            raise e  # Propagate to higher layers
        except Exception as e:
            self.logger.error(f"Failed to register resource: {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to register resource: {e}")



    @log_runtime("resource_orchestrator")
    async def list_resources(self, limit: int, offset: int, resource_type: Optional[str] = None, species: Optional[str] = None, session: Optional[AsyncSession] = None) -> List[ResourceResponse]:
        """
        Orchestrates listing resources with optional filtering and pagination.

        Args:
            limit (int): Maximum number of resources to retrieve.
            offset (int): Pagination offset.
            resource_type (Optional[str]): Filter by resource type.
            species (Optional[str]): Filter by species.
            session (Optional[AsyncSession]): The database session.

        Returns:
            List[ResourceResponse]: A list of resource records (filtered and paginated).

        Raises:
            ResourceValidationError: If pagination parameters are invalid.
            ResourceUnexpectedDatabaseError: If a database error occurs.
        """
        self.logger.info(
            f"Filtering resources with limit={limit}, offset={offset}, resource_type={resource_type}, species={species}."
        )

        try:
            filters = {}

            # Apply filters based on provided values
            if resource_type:
                filters["resource_type"] = resource_type.strip()
            if species:
                filters["species"] = species.strip()

            # Validate pagination parameters before querying
            if limit < 1 or offset < 0:
                raise ResourceValidationError(detail="Invalid pagination parameters: limit must be >=1 and offset must be >=0")

            # Fetch resources via resource manager
            resources = await self.resource_manager.list_resources(
                limit=limit,
                offset=offset,
                filters=filters,
                session=session,
            )

            self.logger.info(f"Retrieved {len(resources)} resources.")

            # Convert ORM objects to Pydantic schema
            return [ResourceResponse.from_orm(resource) for resource in resources]
        
        except ResourceValidationError as rve:
            self.logger.error(f"Validation error in resource listing: {rve}")
            raise rve
        except ResourceUnexpectedDatabaseError as e:
            raise e  # Propagate to higher layers
        except Exception as e:
            self.logger.error(f"Failed to retrieve resources: {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to retrieve resources: {e}")


    @log_runtime("resource_orchestrator")
    async def update_resource(self, resource_id: UUID, update_data: ResourceUpdate, user, session: Optional[AsyncSession] = None) -> dict:
        """
        Orchestrates updating resource details in the database.

        Args:
            resource_id (UUID): The unique identifier of the resource.
            update_data (ResourceUpdate): Validated update data.
            user: The authenticated user performing the update.
            session (Optional[AsyncSession]): The database session.

        Returns:
            dict: A success message.

        Raises:
            ResourceNotFoundError: If the resource is not found.
            ResourcePermissionError: If the user is not authorized to update the resource.
            ResourceUnexpectedDatabaseError: If a database error occurs.
        """
        self.logger.info(f"Processing update for resource '{resource_id}' by user {user.email}.")

        try:
            # Retrieve the resource first to check existence and ownership
            resource = await self.resource_manager.get_resource_by_id(resource_id, session)
            if not resource:
                raise ResourceNotFoundError(detail=f"Resource '{resource_id}' not found.")

            # Authorization check: Regular users can update only their own resources. Admins can update any.
            if not user.is_superuser and resource.uploaded_by != user.id:
                raise ResourcePermissionError(detail="You can only update your own resources.")
                
            async_or_sync = True  # True = async | False = sync

            # Check if a new file is provided for update
            if update_data.file is not None:
                self.logger.info(f"New file provided for update of resource '{resource_id}'.")

                if async_or_sync:
                    # Use async method for file copying
                    final_file_path, file_size = await self.resource_service.async_copy_and_save_file(
                        update_data.file,
                        update_data.resource_type or resource.resource_type,
                        update_data.species or resource.species,
                        update_data.version or resource.version,
                        update_data.force_overwrite if update_data.force_overwrite is not None else False
                    )
                else:
                    # Fallback to sync version wrapped in asyncio thread execution
                    final_file_path, file_size = await asyncio.to_thread(
                        self.resource_service.copy_and_save_file,
                        update_data.file,
                        update_data.resource_type or resource.resource_type,
                        update_data.species or resource.species,
                        update_data.version or resource.version,
                        update_data.force_overwrite if update_data.force_overwrite is not None else False
                    )

                update_data = update_data.copy(update={"file_path": final_file_path})
          
            # Perform the update via resource manager
            await self.resource_manager.update_resource(resource_id, update_data.dict(exclude_unset=True), user.id, self.user_manager, session)

            self.logger.info(f"Resource '{resource_id}' updated successfully.")
            return {"message": f"Resource '{resource_id}' updated successfully."}

        except ResourceNotFoundError as rnfe:
            self.logger.error(str(rnfe))
            raise rnfe
        except ResourcePermissionError as rpe:
            self.logger.warning(f"Unauthorized update attempt: {rpe}")
            raise rpe
        except ResourceUnexpectedDatabaseError as e:
            raise e  # Propagate to higher layers
        except Exception as e:
            self.logger.error(f"Failed to update resource '{resource_id}': {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to update resource '{resource_id}': {e}")


    @log_runtime("resource_orchestrator")
    async def delete_resource(self, resource_id: UUID, user, session: Optional[AsyncSession] = None) -> dict:
        """
        Orchestrates the deletion of a resource from the database.

        Args:
            resource_id (UUID): The unique identifier of the resource.
            user: The authenticated user performing the deletion.
            session (Optional[AsyncSession]): The database session.

        Returns:
            dict: A success message.

        Raises:
            ResourceNotFoundError: If the resource is not found.
            ResourcePermissionError: If the user is not authorized to delete the resource.
            ResourceUnexpectedDatabaseError: If a database error occurs.
        """
        self.logger.info(f"Processing deletion for resource '{resource_id}' initiated by {user.email}.")

        try:
            # Retrieve the resource first to check ownership
            resource = await self.resource_manager.get_resource_by_id(resource_id, session)

            if not resource:
                raise ResourceNotFoundError(detail=f"Resource '{resource_id}' not found.")

            # Authorization check (owner or admin)
            if resource.uploaded_by != user.id and not user.is_superuser:
                raise ResourcePermissionError(detail="You can only delete your own resources.")

            # Proceed with deletion
            await self.resource_manager.delete_resource(resource_id, session)
            self.logger.info(f"Resource '{resource_id}' deleted successfully.")
            return {"message": f"Resource '{resource_id}' deleted successfully."}

        except ResourceNotFoundError as rnfe:
            self.logger.error(str(rnfe))
            raise
        except ResourcePermissionError as rpe:
            self.logger.warning(f"Unauthorized delete attempt: {rpe}")
            raise
        except ResourceUnexpectedDatabaseError as e:
            raise e  # Propagate to higher layers
        except Exception as e:
            self.logger.error(f"Failed to delete resource '{resource_id}': {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to delete resource '{resource_id}': {e}")


    @log_runtime("resource_orchestrator")
    async def get_species_list(self, session: Optional[AsyncSession] = None) -> list[SpeciesListResponse]:
        """
        Orchestrates fetching a sorted list of unique species.

        Returns:
            List[str]: A sorted list of unique species names.

        Raises:
            ResourceUnexpectedDatabaseError: If fetching the species list fails.
        """
        self.logger.info("Fetching unique species list.")

        try:
            species = await self.resource_manager.list_unique_species(session)
            sorted_species = sorted(species, key=lambda s: s.lower())
            self.logger.info(f"Retrieved {len(sorted_species)} unique species.")
            return sorted_species #             return [ResourceResponse.from_orm(resource) for resource in resources]

        except ResourceUnexpectedDatabaseError as e:
            raise e  # Propagate to higher layers
        except Exception as e:
            self.logger.error(f"Failed to fetch species list: {e}")
            raise ResourceUnexpectedDatabaseError(detail="Failed to fetch species list.")


    @log_runtime("resource_orchestrator")
    async def get_resource_by_id(self, resource_id: UUID, session: Optional[AsyncSession] = None) -> ResourceResponse:
        """
        Orchestrates fetching a single resource by its ID.

        Args:
            resource_id (UUID): The unique identifier of the resource.
            session (Optional[AsyncSession]): The database session.

        Returns:
            ResourceResponse: The resource details.

        Raises:
            ResourceNotFoundError: If the resource is not found.
            ResourceUnexpectedDatabaseError: If fetching the resource fails.
        """
        self.logger.info(f"Fetching resource with ID '{resource_id}'.")

        try:
            resource = await self.resource_manager.get_resource_by_id(resource_id, session)

            if not resource:
                raise ResourceNotFoundError(detail=f"Resource '{resource_id}' not found.")

            self.logger.info(f"Resource '{resource_id}' retrieved successfully.")
            return ResourceResponse.from_orm(resource)

        except KeyError as e:
            self.logger.error(str(e))
            raise
        
        except ResourceNotFoundError as rnfe:
            self.logger.error(str(rnfe))
            raise
        except ResourceUnexpectedDatabaseError as e:
            raise e  # Propagate to higher layers
        except Exception as e:
            self.logger.error(f"Failed to fetch resource '{resource_id}': {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to fetch resource '{resource_id}': {e}")

    @log_runtime("resource_orchestrator")
    async def get_existing_resource_ids(self, resource_ids: List[UUID], session: AsyncSession) -> Set[UUID]:
        """
        Returns a set of existing resource IDs from the provided list.

        Args:
            resource_ids (List[UUID]): A list of resource UUIDs.
            session (AsyncSession): The database session.

        Returns:
            Set[UUID]: A set containing the IDs of resources that exist.
        """
        self.logger.info(f"Fetching resource with ID '{resource_ids}'.")

        try:
            resources = await self.resource_manager.get_existing_resource_ids(resource_ids, session)
            return resources
        
        except ResourceUnexpectedDatabaseError as e:
            raise e  # Propagate to higher layers        
        except Exception as e:
            self.logger.error(f"Failed to fetch resource '{resource_ids}': {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to fetch resource '{resource_ids}': {e}")




# ------------------------------------------------------------------------------
# Dependency Injection for ResourceOrchestrator
# ------------------------------------------------------------------------------
async def get_resource_orchestrator(
    resource_manager: ResourceManager = Depends(get_resource_manager),
    resource_service: ResourceService = Depends(get_resource_service),
    user_manager: UserManager = Depends(get_user_manager),  # ✅ Inject UserManager
):
    """
    Provides an instance of ResourceOrchestrator for dependency injection.

    Args:
        resource_manager: The ResourceManager dependency.
        resource_service: The ResourceService dependency.
        user_manager: The UserManager dependency.

    Yields:
        ResourceOrchestrator: An instance of ResourceOrchestrator.
    """
    yield ResourceOrchestrator(resource_manager, resource_service, user_manager)





'''
Usage Example:
Case 1: New Resource Submission (No Duplicates)
python
Copiar
resource_data = {
    "name": "Mouse Genome Reference",
    "type": "genome",
    "species": "Mus musculus",
    "version": "GRCm39",
    "file_path": "/data/GRCm39.fasta",
    "uploaded_by": "admin",
    "force_overwrite": False
}

orchestrator_run_resource_manager(session, resource_data)
The resource will be registered successfully if no duplicate exists.
Case 2: Submission with Duplicate Resource (Overwrite Enabled)
python
Copiar
resource_data = {
    "name": "Human Genome Reference",
    "type": "genome",
    "species": "Homo sapiens",
    "version": "GRCh38",
    "file_path": "/data/GRCh38.fasta",
    "uploaded_by": "bioinfo_user",
    "force_overwrite": True
}

orchestrator_run_resource_manager(session, resource_data)
Since force_overwrite=True, the orchestrator will overwrite the existing resource.
Case 3: Submission with Duplicate Resource (Overwrite Disabled)
python
Copiar
resource_data = {
    "name": "Human Genome Reference",
    "type": "genome",
    "species": "Homo sapiens",
    "version": "GRCh38",
    "file_path": "/data/GRCh38.fasta",
    "uploaded_by": "bioinfo_user",
    "force_overwrite": False
}

try:
    orchestrator_run_resource_manager(session, resource_data)
except ValueError as e:
    print(f"Failed to register resource: {e}")
Since force_overwrite=False, this will raise:
vbnet
Copiar
ValueError: Resource 'genome_homo_sapiens_grch38' already exists in the database.








Additional Validation Ideas:
Checksum Verification (Optional): Add an MD5 or SHA256 checksum validation to compare the incoming file with the existing file.

import hashlib

def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


'''
'''
resource_data = {
    "name": "Human Genome Reference",
    "type": "genome",
    "species": "Homo sapiens",
    "version": "GRCh38",
    "file_path": "/path/to/GRCh38.fasta",
    "uploaded_by": "admin"
}
'''
'''
Testing the Flow
Example call:

python
Copiar código
orchestrator_run_resource_manager(
    session,
    {
        "name": "Human Genome Reference",
        "type": "genome",
        "species": "Homo sapiens",
        "version": "GRCh38",
        "file_path": "/data/genome/GRCh38.fa",
        "uploaded_by": "admin"
    }
)
Expected output:

json
Copiar código
{
    "resource_id": "genome_homo_sapiens_grch38",
    "name": "Human Genome Reference",
    "file_path": "/resources/genome/Homo sapiens/GRCh38/GRCh38.fa",
    "uploaded_by": "admin",
    "date_added": "2025-01-15T12:34:56"
}


'''

'''
from flask import Blueprint, request, jsonify
from backend.database.base import get_session
from backend.services.orchestrators.resource_orchestrator import ResourceOrchestrator

resource_bp = Blueprint("resources", __name__)
session = get_session()
orchestrator = ResourceOrchestrator(session)

@resource_bp.route("/register", methods=["POST"])
def register_resource():
    data = request.json
    resource_data = orchestrator.register_resource(**data)
    return jsonify(resource_data), 201

@resource_bp.route("/list", methods=["GET"])
def list_resources():
    resource_type = request.args.get("type")
    resources = orchestrator.list_resources(resource_type)
    return jsonify(resources)

@resource_bp.route("/delete/<resource_id>", methods=["DELETE"])
def delete_resource(resource_id):
    orchestrator.delete_resource(resource_id)
    return jsonify({"message": f"Resource '{resource_id}' deleted successfully."})


'''