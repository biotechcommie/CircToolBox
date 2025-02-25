# circ_toolbox_project/circ_toolbox/backend/scripts/create_admin_user.py
import asyncio
from circ_toolbox.backend.database.user_db import get_user_db_manual
from circ_toolbox.backend.database.user_manager import UserManager
from circ_toolbox.backend.api.schemas.user_schemas import UserCreate
from fastapi_users.exceptions import UserNotExists
from circ_toolbox.backend.database.base import get_session_instance
from circ_toolbox.backend.utils import get_logger

logger = get_logger("create_admin_user")

async def create_admin_user():
    """
    Ensure that an admin user exists in the database. If not, create one.
    """
    async for user_db in get_user_db_manual():  # ✅ Manually get user database
        user_manager = UserManager(user_db)  # ✅ Explicitly instantiate `UserManager`
        session = await get_session_instance()  # ✅ Ensure session is explicitly handled

        try:
            # ✅ Check if the admin user already exists
            existing_admin = await user_manager.has_any_admin(session=session)  # await user_manager.get_by_email("admin@circtoolbox.com")
            print(f"existing admin = {existing_admin}")
            logger.info(f"existing admin = {existing_admin}")
            if existing_admin:
                print("⚠️ Admin user already exists.")
                return

            admin_user = UserCreate(
                email="admin@circtoolbox.com",
                password="Admin@123",
                is_active=True,
                is_superuser=True,
                is_verified=True,
                username="admin"
            )
            await user_manager.create_user(admin_user, session) # ✅ Use FastAPI Users `create()`
            await session.commit()  # ✅ Ensure transaction is saved
            print("✅ Admin user created successfully!")

        except Exception as e:
            print(f"❌ Failed to create admin user: {e}")
            await session.rollback()
        finally:
            await session.close()  # ✅ Explicitly close session
            
if __name__ == "__main__":
    asyncio.run(create_admin_user())





'''
async def create_admin_user():
    async for user_db in get_user_db_manual():  # Manually resolve session
        user_manager = UserManager(user_db)

        try:
            existing_admin = await user_manager.get_by_email("admin@circtoolbox.com")
            print("⚠️ Admin user already exists.")
        except UserNotExists:
            admin_user = UserCreate(
                email="admin@circtoolbox.com",
                password="Admin@123",
                is_active=True,
                is_superuser=True,
                username="admin"
            )
            await user_manager.create(admin_user)
            print("✅ Admin user created successfully!")

if __name__ == "__main__":
    asyncio.run(create_admin_user())

async def create_admin_user():
    async for user_db in get_user_db_manual():  # Manually resolve session
        user_manager = UserManagerCustom(user_db)

        try:
            existing_admin = await user_manager.get_by_email("admin@circtoolbox.com")
            print("⚠️ Admin user already exists.")
        except UserNotExists:
            admin_user = UserCreate(
                email="admin@circtoolbox.com",
                password="Admin@123",
                is_active=True,
                is_superuser=True,
                username="admin"
            )
            await user_manager.create(admin_user)
            print("✅ Admin user created successfully!")
'''