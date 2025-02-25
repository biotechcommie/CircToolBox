# circ_toolbox_project/circ_toolbox/backend/api/schemas/resource_schemas.py
"""
Resource Schemas

This module defines Pydantic models for resource creation, update, response,
and species list. These models are fully compatible with Pydantic v2 and are
configured to be used as FastAPI form-data dependencies via an as_form decorator.
They include validations for file extensions based on the resource_type and
support asynchronous file uploads using FastAPI's UploadFile.
"""

import inspect
from inspect import Parameter, signature, _empty
from typing import Optional, List, Literal, Type, Annotated, get_origin, get_args, Union
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, constr, Field, validator
from fastapi import UploadFile, Form, File
from circ_toolbox.backend.utils.logging_config import get_logger
print(">>> USING ResourceUpdate from new code <<<")
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)

logger = get_logger("resource_schemas")
# ------------------------------------------------------------------------------
# Helper decorator to allow a Pydantic model to be used as form data.
# This version uses the new Pydantic v2 attribute `model_fields` and explicitly 
# builds Annotated types with FastAPI's File and Form dependencies.
# ------------------------------------------------------------------------------

# Define special fields that are not provided by the client
SPECIAL_FIELDS = {"uploaded_by", "updated_by"}

def as_form(cls: Type[BaseModel]) -> Type[BaseModel]:
    """
    Decorator to add support for FastAPI form data to a Pydantic model.
    
    It processes each non‑special field as follows:
      1. Determines if the field is required (if its default is _empty, unless its type includes None).
      2. Determines if the field is a file field (i.e. its type is UploadFile or a Union including UploadFile).
      3. Chooses the appropriate dependency:
            - For file fields: use File(...) if required; otherwise, use File() with no default.
            - For other fields: use Form(...) if required; otherwise, use Form() with no default.
      4. Sets the Parameter’s default value to _empty if required or to the Pydantic field’s default otherwise.
      5. Constructs an Annotated type that “attaches” the dependency.
      6. Finally, it sorts the parameters (required ones first) and replaces the model’s __signature__.
      
    This avoids the FastAPI error: “`Form` default value cannot be set in `Annotated` …”
    because no default is passed inside Form() or File().
    """
    logger.debug(f"Processing class: {cls.__name__}")
    new_params = []
    
    for field_name, model_field in cls.model_fields.items():
        logger.debug(f"Processing field: {field_name}")
        
        # For special fields, do not change the parameter.
        if field_name in SPECIAL_FIELDS:
            logger.debug(f"Skipping special field: {field_name}")
            param = Parameter(
                name=field_name,
                kind=Parameter.POSITIONAL_ONLY,
                default=model_field.default,
                annotation=model_field.annotation,
            )
            new_params.append(param)
            continue
        
        # Determine if the field is required.
        # A field is considered required if its default is _empty,
        # unless its type is a Union that includes None.
        is_required = (model_field.default is _empty)
        field_annotation = model_field.annotation
        origin = get_origin(field_annotation)
        if origin is Union and type(None) in get_args(field_annotation):
            is_required = False
        logger.debug(f"Field '{field_name}' required (by default check): {is_required}")
        
        # Determine if the field is a file field.
        is_file_field = (
            field_annotation == UploadFile or
            (origin in (Union,) and UploadFile in get_args(field_annotation))
        )
        logger.debug(f"Field '{field_name}' is file field: {is_file_field}")
        
        # Choose the appropriate dependency.
        # Notice: We call Form() or File() without a default value.
        if is_file_field:
            dependency = File(...) if is_required else File()
        else:
            dependency = Form(...) if is_required else Form()
        logger.debug(f"Field '{field_name}' dependency: {dependency}")
        
        # Set the default value for the Parameter:
        # Use _empty if required; otherwise, use the Pydantic field's default.
        default_val = _empty if is_required else model_field.default if model_field.default is not _empty else None
        logger.debug(f"Field '{field_name}' default value for parameter: {default_val}")
        
        # Build the Annotated type that attaches the dependency as metadata.
        annotated_type = Annotated[field_annotation, dependency]
        logger.debug(f"Field '{field_name}' annotated type: {annotated_type}")
        
        # Create a new Parameter with no default inside the dependency.
        param = Parameter(
            name=field_name,
            kind=Parameter.POSITIONAL_ONLY,
            default=default_val,
            annotation=annotated_type,
        )
        logger.debug(f"Parameter created for field '{field_name}': {param}")
        new_params.append(param)
    
    # Sort parameters so that required ones (default _empty) come first.
    new_params.sort(key=lambda p: p.default is _empty, reverse=True)
    new_sig = signature(cls).replace(parameters=new_params)
    logger.debug(f"New signature: {new_sig}")
    cls.__signature__ = new_sig
    return cls



