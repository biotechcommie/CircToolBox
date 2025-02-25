# circ_toolbox_project/circ_toolbox/main.py
from fastapi import FastAPI, Depends, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from circ_toolbox.celery_app import celery_app
from circ_toolbox.config import API_HOST, API_PORT, ALLOW_ORIGINS, ALLOW_METHODS, ALLOW_HEADERS
from circ_toolbox.backend.api.routes.resource_routes import router as resource_router
from circ_toolbox.backend.api.routes.user_routes import router as user_router
from circ_toolbox.backend.api.routes.pipeline_routes import router as pipeline_router
from circ_toolbox.backend.utils.logging_config import setup_logging, get_logger
from circ_toolbox.backend.scripts.create_admin_user import create_admin_user
from circ_toolbox.backend.database.base import Base
from circ_toolbox.backend.database.models import *  # Ensure models are loaded into the metadata registry
import time

from circ_toolbox.backend.exception_handlers import add_exception_handlers



# Initialize logging before creating the app
setup_logging()
logger = get_logger("app")

# Lifespan event handlers
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Ensuring database and admin setup...")

    try:
        logger.info("Starting CircToolbox API...")
        await create_admin_user()
        logger.info("Database and admin user setup completed.")
        
        # Check Celery connectivity
        result = celery_app.send_task("circ_toolbox.tasks.example_task", args=["ping"])
        logger.info(f"Test Celery task submitted with ID: {result.id}")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

    yield  # Application startup
    logger.info("CircToolbox API shutting down.")

# Create the FastAPI app
app = FastAPI(
    title="CircToolbox API",
    description="API for circRNA resource management",
    version="1.0.0",
    lifespan=lifespan
)

# Add exception handlers
add_exception_handlers(app)


# Add CORS middleware (for cross-origin requests from frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,  # Loaded from config.py
    allow_credentials=True,
    allow_methods=ALLOW_METHODS,
    allow_headers=ALLOW_HEADERS,
)

# Middleware to log requests and responses
@app.middleware("http")
async def log_requests(request: Request, call_next):
    
    start_time = time.time()
    logger.info(f"Incoming Request: {request.method} {request.url}")
    logger.info(f"Headers: {request.headers}")
    # logger.info(f"Body: {await request.body()}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"Response {response.status_code} for {request.method} {request.url} in {process_time:.4f} seconds")
        return response
    except Exception as e:
        logger.error(f"Error processing request {request.method} {request.url}: {str(e)}")
        raise

# Include routers
app.include_router(resource_router, prefix="/api/v1", tags=["Resources"])
app.include_router(user_router, prefix="/api/v1", tags=["Users"])
app.include_router(pipeline_router, prefix="/api/v1", tags=["Pipelines"])

# Default root endpoint for testing logging
@app.get("/")
async def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to CircToolbox API"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Launching the API using Uvicorn.")
    logger.info(f"Registered models:, {Base.registry._class_registry.items()}")
    logger.info(f"Registered models:, {Base}")
    # Print registered classes to debug duplicates
    logger.info(f"Registered models: {list(Base.registry._class_registry.items())}")

    logger.info("Registered models:")
    for key, value in Base.registry._class_registry.items():
        logger.info(f"{key}: {value}")

    uvicorn.run(app, host=API_HOST, port=API_PORT)











'''

import copy

class ImprovedLoggingMiddleware:
    async def __call__(self, request: Request, call_next):
        start_time = time.time()
        request_body = await request.body()
        # Log request without sensitive info
        logger.info(f"Request: {request.method} {request.url.path}")
        logger.info(f"Headers: {dict(request.headers)}")
        
        # Clone request to include cached body
        request_new = copy.copy(request)
        request_new.body = lambda: copy.deepcopy(request_body)
        
        response = await call_next(request_new)
        process_time = time.time() - start_time
        logger.info(f"Response {response.status_code} in {process_time:.4f}s")
        return response



@app.middleware("http")
async def exception_catcher(request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Critical error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimiter)
app.add_middleware(CORSMiddleware)
app.add_middleware(logging_middleware)
app.add_middleware(GZipMiddleware)



# Use background tasks for file processing
from fastapi.background import BackgroundTasks

@app.post("/upload")
async def upload_file(
    data: UploadForm = Depends(),
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks
):
    # Validate form and file
    background_tasks.add_task(move_and_save_file, file, data.resource_type)
    return {"message": "File processing started in the background"}



@app.middleware("http")
async def healthcheck_monitor(request, call_next):
    # Implement health checks here (e.g., ping database)
    return await call_next(request)

'''