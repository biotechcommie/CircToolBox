# circ_toolbox_project/circ_toolbox/backend/api/schemas/user_schemas.py
from fastapi_users import schemas
from pydantic import BaseModel, EmailStr
from uuid import UUID

# Schema for user creation (Admin registration only)
class UserCreate(schemas.BaseUserCreate):
    username: str  # Custom field
    email: EmailStr
    password: str
    is_superuser: bool = False  # Enforce default

# Schema for reading user information (Response Model)
class UserRead(schemas.BaseUser[UUID]):
    id: UUID
    username: str
    email: str
    is_superuser: bool

# Schema for updating user information (Regular users can only modify certain fields)
class UserUpdate(schemas.BaseUserUpdate):
    username: str | None = None  # Allow updating username
    email: EmailStr | None = None  # Allow updating email


'''
Solution:
1. Use Optional from the typing module (Compatible with Python 3.9):
Modify your UserUpdate schema in user_schemas.py:

python
Copiar
Editar
from typing import Optional

class UserUpdate(schemas.BaseUserUpdate):
    username: Optional[str] = None
    is_admin: Optional[bool] = None
This is the correct approach for Python versions earlier than 3.10.
'''