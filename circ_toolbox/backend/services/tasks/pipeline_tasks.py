# circ_toolbox/backend/services/tasks/pipeline_tasks.py
"""
Celery Tasks for Pipeline Execution

This module defines Celery tasks that are responsible for executing
the entire pipeline or a single pipeline step in a synchronous context.
It relies on the synchronous version of PipelineManager (PipelineManagerSync)
to perform database operations using a dedicated synchronous session (via get_sync_session).

The tasks are structured as follows:
  - execute_pipeline: Entry task for full pipeline execution.
      • Updates the overall pipeline status to "running".
      • Validates that steps exist.
      • Identifies the first pending step.
      • Triggers execution of the first step.
  - execute_step: Executes a single pipeline step by:
      1. Updating the step status to "running".
      2. Retrieving and instantiating the low-level orchestrator for the step.
      3. Executing the step logic.
      4. Upon success, updating the step status to "completed".
      5. Querying for the next pending step:
            - If found, triggers a new execute_step task.
            - If not found, marks the pipeline as "completed".
      6. If any step fails, marks the step and the overall pipeline as "failed".
      
Both tasks include detailed logging and error handling.
"""
# circ_toolbox/backend/services/tasks/pipeline_tasks.py

import logging
from datetime import datetime
from uuid import UUID
from circ_toolbox.celery_app import celery_app
from circ_toolbox.backend.database.pipeline_manager import PipelineManagerSync
from circ_toolbox.backend.constants.step_mapping import get_step_orchestrator, ensure_steps_order
from circ_toolbox.backend.utils.logging_config import get_logger

logger = get_logger("pipeline_tasks")

@celery_app.task(bind=True, name="circ_toolbox.tasks.execute_pipeline")
def execute_pipeline(self, pipeline_id, pipeline_data):
    """
    Entry task for executing an entire pipeline synchronously.

    This task:
      1. Updates the overall pipeline status to "running".
      2. Validates that the provided pipeline_data (minimal context) is valid.
      3. Retrieves the current list of steps from the database.
      4. Identifies the first pending step.
      5. Triggers the execution of the first step via the execute_step task.

    Args:
        pipeline_id (str): The unique identifier for the pipeline.
        pipeline_data (dict): A dictionary containing minimal context (e.g., run_directory).

    Returns:
        dict: A status message with either a task ID for the next step or a completion message.
    """
    logger.info(f"Starting full pipeline execution for pipeline: {pipeline_id}")
    manager = PipelineManagerSync()

    # Update the overall pipeline status to "running".
    try:
        manager.update_pipeline_status_sync(pipeline_id, "running")
    except Exception as e:
        logger.error(f"Failed to update pipeline status to 'running': {e}")
        raise e

    # Retrieve the current list of steps.
    steps = manager.get_pipeline_steps_sync(pipeline_id)
    if not steps:
        logger.error("No steps found for pipeline execution.")
        raise ValueError("Pipeline has no steps to execute.")
    try:
        ordered_steps = ensure_steps_order(steps)
    except Exception as e:
        logger.error(f"Step order validation failed: {e}")
        raise e
    
    # Identify the first pending step.
    next_step = next((step for step in ordered_steps if getattr(step, "status", "pending") == "pending"), None)
    if not next_step:
        logger.info(f"All steps are already completed for pipeline {pipeline_id}.")
        manager.update_pipeline_status_sync(pipeline_id, "completed")
        return {"status": "completed", "message": "Pipeline already completed."}

    # Build payload for the first pending step.
    step_payload = {
        "step_id": str(next_step.id),
        "step_name": next_step.step_name,
        "parameters": next_step.parameters,
        "input_data": next_step.input_files if next_step.input_files else {},
    }

    # Trigger execution of the first step.
    result = execute_step.delay(pipeline_id, step_payload)
    logger.info(f"Triggered execution of step '{next_step.step_name}' with task ID: {result.id}")
    return {"status": "running", "task_id": result.id}


