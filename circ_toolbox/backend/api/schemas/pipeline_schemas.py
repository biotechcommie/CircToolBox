# circ_toolbox_project/circ_toolbox/backend/api/schemas/pipeline_schemas.py
from pydantic import BaseModel, constr, Field, validator
from typing import List, Optional, Dict, Union, Literal
from datetime import datetime
from uuid import UUID

# -------------------------------------------
# Pipeline Run Schemas
# -------------------------------------------

# Schema for creating a new pipeline run
class PipelineRunCreate(BaseModel):
    pipeline_name: constr(min_length=1, max_length=100)
    user_id: Optional[UUID] = None  # Make user_id optional for injection later  # Aligned with PostgreSQL schema
    resource_files: Optional[List[UUID]]  # List of resource file UUIDs
    steps: List["PipelineStepCreate"]  # Steps to execute
    status: Optional[Literal["pending", "running", "completed", "failed"]] = "pending"
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None

    model_config = {
        "str_strip_whitespace": True,
        "from_attributes": True
    }


# Schema for updating a pipeline run (partial update)
class PipelineRunUpdate(BaseModel):
    pipeline_name: constr(min_length=1, max_length=100)
    status: Optional[constr(min_length=1, max_length=20)]  # pending, running, completed, failed
    end_time: Optional[datetime] = None
    notes: Optional[str] = None

# Schema for response when retrieving pipeline runs
class PipelineRunResponse(BaseModel):
    id: UUID
    pipeline_name: str
    user_id: UUID
    status: str
    created_at: datetime
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    notes: Optional[str]
    steps: List["PipelineStepResponse"]
    configurations: List["PipelineConfigResponse"]  # FIXED: Renamed to match ORM
    resources: List["ResourceResponse"]  # FIXED: Added missing field

    model_config = {
        "from_attributes": True
    }



# -------------------------------------------
# Pipeline Step Schemas
# -------------------------------------------

class PipelineStepCreate(BaseModel):
    step_name: constr(min_length=1, max_length=100)
    parameters: Dict[str, Union[str, int, float, bool]] = {}
    required_resource_types: Optional[List[Literal["GENOME", "ANNOTATION", "REFERENCE"]]] = []  # Define which resource types this step requires
    requires_input_file: bool  # Whether input files are needed for this step
    input_files: Optional[
        Union[
            Dict[str, str],  # Dict of project ID -> One file
            List[str]  # Flat list of files
        ]
    ] = Field(default_factory=list)
    status: Optional[Literal["pending", "running", "completed", "failed"]] = "pending"

    @validator("input_files", pre=True, always=True)
    def validate_input_files(cls, v, values):
        """
        Validate input file format:
        - If dictionary, must have only ONE project ID and ONE file.
        - If list, must contain only strings (file paths).
        """
        if v:
            if isinstance(v, dict):
                if len(v) != 1 or not isinstance(next(iter(v.values())), str):
                    raise ValueError("If using a dict, it must have exactly one key-value pair (one project ID per file).")
            elif isinstance(v, list):
                if not all(isinstance(item, str) for item in v):
                    raise ValueError("Input files as a list must contain only string file names.")
            else:
                raise ValueError("Input files must be a valid list of strings or a dictionary with one project ID per file.")
        return v
    
    model_config = {
        "str_strip_whitespace": True,
        "from_attributes": True
    }



# Schema for pipeline step response
class PipelineStepResponse(BaseModel):
    id: UUID
    step_name: str
    status: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    result_file_path: Optional[str]
    parameters: Dict[str, Union[str, int, float, bool]]
    resources_used: List["ResourceResponse"]  # Assigned resource files
    results: Optional[Dict[str, Union[str, int, float, bool]]]  # FIXED: Added field
    input_mapping: Optional[Dict[str, str]]  # FIXED: Added field

    model_config = {
        "from_attributes": True
    }


# response model to return only the pipeline ID and message 
class PipelineRunCreateResponse(BaseModel):
    pipeline_id: UUID
    message: str

    model_config = {
        "from_attributes": True
    }


# -------------------------------------------
# Pipeline Configuration Schemas
# -------------------------------------------

class PipelineConfigCreate(BaseModel):
    pipeline_id: UUID  # FIXED: Renamed to match ORM
    config_type: Literal["initial", "final"]
    config_data: Dict[str, Union[str, int, float, bool]]
    config_file_path: str

    model_config = {
        "from_attributes": True
    }


# Schema for pipeline configuration response
class PipelineConfigResponse(BaseModel):
    id: UUID
    config_type: str
    config_data: Dict[str, Union[str, int, float, bool]]
    config_file_path: str
    date_added: datetime

    model_config = {
        "from_attributes": True
    }



