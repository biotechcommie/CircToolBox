# circ_toolbox/backend/api/schemas/execution_schemas.py
# execution_schemas.py
from datetime import datetime
from pydantic import BaseModel
from uuid import UUID
from enum import Enum

class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class StepExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ExecutionCreate(BaseModel):
    pipeline_id: UUID
    context: dict

class ExecutionResponse(ExecutionCreate):
    id: UUID
    status: ExecutionStatus
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

class StepExecutionBase(BaseModel):
    input_data: dict
    output_data: dict | None

class StepExecutionResponse(StepExecutionBase):
    id: UUID
    status: StepExecutionStatus
    attempt: int
    started_at: datetime | None
    completed_at: datetime | None