def asadaas_form(cls: Type[BaseModel]) -> Type[BaseModel]:
    """
    Decorator to add support for FastAPI form data to a Pydantic model.

    For each non‑special field:
      1. It determines if the field is required (if the field’s default is _empty and its type does not include None).
      2. It checks if the field is a file field (i.e. its type is UploadFile or a Union that includes UploadFile).
      3. It chooses the dependency:
           - For file fields: File(...) if required; File() (without a default) if optional.
           - For all other fields: Form(...) if required; Form() (without a default) if optional.
      4. It sets the Parameter’s default to _empty if required or to None if optional.
      5. It builds an Annotated type attaching the chosen dependency.
      6. Finally, it sorts parameters so required ones come first and replaces the model’s __signature__.
      
    This approach avoids embedding a default value inside Form() or File(), which FastAPI does not allow.
    """
    logger.debug(f"Processing class: {cls.__name__}")
    new_params = []
    
    for field_name, model_field in cls.model_fields.items():
        logger.debug(f"Processing field: {field_name}")
        
        # For special fields, retain original parameter
        if field_name in SPECIAL_FIELDS:
            logger.debug(f"Skipping special field: {field_name}")
            param = Parameter(
                name=field_name,
                kind=Parameter.POSITIONAL_ONLY,
                default=model_field.default,
                annotation=model_field.annotation,
            )
            new_params.append(param)
            continue

        # Determine if the field is required.
        # A field is required if its default is _empty and its type does not include None.
        is_required = (model_field.default is _empty)
        field_annotation = model_field.annotation
        origin = get_origin(field_annotation)
        if origin is Union and type(None) in get_args(field_annotation):
            is_required = False
        logger.debug(f"Field '{field_name}' required (by default check): {is_required}")
        
        # Determine if the field is a file field.
        is_file_field = (
            field_annotation == UploadFile or 
            (origin in (Union,) and UploadFile in get_args(field_annotation))
        )
        logger.debug(f"Field '{field_name}' is file field: {is_file_field}")
        
        # Choose the dependency.
        # Note: We never pass a default value to Form() or File() here.
        if is_file_field:
            dependency = File(...) if is_required else File()
        else:
            dependency = Form(...) if is_required else Form()
        logger.debug(f"Field '{field_name}' dependency: {dependency}")
        
        # Set the parameter's default: if required, use _empty; otherwise, use None.
        default_val = _empty if is_required else None
        logger.debug(f"Field '{field_name}' default value for parameter: {default_val}")
        
        # Build the Annotated type with the chosen dependency added to metadata.
        # (Do not include any default value in the dependency itself.)
        annotated_type = Annotated[field_annotation, dependency]
        logger.debug(f"Field '{field_name}' annotated type: {annotated_type}")
        
        param = Parameter(
            name=field_name,
            kind=Parameter.POSITIONAL_ONLY,
            default=default_val,
            annotation=annotated_type,
        )
        logger.debug(f"Parameter created for field '{field_name}': {param}")
        new_params.append(param)
    
    # Sort parameters so that required ones (with default=_empty) come first.
    new_params.sort(key=lambda p: p.default is _empty, reverse=True)
    new_sig = signature(cls).replace(parameters=new_params)
    logger.debug(f"New signature: {new_sig}")
    cls.__signature__ = new_sig
    return cls
