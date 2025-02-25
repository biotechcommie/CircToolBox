# circ_toolbox/backend/services/orchestrators/pipeline_execution_orchestrator.py

"""
High-Level Pipeline Execution Orchestrator

This orchestrator is called from FastAPI and runs in an async context.
It performs the following:
  1. Validates that the pipeline exists and is in a valid state (pending, paused, or failed).
  2. Updates the pipeline status to "running".
  3. Creates a dedicated run directory for the pipeline execution.
  4. Triggers a Celery task to execute the first pipeline step by passing the minimal context:
       - pipeline_id
       - run_directory

Note: The Celery tasks will query the database (via PipelineManagerSync) to obtain
      the current steps and execute them sequentially.
"""


"""
High-Level Pipeline Execution Orchestrator

This orchestrator is invoked from FastAPI endpoints (asynchronously) to:
  1. Validate that the pipeline exists and is in an executable state (pending, paused, or failed).
  2. Update the pipeline status to "running" (or, if no pending steps exist, to "completed" or "failed").
  3. Create a dedicated run directory for the pipeline.
  4. Trigger a Celery task with minimal context (pipeline_id and run_directory) so that the tasks
     will fetch the current state from the database using the synchronous manager.
     
It also provides an optional method, `run_next_pending_step`, to trigger only the next available step.
"""
from fastapi import Depends

import os
import logging
from uuid import UUID
from typing import Optional, Dict
from datetime import datetime
from circ_toolbox.backend.constants.step_mapping import ensure_steps_order  # New ordering function.
from sqlalchemy.ext.asyncio import AsyncSession
from circ_toolbox.backend.database.pipeline_manager import PipelineManager, get_pipeline_manager
from circ_toolbox.backend.utils.logging_config import get_logger, log_runtime
from circ_toolbox.backend.utils.file_handling import create_pipeline_run_directory
from circ_toolbox.celery_app import celery_app

logger = get_logger("pipeline_execution_orchestrator")

