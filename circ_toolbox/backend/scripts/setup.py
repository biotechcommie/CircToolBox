# circ_toolbox_project/circ_toolbox/backend/scripts/setup.py
import asyncio
from circ_toolbox.backend.scripts.init_db import setup_database

async def main():
    print("🔧 Setting up the database...")
    await setup_database()
    print("✅ Setup completed. Now run 'alembic' manually.")

if __name__ == "__main__":
    asyncio.run(main())
