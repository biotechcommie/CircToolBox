# circ_toolbox/backend/services/orchestrators/pipeline_registration_orchestrator.py
from fastapi import Depends

from circ_toolbox.backend.database.pipeline_manager import PipelineManager, get_pipeline_manager
from circ_toolbox.backend.database.user_manager import UserManager, get_user_manager

from circ_toolbox.backend.services.orchestrators import ResourceOrchestrator
from circ_toolbox.backend.services.orchestrators.resource_orchestrator import get_resource_orchestrator

from circ_toolbox.backend.api.schemas.pipeline_schemas import PipelineRunCreate, PipelineRunResponse, PipelineRunCreateResponse
from circ_toolbox.backend.database.models import Pipeline, PipelineStep, PipelineConfig, PipelineLog, Resource
from circ_toolbox.backend.utils.file_handling import save_initial_config_to_file
from circ_toolbox.backend.utils.logging_config import get_logger, log_runtime
from circ_toolbox.backend.utils.validation import validate_file_path # this needs to be resolved | we need to build file verification.
from circ_toolbox.backend.database.base import get_session
from circ_toolbox.backend.constants.step_mapping import STEP_EXECUTION_ORDER, GLOBAL_INPUT_MAPPING
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
import json


'''
PipelineRegistrationOrchestrator

Handles user input and registration of the pipeline and all its dependencies (steps, resources, configurations).    
Ensures data is stored correctly in the database via the PipelineManager service.
Responsible for updating pipeline metadata, like changing configurations or updating notes.
'''

class PipelineRegistrationOrchestrator:
    def __init__(
        self, 
        pipeline_manager: PipelineManager = None, 
        resource_orchestrator: ResourceOrchestrator = None,
        user_manager: UserManager = None
    ):
        self.pipeline_manager = pipeline_manager or PipelineManager()
        self.resource_orchestrator = resource_orchestrator or ResourceOrchestrator()
        self.user_manager = user_manager or UserManager() # ✅ Injected UserManager
        self.logger = get_logger("pipeline_registration_orchestrator")