# ------------------------------------------------------------------------------
# Resource Create Schema
# ------------------------------------------------------------------------------
@as_form
class ResourceCreate(BaseModel):
    """
    Schema for validating and creating a new resource.
    
    This schema expects the client to upload a real file via a multipart/form-data request.
    The file is provided as an UploadFile, whose filename is validated against allowed extensions
    based on the resource_type. Non-file fields (such as name, resource_type, species, and version)
    are also validated.
    
    Attributes:
        name (str): The resource name (1–100 characters).
        resource_type (Literal["GENOME", "ANNOTATION", "PEPTIDE"]): The type of the resource.
        species (Optional[str]): The species associated with the resource (1–50 characters).
        version (Optional[str]): The version of the resource (1–50 characters).
        file (UploadFile): The uploaded file.
        force_overwrite (bool): Flag to force overwrite if resource already exists.
    """
    name: constr(min_length=1, max_length=100)
    resource_type: Literal["GENOME", "ANNOTATION", "PEPTIDE"]
    species: constr(min_length=1, max_length=50) | None = None
    version: constr(min_length=1, max_length=50) | None = None
    file: UploadFile  # Required file
    uploaded_by: UUID | None = None
    force_overwrite: bool = False
    
    @validator("file", pre=True)
    def validate_file_extension(cls, v, values):
        """
        Validate that the uploaded file's filename ends with one of the allowed extensions
        for the given resource_type.
        
        Args:
            v (UploadFile): The uploaded file.
            values (dict): Other field values, including resource_type.
        
        Raises:
            ValueError: If the file's extension is not among the allowed extensions.
        
        Returns:
            UploadFile: The validated file.
        """
        resource_type = values.get("resource_type")
        allowed_extensions = {
            "GENOME": [".fasta", ".fa", ".fastq"],
            "ANNOTATION": [".gff", ".gtf", ".gff3"],
            "PEPTIDE": [".pep", ".fasta", ".fa", ".fastq"],
        }
        allowed = allowed_extensions.get(resource_type, [])
        # Validate file extension using the file's filename
        if not any(v.filename.lower().endswith(ext) for ext in allowed):
            raise ValueError(
                f"For resource type '{resource_type}', the file must have one of the following extensions: {', '.join(allowed)}"
            )
        return v

    model_config = {
        "str_strip_whitespace": True,
        "from_attributes": True,
    }


# ------------------------------------------------------------------------------
# Resource Update Schema
# ------------------------------------------------------------------------------
@as_form
class ResourceUpdate(BaseModel):
    """
    Schema for validating updates to a resource.
    
    In an update request, the file field is optional. If provided, its filename is validated 
    against the allowed extensions for the resource_type (if resource_type is being updated).
    
    Attributes:
        name (Optional[str]): Updated resource name.
        resource_type (Optional[Literal["GENOME", "ANNOTATION", "PEPTIDE"]]): Updated resource type.
        species (Optional[str]): Updated species.
        version (Optional[str]): Updated version.
        file (Optional[UploadFile]): Optional new uploaded file.
        updated_by (Optional[UUID]): Optional user ID performing the update.
    """
    name: constr(min_length=1, max_length=100) | None = None
    resource_type: Literal["GENOME", "ANNOTATION", "PEPTIDE"] | None = None
    species: constr(min_length=1, max_length=50) | None = None
    version: constr(min_length=1, max_length=50) | None = None
    file: UploadFile | None = None
    updated_by: UUID | None = None
    force_overwrite: bool = False

    @validator("file", pre=True, always=False)
    def validate_file_extension(cls, v, values):
        """
        Validate the file extension for the uploaded file during an update.
        If the file is provided, and resource_type is also provided, ensure that the file's filename
        has one of the allowed extensions.
        
        Args:
            v (Optional[UploadFile]): The uploaded file (if any).
            values (dict): Other field values, including resource_type.
        
        Raises:
            ValueError: If the file extension is invalid.
        
        Returns:
            Optional[UploadFile]: The validated file or None.
        """
        if v is None:
            return v
        resource_type = values.get("resource_type")
        if resource_type is None:
            # If resource_type isn't provided, skip file extension validation.
            return v  # Skip validation if resource_type is not provided
        allowed_extensions = {
            "GENOME": [".fasta", ".fa", ".fastq"],
            "ANNOTATION": [".gff", ".gtf", ".gff3"],
            "PEPTIDE": [".pep", ".fasta", ".fa", ".fastq"],
        }
        allowed = allowed_extensions.get(resource_type, [])
        if not any(v.filename.lower().endswith(ext) for ext in allowed):
            raise ValueError(
                f"For resource type '{resource_type}', the file must have one of the following extensions: {', '.join(allowed)}"
            )
        return v

    model_config = {
        "str_strip_whitespace": True,
    }

