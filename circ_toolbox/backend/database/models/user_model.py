# circ_toolbox_project/circ_toolbox/backend/database/models/user.py
import fastapi_users_db_sqlalchemy 
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship
from circ_toolbox.backend.database.base import Base

# User model with custom fields for roles
class Users(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"  # Explicitly set the table name
    username = Column(String, nullable=False, unique=True)

    # ✅ FIX: Add relationship to `Resource`
    resources = relationship("Resource", back_populates="user", cascade="all, delete-orphan")
    pipelines = relationship("Pipeline", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(username={self.username})>"
    

        # srr_resources = relationship("SRRResource", back_populates="user", cascade="all, delete-orphan")
    # bioprojects = relationship("BioProject", back_populates="owner", cascade="all, delete-orphan")

'''

Relationships (To be added):
If necessary, you can add a relationship in the Users model to reference resources uploaded by the user:

python
Copiar
Editar
from sqlalchemy.orm import relationship

class Users(SQLAlchemyBaseUserTableUUID, Base):
    username = Column(String, nullable=False, unique=True)
    resources = relationship("Resource", back_populates="user", cascade="all, delete-orphan")
And update Resource model with:

python
Copiar
Editar
user = relationship("Users", back_populates="resources")

'''

'''
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4

class User(SQLAlchemyBaseUserTableUUID, Base):
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    username = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)

'''