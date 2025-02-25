# circ_toolbox/backend/api/routes/user_routes.py
"""
User Management API Routes

This module defines the user-related API endpoints for authentication,
profile management, and administrative user control.

It provides endpoints for:
  - User authentication (login, logout, password reset)
  - Retrieving and updating the authenticated user's profile
  - Administrative actions to create, list, update, and delete users

All endpoints leverage FastAPI’s dependency injection to obtain the necessary 
database session, current authenticated user, and business logic encapsulated 
in the UserOrchestrator. Custom exceptions from the backend are used to ensure 
consistent and meaningful HTTP responses.

For more detailed information on each endpoint, please refer to their respective 
docstrings below.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from circ_toolbox.backend.database.models.user_model import Users
from circ_toolbox.backend.database.base import get_session
from circ_toolbox.backend.api.dependencies import current_active_user, current_superuser
from circ_toolbox.backend.api.schemas.user_schemas import UserRead, UserCreate, UserUpdate
from circ_toolbox.backend.services.auth import fastapi_users, auth_backend
from circ_toolbox.backend.services.orchestrators.user_orchestrator import UserOrchestrator, get_user_orchestrator
from circ_toolbox.backend.utils import get_logger
from circ_toolbox.backend.exceptions import UserAlreadyExistsError, UserNotFoundError, LastSuperuserError, UnexpectedDatabaseError

router = APIRouter()
logger = get_logger("user_routes")

# ===========================
# Authentication Routes
# ===========================
#
# The following routes are provided by FastAPI Users to handle authentication:
# - Login and logout routes under `/auth/jwt`
# - Password reset routes under `/auth`
#
# These endpoints are included here via router.include_router.

# Include authentication routes (Login, Logout)
router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["Auth"]
)

# Include password recovery routes
router.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["Auth"]
)


# ===========================
# User Management Routes
# ===========================

@router.get(
    "/users/me",
    response_model=UserRead,
    responses={
        status.HTTP_200_OK: {"description": "Authenticated user's profile retrieved successfully"},
        status.HTTP_401_UNAUTHORIZED: {"description": "User is not authenticated"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    tags=["Users"]
)
async def get_user_profile(
    user: Users = Depends(current_active_user)
):
    """
    Retrieve the profile of the currently authenticated user.

    This endpoint returns the profile details of the user who is currently authenticated.
    It uses dependency injection to obtain the user information from the authentication system.

    Args:
        user (Users): The currently authenticated user.

    Returns:
        UserRead: The user's profile details.

    Raises:
        HTTPException 401: If the user is not authenticated.
        HTTPException 500: If an unexpected error occurs.
    """
    try:
        return user
    except Exception as e:
        logger.error(f"Unexpected error retrieving user profile: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.patch(
    "/users/me",
    response_model=UserRead,
    responses={
        status.HTTP_200_OK: {"description": "User profile updated successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "Validation error or incorrect input data"},
        status.HTTP_401_UNAUTHORIZED: {"description": "User is not authenticated"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    tags=["Users"]
)
async def update_user_profile(
    update_data: UserUpdate,
    user: Users = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
    orchestrator: UserOrchestrator = Depends(get_user_orchestrator)
):
    """
    Update the profile of the currently authenticated user.

    This endpoint allows a user to update their own profile. Only the fields provided in the
    request body are updated; any fields not provided remain unchanged. Input validation is 
    performed via Pydantic.

    Args:
        update_data (UserUpdate): The new profile data to be updated.
            - Fields not provided remain unchanged (`exclude_unset=True`).
            - Validation is enforced through Pydantic.
        user (Users): The authenticated user obtained via dependency injection.
        session (AsyncSession): The async database session for executing queries.
        orchestrator (UserOrchestrator): Handles business logic for updating user data.

    Returns:
        UserRead: The updated user profile.

    Raises:
        HTTPException (400 Bad Request): If validation fails (e.g., invalid email format, missing required fields).
        HTTPException (401 Unauthorized): If the user is not authenticated.
        HTTPException (500 Internal Server Error): If a database update fails due to an internal server issue.
    """
    try:
        return await orchestrator.update_user_profile(user, update_data.dict(exclude_unset=True), session)
    
    except UserAlreadyExistsError as e:
        logger.info(f"Validation error during profile update: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except UnexpectedDatabaseError as e:
        logger.error(f"Unexpected database error during profile update: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.critical(f"Unrecoverable error during profile update: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.post(
    "/admin/users",
    response_model=UserRead,
    responses={
        status.HTTP_201_CREATED: {"description": "User created successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "User already exists"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    tags=["Admin"]
)
async def create_user(
    user_create: UserCreate,
    admin: Users = Depends(current_superuser),
    session: AsyncSession = Depends(get_session),
    orchestrator: UserOrchestrator = Depends(get_user_orchestrator)
):
    """
    Create a new user (Admin-only).

    This endpoint allows an admin to create a new user by providing the required details.
    It is accessible only to users with admin privileges.
    
    Args:
        user_create (UserCreate): The details of the user to be created.
        admin (Users): The authenticated admin user.
        session (AsyncSession): The async database session.
        orchestrator (UserOrchestrator): The orchestrator handling business logic for user creation.

    Returns:
        UserRead: The details of the newly created user.

    Raises:
        HTTPException (400 Bad Request): If a user with the same email or username already exists.
        HTTPException (500 Internal Server Error): If an unexpected server error occurs.
    """
    try:
        return await orchestrator.create_user(user_create, session) # ✅ No session needed in the UserManager, but passing to orchestrator as default behaviour, even if its not going to be used.
    
    except UserAlreadyExistsError as e:
        logger.info(f"User creation failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except UnexpectedDatabaseError as e:
        logger.error(f"Unexpected database error during user creation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.critical(f"Unrecoverable error during user creation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get(
    "/admin/users",
    response_model=list[UserRead],
    responses={
        status.HTTP_200_OK: {"description": "List of users retrieved successfully"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    tags=["Admin"]
)
async def list_all_users(
    skip: int = Query(0, description="The number of users to skip for pagination."),
    limit: int = Query(10, description="The maximum number of users to return per request."),
    admin: Users = Depends(current_superuser),
    session: AsyncSession = Depends(get_session),
    orchestrator: UserOrchestrator = Depends(get_user_orchestrator)
):
    """
    Retrieve a paginated list of all users (Admin-only).

    This endpoint returns a list of user profiles based on the specified pagination parameters.
    It is restricted to admin users.

    Args:
        skip (int): The number of users to skip (pagination offset).
        limit (int): The maximum number of users to return in this request.
        admin (Users): The authenticated admin user.
        session (AsyncSession): The async database session.
        orchestrator (UserOrchestrator): The orchestrator handling business logic for listing users.

    Returns:
        list[UserRead]: A list of users. If no users exist, returns an empty list.

    Raises:
        HTTPException (500): If an internal server error occurs.
    """
    try:
        return await orchestrator.list_all_users(skip, limit, session)
    except UnexpectedDatabaseError as e:
        logger.error(f"Unexpected error retrieving users - UnexpectedDatabaseError: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error retrieving users: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get(
    "/admin/users/{user_id}",
    response_model=UserRead,
    responses={
        status.HTTP_200_OK: {"description": "User retrieved successfully"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    tags=["Admin"]
)
async def get_user_by_id(
    user_id: UUID,
    admin: Users = Depends(current_superuser),
    session: AsyncSession = Depends(get_session),
    orchestrator: UserOrchestrator = Depends(get_user_orchestrator)
):
    """
    Retrieve a user by their ID (Admin-only).

    This endpoint allows an admin to fetch the profile of a specific user by UUID.

    Args:
        user_id (UUID): The ID of the user to retrieve.
        admin (Users): The authenticated admin user.
        session (AsyncSession): The async database session.
        orchestrator (UserOrchestrator): The orchestrator handling user retrieval logic.

    Returns:
        UserRead: The requested user's data.

    Raises:
        HTTPException (404): If the user is not found.
        HTTPException (500): If an internal server error occurs.
    """
    try:
        return await orchestrator.get_user_by_id(user_id, session)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except UnexpectedDatabaseError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error retrieving user {user_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.patch(
    "/admin/users/{user_id}",
    response_model=UserRead,
    responses={
        status.HTTP_200_OK: {"description": "User updated successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "User already exists"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    tags=["Admin"]
)
async def update_user_by_id(
    user_id: UUID,
    update_data: UserUpdate,
    admin: Users = Depends(current_superuser),
    session: AsyncSession = Depends(get_session),
    orchestrator: UserOrchestrator = Depends(get_user_orchestrator)
):
    """
    Update a user's details by their ID (Admin-only).

    This endpoint allows an admin to update any user's profile. Only the fields provided in the request
    are updated; fields not provided remain unchanged. Uniqueness constraints are enforced to prevent duplicate
    emails or usernames (except when updating a user with its own current email).

    Args:
        user_id (UUID): The ID of the user to update.
        update_data (UserUpdate): The fields to update. 
            - All fields are **optional**.
            - Fields not provided will remain unchanged.
            - Uses `exclude_unset=True` to prevent overwriting fields with `None`.
        admin (Users): The authenticated admin user.
        session (AsyncSession): The async database session.
        orchestrator (UserOrchestrator): The orchestrator handling business logic for updates.

    Returns:
        UserRead: The updated user's details.

    Raises:
        HTTPException (404 Not Found): If the user does not exist.
        HTTPException (500 Internal Server Error): If an unexpected server error occurs.
    """
    try:
        return await orchestrator.update_user_by_id(user_id, update_data.dict(exclude_unset=True), session)
    
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except UserAlreadyExistsError as e:
        logger.info(f"User creation failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except UnexpectedDatabaseError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    


    except Exception as e:
        logger.error(f"Unexpected error updating user {user_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.delete(
    "/admin/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "User deleted successfully"},
        status.HTTP_403_FORBIDDEN: {"description": "Cannot delete the last superuser"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
    tags=["Admin"]
)
async def delete_user_by_id(
    user_id: UUID,
    admin: Users = Depends(current_superuser),
    session: AsyncSession = Depends(get_session),
    orchestrator: UserOrchestrator = Depends(get_user_orchestrator)
):
    """
    Delete a user by their ID (Admin-only).

    This endpoint allows an admin to delete a user from the system. Deletion is not permitted if the user
    is the last remaining superuser.

    Args:
        user_id (UUID): The ID of the user to delete.
        admin (Users): The authenticated admin user.
        session (AsyncSession): The async database session.
        orchestrator (UserOrchestrator): The orchestrator handling business logic for deletion.

    Returns:
        None (204 No Content).

    Raises:
        HTTPException (403): If attempting to delete the last superuser.
        HTTPException (404): If the user is not found.
        HTTPException (500): If an internal server error occurs.
    """
    try:
        await orchestrator.delete_user(user_id, session)
    
    except LastSuperuserError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except UnexpectedDatabaseError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error deleting user {user_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


















# User registration
# router.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["Auth"])

# Email verification (optional)
# router.include_router(fastapi_users.get_verify_router(), prefix="/auth", tags=["Auth"])

# Password recovery
# router.include_router(fastapi_users.get_reset_password_router(), prefix="/auth", tags=["Auth"])

# OAuth login (optional)
# router.include_router(fastapi_users.get_oauth_router(), prefix="/auth/oauth", tags=["Auth"])

# ===========================
# User management routes
# ===========================

# User management (Get current user, update, delete)
# router.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["Users"])




'''


# ===========================
# Protected routes
# ===========================

# Route for all authenticated users
@router.get("/protected", tags=["Protected"])
async def protected_route(user: User = Depends(current_user)):
    return {"message": f"Hello, {user.email}"}

# Route for active users only
@router.get("/protected-active", tags=["Protected"])
async def protected_active_route(user: User = Depends(current_active_user)):
    return {"message": f"Hello, active user {user.email}"}

# Route for verified users only
@router.get("/protected-verified", tags=["Protected"])
async def protected_verified_route(user: User = Depends(current_active_verified_user)):
    return {"message": f"Hello, verified user {user.email}"}

# Route for superuser only
@router.get("/admin-only", tags=["Admin"])
async def admin_route(user: User = Depends(current_superuser)):
    return {"message": f"Welcome, superuser {user.email}"}






def role_required(role: str):
    def role_dependency(user: User = Depends(current_active_user)):
        if role == "admin" and not user.is_superuser:
            raise HTTPException(status_code=403, detail="Admin role required")
        return user
    return role_dependency

@router.get("/admin-dashboard")
async def admin_dashboard(user: User = Depends(role_required("admin"))):
    return {"message": f"Welcome Admin {user.email}"}

'''