# ------------------------------------------------------------------------------
# Resource Response Schema
# ------------------------------------------------------------------------------
class ResourceResponse(BaseModel):
    """
    Schema for returning resource data in API responses.
    
    This schema reflects the resource record as stored in the database. It includes the file_path
    (i.e. the destination where the file was ultimately saved) and the file_size.
    
    Attributes:
        id (UUID): The unique identifier of the resource.
        name (str): The resource name.
        resource_type (str): The type of the resource.
        species (Optional[str]): The species associated with the resource.
        version (Optional[str]): The version of the resource.
        file_path (str): The file's storage path.
        file_size (Optional[int]): The file size in bytes.
        date_added (datetime): The date when the resource was added.
        uploaded_by (UUID): The user ID who uploaded the resource.
    """
    id: UUID
    name: str
    resource_type: str
    species: str | None = None
    version: str | None = None
    file_path: str
    file_size: int | None = None
    date_added: datetime
    uploaded_by: UUID

    model_config = {
        "str_strip_whitespace": True,
        "from_attributes": True,
    }

# ------------------------------------------------------------------------------
# Species List Response Schema
# ------------------------------------------------------------------------------
class SpeciesListResponse(BaseModel):
    """
    Schema for returning a list of unique species names.
    
    Attributes:
        species (List[str]): A list of species names.
    """
    species: List[str]

    model_config = {
        "from_attributes": True,
    }




'''

Using Field in Pydantic models provides several benefits over defining default values directly in type hints. Let's break down the differences between the two implementations and understand when and why to use Field.

Differences between the two implementations:
1. First Implementation (without Field for most fields):
python
Copiar
Editar
class ResourceUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=100)]
    resource_type: Optional[Literal["GENOME", "ANNOTATION", "PEPTIDE"]]
    species: Optional[constr(min_length=1, max_length=50)]
    version: Optional[constr(min_length=1, max_length=50)]
    file_path: Optional[str]
    file_size: Optional[int] = Field(None, gt=0)
    updated_by: Optional[UUID] = None  # Make user_id optional for injection later  # Aligned with PostgreSQL schema

    class Config:
        str_strip_whitespace = True
Explanation:

constr(min_length=1, max_length=100) is used to apply validation constraints for string length.
Optional makes the field optional.
Default values are directly assigned using = None for optional fields.
Only file_size explicitly uses Field to set validation constraints beyond type checking (e.g., ensuring a positive value).
Pros:

Concise syntax for most fields.
Constraints like min_length and max_length are applied via constr() directly.
Readability is improved since there are fewer lines of code.
Cons:

Lacks detailed metadata descriptions for fields.
Doesn't allow setting more advanced constraints, such as custom titles, descriptions, regex, or example values.
2. Second Implementation (using Field for all fields):
python
Copiar
Editar
class ResourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    resource_type: Optional[constr(min_length=1, max_length=50)]
    species: Optional[str] = Field(None, min_length=1, max_length=50)
    version: Optional[str] = Field(None, min_length=1, max_length=50)
    uploaded_by: Optional[str] = Field(None, min_length=1, max_length=50)
    file_path: Optional[str]  # Optional in case file path doesn't need to be changed

    class Config:
        str_strip_whitespace = True  # Automatically strip whitespace from strings
Explanation:

The Field function is used to apply constraints directly within the type definition.
Default values like None are explicitly set inside Field.
Fields include constraints like min_length, max_length, or other validations within the Field function.
Pros:

More flexibility and control over field attributes.
Allows additional metadata such as:
title="Resource Name" → Adds a title for documentation purposes.
description="Enter resource name" → Provides detailed API documentation.
example="Human Genome Reference" → Provides an example value.
regex="^[A-Za-z0-9_]+$" → Ensures pattern matching.
Useful for auto-generated documentation (e.g., OpenAPI schema in FastAPI).
Consistency in how constraints are applied across fields.
'''

