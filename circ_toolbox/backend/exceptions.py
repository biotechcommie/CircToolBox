# circ_toolbox/backend/exceptions.py
from fastapi import HTTPException
from fastapi import status

# User-related exceptions
class UserNotFoundError(HTTPException):
    def __init__(self, detail: str = "User not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class LastSuperuserError(HTTPException):
    def __init__(self, detail: str = "Cannot delete the last superuser"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

class UserAlreadyExistsError(HTTPException):
    def __init__(self, detail: str = "User with this email or username already exists"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

class UnexpectedDatabaseError(HTTPException):
    def __init__(self, detail: str = "Unexpected database error"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)

class UnauthorizedActionError(HTTPException):
    """
    Raised when a user attempts an action they are not authorized to perform.
    
    Example Scenarios:
      - A user tries to modify or delete another user's resource.
      - A non-admin user attempts an admin-only action.
      - Any other unauthorized business logic violations.
    """
    def __init__(self, detail: str = "You are not authorized to perform this action"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

# Resource-related exceptions
class ResourceNotFoundError(HTTPException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class ResourcePermissionError(HTTPException):
    def __init__(self, detail: str = "You do not have permission to perform this action on the resource"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

class ResourceValidationError(HTTPException):
    def __init__(self, detail: str = "Invalid resource data"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

class ResourceUnexpectedDatabaseError(HTTPException):
    def __init__(self, detail: str = "Unexpected database error while handling resource"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)



'''
# Example definition using fastapi.status constants
from fastapi import status

GENERIC_RESPONSES = {
    status.HTTP_200_OK: {"description": "Successful operation"},
    status.HTTP_400_BAD_REQUEST: {"description": "Validation error or incorrect input"},
    status.HTTP_401_UNAUTHORIZED: {"description": "User is not authenticated"},
    status.HTTP_403_FORBIDDEN: {"description": "Insufficient permissions"},
    status.HTTP_404_NOT_FOUND: {"description": "Resource not found"},
    status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
}

   intro
   service_layer
   managers_layer
   orchestrators_layer
   routes_layer
   refs

'''