# -------------------------------------------
# Additional Monitoring and Logs
# -------------------------------------------

class PipelineStatusResponse(BaseModel):
    pipeline_id: UUID
    status: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    progress_percentage: Optional[float]
    logs_url: Optional[str]

    class Config:
        from_attributes = True


class PipelineResultResponse(BaseModel):
    pipeline_id: UUID
    output_files: List[Dict[Literal["filename", "download_url"], str]]  # [{'filename': 'result.csv', 'download_url': '/path/to/file'}]

    class Config:
        from_attributes = True


class PipelineStepLogsResponse(BaseModel):
    step_id: UUID
    logs: str

    model_config = {
        "from_attributes": True
    }




# Import necessary schemas after class definitions to avoid circular import
from circ_toolbox.backend.api.schemas.resource_schemas import ResourceResponse

# Resolve forward references to prevent import errors
#PipelineRunResponse.update_forward_refs()
#PipelineStepResponse.update_forward_refs()
# Resolve forward references
PipelineRunResponse.model_rebuild()
PipelineStepResponse.model_rebuild()


'''
Key Changes and Enhancements
Enhanced PipelineRunCreate Schema:

Added resource_files as a list of UUIDs to indicate selected resource files.
Added created_at to track when the pipeline was created.
Retained steps field to hold the list of pipeline steps.
Expanded PipelineStepCreate Schema:

Added required_resource_types: A list of required resource file types per step.
Added requires_input_file: A flag to indicate if step needs user input.
Enhanced input_files: Supports either a simple list of paths or a complex dictionary (bioproject ID → list of files).
Resource Allocation Logic in PipelineStepResponse:

Introduced resources_used to track which resources were allocated by backend logic.
Monitoring and Logging Enhancements:

PipelineStatusResponse to track execution progress, logs, and completion times.
PipelineResultResponse provides downloadable output files.
PipelineStepLogsResponse to fetch logs of a specific step.
Pipeline Configuration Refinements:

Both PipelineConfigCreate and PipelineConfigResponse use structured dictionaries for flexible configuration settings.
How It Works with Frontend
Pipeline Creation Flow:

Frontend collects pipeline name and steps.
Frontend submits resource_files list to backend, not worrying about step-level assignments.
Backend assigns resources intelligently.
Step Input Handling:

If the selected first step requires input, the user provides bioprojects and input files.
The frontend submits inputs in the correct JSON format (list or dictionary).
Execution Tracking:

Frontend polls /pipelines/{pipeline_id}/status for updates.
Logs are accessible via /pipelines/{pipeline_id}/steps/{step_id}/logs.
Result Retrieval:

After completion, frontend calls /pipelines/{pipeline_id}/results to list downloadable files.
Advantages of This Schema Design
Extensibility:

Easy to add new features without breaking existing functionality.
Scalability:

Handles complex multi-step pipelines with minimal frontend logic.
Error Handling:

Backend ensures valid resource file assignments, reducing user errors.
Future-Proofing:

Designed to support additional fields for progress tracking, retries, and versioning.
Next Steps for Implementation
Update API Endpoints to Use New Schema

Ensure all routes expect the new schema structure.
Write Database Models and Migrations

Align these schemas with SQLAlchemy models.
Develop Backend Business Logic

Implement resource allocation and validation functions.
Integrate with Frontend

Ensure UI form submission aligns with schema changes.


'''




'''

Naming Consistency and Validation

Ensured field names like resource_type align with SQLAlchemy models.
Used constr() for better string validation (e.g., lengths and whitespace trimming).
Added optional fields with None defaults where applicable.
Schema Types for Different Operations

PipelineRunCreate: For creating new pipeline runs, excluding run_id (generated).
PipelineRunUpdate: Allows updating specific fields without overwriting everything.
PipelineRunResponse: Provides nested relationships in API responses.
ORM Mode

Enabled from_attributes = True to allow SQLAlchemy models to be directly converted to API responses.
Nested Relationships

PipelineRunResponse includes a list of PipelineStepResponse, which further nests ResourceResponse.
Ensures API returns a structured view of pipeline data.
'''


'''

How This Maps to the Frontend
Form Structure

The frontend should have:
Step 1: Choose pipeline name, select input resources.
Step 2: Configure each step (multi-step form with optional navigation).
Step 3: Review and submit.
Validation

Use frontend form libraries (React Hook Form, Formik) to validate fields based on Pydantic constraints.
API Interaction

Create a pipeline: POST /api/pipelines/
Update pipeline status: PATCH /api/pipelines/{run_id}
Get pipeline details: GET /api/pipelines/{run_id}
'''