class PipelineExecutionOrchestrator:
    def __init__(self, pipeline_manager: Optional[PipelineManager] = None):
        self.pipeline_manager = pipeline_manager or PipelineManager()
        self.logger = get_logger("pipeline_execution_orchestrator")

    @log_runtime("pipeline_execution_orchestrator")
    async def start_pipeline_execution(
        self, pipeline_id: UUID, user_id: UUID, session: Optional[AsyncSession] = None
    ) -> Dict:
        """
        Initiates full pipeline execution.

        Steps:
          1. Retrieve minimal pipeline information.
          2. Validate that the pipeline is in an executable state.
          3. Update the pipeline status to "running".
          4. Create a dedicated run directory.
          5. Trigger the Celery task 'execute_pipeline' with minimal context.

        Args:
            pipeline_id (UUID): The unique identifier for the pipeline.
            user_id (UUID): The unique identifier for the user (for file storage).
            session (Optional[AsyncSession]): An async DB session.

        Returns:
            Dict: Contains a confirmation message and the Celery task ID.
        """
        # Retrieve minimal pipeline data.
        pipeline_min = await self.pipeline_manager.get_pipeline_minimal(pipeline_id, session)
        if not pipeline_min:
            raise ValueError(f"Pipeline '{pipeline_id}' not found.")
        if pipeline_min["status"] not in ["pending", "paused", "failed"]:
            raise ValueError(f"Pipeline '{pipeline_id}' is not in an executable state.")

        # Update pipeline status to "running".
        await self.pipeline_manager.update_pipeline_status(pipeline_id, "running", session)

        # Create the run directory.
        run_directory = create_pipeline_run_directory(user_id, pipeline_id)
        self.logger.info(f"Run directory created at: {run_directory}")

        # (Optional) Verify and correct the step order before triggering tasks.
        steps = await self.pipeline_manager.get_pipeline_steps(pipeline_id, session)
        ordered_steps = ensure_steps_order(steps)  # This function will raise an error if order is incorrect.
        # (You might also update the 'order' field in the database here if desired.)


        # Build minimal payload (only pipeline_id and run_directory).
        payload = {
            "pipeline_id": str(pipeline_id),
            "run_directory": run_directory,
        }

        # Trigger the Celery task for full pipeline execution.
        task = celery_app.send_task("circ_toolbox.tasks.execute_pipeline", args=[str(pipeline_id), payload])
        self.logger.info(f"Pipeline execution triggered for pipeline {pipeline_id} with task ID: {task.id}")
        return {"message": "Pipeline execution started", "task_id": task.id}

    @log_runtime("pipeline_execution_orchestrator")
    async def run_next_pending_step(
        self, pipeline_id: UUID, user_id: UUID, session: Optional[AsyncSession] = None
    ) -> Dict:
        """
        Triggers execution of only the next pending step of a pipeline.

        It performs the following:
          1. Retrieves minimal pipeline information.
          2. Queries for pending steps.
          3. If a pending step is found, triggers a Celery task for that step.
          4. If no pending step is found, updates the pipeline status:
               - If any step is marked as "failed", update pipeline to "failed".
               - Otherwise, update pipeline to "completed".

        Args:
            pipeline_id (UUID): The unique identifier for the pipeline.
            user_id (UUID): The unique identifier for the user (for file storage).
            session (Optional[AsyncSession]): An async DB session.

        Returns:
            Dict: Contains a status message and, if applicable, the Celery task ID.
        """
        # Retrieve minimal pipeline data.
        pipeline_min = await self.pipeline_manager.get_pipeline_minimal(pipeline_id, session)
        if not pipeline_min:
            raise ValueError(f"Pipeline '{pipeline_id}' not found.")

        # (Optional) Create or re-use the run directory.
        run_directory = create_pipeline_run_directory(user_id, pipeline_id)
        self.logger.info(f"Run directory for next pending step: {run_directory}")

        # Query the full list of steps (to determine pending/failure status).
        steps = await self.pipeline_manager.get_pipeline_steps(pipeline_id, session)
        ordered_steps = ensure_steps_order(steps)

        # Check for failed steps first—if any exist, we consider the pipeline failed.
        if any(step.status == "failed" for step in ordered_steps):
            await self.pipeline_manager.update_pipeline_status(pipeline_id, "failed", session)
            self.logger.info(f"Pipeline {pipeline_id} contains failed steps; marked as failed.")
            return {"status": "failed", "message": "Pipeline contains failed steps."}

        # Identify the next pending step.
        next_step = next((step for step in ordered_steps if step.status == "pending"), None)
        if not next_step:
            # No pending steps remain; mark the pipeline as completed.
            await self.pipeline_manager.update_pipeline_status(pipeline_id, "completed", session)
            self.logger.info(f"No pending steps for pipeline {pipeline_id}. Marked as completed.")
            return {"status": "completed", "message": "Pipeline already completed."}

        # Build the payload for the next pending step.
        payload = {
            "step_id": str(next_step.id),
            "step_name": next_step.step_name,
            "parameters": next_step.parameters,
            "input_data": next_step.input_files if next_step.input_files else {},
        }

        # Trigger the Celery task for the next pending step.
        task = celery_app.send_task("circ_toolbox.tasks.execute_step", args=[str(pipeline_id), payload])
        self.logger.info(f"Triggered next pending step '{next_step.step_name}' for pipeline {pipeline_id} with task ID: {task.id}")
        return {"status": "running", "task_id": task.id}


# ------------------------------------------------------------------------------
# Dependency Injection for ResourceOrchestrator
# ------------------------------------------------------------------------------
async def get_pipeline_execution_orchestrator(
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
):
    """
    Provides an instance of PipelineExecutionOrchestrator for dependency injection.

    Args:
        pipeline_manager: The PipelineManager dependency.
        user_manager: The UserManager dependency.

    Yields:
        PipelineExecutionOrchestrator: An instance of PipelineExecutionOrchestrator.
    """
    yield PipelineExecutionOrchestrator(pipeline_manager)



'''
PipelineExecutionOrchestrator

Handles triggering and monitoring of pipeline execution.
Calls Celery tasks to execute pipeline steps.
Manages the pipeline execution flow (sequential step execution, logging, and error handling).
Updates step and pipeline statuses in the database via PipelineManager.
'''
'''
Pipeline Execution Orchestrator (High-Level)
The high-level orchestrator will be responsible for:

Validation & Initialization

Ensure the pipeline exists and is in a valid state (e.g., pending, paused).
Update the pipeline status to running.
Validate step order to ensure correct execution flow.
Save the initial execution configuration in the database.
Execution Control

Trigger Celery tasks for either:
Full pipeline execution (triggers steps sequentially inside Celery).
Step-by-step execution (handles the next step separately).
Fetch and pass minimal data required to start Celery tasks (e.g., pipeline ID, run directory).
Maintain an execution log to track progress.
Resource Handling

Ensure directories are created before execution.
Fetch and validate necessary resource files and paths using PipelineManager.
Error Handling

Catch initial validation or orchestration errors.
Provide informative feedback to the frontend if execution fails at the initiation phase.
Summary of responsibilities of high-level orchestrator:

Step validation and ordering logic
Initial pipeline status updates
Triggering Celery tasks
Minimal data preparation and passing
Directory setup

'''