'''
Explanation of Changes and Alignments
resource_type Field Updated:

Changed to Literal to ensure only allowed values (GENOME, ANNOTATION, PEPTIDE) are accepted.
This aligns with the ORM definition where the enum is strictly defined.
file_size Validation:

Added a positive integer constraint to ensure only valid sizes are accepted.
Foreign Key for uploaded_by:

Changed to UUID to align with the ORM where it's a foreign key to the users table.
Alignment of Field Names:

Changed resource_id to id to maintain uniformity with the database schema.
Added Resource with Pipelines Relationship Schema:

The ResourceWithPipelineResponse schema includes an association with pipelines, reflecting the ORM relationship through secondary=pipeline_resources.
Config.from_attributes = True:

This is set to enable Pydantic to convert SQLAlchemy objects to JSON responses properly.
Example Usage of Schemas
1. Creating a Resource (POST Request Example):
Request Body (Frontend):

json
Copiar
Editar
{
    "name": "Human Genome Reference",
    "resource_type": "GENOME",
    "species": "Homo sapiens",
    "version": "hg38",
    "file_path": "/data/resources/hg38.fa",
    "file_size": 2500,
    "uploaded_by": "550e8400-e29b-41d4-a716-446655440000",
    "force_overwrite": false
}
2. Resource Update (PATCH Request Example):
Request Body (Frontend):

json
Copiar
Editar
{
    "version": "hg39",
    "file_size": 2600
}
3. Resource Response (API Response Example):
Response:

json
Copiar
Editar
{
    "id": "2d5e6c16-4e51-4b7d-9fd8-0a4df254f8b6",
    "name": "Human Genome Reference",
    "resource_type": "GENOME",
    "species": "Homo sapiens",
    "version": "hg38",
    "file_path": "/data/resources/hg38.fa",
    "file_size": 2500,
    "date_added": "2024-06-01T12:00:00Z",
    "uploaded_by": "550e8400-e29b-41d4-a716-446655440000"
}

'''


















'''
How This Maps to the Frontend
Frontend Input Forms:

For resource creation:
The frontend should provide name, resource_type, species, version, file_path, and uploaded_by.
Fields like resource_id and date_added are managed by the backend.
Form Validation:

Frontend frameworks (React, Vue, etc.) can implement validation based on Pydantic schema specifications.
Data Flow:

Frontend: User submits resource creation form.
Backend: Validates via ResourceCreate, stores data in DB.
Frontend: Receives ResourceResponse to confirm creation.

'''

'''

Explanation of Pydantic Models:
    BaseModel: All Pydantic models inherit from this.
    constr(): Constrains string length (e.g., min_length=1 ensures that empty strings are rejected).
    Optional[str]: Specifies that the field is optional during updates.
    Field(): Allows defining additional constraints such as length for Optional fields.

'''


'''

Explanation of Config in Pydantic
What is Config?
Config is a nested class in Pydantic models that allows customization of model behavior. It provides various attributes that control how data is validated, serialized, and integrated with other systems.

Applied Configurations
from_attributes = True:

Purpose: Enables compatibility with SQLAlchemy models.
Benefit: Allows Pydantic models to accept ORM objects (e.g., SQLAlchemy models) directly and convert them to the defined schema. This avoids manual conversion of SQLAlchemy objects to dictionaries.
Example:
python
Copiar
resource = session.query(Resource).first()
resource_response = ResourceResponse.from_orm(resource)
str_strip_whitespace = True:

Purpose: Automatically removes leading and trailing whitespaces from all string fields.
Benefit: Simplifies input validation by ensuring no unnecessary whitespace in user-provided fields.
Example:
python
Copiar
data = {"name": "   Genome Reference   "}
resource = ResourceCreate(**data)
print(resource.name)  # Output: "Genome Reference"
Impact of Enhancements
Consistency in Response:

Using orm_mode ensures consistent responses without additional transformation logic in API routes.
Cleaner Input Validation:

Automatically trimming whitespace reduces potential user errors and ensures clean data storage.
Simplified ORM Integration:

Direct integration of SQLAlchemy models with Pydantic response models speeds up development and minimizes boilerplate code.


'''