# -------------------------------------------
# Pipeline Creation 
# -------------------------------------------

    async def register_pipeline(
        self, 
        pipeline_data: PipelineRunCreate, 
        user, 
        session: Optional[AsyncSession] = None
    ) -> PipelineRunResponse:
        """
        Orchestrates the pipeline registration process, ensuring validation and data persistence.

        Args:
            pipeline_data (PipelineRunCreate): Pipeline creation data.
            user: Authenticated user performing the action.
            session (Optional[AsyncSession]): Database session, passed explicitly.

        Returns:
            PipelineRunResponse: Registered pipeline details.
        """
        self.logger.info(f"Starting pipeline registration for user: {user.email}")

        enriched_pipeline_data = pipeline_data.model_copy(update={"user_id": user.id})

        try:
            # Validate pipeline configuration first
            await self._validate_pipeline_data(enriched_pipeline_data, session)
            
            # Open database session if not provided
            close_session = False
            if session is None:
                session = await anext(get_session())
                close_session = True

            async with session.begin():
                # Create pipeline entity
                pipeline = Pipeline(
                    pipeline_name=enriched_pipeline_data.pipeline_name,
                    user_id=user.id,
                    status="pending",
                    notes=enriched_pipeline_data.notes
                )
                
                # Register pipeline
                pipeline = await self.pipeline_manager.register_pipeline(pipeline, session)
                if not pipeline.id:
                    raise RuntimeError("Pipeline registration failed - no ID assigned")

                # Process pipeline steps
                first_step_index = self._prepare_pipeline_steps(enriched_pipeline_data)
                await self._register_pipeline_components(enriched_pipeline_data, pipeline, first_step_index, session)

                return PipelineRunCreateResponse(
                    pipeline_id=pipeline.id,
                    message="Pipeline registered successfully"
                )

        except ValueError as ve:
            self.logger.error(f"Validation error: {ve}")
            raise
        except Exception as e:
            self.logger.error(f"Registration failed: {str(e)}")
            raise RuntimeError(f"Pipeline registration failed: {str(e)}")
        finally:
            if close_session and session:
                await session.close()

    async def _validate_pipeline_data(self, pipeline_data: PipelineRunCreate, session: AsyncSession):
        """
        Comprehensive pipeline validation
        """
        # Validate step continuity
        step_names = [s.step_name for s in pipeline_data.steps]
        if not self._is_contiguous_subset(step_names):
            raise ValueError("Selected steps must form a contiguous sequence from the execution order")

        # Validate resources exist
        missing_resources = await self._validate_resources_exist(pipeline_data.resource_files, session)
        if missing_resources:
            raise ValueError(f"Missing resources: {', '.join(missing_resources)}")

    def _is_contiguous_subset(self, step_names: List[str]) -> bool:
        """
        Validates steps form a continuous block from STEP_EXECUTION_ORDER
        """
        try:
            indices = [STEP_EXECUTION_ORDER.index(name) for name in step_names]
        except ValueError as e:
            raise ValueError(f"Invalid step in pipeline: {str(e)}")

        if not indices:
            return False
            
        expected = list(range(min(indices), max(indices)+1))
        return sorted(indices) == expected

    async def _validate_resources_exist(self, resource_ids: List[UUID], session: AsyncSession) -> List[UUID]:
        """
        Returns list of missing resource IDs as UUID objects
        """
        if not resource_ids:
            return []
        
        # Get existing IDs through proper manager channel
        existing_ids = await self.resource_orchestrator.get_existing_resource_ids(resource_ids, session)
        
        return [rid for rid in resource_ids if rid not in existing_ids]

    def _get_first_step_index(self, steps: List[PipelineStep]) -> int:
        """
        Returns index of first step in execution sequence
        """
        indices = [STEP_EXECUTION_ORDER.index(s.step_name) for s in steps]
        return indices.index(min(indices))

    def _prepare_pipeline_steps(self, pipeline_data: PipelineRunCreate) -> int:
        """
        Ensures input files are only provided for the first valid step in sequence
        """
        # Find first step in the contiguous sequence
        first_step_index = self._get_first_step_index(pipeline_data.steps)
        
        # Clear input files from non-initial steps
        for idx, step in enumerate(pipeline_data.steps):
            if idx != first_step_index and step.input_files:
                self.logger.warning(f"Clearing input files from non-initial step: {step.step_name}")
                step.input_files = []

        # Validate initial step requirements
        first_step = pipeline_data.steps[first_step_index]
        if first_step.requires_input_file and not first_step.input_files:
            raise ValueError(f"Initial step '{first_step.step_name}' requires input files")

        return first_step_index

    async def _register_pipeline_components(
        self,
        pipeline_data: PipelineRunCreate,
        pipeline: Pipeline,
        first_step_index: int,
        session: AsyncSession
    ):
        """
        Registers all pipeline components with proper error handling
        """
        # Save initial config
        config_path = self._save_initial_config_to_file(
            pipeline_data, 
            pipeline.id,
            pipeline.user_id
        )
        config = PipelineConfig(
            pipeline_id=pipeline.id,
            config_type="initial",
            config_data=pipeline_data.model_dump(),
            config_file_path=config_path
        )
        if not await self.pipeline_manager.save_pipeline_config(config, session):
            raise RuntimeError("Failed to save pipeline configuration")

        # Register steps
        for idx, step_data in enumerate(pipeline_data.steps):
            input_mapping = step_data.input_mapping if hasattr(step_data, "input_mapping") else GLOBAL_INPUT_MAPPING.get(step_data.step_name, {})
            step = PipelineStep(
                pipeline_id=pipeline.id,
                step_name=step_data.step_name,
                parameters=step_data.parameters,
                requires_input_file=step_data.requires_input_file,
                input_files=step_data.input_files if idx == first_step_index else [],
                status="pending",
                input_mapping=input_mapping  # store the mapping
            )
            if not await self.pipeline_manager.register_pipeline_step(step, session):
                raise RuntimeError(f"Failed to register step: {step_data.step_name}")

        # Associate resources
        if pipeline_data.resource_files:
            success = await self.pipeline_manager.add_resources_to_pipeline(
                pipeline.id,
                pipeline_data.resource_files,
                session
            )
            if not success:
                raise RuntimeError("Failed to associate resources with pipeline")

        # Log registration
        log_entry = PipelineLog(
            pipeline_id=pipeline.id,
            logs=f"Pipeline {pipeline.pipeline_name} registered successfully"
        )
        if not await self.pipeline_manager.save_pipeline_log(log_entry, session):
            self.logger.warning("Failed to save pipeline log entry")

    def _save_initial_config_to_file(self, pipeline_data: PipelineRunCreate, pipeline_id: UUID, user_id: UUID) -> str:
        """
        Saves the initial pipeline configuration to a JSON file.

        Args:
            pipeline_data (PipelineRunCreate): The pipeline input data.
            pipeline_id (UUID): The pipeline's unique identifier.
            user_id (UUID): The user's unique identifier.

        Returns:
            str: Path to the saved file.
        """
        try:
            pipeline_data_dict = pipeline_data.model_dump()
            config_file_path = save_initial_config_to_file(
                pipeline_data_dict,
                user_id,
                pipeline_id
            )
            self.logger.info(f"Initial pipeline configuration saved at {config_file_path}")
            return config_file_path
        except Exception as e:
            self.logger.error(f"Failed to save initial config file: {e}")
            raise RuntimeError(f"Could not save config file for pipeline {pipeline_id}")


