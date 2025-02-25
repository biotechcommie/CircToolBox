# circ_toolbox_project/circ_toolbox/backend/api/schemas/srr_resource_schemas.py
from pydantic import BaseModel, constr, Field
from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

# Schema for creating a new SRR resource
class SRRResourceCreate(BaseModel):
    bioproject_id: constr(min_length=1, max_length=50)
    srr_id: constr(min_length=1, max_length=50)
    file_path: str
    file_size: Optional[int] = Field(default=0, ge=0)
    status: Optional[Literal["registered", "downloaded", "failed"]] = "registered"
    date_added: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "str_strip_whitespace": True
    }



# Schema for updating an SRR resource (partial update)
class SRRResourceUpdate(BaseModel):
    file_path: Optional[str] = None
    file_size: Optional[int] = Field(None, ge=0)
    status: Optional[Literal["registered", "downloaded", "failed"]] = "registered"


# Schema for response of SRR resource
class SRRResourceResponse(BaseModel):
    id: int
    bioproject_id: str
    srr_id: str
    file_path: str
    file_size: int
    date_added: datetime
    status: Optional[Literal["registered", "downloaded", "failed"]] = "registered"

    model_config = {
        "from_attributes": True
    }

