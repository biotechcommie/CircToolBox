# circ_toolbox_project/circ_toolbox/backend/database/models/pipeline_run.py
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Text, JSON, Table, Integer, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from circ_toolbox.backend.database.base import Base
from circ_toolbox.backend.database.models.association_tables import pipeline_resources

import uuid



# -------------------------------------------
# Pipeline ORM Model
# -------------------------------------------

class Pipeline(Base):
    __tablename__ = 'pipelines'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_name = Column(String(100), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum("pending", "running", "completed", "failed", name="pipeline_status"), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    steps = relationship("PipelineStep", back_populates="pipeline", cascade="all, delete-orphan")
    configurations = relationship("PipelineConfig", back_populates="pipeline", cascade="all, delete-orphan")
    user = relationship("Users", back_populates="pipelines")
    #executions = relationship("Execution", back_populates="pipeline", cascade="all, delete-orphan")

    resources = relationship("Resource", secondary=pipeline_resources, back_populates="pipelines")

    def __repr__(self):
        return f"<Pipeline(name={self.pipeline_name}, status={self.status})>"


# -------------------------------------------
# Pipeline Step ORM Model
# -------------------------------------------

class PipelineStep(Base):
    __tablename__ = "pipeline_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"))
    step_name = Column(String(100), nullable=False)
    parameters = Column(JSON, nullable=False)
    requires_input_file = Column(Boolean, nullable=False)  # ✅ FIXED: Changed from String to Boolean
    input_files = Column(JSON, nullable=True)
    status = Column(Enum("pending", "running", "completed", "failed", name="step_status"), default="pending")
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    results = Column(JSON, nullable=True)
    input_mapping = Column(JSON, nullable=True)  # New field: maps input keys to dependency step names.
    
    # Relationships
    pipeline = relationship("Pipeline", back_populates="steps")
    #executions = relationship("StepExecution", back_populates="pipeline_step", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PipelineStep(name={self.step_name}, status={self.status})>"


# -------------------------------------------
# Pipeline Configuration ORM Model
# -------------------------------------------

class PipelineConfig(Base):
    __tablename__ = "pipeline_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"))
    config_type = Column(Enum("initial", "final", name="config_type_enum"), nullable=False)
    config_data = Column(JSON, nullable=False)
    config_file_path = Column(String, nullable=False)
    date_added = Column(DateTime, default=datetime.utcnow)

    # Relationships
    pipeline = relationship("Pipeline", back_populates="configurations")

    def __repr__(self):
        return f"<PipelineConfig(type={self.config_type})>"


# -------------------------------------------
# Monitoring and Logs ORM Model
# -------------------------------------------

class PipelineLog(Base):
    __tablename__ = "pipeline_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"))
    step_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_steps.id", ondelete="CASCADE"))
    logs = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PipelineLog(step_id={self.step_id})>"
    




'''

Key Considerations for Each Model:
1. Pipeline Table
user_id: Foreign key that links to the User model (not included here but assumed to exist).
status: Enum field to restrict pipeline status values.
steps and configurations: Relationships to related tables.
created_at: Automatically populated timestamp.
2. PipelineStep Table
parameters: Stored as a JSON object.
input_files: Stored as JSON to accommodate different input formats.
status: Enum to track step progression.
result_file_path: Path where the step output is stored.
3. Resource Association
Many-to-many relationship between pipelines and resources.
4. PipelineConfig Table
config_data: JSON field to store arbitrary configuration data.
config_type: Enum for initial or final configurations.
date_added: Timestamp to track changes.
5. PipelineLog Table
Tracks logs related to each step.




class PipelineResource(Base):
    __tablename__ = "pipeline_resources"

    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), primary_key=True)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    pipeline = relationship("Pipeline", back_populates="resources")
    resource = relationship("Resource", back_populates="pipelines")



'''

















'''
Accessing the Configurations:

To get the initial and final configurations, you can filter based on config_type:

initial_config = next((cfg for cfg in pipeline_run.configs if cfg.config_type == 'initial'), None)
final_config = next((cfg for cfg in pipeline_run.configs if cfg.config_type == 'final'), None)

'''
'''

Where to Save the Pipeline and Step Information?
Pipeline Metadata (PipelineRun): Should be handled by the pipeline_runner at the start of the pipeline and updated at the end.
Pipeline Steps (PipelineStep): Should be handled within each orchestrator (e.g., srr_orchestrator) to register the step start, end, status, and outputs.
Configurations (PipelineConfig): Should be saved at relevant points, e.g., initial and final configs.
By separating these responsibilities:

The pipeline_runner handles overall pipeline-level metadata and execution.
The orchestrators handle step-specific metadata and output trackin

'''