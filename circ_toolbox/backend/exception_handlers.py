# circ_toolbox/backend/exception_handlers.py
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from circ_toolbox.backend.exceptions import (
    UserNotFoundError,
    LastSuperuserError,
    UserAlreadyExistsError,
    UnexpectedDatabaseError,
    ResourceNotFoundError,
    ResourcePermissionError,
    ResourceValidationError,
    ResourceUnexpectedDatabaseError,
)

def add_exception_handlers(app):
    @app.exception_handler(UserNotFoundError)
    async def user_not_found_handler(request: Request, exc: UserNotFoundError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(LastSuperuserError)
    async def last_superuser_handler(request: Request, exc: LastSuperuserError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(UserAlreadyExistsError)
    async def user_already_exists_handler(request: Request, exc: UserAlreadyExistsError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(UnexpectedDatabaseError)
    async def unexpected_database_error_handler(request: Request, exc: UnexpectedDatabaseError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})





    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(ResourcePermissionError)
    async def resource_permission_handler(request: Request, exc: ResourcePermissionError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(ResourceValidationError)
    async def resource_validation_handler(request: Request, exc: ResourceValidationError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(ResourceUnexpectedDatabaseError)
    async def resource_unexpected_database_handler(request: Request, exc: ResourceUnexpectedDatabaseError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})






    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
    
