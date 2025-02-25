# circ_toolbox/backend/api/routes/resource_routes.py
"""
Resource Management API Routes

This module defines the REST API endpoints for managing resources within the CircToolbox system.
It provides endpoints for:
  - Registering a new resource linked to the authenticated user.
  - Listing resources with support for pagination and optional filtering.
  - Updating existing resources (only allowed for the resource owner or an admin).
  - Deleting resources (only allowed for the resource owner or an admin).
  - Retrieving a list of unique species for dropdown autofill.
  - Retrieving a specific resource by its UUID.

Each endpoint uses custom exceptions such as:
  - ResourceNotFoundError
  - ResourcePermissionError
  - ResourceValidationError
  - ResourceUnexpectedDatabaseError

These exceptions ensure that clients receive consistent and meaningful HTTP status codes and error messages.

Usage:
  Endpoints (routes) leverage FastAPI’s dependency injection to obtain the necessary database session,
  current authenticated user, and an instance of the ResourceOrchestrator, which encapsulates
  the business logic and error handling.

For further details, refer to the inline function docstrings that follow Google-style guidelines.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

# Import our Pydantic schemas (which now include UploadFile fields and as_form support)
from circ_toolbox.backend.api.schemas.resource_schemas import (
    ResourceCreate,
    ResourceUpdate,
    ResourceResponse,
    SpeciesListResponse,
)

# Import the orchestrator and its dependency provider
from circ_toolbox.backend.services.orchestrators.resource_orchestrator import (
    ResourceOrchestrator,
    get_resource_orchestrator,
)

from circ_toolbox.backend.utils.logging_config import get_logger, log_runtime

# Import database session dependency and current user dependency
from circ_toolbox.backend.database.base import get_session
from circ_toolbox.backend.api.dependencies import current_active_user

from typing import Optional, List
from uuid import UUID

# Import the new custom exceptions
from circ_toolbox.backend.exceptions import (
    ResourceNotFoundError,
    ResourcePermissionError,
    ResourceValidationError,
    ResourceUnexpectedDatabaseError,
    UnauthorizedActionError,
)


router = APIRouter()
logger = get_logger("resource_routes")


# ------------------------------------------------------------------------------
# Register new resource with user association
# ------------------------------------------------------------------------------
@router.post(
    "/resources/",
    response_model=ResourceResponse,  
    responses={
        status.HTTP_201_CREATED: {"description": "Resource created successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "Validation error occurred"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
) 
@log_runtime("resource_routes")
async def register_resource(
    resource: ResourceCreate = Depends(), 
    user=Depends(current_active_user),
    orchestrator: ResourceOrchestrator = Depends(get_resource_orchestrator),
    session: AsyncSession = Depends(get_session)
):
    """
    Register a new resource in the database linked to the authenticated user.

    This endpoint accepts a multipart/form-data request containing form fields and a file upload.
    The ResourceCreate model (modified with as_form) validates both the non-file fields and the file's
    extension before the data is passed to the ResourceOrchestrator.

    Args:
        resource (ResourceCreate): The validated resource data (including the uploaded file).
        user (User): The currently authenticated user.
        orchestrator (ResourceOrchestrator): The orchestrator that handles business logic.
        session (AsyncSession): The database session.

    Returns:
        ResourceResponse: The registered resource record.

    Raises:
        HTTPException 400: If resource validation fails.
        HTTPException 500: If an unexpected error occurs during processing.
    """
    logger.info(f"User {user.email} is attempting to register a resource.")

    try:
        # Delegate the entire business logic (including file copy and DB registration)
        response = await orchestrator.register_resource(resource, user, session)

        logger.info(f"Resource '{response.name}' registered by {user.email} successfully.")
        return response  # Return directly, orchestrator handles conversion

    except ResourceValidationError as rve:
        logger.warning(f"Validation error for resource registration: {rve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(rve))
    except ResourceUnexpectedDatabaseError as rde:
        logger.error(f"Database error registering resource: {rde}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(rde))
    except Exception as e:
        logger.error(f"Failed to register resource: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")




# ------------------------------------------------------------------------------
# List resources with pagination and optional filtering
# ------------------------------------------------------------------------------
@router.get(
    "/resources/",
    response_model=list[ResourceResponse],
    responses={
        status.HTTP_200_OK: {"description": "List of resources retrieved successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid query parameters"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)
@log_runtime("resource_routes")
async def list_resources(
    limit: int = Query(10, ge=1, le=100, description="Number of resources to retrieve"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    species: Optional[str] = Query(None, description="Filter by species"),
    orchestrator: ResourceOrchestrator = Depends(get_resource_orchestrator),
    session: AsyncSession = Depends(get_session)
):
    """
    List all registered resources with pagination support.

    Args:
        limit (int): Number of resources to retrieve.
        offset (int): Offset for pagination.
        resource_type (Optional[str]): Filter for resource type.
        species (Optional[str]): Filter for species.
        orchestrator (ResourceOrchestrator): The orchestrator handling resource retrieval.
        session (AsyncSession): The database session.

    Returns:
        list[ResourceResponse]: A list of resources.

    Raises:
        HTTPException 400: If query parameters are invalid.
        HTTPException 500: If an unexpected database error occurs.
    """
    logger.info(f"Incoming request to list resources with limit={limit}, offset={offset}, resource_type={resource_type}, species={species}")
    
    try:
        # Delegate responsibility to orchestrator
        resources = await orchestrator.list_resources(
            limit=limit,
            offset=offset,
            resource_type=resource_type,
            species=species,
            session=session
        )

        logger.info(f"Retrieved {len(resources)} resources.")
        return resources

    except ResourceValidationError as rve:
        logger.warning(f"Validation error listing resources: {rve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(rve))
    except ResourceUnexpectedDatabaseError as rde:
        logger.error(f"Database error listing resources: {rde}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(rde))
    except Exception as e:
        logger.error(f"Failed to list resources: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve resources")


@router.put("/test-resource-update")
async def test_resource_update(payload: ResourceUpdate = Depends()):
    logger.info(">>> ENTERED test_resource_update WITH:", payload.__class__)
    print(">>> ENTERED test_resource_update WITH:", payload.__class__)
    print(">>> Payload fields:", payload.__fields_set__)
    return payload.dict(exclude_unset=True)



# ------------------------------------------------------------------------------
# Update resource (only owner or admin)
# ------------------------------------------------------------------------------
@router.put(
    "/resources/{resource_id}/",
    response_model=dict,
    responses={
        status.HTTP_200_OK: {"description": "Resource updated successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "Validation error occurred"},
        status.HTTP_403_FORBIDDEN: {"description": "Unauthorized update attempt"},
        status.HTTP_404_NOT_FOUND: {"description": "Resource not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)
@log_runtime("resource_routes")
async def update_resource(
    resource_id: UUID,  # Use UUID to ensure type consistency
    update_data: ResourceUpdate = Depends(),
    user=Depends(current_active_user),
    orchestrator: ResourceOrchestrator = Depends(get_resource_orchestrator),
    session: AsyncSession = Depends(get_session),
):
    """
    Update an existing resource in the database.

    This endpoint accepts multipart/form-data, validating both form fields and the optional file upload.
    The validated data is then passed to the ResourceOrchestrator, which handles business logic.

    Args:
        resource_id (UUID): The unique ID of the resource to update.
        update_data (ResourceUpdate): The data to update.
        user (User): The authenticated user.
        orchestrator (ResourceOrchestrator): The orchestrator handling update logic.
        session (AsyncSession): The database session.

    Returns:
        dict: The updated resource data.

    Raises:
        HTTPException 400: If the update data is invalid.
        HTTPException 403: If the user is not allowed to update this resource.
        HTTPException 404: If the resource is not found.
        HTTPException 500: If an unexpected error occurs.
    """
    logger.info(f"User {user.email} is attempting to update resource '{resource_id}'.")

    try:
        # Delegate the entire process to the orchestrator
        response = await orchestrator.update_resource(resource_id, update_data, user, session)
        logger.info(f"Resource '{resource_id}' updated successfully by {user.email}")
        return response
    
    except ResourceValidationError as rve:
        logger.warning(f"Validation error for resource '{resource_id}': {rve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(rve))
    except ResourceNotFoundError as rnfe:
        logger.error(f"Resource '{resource_id}' not found: {rnfe}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(rnfe))
    except ResourcePermissionError as rpe:
        logger.warning(f"Unauthorized update attempt by {user.email}: {rpe}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(rpe))
    except UnauthorizedActionError as rpe:
        logger.warning(f"Unauthorized update attempt by {user.email}: {rpe}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(rpe))
    except ResourceUnexpectedDatabaseError as rde:
        logger.error(f"Database error updating resource '{resource_id}': {rde}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(rde))
    except Exception as e:
        logger.error(f"Failed to update resource '{resource_id}': {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update resource")



# ------------------------------------------------------------------------------
# Delete resource (only owner or admin)
# ------------------------------------------------------------------------------
@router.delete(
    "/resources/{resource_id}/",
    responses={
        status.HTTP_200_OK: {"description": "Resource deleted successfully"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden: You can only delete your own resources"},
        status.HTTP_404_NOT_FOUND: {"description": "Resource not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)
@log_runtime("resource_routes")
async def delete_resource(
    resource_id: UUID,  # Use UUID to ensure type consistency
    user=Depends(current_active_user),
    orchestrator: ResourceOrchestrator = Depends(get_resource_orchestrator),
    session: AsyncSession = Depends(get_session),
):
    """
    Delete a resource from the database if the user owns it or is an admin.

    Args:
        resource_id (UUID): The unique ID of the resource to delete.
        user (User): The authenticated user.
        orchestrator (ResourceOrchestrator): The orchestrator handling deletion logic.
        session (AsyncSession): The database session.

    Returns:
        dict: An empty response indicating successful deletion.

    Raises:
        HTTPException 403: If the user is not permitted to delete this resource.
        HTTPException 404: If the resource is not found.
        HTTPException 500: If an unexpected error occurs.
    """
    logger.info(f"User {user.email} is attempting to delete resource '{resource_id}'.")

    try:
        response = await orchestrator.delete_resource(resource_id, user, session)
        logger.info(f"Resource '{resource_id}' deleted by {user.email}")
        return response
    
    except ResourcePermissionError as rpe:
        logger.warning(f"Unauthorized delete attempt by {user.email}: {rpe}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(rpe))
    except ResourceNotFoundError as rnfe:
        logger.error(f"Resource '{resource_id}' not found: {rnfe}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(rnfe))
    except ResourceUnexpectedDatabaseError as rde:
        logger.error(f"Failed to delete resource '{resource_id}': {rde}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(rde))
    except Exception as e:
        logger.error(f"Failed to delete resource '{resource_id}': {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete resource")



# ------------------------------------------------------------------------------
# Get species list for dropdowns
# ------------------------------------------------------------------------------
@router.get(
    "/resources/species/",
    response_model=SpeciesListResponse,
    responses={
        status.HTTP_200_OK: {"description": "Species list retrieved successfully"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)
@log_runtime("resource_routes")
async def get_species_list(
    user=Depends(current_active_user),
    orchestrator: ResourceOrchestrator = Depends(get_resource_orchestrator),
    session: AsyncSession = Depends(get_session),
):
    """
    Retrieve a list of unique species for dropdown autofill.

    Args:
        user (User): The authenticated user.
        orchestrator (ResourceOrchestrator): The orchestrator for fetching species.
        session (AsyncSession): The database session.

    Returns:
        SpeciesListResponse: A response containing the list of unique species.

    Raises:
        HTTPException 500: If an internal server error occurs.
    """
    logger.info(f"User {user.email} requested unique species list.")

    try:
        species_list = await orchestrator.get_species_list(session)
        logger.info(f"Retrieved {len(species_list)} unique species.")
        return SpeciesListResponse(species=species_list)

    except ResourceUnexpectedDatabaseError as rde:
        logger.error(f"Failed to retrieve species list: {rde}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(rde))
    except Exception as e:
        logger.error(f"Failed to retrieve species list: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve species list")


# ------------------------------------------------------------------------------
# Retrieve a specific resource by ID
# ------------------------------------------------------------------------------
@router.get(
    "/resources/{resource_id}/",
    response_model=ResourceResponse,
    responses={
        status.HTTP_200_OK: {"description": "Resource retrieved successfully"},
        status.HTTP_404_NOT_FOUND: {"description": "Resource not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)
@log_runtime("resource_routes")
async def get_resource_by_id(
    resource_id: UUID,  # Use UUID for consistency
    user=Depends(current_active_user),
    orchestrator: ResourceOrchestrator = Depends(get_resource_orchestrator),
    session: AsyncSession = Depends(get_session),
):
    """
    Retrieve a specific resource by its ID.

    Args:
        resource_id (UUID): The unique ID of the resource.
        user (User): The authenticated user.
        orchestrator (ResourceOrchestrator): The orchestrator handling resource retrieval.
        session (AsyncSession): The database session.

    Returns:
        ResourceResponse: The retrieved resource details.

    Raises:
        HTTPException 404: If the resource is not found.
        HTTPException 500: If an internal server error occurs.
    """
    logger.info(f"User {user.email} is retrieving resource '{resource_id}'.")

    try:
        resource = await orchestrator.get_resource_by_id(resource_id, session)
        logger.info(f"Resource '{resource_id}' retrieved successfully.")
        return resource

    except ResourceNotFoundError as rnfe:
        logger.error(f"Resource '{resource_id}' not found: {rnfe}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(rnfe))
    except Exception as e:
        logger.error(f"Failed to retrieve resource '{resource_id}': {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve resource")



'''

curl -X POST "http://127.0.0.1:8000/api/v1/resources/" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "name=Example Resource" \
  -F "resource_type=GENOME" \
  -F "species=Homo sapiens" \
  -F "version=v1" \
  -F "force_overwrite=false" \
  -F "file=@/path/to/local/file.fasta"

  
  
'''


'''

from fastapi import UploadFile, File, HTTPException
from circ_toolbox.backend.api.schemas.resource_schemas import ResourceFileCreate, ResourceFileRead

@router.post("/resources", response_model=ResourceFileRead)
async def upload_resource_file(
    file: UploadFile = File(...),
    resource_data: ResourceFileCreate = Depends(),
    user: User = Depends(current_active_user)
):
    """Upload a new resource file."""
    # Placeholder for file saving logic
    return {"id": uuid.uuid4(), "name": file.filename, "uploadedBy": user.id}

@router.get("/resources", response_model=list[ResourceFileRead])
async def list_resources(user: User = Depends(current_active_user)):
    """List all available resource files."""
    # Placeholder for fetching resource files
    return []

@router.patch("/resources/{resource_id}", response_model=ResourceFileRead)
async def update_resource_file(resource_id: UUID, update_data: ResourceFileCreate, user: User = Depends(current_active_user)):
    """Update resource file metadata."""
    # Placeholder for update logic
    return {"id": resource_id, "name": update_data.name, "uploadedBy": user.id}

@router.delete("/resources/{resource_id}")
async def delete_resource_file(resource_id: UUID, user: User = Depends(current_superuser)):
    """Delete a resource file (Admin only)."""
    # Placeholder for deletion logic
    return {"message": "Resource file deleted successfully"}


'''


'''
3. Handling User Object in Responses:
If you're getting an SQLAlchemy model directly and want to return it as a response, use:

python
Copiar
Editar
user_dict = UserRead.from_orm(user).dict()
Where to Apply:
Example in a route where you manually fetch user details:

python
Copiar
Editar
@router.get("/user/{user_id}", response_model=UserRead)
async def get_user(user_id: UUID, session: AsyncSession = Depends(get_session)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserRead.from_orm(user)

'''



'''
Example API Requests:
1. Update Resource (Valid File Path)
bash
Copiar
PUT /resources/genome_mouse_grcm39/
Content-Type: application/json

{
    "name": "Mouse Genome GRCm39 Updated",
    "species": "Mus musculus",
    "version": "GRCm39",
    "uploaded_by": "admin",
    "file_path": "/data/genomes/new_grcm39.fasta"
}
The file at /data/genomes/new_grcm39.fasta is validated before updating.
2. Update Resource (Invalid File Path)
bash
Copiar
PUT /resources/genome_mouse_grcm39/
Content-Type: application/json

{
    "name": "Mouse Genome",
    "species": "Mus musculus",
    "version": "GRCm39",
    "uploaded_by": "admin",
    "file_path": "../../etc/passwd"
}
Response:

json
Copiar
{
    "detail": "File path '../../etc/passwd' is invalid or the file does not exist."
}
Next Steps:
Logging Improvements:

Add detailed logs to track validation failures and user activity.
Use logger.info() and logger.error() in endpoints for debugging.
Error Handling Improvements:

Create custom exceptions (e.g., InvalidFilePathException) for clarity.
Testing:

Add unit tests to cover valid and invalid file paths, updates, and deletions.
By implementing these changes, the API remains secure, efficient, and aligned with your local file system-based architecture.

'''



'''

Example Requests:
Valid File Path:

json
Copiar
{
    "name": "Mouse Genome",
    "resource_type": "genome",
    "species": "Mus musculus",
    "version": "GRCm39",
    "file_path": "/data/genomes/mouse.fasta",
    "uploaded_by": "local_user",
    "force_overwrite": false
}
If the file path is valid and exists, the resource is registered successfully.
Invalid File Extension:

json
Copiar
{
    "file_path": "/data/unknown.file"
}
Response:

json
Copiar
{
    "detail": "Unsupported file format: .file. Allowed formats: ['.fasta', '.fa', '.txt']"
}
Further Customization:
Dynamic Allowed Extensions: You can load ALLOWED_EXTENSIONS from a config file (config.yaml) for flexibility.

yaml
Copiar
allowed_extensions:
  - .fasta
  - .fa
  - .txt
Then:

python
Copiar
import yaml

with open("config.yaml") as f:
    config = yaml.safe_load(f)
ALLOWED_EXTENSIONS = config["allowed_extensions"]
Adding Hash Validation (Optional Security Check): Compare the MD5 or SHA256 checksum of the incoming file with a known checksum to detect tampering:

python
Copiar
import hashlib

def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()
Conclusion:
The register_resource function now handles local file paths securely by:
Validating file paths and extensions.
Preventing path traversal attacks.
Ensuring files exist locally before copying.

'''