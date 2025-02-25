# circ_toolbox_project/circ_toolbox/backend/api/schemas/bioproject_schemas.py
from pydantic import BaseModel, constr
from datetime import datetime
from typing import List, Optional
from uuid import UUID


# Schema for creating a new BioProject
class BioProjectCreate(BaseModel):
    bioproject_id: constr(min_length=1, max_length=50)
    description: constr(min_length=5, max_length=500) = "No description provided"

    model_config = {
        "str_strip_whitespace": True,
    }




# Schema for updating a BioProject
class BioProjectUpdate(BaseModel):
    description: Optional[constr(min_length=5, max_length=500)] = None


# Schema for response of BioProject
class BioProjectResponse(BaseModel):
    id: UUID
    bioproject_id: str
    description: str
    date_added: datetime
    srr_resources: List["SRRResourceResponse"]  # Use string for forward declaration -> NOT # List[SRRResourceResponse]  # Nested resources

    model_config = {
        "from_attributes": True
    }



# Register the forward references at runtime to avoid import issues
from circ_toolbox.backend.api.schemas.srr_resource_schemas import SRRResourceResponse
BioProjectResponse.update_forward_refs()