# circ_toolbox/backend/api/routes/pipeline_routes.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from circ_toolbox.backend.api.schemas.pipeline_schemas import (
    PipelineRunCreate, PipelineRunResponse, PipelineRunUpdate, PipelineStatusResponse, 
    PipelineResultResponse, PipelineStepLogsResponse
)
from circ_toolbox.backend.api.dependencies import current_active_user, current_superuser
# Import the orchestrator and its dependency provider
from circ_toolbox.backend.services.orchestrators.pipeline_registration_orchestrator import (
    PipelineRegistrationOrchestrator,
    get_pipeline_registration_orchestrator,
)
from circ_toolbox.backend.services.orchestrators.pipeline_execution_orchestrator import (
    PipelineExecutionOrchestrator,
    get_pipeline_execution_orchestrator,
)
from circ_toolbox.backend.services.orchestrators import PipelineRegistrationOrchestrator, PipelineExecutionOrchestrator
from circ_toolbox.backend.database.base import get_session
from uuid import UUID
from fastapi.exceptions import RequestValidationError

from circ_toolbox.backend.utils.logging_config import get_logger, log_runtime

logger = get_logger(__name__)

router = APIRouter()


# =======================================
# Pipeline Creation and Validation
# =======================================

@router.post(
    "/pipelines/",
    response_model=PipelineRunResponse,
    responses={
        201: {"description": "Pipeline created successfully"}, 
        400: {"description": "Validation error"},
        422: {"description": "Validation error from Pydantic"},
        500: {"description": "Internal server error"}
    },
) 
@log_runtime("pipeline_routes")
async def create_pipeline(
    pipeline_data: PipelineRunCreate, 
    user=Depends(current_active_user),
    orchestrator: PipelineRegistrationOrchestrator = Depends(get_pipeline_registration_orchestrator),
    session: AsyncSession = Depends(get_session)
):
    """
    Register a new pipeline.

    Steps:
    1. Inject user_id.
    2. Validate data (FastAPI).
    3. Further validation in orchestrator.
    4. Store pipeline configuration.
    """
    try:
        response = await orchestrator.register_pipeline(pipeline_data, user, session)
        return response

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


'''

Purpose:
This endpoint allows users to create a new pipeline, which includes resource files, steps, and configurations.

Logic Flow:

Validate pipeline input (resources, steps).
Assign resource files correctly to required steps.
Register the pipeline in the database via orchestrator.
Possible Refinements:

Ensure that the user cannot create duplicate pipelines by checking for existing names under their account.
Validate resource file ownership to prevent unauthorized access.


'''

@router.get("/pipelines", response_model=list[PipelineRunResponse], tags=["Pipelines"])
async def list_pipelines(
    all_users: bool = False,
    user=Depends(current_active_user),
    orchestrator: PipelineRegistrationOrchestrator = Depends(get_pipeline_registration_orchestrator),
):
    if all_users and user.is_superuser:
        return await orchestrator.get_all_pipelines()
    return await orchestrator.get_pipelines_by_user(user.id)


'''
Purpose:
Retrieves all pipelines created by the authenticated user.

Logic Flow:

Fetch pipelines where user_id matches the logged-in user.
Return serialized pipeline data.
Superuser Enhancement:
Allow an optional query parameter to let superusers list all users' pipelines:

'''

@router.get(
    "/pipelines/{pipeline_id}",
    response_model=PipelineRunResponse,  
    responses={
        200: {"description": "Pipeline details retrieved successfully"},
        404: {"description": "Pipeline not found"},
        500: {"description": "Internal server error"}
    },
)
async def get_pipeline_details(
    pipeline_id: UUID,
    orchestrator: PipelineRegistrationOrchestrator = Depends(get_pipeline_registration_orchestrator),
    session: AsyncSession = Depends(get_session)
):
    """
    Retrieve full pipeline details, including steps, configurations, and resources.
    """
    try:
        pipeline = await orchestrator.get_pipeline_by_id(pipeline_id, session)
        return pipeline  # Return the full PipelineRunResponse schema

    except KeyError:
        raise HTTPException(status_code=404, detail="Pipeline not found.")

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