@celery_app.task(bind=True, name="circ_toolbox.tasks.execute_step")
def execute_step(self, pipeline_id, step_payload):
    """
    Executes a single pipeline step synchronously and triggers the next step if available.

    This task:
      1. Updates the step status to "running" and records the start time.
      2. Retrieves the low-level orchestrator for the step.
      3. Executes the step logic via the orchestrator.
      4. Upon success, updates the step status to "completed".
      5. Queries for the next pending step:
            - If found, triggers a new execute_step task.
            - If not found, marks the overall pipeline as "completed".
      6. If any error occurs, marks the step and overall pipeline as "failed".

    Args:
        pipeline_id (str): The unique identifier for the pipeline.
        step_payload (dict): Contains:
            - step_id: The unique identifier of the step.
            - step_name: The name of the step.
            - parameters: Configuration parameters for the step.
            - input_data: Input data for the step.

    Returns:
        dict: The output data from executing the step.
    """
    logger.info(f"Executing step '{step_payload.get('step_name')}' for pipeline {pipeline_id}")
    manager = PipelineManagerSync()
    step_id = step_payload.get("step_id")
    step_name = step_payload.get("step_name")
    parameters = step_payload.get("parameters", {})
    input_data = step_payload.get("input_data", {})

    # Enrich input_data based on input_mapping stored in the step record.
    step_record = manager.get_pipeline_step_by_id(pipeline_id, step_id)
    if step_record and step_record.input_mapping:
        enriched_input = input_data.copy()
        for key, dependency_step_name in step_record.input_mapping.items():
            dependency_output = manager.get_pipeline_step_output_by_name(pipeline_id, dependency_step_name)
            if dependency_output and key in dependency_output:
                enriched_input[key] = dependency_output[key]
        input_data = enriched_input
        step_payload["input_data"] = input_data
        logger.info(f"Enriched input_data with mapping {step_record.input_mapping}: {input_data}")

    # Update step status to "running".
    try:
        manager.update_step_status_sync(pipeline_id, step_id, "running", start_time=datetime.utcnow())
    except Exception as e:
        logger.error(f"Error updating step '{step_name}' to 'running': {e}")
        raise e

    # Retrieve the low-level orchestrator for this step.
    try:
        orchestrator_class = get_step_orchestrator(step_name)
        orchestrator_instance = orchestrator_class()
    except Exception as e:
        logger.error(f"Error obtaining orchestrator for step '{step_name}': {e}")
        manager.update_step_status_sync(pipeline_id, step_id, "failed")
        manager.update_pipeline_status_sync(pipeline_id, "failed")
        raise e

    # Execute the step logic.
    try:
        output_data = orchestrator_instance.execute(parameters=parameters, input_data=input_data)
        # *** New Step: Update the step record with its output in the database.
        manager.update_step_results_sync(pipeline_id, step_id, output_data)
    except Exception as e:
        logger.error(f"Execution error in step '{step_name}': {e}")
        manager.update_step_status_sync(pipeline_id, step_id, "failed", end_time=datetime.utcnow())
        manager.update_pipeline_status_sync(pipeline_id, "failed")
        raise e

    # Mark the step as "completed".
    try:
        manager.update_step_status_sync(pipeline_id, step_id, "completed", end_time=datetime.utcnow())
    except Exception as e:
        logger.error(f"Failed to update step '{step_name}' status to 'completed': {e}")
        raise e

    # Do not directly pass output_data as input_data for the next step.
    # The next step will always retrieve its dependencies from the database via its input_mapping.
    try:
        steps = manager.get_pipeline_steps_sync(pipeline_id)
        ordered_steps = ensure_steps_order(steps)
        # If any step is marked "failed", mark the pipeline as "failed" and stop execution.
        if any(getattr(step, "status", "") == "failed" for step in ordered_steps):
            manager.update_pipeline_status_sync(pipeline_id, "failed")
            logger.info(f"Pipeline {pipeline_id} has failed steps; execution halted.")
            return output_data

        next_step = next((step for step in ordered_steps if getattr(step, "status", "pending") == "pending"), None)
        if next_step:
            # For the next step, do not directly pass output_data; pass an empty payload (or just its parameters)
            next_payload = {
                "step_id": str(next_step.id),
                "step_name": next_step.step_name,
                "parameters": next_step.parameters,
                "input_data": {}  # The next step will enrich its input by fetching dependency outputs.
            }
            result = execute_step.delay(pipeline_id, next_payload)
            logger.info(f"Triggered next step '{next_step.step_name}' with task ID: {result.id}")
        else:
            manager.update_pipeline_status_sync(pipeline_id, "completed", end_time=datetime.utcnow())
            logger.info(f"Pipeline {pipeline_id} completed successfully.")
    except Exception as e:
        logger.error(f"Error while checking/triggering the next step: {e}")
        raise e

    return output_data

