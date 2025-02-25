# circ_toolbox_project/circ_toolbox/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set BASE_DIR to the project root (circ_toolbox_project/)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------
# Database Configuration (SQLite)
# ---------------------------
# DATABASE_FILENAME = os.getenv("DATABASE_FILENAME", "resources.db")
# DATABASE_DIR = os.getenv("DATABASE_DIR", os.path.join(BASE_DIR, "circ_toolbox", "backend", "database"))
# DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{os.path.join(DATABASE_DIR, DATABASE_FILENAME)}")
# ---------------------------
# Database Configuration (PostgreSQL)
# ---------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://appuser:apppassword@localhost:5432/circ_toolbox_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "appuser")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "apppassword")
POSTGRES_DB = os.getenv("POSTGRES_DB", "circ_toolbox_db")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
PGDATA_DIR = os.getenv("PGDATA_DIR", "./circ_toolbox/backend/database/pgdata")

# Construct DATABASE_URL dynamically
#DATABASE_URL = (
#    f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
#    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
#)


# ---------------------------
# Security Configuration
# ---------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "defaultsecretkey")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_LIFETIME_SECONDS = int(os.getenv("JWT_LIFETIME_SECONDS", 3600))
PASSWORD_SALT = os.getenv("PASSWORD_SALT", "default_salt")

# ---------------------------
# Logging Configuration
# ---------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
LOG_DIR = os.getenv("LOG_DIR", os.path.join(BASE_DIR, "circ_toolbox", "logs"))
LOG_FILE = os.getenv("LOG_FILE", os.path.join(LOG_DIR, "application.log"))
LOG_CONFIG_PATH = os.getenv("LOG_CONFIG_PATH", os.path.join(BASE_DIR, "circ_toolbox", "backend", "config", "logging_config.yaml"))

# ---------------------------
# File Storage Directories
# ---------------------------
RESOURCE_DIR = os.getenv("RESOURCE_DIR", os.path.join(BASE_DIR, "circ_toolbox", "resources"))
SRA_DIR = os.getenv("SRA_DIR", os.path.join(BASE_DIR, "circ_toolbox", "SRA"))
USER_OUTPUT_DIR = os.getenv("USER_OUTPUT_DIR", os.path.join(BASE_DIR, "circ_toolbox", "user_outputs"))

# ---------------------------
# Alembic Configuration
# ---------------------------
ALEMBIC_INI_PATH = os.getenv("ALEMBIC_INI_PATH", os.path.join(BASE_DIR, "circ_toolbox", "backend", "database", "alembic.ini"))
ALEMBIC_MIGRATION_VERSION_PATH = os.getenv("ALEMBIC_MIGRATION_VERSION_PATH", os.path.join(BASE_DIR, "circ_toolbox", "backend", "database", "migrations", "versions"))

# ---------------------------
# Backend API Configuration
# ---------------------------
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))
API_WORKERS = int(os.getenv("API_WORKERS", 4))

# ---------------------------
# Frontend Configuration
# ---------------------------
FRONTEND_DIR = os.getenv("FRONTEND_DIR", os.path.join(BASE_DIR, "circ_toolbox", "frontend"))
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", 3000))
FRONTEND_BUILD_DIR = os.getenv("FRONTEND_BUILD_DIR", os.path.join(FRONTEND_DIR, "build"))

# ---------------------------
# CORS Configuration
# ---------------------------
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
ALLOW_METHODS = os.getenv("ALLOW_METHODS", "GET,POST,PUT,DELETE,OPTIONS").split(",")
ALLOW_HEADERS = os.getenv("ALLOW_HEADERS", "Authorization,Content-Type").split(",")

# ---------------------------
# Celery + Redis Configuration
# ---------------------------
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_CONCURRENCY = int(os.getenv("CELERY_CONCURRENCY", 1))  # Default to 1 task at a time

# ---------------------------
# Email Configuration (Optional)
# ---------------------------
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.yourmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME", "your-email@example.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "your-email-password")
EMAIL_FROM = os.getenv("EMAIL_FROM", "your-email@example.com")

# ---------------------------
# Environment Settings
# ---------------------------
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG_MODE = os.getenv("DEBUG", "0") == "1"

# ---------------------------
# Ensure necessary directories exist
# ---------------------------
# os.makedirs(DATABASE_DIR, exist_ok=True) # only on SQLite
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(RESOURCE_DIR, exist_ok=True)
os.makedirs(USER_OUTPUT_DIR, exist_ok=True)

# ---------------------------
# Print configuration for debugging purposes
# ---------------------------
if DEBUG_MODE:
    print(f"Database URL: {DATABASE_URL}")
    print(f"Logging Level: {LOG_LEVEL}")
    print(f"Running in Debug Mode: {DEBUG_MODE}")
    # print(f"Database Directory: {DATABASE_DIR}") # only on SQLite
    print(f"Log Directory: {LOG_DIR}")
    print(f"Resource Directory: {RESOURCE_DIR}")
    print(f"User Output Directory: {USER_OUTPUT_DIR}")