'''
Purpose:
Allows users to fetch details of a specific pipeline they own.

Logic Flow:

Check if pipeline belongs to the user.
Return pipeline details.
Possible Refinements:

Ensure superusers can access any pipeline.
Handle permission errors if users try accessing others' pipelines.
'''

@router.delete("/pipelines/{pipeline_id}", tags=["Pipelines"])
async def delete_pipeline(pipeline_id: UUID, user=Depends(current_superuser), orchestrator: PipelineRegistrationOrchestrator = Depends(get_pipeline_registration_orchestrator),
):
    """
    Allow superusers to delete a pipeline.
    """
    success = await orchestrator.delete_pipeline(pipeline_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pipeline not found or cannot be deleted")
    return {"message": "Pipeline deleted successfully"}

'''
Purpose:
Allows superusers to delete any pipeline.

Logic Flow:

Check if the pipeline exists.
Delete from database.
Log the action.
Possible Refinements:

Add a safeguard to prevent deletion of active pipelines.
'''

# =======================================
# Pipeline Execution and Monitoring
# =======================================

@router.post("/pipelines/{pipeline_id}/run", tags=["Execution"])
async def execute_pipeline(
    pipeline_id: UUID, 
    user=Depends(current_active_user), 
    orchestrator=Depends(get_pipeline_execution_orchestrator)
):
    """
    Starts the execution of a pipeline asynchronously using Celery.
    """
    logger.info(f"Pipeline Execution Started for {pipeline_id}")
    logger.info(f"Orchestrator Type: {type(orchestrator)}")  # 🛑 Log dependency type

    try:
        task_id = await orchestrator.start_pipeline_execution(pipeline_id)
        return {"message": "Pipeline execution started", "task_id": task_id}
    except ValueError as e:
        logger.error(f"ValueError: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while starting pipeline execution.")


'''
Purpose:
Triggers the pipeline execution after validation.

Logic Flow:

Check if pipeline is valid.
Initiate execution asynchronously.
Return execution status.
Enhancements:

Introduce a status check before execution to prevent re-running completed pipelines.

'''

@router.get("/pipelines/{pipeline_id}/status", response_model=PipelineStatusResponse, tags=["Monitoring"])
async def get_pipeline_status(pipeline_id: UUID, user=Depends(current_active_user), orchestrator: PipelineRegistrationOrchestrator = Depends(get_pipeline_registration_orchestrator),
):
    """
    Get the current status of the pipeline execution.
    """
    status = await orchestrator.get_pipeline_status(pipeline_id)
    if not status:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return status

'''
Purpose:
Retrieve the execution status of a given pipeline.

Logic Flow:

Check ownership or admin privilege.
Return current status (Pending, Running, Completed).

'''

@router.get("/pipelines/{pipeline_id}/results", response_model=PipelineResultResponse, tags=["Results"])
async def list_pipeline_results(pipeline_id: UUID, user=Depends(current_active_user), orchestrator: PipelineRegistrationOrchestrator = Depends(get_pipeline_registration_orchestrator),
):
    """
    List all output files for the completed pipeline.
    """
    results = await orchestrator.get_pipeline_results(pipeline_id)
    if not results:
        raise HTTPException(status_code=404, detail="Results not available")
    return results

'''
Purpose:
Provides a list of result files generated from pipeline execution.

Enhancements:

Implement pagination if many results exist.

'''

# =======================================
# Pipeline Step Execution and Logs
# =======================================

@router.post("/pipelines/{pipeline_id}/steps/{step_id}/execute", tags=["Execution"])
async def execute_pipeline_step(pipeline_id: UUID, step_id: UUID, user=Depends(current_active_user), orchestrator: PipelineRegistrationOrchestrator = Depends(get_pipeline_registration_orchestrator),
):
    """
    Execute a specific pipeline step.

    - Can be triggered separately for a partial pipeline run.
    """
    step_execution = await orchestrator.execute_pipeline_step(pipeline_id, step_id)
    if not step_execution:
        raise HTTPException(status_code=400, detail="Step execution failed")
    return {"message": f"Step {step_id} execution started successfully"}

'''
Purpose:
Allows execution of individual steps within a pipeline.

Enhancements:

Add dependency checks to ensure sequential execution.

'''

@router.get("/pipelines/{pipeline_id}/steps/{step_id}/logs", response_model=PipelineStepLogsResponse, tags=["Monitoring"])
async def get_step_logs(pipeline_id: UUID, step_id: UUID, user=Depends(current_active_user), orchestrator: PipelineRegistrationOrchestrator = Depends(get_pipeline_registration_orchestrator),
):
    """
    Retrieve logs for a specific pipeline step.
    """
    logs = await orchestrator.get_step_logs(pipeline_id, step_id)
    if not logs:
        raise HTTPException(status_code=404, detail="Logs not found for this step")
    return logs

'''
Purpose:
Provides logs for specific pipeline steps.

'''



























'''
Security Enhancements:

Ensure users cannot access other users' pipelines unless they are superusers.
Audit access permissions before allowing actions like deletion.
Logging and Auditing:

Implement logging on critical actions such as deletion, execution, and result access.
'''









''''''


'''




from circ_toolbox.backend.api.schemas.pipeline_schemas import PipelineCreate, PipelineRead

@router.post("/pipelines", response_model=PipelineRead)
async def create_pipeline(pipeline_data: PipelineCreate, user: User = Depends(current_active_user)):
    """
    Register a new pipeline and automatically assign resource files to the required steps.
    """

    # Fetch required resource types from step definitions (mocking for now)
    step_resource_requirements = {
        "Quality Check": "GENOME",
        "Alignment": "GENOME",
        "Variant Calling": "ANNOTATION"
    }

    # Assign resources to steps based on their type
    assigned_resources = {}
    for step in pipeline_data.steps:
        required_type = step_resource_requirements.get(step.name)
        assigned_resources[step.name] = next(
            (res for res in pipeline_data.resource_files if get_resource_type(res) == required_type), None
        )
    
    # Validate resource assignment
    if None in assigned_resources.values():
        raise HTTPException(status_code=400, detail="Missing required resource files for one or more steps")

    # Proceed to pipeline registration with assigned resources
    pipeline_id = uuid.uuid4()
    return {
        "id": pipeline_id,
        "name": pipeline_data.name,
        "createdBy": user.id,
        "status": "PENDING",
        "steps": [
            {
                "name": step.name,
                "parameters": step.parameters,
                "resource_file": assigned_resources[step.name]
            } for step in pipeline_data.steps
        ]
    }


@router.get("/pipelines", response_model=list[PipelineRead])
async def list_pipelines(user: User = Depends(current_active_user)):
    """List all pipelines for the logged-in user."""
    return []

@router.get("/pipelines/{pipeline_id}", response_model=PipelineRead)
async def get_pipeline_details(pipeline_id: UUID, user: User = Depends(current_active_user)):
    """Retrieve details of a specific pipeline."""
    return {"id": pipeline_id, "name": "Test Pipeline"}

@router.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: UUID, user: User = Depends(current_superuser)):
    """Superuser can delete any pipeline."""
    return {"message": "Pipeline deleted successfully"}

@router.get("/pipelines/{pipeline_id}/status", response_model=PipelineRead)
async def get_pipeline_status(pipeline_id: UUID, user: User = Depends(current_active_user)):
    """Retrieve the current status of the pipeline execution."""
    return {"id": pipeline_id, "status": "RUNNING"}


@router.get("/pipelines/{pipeline_id}/results")
async def list_pipeline_results(pipeline_id: UUID, user: User = Depends(current_active_user)):
    """List all output files for the completed pipeline."""
    return [
        {"filename": "results_summary.txt", "size": "2MB", "download_url": "/pipelines/{pipeline_id}/results/results_summary.txt"}
    ]

@router.get("/pipelines/{pipeline_id}/results/{filename}")
async def download_pipeline_result(pipeline_id: UUID, filename: str, user: User = Depends(current_active_user)):
    """Download a specific output file from the pipeline execution."""
    return {"message": f"Downloading file {filename}"}


'''