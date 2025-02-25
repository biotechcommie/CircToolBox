# circ_toolbox/backend/services/auth.py
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import JWTStrategy, AuthenticationBackend, BearerTransport
from circ_toolbox.backend.api.schemas.user_schemas import UserCreate, UserRead, UserUpdate
from circ_toolbox.backend.database.models.user_model import Users
from circ_toolbox.backend.database.user_manager import get_user_manager
from circ_toolbox.config import SECRET_KEY, JWT_LIFETIME_SECONDS
from uuid import UUID
import logging

# Define JWT strategy using values from config.py
def get_jwt_strategy():
    return JWTStrategy(secret=SECRET_KEY, lifetime_seconds=JWT_LIFETIME_SECONDS)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=BearerTransport(tokenUrl="/api/v1/auth/jwt/login"),
    get_strategy=get_jwt_strategy,
)

# Instantiate FastAPIUsers 
fastapi_users = FastAPIUsers[Users, UUID](
    get_user_manager,
    [auth_backend],

)


