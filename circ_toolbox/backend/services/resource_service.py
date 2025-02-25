# circ_toolbox/backend/services/resource_service.py
import os
from datetime import datetime
import shutil
import asyncio
import tempfile
from fastapi import UploadFile
from typing import Optional
from circ_toolbox.backend.database.models import Resource
from circ_toolbox.backend.utils import copy_file_to_storage, async_copy_file_to_storage, sanitize_filename, get_logger
from circ_toolbox.backend.exceptions import (
    ResourceValidationError,
    ResourceUnexpectedDatabaseError,
)

class ResourceService:
    """
    Handles the business logic for file operations and resource creation.

    This service is responsible for:
      - Validating the existence of the source file.
      - Copying the file to a designated storage location.
      - Creating and returning a new Resource object with the computed properties.

    Attributes:
        logger (Logger): The logger instance for this module.
    """

    def __init__(self):
        """Initializes the ResourceService with a logger."""
        self.logger = get_logger("resource_service")


    
    async def async_copy_and_save_file(
        self,
        file: UploadFile,
        resource_type: str,
        species: Optional[str],
        version: Optional[str],
        force_overwrite: bool = False
    ) -> tuple[str, int]:
        """
        Asynchronously copies the uploaded file from its temporary location to the designated storage directory.
        
        This method first checks if the underlying file (a SpooledTemporaryFile) already has a stable
        file path on disk. If not, it creates a new temporary file and writes the content there.
        Then, it uses an asynchronous file-copy function (async_copy_file_to_storage) to move the file to its
        final destination based on resource_type, species, and version.
        
        This function is designed to be awaited directly (or indirectly via an orchestrator) without blocking the event loop.
        
        Args:
            file (UploadFile): The uploaded file object.
            resource_type (str): The type/category of the resource.
            species (Optional[str]): The species associated with the resource.
            version (Optional[str]): The version of the resource.
            force_overwrite (bool): Flag to force overwriting if the destination file exists.
        
        Returns:
            tuple[str, int]: A tuple containing the final file path and the file size in bytes.
        
        Raises:
            ResourceValidationError: If the source file cannot be accessed.
            ResourceUnexpectedDatabaseError: If any error occurs during file copying.
        """
        try:
            # Ensure the file pointer is at the beginning.
            file.file.seek(0)
            
            # Retrieve the temporary file path from the underlying SpooledTemporaryFile.
            temp_path = getattr(file.file, "name", None)
            if not isinstance(temp_path, str) or not os.path.exists(temp_path) or temp_path.startswith("<"):
                self.logger.info("No valid temporary file path found; creating a new temporary file.")
                contents = await file.read()
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(contents)
                    temp_path = tmp.name
            
            # Use the original filename (sanitized) for the destination
            original_filename = sanitize_filename(file.filename)
            # Optionally, you might want to pass original_filename to async_copy_file_to_storage if you modify it to accept that.
            # For now, assume async_copy_file_to_storage uses the sanitized original filename.
            
            # Asynchronously copy the file to the designated storage directory.
            final_path = await async_copy_file_to_storage(
                temp_path, original_filename, resource_type, species, version, force_overwrite
            )
            file_size = os.path.getsize(final_path)
            self.logger.info(f"File '{file.filename}' copied to '{final_path}' with size {file_size} bytes.")
            return final_path, file_size
        except Exception as e:
            self.logger.error(f"Failed to copy and save file: {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to copy and save file: {e}")
        
        
    def copy_and_save_file(
        self,
        file: UploadFile,
        resource_type: str,
        species: Optional[str],
        version: Optional[str],
        force_overwrite: bool = False
    ) -> tuple[str, int]:
        """
        Copies the uploaded file from its temporary location to the designated storage directory.
        This function is expected to be run in a separate thread (e.g. via asyncio.to_thread)
        because it performs blocking I/O operations.

        The function first checks if the underlying file (a SpooledTemporaryFile)
        already has a stable file path (i.e. it has been rolled to disk). If not, it creates a new
        temporary file by streaming the content. Then, it uses the copy_file_to_storage function
        to copy/move the file to the final destination based on resource_type, species, and version.

        Args:
            file (UploadFile): The uploaded file object.
            resource_type (str): The type/category of the resource.
            species (Optional[str]): The species associated with the resource.
            version (Optional[str]): The version of the resource.
            force_overwrite (bool): Flag to force overwriting if the destination file exists.

        Returns:
            tuple[str, int]: A tuple containing the final file path and the file size in bytes.

        Raises:
            ResourceValidationError: If the source file cannot be accessed.
            ResourceUnexpectedDatabaseError: If any error occurs during file copying.
        """
        try:
            # Ensure the file pointer is at the beginning
            file.file.seek(0)

            # Try to get a stable file path from the underlying SpooledTemporaryFile.
            # Note: UploadFile.filename is just the client-provided name—not a file system path.
            temp_path = getattr(file.file, "name", None)
            # If temp_path is not valid (e.g. if it's an in-memory file or not a valid path),
            # create a temporary file and write the content there.
            if not isinstance(temp_path, str) or not os.path.exists(temp_path) or temp_path.startswith("<"):
                self.logger.info("No valid temporary file path found; creating a new temporary file.")
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    shutil.copyfileobj(file.file, tmp)
                    temp_path = tmp.name


            # Extract original filename and sanitize
            original_filename = sanitize_filename(file.filename)

            # Copy file to final storage
            final_path = copy_file_to_storage(
                temp_path, original_filename, resource_type, species, version, force_overwrite
            )
            file_size = os.path.getsize(final_path)

            self.logger.info(f"File '{file.filename}' copied to '{final_path}' with size {file_size} bytes.")
            return final_path, file_size

        except Exception as e:
                self.logger.error(f"Failed to copy and save file: {e}")
                raise ResourceUnexpectedDatabaseError(detail=f"Failed to copy and save file: {e}")

    def create_resource_from_data(
        self,
        name: str,
        resource_type: str,
        species: Optional[str],
        version: Optional[str],
        file_path: str,
        file_size: int,
        uploaded_by,
    ) -> Resource:
        """
        Creates a new Resource ORM object using the provided data.

        Args:
            name (str): The resource name.
            resource_type (str): The type/category of the resource.
            species (Optional[str]): The species associated with the resource.
            version (Optional[str]): The version of the resource.
            file_path (str): The destination file path where the file was saved.
            file_size (int): The size of the file in bytes.
            uploaded_by: The user ID of the uploader.

        Returns:
            Resource: The newly created Resource ORM object.
        """
        try:

            resource = Resource(
                name=name,
                resource_type=resource_type,
                species=species,
                version=version,
                file_path=file_path,
                file_size=file_size,
                uploaded_by=uploaded_by,
                date_added=datetime.utcnow()
            )
            self.logger.info(f"Resource '{resource.name}' object created successfully.")
            return resource
        
        except ResourceValidationError as rve:
            # Propagate our own validation errors
            raise rve
        except Exception as e:
            self.logger.error(f"Failed to create resource object: {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to create resource object: {e}")

    def create_resource(self, name, resource_type, species, version, file_path, uploaded_by):
        """
        Creates a Resource object after copying the file to storage.

        Args:
            name (str): The name of the resource.
            resource_type (str): The type/category of the resource.
            species (str): The species associated with the resource.
            version (str): The version of the resource.
            file_path (str): The path to the source file.
            uploaded_by (UUID): The ID of the user uploading the resource.

        Returns:
            Resource: The newly created Resource ORM object.

        Raises:
            ResourceValidationError: If the source file does not exist.
            ResourceUnexpectedDatabaseError: If any unexpected error occurs during creation.
        """
        try:
            if not os.path.exists(file_path):
                self.logger.error(f"Source file '{file_path}' not found.")
                raise ResourceValidationError(f"Source file '{file_path}' not found.")

            # Copy file to storage location
            final_path = copy_file_to_storage(file_path, resource_type, species, version)
            file_size = os.path.getsize(final_path)
            resource_id = f"{resource_type}_{species}_{version}".lower()

            resource = Resource(
                resource_id=resource_id,
                name=name,
                type=resource_type,
                species=species,
                version=version,
                file_path=final_path,
                file_size=file_size,
                uploaded_by=uploaded_by,
                date_added=datetime.utcnow()
            )
            self.logger.info(f"Resource '{resource_id}' created at '{final_path}' with size {file_size} bytes.")
            return resource

        except ResourceValidationError as rve:
            # Propagate our own validation errors
            raise rve
        except Exception as e:
            self.logger.error(f"Failed to create resource: {e}")
            raise ResourceUnexpectedDatabaseError(detail=f"Failed to create resource: {e}")


# ------------------------------------------------------------------------------
# Dependency Injection for ResourceService
# ------------------------------------------------------------------------------
def get_resource_service() -> ResourceService:
    """
    Provides an instance of ResourceService.

    Returns:
        ResourceService: A new ResourceService instance.
    """
    return ResourceService()