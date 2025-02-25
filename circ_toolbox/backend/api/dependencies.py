# circ_toolbox_project/circ_toolbox/backend/api/dependencies.py
from fastapi import Depends, HTTPException
from circ_toolbox.backend.services.auth import fastapi_users
from circ_toolbox.backend.database.models.user_model import Users

# Get the current authenticated user (active or not)
current_user = fastapi_users.current_user()

# Get the current active user (authenticated and active)
current_active_user = fastapi_users.current_user(active=True)

# Get the current active and verified user
current_active_verified_user = fastapi_users.current_user(active=True, verified=True)

# Get the current active superuser
current_superuser = fastapi_users.current_user(active=True, superuser=True)

# Alias for superuser permission
admin_required = fastapi_users.current_user(active=True, superuser=True)

# Alias for active and verified user permission
user_required = fastapi_users.current_user(active=True, verified=True)

def get_current_admin_user(user: Users = Depends(current_superuser)):
    return user


def role_required(role: str):
    def role_dependency(user: Users = Depends(current_active_user)):
        if role == "admin" and not user.is_superuser:
            raise HTTPException(status_code=403, detail="Admin role required")
        return user
    return role_dependency