# -------------------------------------------
# Pipeline 
# -------------------------------------------


    async def get_all_pipelines(self, session: AsyncSession) -> List[PipelineRunResponse]:
        """
        Retrieve all pipelines.
        """
        pipelines = await self.pipeline_manager.get_all_pipelines(session)
        return [PipelineRunResponse.from_orm(p) for p in pipelines]

    async def get_pipelines_by_user(self, user_id: UUID, session: AsyncSession) -> List[PipelineRunResponse]:
        """
        Retrieve all pipelines by user.
        """
        pipelines = await self.pipeline_manager.get_pipeline_by_user_id(user_id, session)
        return [PipelineRunResponse.from_orm(p) for p in pipelines]

    async def get_pipeline_by_id(self, pipeline_id: UUID, session: AsyncSession) -> PipelineRunResponse:
        """
        Retrieve a pipeline by ID.
        """
        pipeline = await self.pipeline_manager.get_pipeline(pipeline_id, session)
        return PipelineRunResponse.from_orm(pipeline)

    async def delete_pipeline(self, pipeline_id: UUID, session: AsyncSession) -> dict:
        """
        Delete a pipeline by ID.
        """
        await self.pipeline_manager.delete_pipeline(pipeline_id, session)
        return {"message": f"Pipeline '{pipeline_id}' deleted successfully."}

    async def get_pipeline_status(self, pipeline_id: UUID, session: AsyncSession) -> dict:
        """
        Retrieve the current status of a pipeline.
        """
        pipeline = await self.pipeline_manager.get_pipeline(pipeline_id, session)
        if not pipeline:
            raise ValueError(f"Pipeline with ID {pipeline_id} not found.")
        
        return {"pipeline_id": str(pipeline_id), "status": pipeline.status, "start_time": pipeline.start_time, "end_time": pipeline.end_time}

    async def get_pipeline_results(self, pipeline_id: UUID, session: AsyncSession) -> dict:
        """
        Retrieve pipeline results (output files).
        """
        resources = await self.pipeline_manager.get_pipeline_resources(pipeline_id, session)
        output_files = [
            {"filename": res.file_name, "download_url": res.file_path}
            for res in resources
        ]
        return {"pipeline_id": str(pipeline_id), "output_files": output_files}

    async def get_step_logs(self, pipeline_id: UUID, step_id: UUID, session: AsyncSession) -> dict:
        """
        Retrieve execution logs for a specific step.
        """
        logs = await self.pipeline_manager.get_pipeline_logs(pipeline_id, session)
        step_logs = [log.logs for log in logs if log.step_id == step_id]
        
        if not step_logs:
            raise ValueError(f"No logs found for step '{step_id}' in pipeline '{pipeline_id}'")
        
        return {"step_id": str(step_id), "logs": step_logs}



# ------------------------------------------------------------------------------
# Dependency Injection for ResourceOrchestrator
# ------------------------------------------------------------------------------
async def get_pipeline_registration_orchestrator(
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
    resource_orchestrator: ResourceOrchestrator = Depends(get_resource_orchestrator),
    user_manager: UserManager = Depends(get_user_manager),  # ✅ Inject UserManager
):
    """
    Provides an instance of PipelineRegistrationOrchestrator for dependency injection.

    Args:
        pipeline_manager: The PipelineManager dependency.
        user_manager: The UserManager dependency.

    Yields:
        PipelineRegistrationOrchestrator: An instance of PipelineRegistrationOrchestrator.
    """
    yield PipelineRegistrationOrchestrator(pipeline_manager, resource_orchestrator, user_manager)


'''

from fastapi import APIRouter, Depends
from circ_toolbox.backend.api.schemas.pipeline_schemas import PipelineRunCreate
from circ_toolbox.backend.services.orchestrators.pipeline_registration_orchestrator import PipelineRegistrationOrchestrator

router = APIRouter()

@router.post("/pipelines/register")
async def register_pipeline(
    pipeline_data: PipelineRunCreate,
    orchestrator: PipelineRegistrationOrchestrator = Depends()
):
    return await orchestrator.register_pipeline(pipeline_data, user_id="user-123")

@router.post("/pipelines/{pipeline_id}/execute")
async def execute_pipeline(pipeline_id: UUID, orchestrator: PipelineRegistrationOrchestrator = Depends()):
    return await orchestrator.start_pipeline(pipeline_id)

@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: UUID, orchestrator: PipelineRegistrationOrchestrator = Depends()):
    return await orchestrator.get_pipeline_by_id(pipeline_id)
'''



'''

Next Steps
Database Implementation:

Define SQLAlchemy models for Pipeline and PipelineStep.
Implement database transactions within the orchestrator.
Validation Enhancements:

Ensure validation logic for resource file types and input constraints.
Pipeline Execution Handling:

Implement Celery or background task management to handle long-running executions asynchronously.
'''