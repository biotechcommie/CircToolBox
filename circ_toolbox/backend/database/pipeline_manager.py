# circ_toolbox_project/circ_toolbox/backend/database/pipeline_manager.py
from fastapi import Depends

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from circ_toolbox.backend.database.models import Pipeline, PipelineStep, PipelineConfig, PipelineLog, Resource
from circ_toolbox.backend.utils.logging_config import get_logger, log_runtime
from circ_toolbox.backend.database.base import get_session
from circ_toolbox.backend.constants.step_mapping import STEP_EXECUTION_ORDER
from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime

class PipelineManager:
    """
    Manages pipeline operations.
    """

    def __init__(self):
        self.logger = get_logger("pipeline_manager")

    # -------------------------------------------
    # PIPELINE OPERATIONS
    # -------------------------------------------
    
    @log_runtime("pipeline_manager")
    async def register_pipeline(self, pipeline: Pipeline, session: Optional[AsyncSession] = None):
        """
        Register a new pipeline run in the database.
        """
        try:
            existing_pipeline = await session.get(Pipeline, pipeline.id)
            if existing_pipeline:
                self.logger.warning(f"Pipeline '{pipeline.pipeline_name}' already exists.")
                raise ValueError(f"Pipeline '{pipeline.pipeline_name}' already exists.")

            session.add(pipeline)
            await session.flush()  # Ensures ID is assigned
            
            self.logger.info(f"Pipeline '{pipeline.pipeline_name}' registered successfully.")
            return pipeline

        except Exception as e:
            self.logger.error(f"Failed to register pipeline '{pipeline.pipeline_name}': {e}")
            raise RuntimeError(f"Failed to register pipeline: {e}")

    @log_runtime("pipeline_manager")
    async def add_resources_to_pipeline(self, pipeline_id: UUID, resource_ids: Optional[List[UUID]], session: Optional[AsyncSession] = None):
        """
        Associate resources with a pipeline.

        Args:
            pipeline_id (UUID): The ID of the pipeline.
            resource_ids (Optional[List[UUID]]): List of resource UUIDs.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            pipeline = await session.get(Pipeline, pipeline_id)
            if not pipeline:
                raise KeyError(f"Pipeline '{pipeline_id}' not found.")

            if not resource_ids:
                self.logger.info(f"No resources provided to add to pipeline '{pipeline_id}'.")
                return True  # Nothing to add, but consider as success

            # Fetch resources
            resources = await session.execute(select(Resource).where(Resource.id.in_(resource_ids)))
            existing_resources = resources.scalars().all()

            # Validate if all resources were found
            if len(existing_resources) != len(resource_ids):
                missing_ids = set(resource_ids) - {res.id for res in existing_resources}
                raise ValueError(f"Some resources were not found: {missing_ids}")

            # Associate resources with the pipeline
            pipeline.resources.extend(existing_resources)

            self.logger.info(f"Resources added to pipeline '{pipeline_id}' successfully.")
            return True

        except KeyError as e:
            self.logger.warning(str(e))
            return False

        except ValueError as ve:
            self.logger.error(f"Resource validation failed: {ve}")
            raise

        except Exception as e:
            self.logger.error(f"Failed to add resources to pipeline: {e}")
            raise RuntimeError(f"Failed to add resources to pipeline: {e}")

    @log_runtime("pipeline_manager")
    async def update_pipeline(self, pipeline_id: UUID, update_data: dict, session: Optional[AsyncSession] = None):
        """
        Update pipeline details (e.g., status, end_time).
        """
        close_session = False
        if session is None:
            session = await anext(get_session())
            close_session = True

        try:
            async with session.begin():
                stmt = update(Pipeline).where(Pipeline.id == pipeline_id).values(**update_data)
                result = await session.execute(stmt)

                if result.rowcount == 0:
                    self.logger.warning(f"Pipeline '{pipeline_id}' not found.")
                    raise KeyError(f"Pipeline '{pipeline_id}' not found.")

            self.logger.info(f"Pipeline '{pipeline_id}' updated successfully.")
            return {"message": f"Pipeline '{pipeline_id}' updated successfully."}

        except Exception as e:
            self.logger.error(f"Failed to update pipeline '{pipeline_id}': {e}")
            raise RuntimeError(f"Failed to update pipeline: {e}")

        finally:
            if close_session:
                await session.close()

    @log_runtime("pipeline_manager")
    async def delete_pipeline(self, pipeline_id: UUID, session: Optional[AsyncSession] = None):
        """
        Delete a pipeline by its ID.
        """
        close_session = False
        if session is None:
            session = await anext(get_session())
            close_session = True

        try:
            async with session.begin():
                stmt = delete(Pipeline).where(Pipeline.id == pipeline_id)
                result = await session.execute(stmt)

                if result.rowcount == 0:
                    self.logger.warning(f"Pipeline '{pipeline_id}' not found.")
                    raise KeyError(f"Pipeline '{pipeline_id}' not found.")

            self.logger.info(f"Pipeline '{pipeline_id}' deleted successfully.")
            return {"message": f"Pipeline '{pipeline_id}' deleted successfully."}

        except Exception as e:
            self.logger.error(f"Failed to delete pipeline '{pipeline_id}': {e}")
            raise RuntimeError(f"Failed to delete pipeline: {e}")

        finally:
            if close_session:
                await session.close()

    @log_runtime("pipeline_manager")
    async def get_pipeline(self, pipeline_id: UUID, session: Optional[AsyncSession] = None) -> Optional[Pipeline]:
        """
        Retrieve a pipeline by its ID.
        """
        close_session = False
        if session is None:
            session = await anext(get_session())
            close_session = True

        try:
            async with session.begin():
                stmt = select(Pipeline).options(
                    joinedload(Pipeline.steps),
                    joinedload(Pipeline.configurations),
                    joinedload(Pipeline.resources)
                ).where(Pipeline.id == pipeline_id)
                
                result = await session.execute(stmt)
                pipeline = result.scalar_one_or_none()

                if not pipeline:
                    self.logger.warning(f"Pipeline '{pipeline_id}' not found.")
                    raise KeyError(f"Pipeline '{pipeline_id}' not found.")

                return pipeline

        except Exception as e:
            self.logger.error(f"Failed to fetch pipeline '{pipeline_id}': {e}")
            raise RuntimeError(f"Failed to fetch pipeline: {e}")

        finally:
            if close_session:
                await session.close()

    @log_runtime("pipeline_manager")
    async def get_pipeline_minimal(self, pipeline_id: UUID, session: Optional[AsyncSession] = None) -> Optional[Dict]:
        """
        Retrieve minimal information for a pipeline by its ID asynchronously.
        
        This method returns only the essential fields (id and status) to reduce data overhead.
        
        Args:
            pipeline_id (UUID): The pipeline's unique identifier.
            session (Optional[AsyncSession]): The async database session.
        
        Returns:
            Optional[Dict]: A dictionary with keys "id" and "status", or None if not found.
        """
        close_session = False
        if session is None:
            session = await anext(get_session())
            close_session = True

        try:
            async with session.begin():
                stmt = select(Pipeline.id, Pipeline.status).where(Pipeline.id == pipeline_id)
                result = await session.execute(stmt)
                row = result.first()
                if not row:
                    self.logger.warning(f"Pipeline '{pipeline_id}' not found (minimal query).")
                    return None
                # Return a minimal dictionary
                return {"id": str(row[0]), "status": row[1]}
        except Exception as e:
            self.logger.error(f"Failed to fetch minimal pipeline '{pipeline_id}': {e}")
            raise RuntimeError(f"Failed to fetch pipeline: {e}")
        finally:
            if close_session:
                await session.close()

    @log_runtime("pipeline_manager")
    async def update_pipeline_status(self, pipeline_id: UUID, status: str, session: Optional[AsyncSession] = None):
        """
        Update the status of a pipeline (with valid state transitions).

        Args:
            pipeline_id (UUID): The pipeline ID.
            status (str): New status (pending, running, completed, failed).
        """
        valid_transitions = {
            "pending": ["running", "failed"],
            "running": ["completed", "failed"],
            "completed": [],
            "failed": [],
        }

        close_session = False
        if session is None:
            session = await anext(get_session())
            close_session = True

        try:
            pipeline = await session.get(Pipeline, pipeline_id)
            if not pipeline:
                raise KeyError(f"Pipeline '{pipeline_id}' not found.")

            if status not in valid_transitions.get(pipeline.status, []):
                raise ValueError(f"Invalid status transition from '{pipeline.status}' to '{status}'.")

            async with session.begin():
                pipeline.status = status
                if status in ["completed", "failed"]:
                    pipeline.end_time = datetime.utcnow()

            self.logger.info(f"Pipeline '{pipeline_id}' updated to status '{status}'.")
            return {"message": f"Pipeline '{pipeline_id}' updated successfully."}

        except Exception as e:
            self.logger.error(f"Failed to update pipeline status: {e}")
            raise RuntimeError(f"Failed to update pipeline status: {e}")

        finally:
            if close_session:
                await session.close()

    @log_runtime("pipeline_manager")
    async def get_pipeline_by_user_id(self, user_id: UUID, session: Optional[AsyncSession] = None) -> List[Pipeline]:
        """
        Retrieve all pipelines associated with a specific user.

        Args:
            user_id (UUID): The user ID to filter pipelines.
            session (Optional[AsyncSession]): Database session.

        Returns:
            List[Pipeline]: Pipelines owned by the given user.
        """
        close_session = False
        if session is None:
            session = await anext(get_session())
            close_session = True

        try:
            async with session.begin():
                stmt = select(Pipeline).where(Pipeline.user_id == user_id).order_by(Pipeline.created_at.desc())
                result = await session.execute(stmt)
                pipelines = result.scalars().all()

            self.logger.info(f"Retrieved {len(pipelines)} pipelines for user '{user_id}'.")
            return pipelines

        except Exception as e:
            self.logger.error(f"Failed to fetch pipelines for user '{user_id}': {e}")
            raise RuntimeError(f"Failed to fetch pipelines: {e}")

        finally:
            if close_session:
                await session.close()

    @log_runtime("pipeline_manager")
    async def get_pipeline_resources(self, pipeline_id: UUID, session: Optional[AsyncSession] = None) -> List:
        """
        Retrieve resources associated with a specific pipeline.

        Args:
            pipeline_id (UUID): The ID of the pipeline.
            session (Optional[AsyncSession]): The database session.

        Returns:
            List: Resources linked to the pipeline.
        """
        close_session = False
        if session is None:
            session = await anext(get_session())
            close_session = True

        try:
            async with session.begin():
                pipeline = await session.get(Pipeline, pipeline_id)
                if not pipeline:
                    raise KeyError(f"Pipeline '{pipeline_id}' not found.")

                resources = pipeline.resources

            self.logger.info(f"Retrieved {len(resources)} resources for pipeline '{pipeline_id}'.")
            return resources

        except Exception as e:
            self.logger.error(f"Failed to fetch resources for pipeline '{pipeline_id}': {e}")
            raise RuntimeError(f"Failed to fetch resources: {e}")

        finally:
            if close_session:
                await session.close()

    @log_runtime("pipeline_manager")
    async def get_pipeline_steps(self, pipeline_id: UUID, session: Optional[AsyncSession] = None) -> List[PipelineStep]:
        """
        Retrieve all steps related to a specific pipeline.

        Args:
            pipeline_id (UUID): The pipeline ID.
            session (Optional[AsyncSession]): The database session.

        Returns:
            List[PipelineStep]: A list of pipeline steps.
        """
        close_session = False
        if session is None:
            session = await anext(get_session())
            close_session = True

        try:
            async with session.begin():
                stmt = (
                    select(PipelineStep)
                    .where(PipelineStep.pipeline_id == pipeline_id)
                    .order_by(PipelineStep.order)
                )
                result = await session.execute(stmt)
                steps = result.scalars().all()

            self.logger.info(f"Retrieved {len(steps)} steps for pipeline '{pipeline_id}'.")
            return steps
        
        except SQLAlchemyError as sae:
            self.logger.error(f"Database error fetching steps: {str(sae)}")
            raise RuntimeError("Failed to retrieve pipeline steps due to database error")
            
        except Exception as e:
            self.logger.error(f"Unexpected error fetching steps: {str(e)}")
            raise RuntimeError("Failed to retrieve pipeline steps")

        finally:
            if close_session:
                await session.close()

    @log_runtime("pipeline_manager")
    async def delete_pipeline_cascade(self, pipeline_id: UUID, session: Optional[AsyncSession] = None):
        """
        Delete a pipeline and all its related records (steps, logs, configurations).

        Args:
            pipeline_id (UUID): The pipeline ID.
            session (Optional[AsyncSession]): The database session.

        Raises:
            RuntimeError: If the operation fails.
        """
        close_session = False
        if session is None:
            session = await anext(get_session())
            close_session = True

        try:
            async with session.begin():
                # Delete related logs
                await session.execute(delete(PipelineLog).where(PipelineLog.pipeline_id == pipeline_id))
                
                # Delete related configurations
                await session.execute(delete(PipelineConfig).where(PipelineConfig.pipeline_id == pipeline_id))
                
                # Delete related steps
                await session.execute(delete(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id))
                
                # Finally delete the pipeline
                result = await session.execute(delete(Pipeline).where(Pipeline.id == pipeline_id))
                if result.rowcount == 0:
                    raise KeyError(f"Pipeline '{pipeline_id}' not found.")

            self.logger.info(f"Pipeline '{pipeline_id}' and all its related records deleted successfully.")
            return {"message": f"Pipeline '{pipeline_id}' deleted successfully."}

        except Exception as e:
            self.logger.error(f"Failed to delete pipeline '{pipeline_id}': {e}")
            raise RuntimeError(f"Failed to delete pipeline: {e}")

        finally:
            if close_session:
                await session.close()

    # -------------------------------------------
    # PIPELINE STEP MANAGEMENT
    # -------------------------------------------
    
    @log_runtime("pipeline_manager")
    async def register_pipeline_step(self, step: PipelineStep, session: Optional[AsyncSession] = None):
        """
        Register a pipeline step and enforce execution order
        
        Changes:
        - Added order enforcement after registration
        - Added automatic order assignment
        """
        try:
            # Validate step exists in execution order
            if step.step_name not in STEP_EXECUTION_ORDER:
                raise ValueError(f"Invalid step {step.step_name}")

            # Set order from predefined sequence
            step.order = STEP_EXECUTION_ORDER.index(step.step_name)
            
            # Existing validation
            pipeline = await session.get(Pipeline, step.pipeline_id)
            if not pipeline:
                raise KeyError(f"Pipeline '{step.pipeline_id}' not found.")

            # Check for existing step with same name
            existing_step = await session.execute(
                select(PipelineStep).where(
                    PipelineStep.pipeline_id == step.pipeline_id,
                    PipelineStep.step_name == step.step_name
                )
            )
            if existing_step.scalar_one_or_none():
                raise ValueError(f"Step '{step.step_name}' already exists in pipeline '{step.pipeline_id}'.")

            session.add(step)
            await session.flush()  # Ensure step is persisted before ordering
           
            self.logger.info(f"Step '{step.step_name}' registered and ordered successfully")
            return True

        except ValueError as ve:
            self.logger.error(f"Step validation failed: {ve}")
            raise
        except Exception as e:
            self.logger.error(f"Registration failed: {e}")
            raise RuntimeError("Step registration error") from e
        
    @log_runtime("pipeline_manager")
    async def complete_pipeline_step(self, step_id: UUID, status: str, result_file_path: Optional[str], session: Optional[AsyncSession] = None):
        """
        Mark a pipeline step as completed or failed.
        """
        valid_transitions = {
            "pending": ["running", "failed"],
            "running": ["completed", "failed"],
            "completed": [],
            "failed": [],
        }

        close_session = False
        if session is None:
            session = await anext(get_session())
            close_session = True

        try:
            async with session.begin():
                step = await session.get(PipelineStep, step_id)
                if not step:
                    raise KeyError(f"Step '{step_id}' not found.")

                if status not in valid_transitions.get(step.status, []):
                    raise ValueError(f"Invalid status transition from '{step.status}' to '{status}'.")

                step.status = status
                step.end_time = datetime.utcnow()
                step.result_file_path = result_file_path

            self.logger.info(f"Step '{step_id}' completed successfully with status '{status}'.")
            return {"message": f"Step '{step_id}' completed successfully."}


        except Exception as e:
            self.logger.error(f"Failed to complete step '{step_id}': {e}")
            raise RuntimeError(f"Failed to complete step: {e}")

        finally:
            if close_session:
                await session.close()

    @log_runtime("pipeline_manager")
    async def get_pending_steps(self, pipeline_id: UUID, session: Optional[AsyncSession] = None) -> List[PipelineStep]:
        """
        Get all pending steps of a pipeline.
        """
        close_session = False
        if session is None:
            session = await anext(get_session())
            close_session = True

        try:
            async with session.begin():
                stmt = select(PipelineStep).where(
                    PipelineStep.pipeline_id == pipeline_id,
                    PipelineStep.status == "pending"
                )
                result = await session.execute(stmt)
                pending_steps = result.scalars().all()

            self.logger.info(f"Retrieved {len(pending_steps)} pending steps for pipeline '{pipeline_id}'.")
            return pending_steps

        except Exception as e:
            self.logger.error(f"Failed to retrieve pending steps: {e}")
            raise RuntimeError("Failed to retrieve pending steps.")

        finally:
            if close_session:
                await session.close()

    # -------------------------------------------
    # PIPELINE CONFIGURATION MANAGEMENT
    # -------------------------------------------

    @log_runtime("pipeline_manager")
    async def save_pipeline_config(self, config: PipelineConfig, session: Optional[AsyncSession] = None):
        """
        Save pipeline configuration details.
        """

        try:
            session.add(config)
            await session.flush()
            self.logger.info(f"Configuration saved for pipeline '{config.pipeline_id}'.")
            return True  # Indicate success

        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            raise RuntimeError(f"Failed to save config: {e}")


    # -------------------------------------------
    # LOGGING
    # -------------------------------------------

    @log_runtime("pipeline_manager")
    async def save_pipeline_log(self, log: PipelineLog, session: Optional[AsyncSession] = None):
        """
        Save logs for pipeline steps.
        """

        try:
            session.add(log)

            self.logger.info(f"Log saved for step '{log.step_id}'.")

            return True
        except Exception as e:
            self.logger.error(f"Failed to save log: {e}")
            raise RuntimeError(f"Failed to save log: {e}")

    @log_runtime("pipeline_manager")
    async def get_pipeline_logs(self, pipeline_id: UUID, limit: int = 10, offset: int = 0, session: Optional[AsyncSession] = None):
        """
        Retrieve logs associated with a pipeline.

        Args:
            pipeline_id (UUID): The pipeline ID.

        Returns:
            List[PipelineLog]: Logs associated with the pipeline.
        """
        close_session = False
        if session is None:
            session = await anext(get_session())
            close_session = True

        try:
            async with session.begin():
                stmt = select(PipelineLog).where(
                    PipelineLog.pipeline_id == pipeline_id
                ).order_by(PipelineLog.created_at.desc()).limit(limit).offset(offset)

                result = await session.execute(stmt)
                logs = result.scalars().all()

            self.logger.info(f"Retrieved {len(logs)} logs for pipeline '{pipeline_id}'.")
            return logs

        except Exception as e:
            self.logger.error(f"Failed to retrieve logs for pipeline '{pipeline_id}': {e}")
            raise RuntimeError(f"Failed to retrieve logs: {e}")

        finally:
            if close_session:
                await session.close()

# ------------------------------------------------------------------------------
# Dependency Injection for ResourceManager
# ------------------------------------------------------------------------------
async def get_pipeline_manager(
    session: AsyncSession = Depends(get_session)
):
    """
    Provides an instance of PipelineManager for dependency injection.

    Args:
        session (AsyncSession): The database session dependency.

    Yields:
        PipelineManager: The resource management service.
    """
    # Here, we simply yield a new instance of PipelineManager.
    yield PipelineManager()


# ------------------------------------------------------------------------------
# SYNCHRONOUS METHODS FOR CELERY WORKERS
# ------------------------------------------------------------------------------
# These methods mirror the asynchronous operations above but use a synchronous session.
# They are intended to be used in contexts (e.g., Celery tasks) where an async event loop is unavailable.
#
# Note: It is assumed that you have implemented or imported a synchronous session maker,
# for example, a function get_sync_session() that returns a SQLAlchemy Session object.
# You might implement it in a module (e.g., circ_toolbox.backend.database.base_sync).
# For demonstration purposes, we assume it is imported as follows:

from circ_toolbox.backend.database.base_sync import get_sync_session  # This should return a sync Session
from sqlalchemy.orm import Session

class PipelineManagerSync:
    """
    Manages pipeline operations synchronously.
    This class provides synchronous counterparts to the asynchronous methods
    in PipelineManager for use in Celery workers or other synchronous contexts.
    """

    def __init__(self):
        self.logger = get_logger("pipeline_manager_sync")

    # -------------------------------------------
    # PIPELINE OPERATIONS (SYNC)
    # -------------------------------------------
    
    @log_runtime("pipeline_manager_sync")
    def register_pipeline_sync(self, pipeline: Pipeline, session: Optional[Session] = None) -> Pipeline:
        """
        Synchronously register a new pipeline run in the database.
        If no session is provided, a new one is created and closed upon completion.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            existing_pipeline = session.get(Pipeline, pipeline.id)
            if existing_pipeline:
                self.logger.warning(f"Pipeline '{pipeline.pipeline_name}' already exists.")
                raise ValueError(f"Pipeline '{pipeline.pipeline_name}' already exists.")

            session.add(pipeline)
            session.flush()  # Ensure ID is assigned
            self.logger.info(f"Pipeline '{pipeline.pipeline_name}' registered successfully.")
            return pipeline

        except Exception as e:
            self.logger.error(f"Failed to register pipeline '{pipeline.pipeline_name}': {e}")
            session.rollback()
            raise RuntimeError(f"Failed to register pipeline: {e}")
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def add_resources_to_pipeline_sync(self, pipeline_id: UUID, resource_ids: Optional[List[UUID]], session: Optional[Session] = None) -> bool:
        """
        Synchronously associate resources with a pipeline.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            pipeline = session.get(Pipeline, pipeline_id)
            if not pipeline:
                raise KeyError(f"Pipeline '{pipeline_id}' not found.")

            if not resource_ids:
                self.logger.info(f"No resources provided to add to pipeline '{pipeline_id}'.")
                return True

            resources = session.execute(select(Resource).where(Resource.id.in_(resource_ids)))
            existing_resources = resources.scalars().all()
            if len(existing_resources) != len(resource_ids):
                missing_ids = set(resource_ids) - {res.id for res in existing_resources}
                raise ValueError(f"Some resources were not found: {missing_ids}")

            pipeline.resources.extend(existing_resources)
            session.commit()
            self.logger.info(f"Resources added to pipeline '{pipeline_id}' successfully.")
            return True

        except KeyError as e:
            self.logger.warning(str(e))
            session.rollback()
            return False
        except ValueError as ve:
            self.logger.error(f"Resource validation failed: {ve}")
            session.rollback()
            raise
        except Exception as e:
            self.logger.error(f"Failed to add resources to pipeline: {e}")
            session.rollback()
            raise RuntimeError(f"Failed to add resources to pipeline: {e}")
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def update_pipeline_sync(self, pipeline_id: UUID, update_data: dict, session: Optional[Session] = None) -> dict:
        """
        Synchronously update pipeline details (e.g., status, end_time).
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            with session.begin():
                stmt = update(Pipeline).where(Pipeline.id == pipeline_id).values(**update_data)
                result = session.execute(stmt)
                if result.rowcount == 0:
                    self.logger.warning(f"Pipeline '{pipeline_id}' not found.")
                    raise KeyError(f"Pipeline '{pipeline_id}' not found.")
            self.logger.info(f"Pipeline '{pipeline_id}' updated successfully.")
            return {"message": f"Pipeline '{pipeline_id}' updated successfully."}
        except Exception as e:
            self.logger.error(f"Failed to update pipeline '{pipeline_id}': {e}")
            session.rollback()
            raise RuntimeError(f"Failed to update pipeline: {e}")
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def delete_pipeline_sync(self, pipeline_id: UUID, session: Optional[Session] = None) -> dict:
        """
        Synchronously delete a pipeline by its ID.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            with session.begin():
                stmt = delete(Pipeline).where(Pipeline.id == pipeline_id)
                result = session.execute(stmt)
                if result.rowcount == 0:
                    self.logger.warning(f"Pipeline '{pipeline_id}' not found.")
                    raise KeyError(f"Pipeline '{pipeline_id}' not found.")
            session.commit()
            self.logger.info(f"Pipeline '{pipeline_id}' deleted successfully.")
            return {"message": f"Pipeline '{pipeline_id}' deleted successfully."}
        except Exception as e:
            self.logger.error(f"Failed to delete pipeline '{pipeline_id}': {e}")
            session.rollback()
            raise RuntimeError(f"Failed to delete pipeline: {e}")
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def get_pipeline_sync(self, pipeline_id: UUID, session: Optional[Session] = None) -> Pipeline:
        """
        Synchronously retrieve a pipeline by its ID.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            with session.begin():
                stmt = select(Pipeline).options(
                    joinedload(Pipeline.steps),
                    joinedload(Pipeline.configurations),
                    joinedload(Pipeline.resources)
                ).where(Pipeline.id == pipeline_id)
                result = session.execute(stmt)
                pipeline = result.scalar_one_or_none()
                if not pipeline:
                    self.logger.warning(f"Pipeline '{pipeline_id}' not found.")
                    raise KeyError(f"Pipeline '{pipeline_id}' not found.")
                return pipeline
        except Exception as e:
            self.logger.error(f"Failed to fetch pipeline '{pipeline_id}': {e}")
            raise RuntimeError(f"Failed to fetch pipeline: {e}")
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def update_pipeline_status_sync(self, pipeline_id: UUID, status: str, session: Optional[Session] = None) -> dict:
        """
        Synchronously update the status of a pipeline.
        Validates state transitions and updates end_time if necessary.
        """
        valid_transitions = {
            "pending": ["running", "failed"],
            "running": ["completed", "failed"],
            "completed": [],
            "failed": [],
        }
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            pipeline = session.get(Pipeline, pipeline_id)
            if not pipeline:
                raise KeyError(f"Pipeline '{pipeline_id}' not found.")
            if status not in valid_transitions.get(pipeline.status, []):
                raise ValueError(f"Invalid status transition from '{pipeline.status}' to '{status}'.")
            with session.begin():
                pipeline.status = status
                if status in ["completed", "failed"]:
                    pipeline.end_time = datetime.utcnow()
            session.commit()
            self.logger.info(f"Pipeline '{pipeline_id}' updated to status '{status}'.")
            return {"message": f"Pipeline '{pipeline_id}' updated successfully."}
        except Exception as e:
            self.logger.error(f"Failed to update pipeline status: {e}")
            session.rollback()
            raise RuntimeError(f"Failed to update pipeline status: {e}")
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def get_pipeline_by_user_id_sync(self, user_id: UUID, session: Optional[Session] = None) -> List[Pipeline]:
        """
        Synchronously retrieve all pipelines for a specific user.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            with session.begin():
                stmt = select(Pipeline).where(Pipeline.user_id == user_id).order_by(Pipeline.created_at.desc())
                result = session.execute(stmt)
                pipelines = result.scalars().all()
            self.logger.info(f"Retrieved {len(pipelines)} pipelines for user '{user_id}'.")
            return pipelines
        except Exception as e:
            self.logger.error(f"Failed to fetch pipelines for user '{user_id}': {e}")
            raise RuntimeError(f"Failed to fetch pipelines: {e}")
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def get_pipeline_resources_sync(self, pipeline_id: UUID, session: Optional[Session] = None) -> List:
        """
        Synchronously retrieve resources associated with a pipeline.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            with session.begin():
                pipeline = session.get(Pipeline, pipeline_id)
                if not pipeline:
                    raise KeyError(f"Pipeline '{pipeline_id}' not found.")
                resources = pipeline.resources
            self.logger.info(f"Retrieved {len(resources)} resources for pipeline '{pipeline_id}'.")
            return resources
        except Exception as e:
            self.logger.error(f"Failed to fetch resources for pipeline '{pipeline_id}': {e}")
            raise RuntimeError(f"Failed to fetch resources: {e}")
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def get_pipeline_steps_sync(self, pipeline_id: UUID, session: Optional[Session] = None) -> List[PipelineStep]:
        """
        Synchronously retrieve all steps for a pipeline, ordered by the predefined order.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            with session.begin():
                stmt = (
                    select(PipelineStep)
                    .where(PipelineStep.pipeline_id == pipeline_id)
                    .order_by(PipelineStep.order)
                )
                result = session.execute(stmt)
                steps = result.scalars().all()
            self.logger.info(f"Retrieved {len(steps)} steps for pipeline '{pipeline_id}'.")
            return steps
        except SQLAlchemyError as sae:
            self.logger.error(f"Database error fetching steps: {str(sae)}")
            raise RuntimeError("Failed to retrieve pipeline steps due to database error")
        except Exception as e:
            self.logger.error(f"Unexpected error fetching steps: {str(e)}")
            raise RuntimeError("Failed to retrieve pipeline steps")
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def delete_pipeline_cascade_sync(self, pipeline_id: UUID, session: Optional[Session] = None) -> dict:
        """
        Synchronously delete a pipeline and all its related records (steps, logs, configurations).
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            with session.begin():
                session.execute(delete(PipelineLog).where(PipelineLog.pipeline_id == pipeline_id))
                session.execute(delete(PipelineConfig).where(PipelineConfig.pipeline_id == pipeline_id))
                session.execute(delete(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id))
                result = session.execute(delete(Pipeline).where(Pipeline.id == pipeline_id))
                if result.rowcount == 0:
                    raise KeyError(f"Pipeline '{pipeline_id}' not found.")
            session.commit()
            self.logger.info(f"Pipeline '{pipeline_id}' and all its related records deleted successfully.")
            return {"message": f"Pipeline '{pipeline_id}' deleted successfully."}
        except Exception as e:
            self.logger.error(f"Failed to delete pipeline '{pipeline_id}': {e}")
            session.rollback()
            raise RuntimeError(f"Failed to delete pipeline: {e}")
        finally:
            if close_session:
                session.close()

    # -------------------------------------------
    # PIPELINE STEP MANAGEMENT (SYNC)
    # -------------------------------------------
    
    @log_runtime("pipeline_manager_sync")
    def update_step_status_sync(
        self,
        pipeline_id: UUID,
        step_id: UUID,
        status: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        session: Optional[Session] = None
    ) -> dict:
        """
        Synchronously update the status of a pipeline step.
        
        This method retrieves the pipeline step (by step_id) and updates its status.
        Optionally, it can update the start_time and/or end_time.
        
        Args:
            pipeline_id (UUID): The ID of the pipeline (for logging and validation).
            step_id (UUID): The ID of the step to update.
            status (str): New status (e.g., "running", "completed", "failed").
            start_time (Optional[datetime]): Optional start time (if setting to "running").
            end_time (Optional[datetime]): Optional end time (if setting to "completed" or "failed").
            session (Optional[Session]): A synchronous SQLAlchemy session; if not provided,
                                         one is created and closed within the function.
        
        Returns:
            dict: A dictionary with a confirmation message.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            # Retrieve the step by its ID.
            step = session.get(PipelineStep, step_id)
            if not step:
                raise KeyError(f"Step '{step_id}' not found in pipeline '{pipeline_id}'.")

            # Update optional timestamps if provided.
            if start_time:
                step.start_time = start_time
            if end_time:
                step.end_time = end_time

            # Update the step status.
            step.status = status

            # Use a transaction block.
            with session.begin():
                session.add(step)
            session.commit()

            self.logger.info(f"Step '{step_id}' updated successfully to status '{status}'.")
            return {"message": f"Step '{step_id}' updated to status '{status}'."}
        except Exception as e:
            self.logger.error(f"Failed to update step '{step_id}' status: {e}")
            session.rollback()
            raise RuntimeError(f"Failed to update step '{step_id}' status: {e}")
        finally:
            if close_session:
                session.close()
    
    @log_runtime("pipeline_manager_sync")
    def register_pipeline_step_sync(self, step: PipelineStep, session: Optional[Session] = None) -> bool:
        """
        Synchronously register a pipeline step and enforce execution order.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            if step.step_name not in STEP_EXECUTION_ORDER:
                raise ValueError(f"Invalid step {step.step_name}")
            step.order = STEP_EXECUTION_ORDER.index(step.step_name)
            pipeline = session.get(Pipeline, step.pipeline_id)
            if not pipeline:
                raise KeyError(f"Pipeline '{step.pipeline_id}' not found.")
            existing_step = session.execute(
                select(PipelineStep).where(
                    PipelineStep.pipeline_id == step.pipeline_id,
                    PipelineStep.step_name == step.step_name
                )
            )
            if existing_step.scalar_one_or_none():
                raise ValueError(f"Step '{step.step_name}' already exists in pipeline '{step.pipeline_id}'.")
            session.add(step)
            session.flush()  # Ensure step is persisted before ordering
            self.logger.info(f"Step '{step.step_name}' registered and ordered successfully")
            session.commit()
            return True
        except ValueError as ve:
            self.logger.error(f"Step validation failed: {ve}")
            session.rollback()
            raise
        except Exception as e:
            self.logger.error(f"Registration failed: {e}")
            session.rollback()
            raise RuntimeError("Step registration error") from e
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def complete_pipeline_step_sync(self, step_id: UUID, status: str, result_file_path: Optional[str], session: Optional[Session] = None) -> dict:
        """
        Synchronously mark a pipeline step as completed or failed.
        """
        valid_transitions = {
            "pending": ["running", "failed"],
            "running": ["completed", "failed"],
            "completed": [],
            "failed": [],
        }
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            with session.begin():
                step = session.get(PipelineStep, step_id)
                if not step:
                    raise KeyError(f"Step '{step_id}' not found.")
                if status not in valid_transitions.get(step.status, []):
                    raise ValueError(f"Invalid status transition from '{step.status}' to '{status}'.")
                step.status = status
                step.end_time = datetime.utcnow()
                step.result_file_path = result_file_path
            session.commit()
            self.logger.info(f"Step '{step_id}' completed successfully with status '{status}'.")
            return {"message": f"Step '{step_id}' completed successfully."}
        except Exception as e:
            self.logger.error(f"Failed to complete step '{step_id}': {e}")
            session.rollback()
            raise RuntimeError(f"Failed to complete step: {e}")
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def get_pending_steps_sync(self, pipeline_id: UUID, session: Optional[Session] = None) -> List[PipelineStep]:
        """
        Synchronously retrieve all pending steps of a pipeline.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            with session.begin():
                stmt = select(PipelineStep).where(
                    PipelineStep.pipeline_id == pipeline_id,
                    PipelineStep.status == "pending"
                )
                result = session.execute(stmt)
                pending_steps = result.scalars().all()
            self.logger.info(f"Retrieved {len(pending_steps)} pending steps for pipeline '{pipeline_id}'.")
            return pending_steps
        except Exception as e:
            self.logger.error(f"Failed to retrieve pending steps: {e}")
            raise RuntimeError("Failed to retrieve pending steps.")
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def get_pipeline_step_by_id(self, pipeline_id: str, step_id: str, session: Optional[Session] = None) -> PipelineStep:
        """
        Synchronously retrieves a pipeline step record by its step_id for a given pipeline.
        
        Args:
            pipeline_id (str): The unique identifier of the pipeline.
            step_id (str): The unique identifier of the step.
            session (Optional[Session]): An optional SQLAlchemy session. If not provided, a new session is created.
        
        Returns:
            PipelineStep: The pipeline step record.
        
        Raises:
            KeyError: If the step is not found.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            stmt = select(PipelineStep).where(
                PipelineStep.pipeline_id == pipeline_id,
                PipelineStep.id == step_id
            )
            result = session.execute(stmt)
            step = result.scalar_one_or_none()
            if not step:
                raise KeyError(f"Step with id {step_id} not found for pipeline {pipeline_id}")
            return step
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def get_pipeline_step_output_by_name(self, pipeline_id: str, step_name: str, session: Optional[Session] = None) -> Dict:
        """
        Synchronously retrieves the output (results) of a pipeline step by its step_name for a given pipeline.
        
        Args:
            pipeline_id (str): The unique identifier of the pipeline.
            step_name (str): The name of the step (as defined in the pipeline).
            session (Optional[Session]): An optional SQLAlchemy session. If not provided, a new session is created.
        
        Returns:
            Dict: The output data stored in the 'results' field of the pipeline step record.
                  If no such step exists or no output is present, returns an empty dictionary.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            stmt = select(PipelineStep).where(
                PipelineStep.pipeline_id == pipeline_id,
                PipelineStep.step_name == step_name
            )
            result = session.execute(stmt)
            step = result.scalar_one_or_none()
            if step and step.results:
                return step.results
            else:
                return {}
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def update_step_results_sync(self, pipeline_id: str, step_id: str, results: Dict, session: Optional[Session] = None) -> None:
        """
        Synchronously updates the 'results' field of a pipeline step.
        
        Args:
            pipeline_id (str): The pipeline identifier.
            step_id (str): The step identifier.
            results (Dict): The output data produced by the step.
            session (Optional[Session]): A synchronous SQLAlchemy session.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True
        try:
            step = session.get(PipelineStep, step_id)
            if not step:
                raise KeyError(f"Step '{step_id}' not found in pipeline '{pipeline_id}'.")
            step.results = results
            with session.begin():
                session.add(step)
            session.commit()
            self.logger.info(f"Updated results for step '{step_id}'.")
        except Exception as e:
            self.logger.error(f"Failed to update results for step '{step_id}': {e}")
            session.rollback()
            raise e
        finally:
            if close_session:
                session.close()


    # -------------------------------------------
    # PIPELINE CONFIGURATION MANAGEMENT (SYNC)
    # -------------------------------------------
    
    @log_runtime("pipeline_manager_sync")
    def save_pipeline_config_sync(self, config: PipelineConfig, session: Optional[Session] = None) -> bool:
        """
        Synchronously save pipeline configuration details.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            session.add(config)
            session.flush()
            self.logger.info(f"Configuration saved for pipeline '{config.pipeline_id}'.")
            session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            session.rollback()
            raise RuntimeError(f"Failed to save config: {e}")
        finally:
            if close_session:
                session.close()

    # -------------------------------------------
    # LOGGING (SYNC)
    # -------------------------------------------
    
    @log_runtime("pipeline_manager_sync")
    def save_pipeline_log_sync(self, log: PipelineLog, session: Optional[Session] = None) -> bool:
        """
        Synchronously save logs for pipeline steps.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            session.add(log)
            session.commit()
            self.logger.info(f"Log saved for step '{log.step_id}'.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save log: {e}")
            session.rollback()
            raise RuntimeError(f"Failed to save log: {e}")
        finally:
            if close_session:
                session.close()

    @log_runtime("pipeline_manager_sync")
    def get_pipeline_logs_sync(self, pipeline_id: UUID, limit: int = 10, offset: int = 0, session: Optional[Session] = None) -> List[PipelineLog]:
        """
        Synchronously retrieve logs associated with a pipeline.
        """
        close_session = False
        if session is None:
            session = get_sync_session()
            close_session = True

        try:
            with session.begin():
                stmt = select(PipelineLog).where(
                    PipelineLog.pipeline_id == pipeline_id
                ).order_by(PipelineLog.created_at.desc()).limit(limit).offset(offset)
                result = session.execute(stmt)
                logs = result.scalars().all()
            self.logger.info(f"Retrieved {len(logs)} logs for pipeline '{pipeline_id}'.")
            return logs
        except Exception as e:
            self.logger.error(f"Failed to retrieve logs for pipeline '{pipeline_id}': {e}")
            raise RuntimeError(f"Failed to retrieve logs: {e}")
        finally:
            if close_session:
                session.close()

