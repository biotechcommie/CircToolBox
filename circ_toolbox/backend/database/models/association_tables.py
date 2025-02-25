# circ_toolbox/backend/database/models/association_tables.py
from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from circ_toolbox.backend.database.base import Base

# -------------------------------------------
# Resource Association Table
# -------------------------------------------

pipeline_resources = Table(
    "pipeline_resources",
    Base.metadata,
    Column("pipeline_id", UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), primary_key=True),
    Column("resource_id", UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
)

