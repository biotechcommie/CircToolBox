# circ_toolbox_project/circ_toolbox/backend/database/models/resource.py
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from circ_toolbox.backend.database.base import Base
from circ_toolbox.backend.database.models.association_tables import pipeline_resources
import uuid


class Resource(Base):
    __tablename__ = 'resources'
    __table_args__ = (Index("idx_resource_type", "resource_type"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    resource_type = Column(Enum("GENOME", "ANNOTATION", "PEPTIDE", name="resource_type_enum"), nullable=False)  
    species = Column(String, nullable=True)
    version = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)  # File size in MB
    date_added = Column(DateTime, default=datetime.utcnow)
    
    # Foreign Key to link uploaded resource to a user
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    user = relationship("Users", back_populates="resources")
    pipelines = relationship("Pipeline", secondary=pipeline_resources, back_populates="resources")

    def __repr__(self):
        return f"<Resource(name={self.name}, type={self.resource_type}, version={self.version})>"




'''
Explanation of Changes and Improvements:
UUID Primary Key:

Changed id to a UUID-based primary key for consistency with the rest of the database structure.
Ensures global uniqueness across distributed environments.
Enum for resource_type:

Introduced an Enum for resource_type to enforce allowed values (GENOME, ANNOTATION, PEPTIDE).
Provides better data integrity and easier querying.
Nullable Fields:

Made species, version, and file_size optional as they may not always be relevant for every resource.
Foreign Key Correction:

Corrected user_id to uploaded_by and pointed to users.id for consistency.
Ensures proper ownership tracking and cascading deletions.
Relationship with Pipelines:

Included pipelines = relationship("Pipeline", secondary=pipeline_resources, back_populates="resources") to create a many-to-many relationship with pipelines.
Links the association table pipeline_resources from the pipeline_run model.
Relationship with User:

Added user = relationship("User", back_populates="resources") to allow resource access through the user relationship.
Enables querying like user.resources.
Default File Size Storage:

file_size in MB ensures proper tracking of resource storage usage.




Here's an improved and aligned version of the Resource model that correctly integrates relationships with the Pipeline model while ensuring foreign keys and data consistency.

Updated Resource Model:
python
Copiar
Editar
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from circ_toolbox.backend.database.base import Base
from circ_toolbox.backend.database.models.pipeline_run import pipeline_resources  # Import association table

class Resource(Base):
    __tablename__ = 'resources'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    resource_type = Column(Enum("GENOME", "ANNOTATION", "PEPTIDE", name="resource_type_enum"), nullable=False)  
    species = Column(String, nullable=True)
    version = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)  # File size in MB
    date_added = Column(DateTime, default=datetime.utcnow)
    
    # Foreign Key to link uploaded resource to a user
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    user = relationship("User", back_populates="resources")
    pipelines = relationship("Pipeline", secondary=pipeline_resources, back_populates="resources")

    def __repr__(self):
        return f"<Resource(name={self.name}, type={self.resource_type}, version={self.version})>"
Explanation of Changes and Improvements:
UUID Primary Key:

Changed id to a UUID-based primary key for consistency with the rest of the database structure.
Ensures global uniqueness across distributed environments.
Enum for resource_type:

Introduced an Enum for resource_type to enforce allowed values (GENOME, ANNOTATION, PEPTIDE).
Provides better data integrity and easier querying.
Nullable Fields:

Made species, version, and file_size optional as they may not always be relevant for every resource.
Foreign Key Correction:

Corrected user_id to uploaded_by and pointed to users.id for consistency.
Ensures proper ownership tracking and cascading deletions.
Relationship with Pipelines:

Included pipelines = relationship("Pipeline", secondary=pipeline_resources, back_populates="resources") to create a many-to-many relationship with pipelines.
Links the association table pipeline_resources from the pipeline_run model.
Relationship with User:

Added user = relationship("User", back_populates="resources") to allow resource access through the user relationship.
Enables querying like user.resources.
Default File Size Storage:

file_size in MB ensures proper tracking of resource storage usage.
Example Usage with SQLAlchemy ORM:
python
Copiar
Editar
from circ_toolbox.backend.database.models.resource import Resource
from circ_toolbox.backend.database.models.pipeline_run import Pipeline
from uuid import uuid4

# Example: Creating a new resource
new_resource = Resource(
    id=uuid4(),
    name="Human Genome Reference",
    resource_type="GENOME",
    species="Homo sapiens",
    version="GRCh38",
    file_path="/data/genomes/human_grch38.fasta",
    file_size=1500,
    uploaded_by=uuid4()
)

session.add(new_resource)
session.commit()

# Example: Querying a resource and its pipelines
resource = session.query(Resource).filter_by(name="Human Genome Reference").first()
print(resource.pipelines)  # List of associated pipelines
Alignment with Pipeline Model:
Since the pipeline_resources association table is imported from the pipeline_run model, everything is kept consistent, and the relationship is now well-established.

In Pipeline model:

python
Copiar
Editar
# Already included relationship in Pipeline
resources = relationship("Resource", secondary=pipeline_resources, back_populates="pipelines")
Potential Enhancements:
Indexing:

Consider adding an index on frequently queried fields like resource_type and uploaded_by for performance improvement.
python
Copiar
Editar
__table_args__ = (Index("idx_resource_type", "resource_type"),)
Soft Deletion:

Add a deleted_at field to allow soft deletion instead of permanent removal.

'''










'''

from sqlalchemy.dialects.postgresql import UUID
import uuid

user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, default=uuid.uuid4)



Note: If you're using SQLite, it doesn't support native UUID fields like PostgreSQL does, so you should use a string-based representation:

python
Copiar
Editar
from sqlalchemy import String
import uuid

user_id = Column(String(36), ForeignKey("user.id"), nullable=False, default=lambda: str(uuid.uuid4()))

'''