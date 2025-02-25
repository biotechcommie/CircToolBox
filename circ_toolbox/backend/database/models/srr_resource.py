# circ_toolbox_project/circ_toolbox/backend/database/models/srr_resource.py
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, CheckConstraint, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from circ_toolbox.backend.database.base import Base
from sqlalchemy.dialects.postgresql import UUID
import uuid

class SRRResource(Base):
    __tablename__ = 'srr_resources'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bioproject_id = Column(String, ForeignKey("bioprojects.bioproject_id"), nullable=False, index=True)
    description = Column(Text, nullable=False, default="No description provided")
    srr_id = Column(String, unique=True, nullable=False, index=True)
    file_path = Column(Text, nullable=False, index=True)  # Use Text for potentially long file paths
    file_size = Column(Integer, nullable=False, default=0)
    date_added = Column(DateTime, default=datetime.utcnow)
    status = Column(
        String(15),
        CheckConstraint("status IN ('registered', 'downloaded', 'failed')"),
        nullable=False,
        default="registered"
    )

    # Relationship
    bioproject = relationship("BioProject", back_populates="srr_resources")

    def __repr__(self):
        return f"<SRRResource(id={self.id}, srr_id='{self.srr_id}', status='{self.status}')>"

    # uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


'''
Consider adding comment="description" to columns for better database documentation.
'''

'''

Improvements:

Enum for statuses: Instead of raw String with CheckConstraint, consider using Python's enum.Enum for statuses (registered, downloaded, failed) and mapping it.
python
Copiar código
from sqlalchemy import Enum

class SRRStatusEnum(enum.Enum):
    registered = "registered"
    downloaded = "downloaded"
    failed = "failed"

status = Column(Enum(SRRStatusEnum), default=SRRStatusEnum.registered)
SQLAlchemy's new-style annotations:

You can use Mapped[] and type hints for better IDE support and maintainability:
python
Copiar código
from sqlalchemy.orm import Mapped

id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

RESOURCE_ROOT_PATH = os.path.join(os.path.dirname(__file__), 'resources')  # Root folder for resource files

'''