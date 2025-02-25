# circ_toolbox_project/circ_toolbox/backend/database/models/bioproject.py
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from circ_toolbox.backend.database.base import Base
from sqlalchemy.dialects.postgresql import UUID
import uuid

class BioProject(Base):
    __tablename__ = 'bioprojects'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bioproject_id = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)
    date_added = Column(DateTime, default=datetime.utcnow)

    # Back-populates relationship with SRRResource
    srr_resources = relationship("SRRResource", back_populates="bioproject", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BioProject(id={self.id}, bioproject_id='{self.bioproject_id}', description='{self.description}')>"





    # owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
