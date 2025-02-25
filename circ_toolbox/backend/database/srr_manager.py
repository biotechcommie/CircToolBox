# circ_toolbox_project/circ_toolbox/backend/database/srr_manager.py
import os
from datetime import datetime
from sqlalchemy.orm import Session
from circ_toolbox.backend.database.models.bioproject import BioProject
from circ_toolbox.backend.database.models.srr_resource import SRRResource
from circ_toolbox.backend.utils.logging_config import get_logger, log_runtime
from circ_toolbox.backend.database.base_sync import get_sync_session  # This should return a sync Session


class SRRManager:
    """
    SRRManager handles database operations for BioProjects and SRR Resources.
    This class abstracts the logic for registering BioProjects and SRR entries,
    querying paths, and checking data completeness.
    """

    def __init__(self, session: Session = None):
        """
        Initialize SRRManager with a database session.

        Args:
            session (Session): SQLAlchemy session for database interactions.
        """
        self.session = session
        self.logger = get_logger(self.__class__.__name__)

    # ===========================
    # INTERNAL SESSION HANDLING
    # ===========================
    @log_runtime("sync_manager")
    def _get_session(self, session: Session = None) -> tuple[Session, bool]:
        """
        Retrieves an active database session for execution.

        This method determines the session handling logic as follows:
        - If a session is provided as an argument, it is reused, and `close_session` is set to False.
        - If the manager instance already has a session (passed via constructor), 
            it is reused, and `close_session` is set to False.
        - If no session is provided, a new synchronous session is created using `get_sync_session()`,
            and `close_session` is set to True.

        Args:
            session (Optional[Session]): An externally provided SQLAlchemy session.
                                        If None, attempts to use the manager’s instance session 
                                        or create a new one.

        Returns:
            tuple[Session, bool]: A tuple containing:
                - The active SQLAlchemy session.
                - A boolean indicating whether the session should be closed after use 
                (`True` if created internally, `False` otherwise).
        """
        if session:
            return session, False  # Externally provided session, do not close
        elif self.session:
            return self.session, False  # Constructor-provided session, do not close
        else:
            new_session = get_sync_session()
            return new_session, True  # Internally created session, must be closed after use

        
    @log_runtime("SRRManager")
    def register_bioproject(self, bioproject_id: str, description: str = "", session: Session = None) -> BioProject:
        """
        Registers a new BioProject in the database if it doesn't exist.

        Args:
            bioproject_id (str): The unique ID of the BioProject.
            description (str, optional): Description of the BioProject. Defaults to "".

        Raises:
            Exception: If any database error occurs.
        """
        session, close_session = self._get_session(session)

        if not bioproject_id:
            raise ValueError("BioProject ID cannot be empty.")

        try:
            # Check if the BioProject already exists
            existing_bioproject = session.query(BioProject).filter_by(bioproject_id=bioproject_id).first()
            if existing_bioproject:
                self.logger.info(f"BioProject '{bioproject_id}' already exists.")
                return existing_bioproject
            
            bioproject = BioProject(
                bioproject_id=bioproject_id,
                description=description,
            )
            
            session.add(bioproject)
            session.commit()
            self.logger.info(f"BioProject '{bioproject_id}' registered successfully.")
            
            return bioproject
        
        except ValueError as ve:
            session.rollback()
            self.logger.error("BioProject ID cannot be empty.")
            raise ve
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error registering BioProject '{bioproject_id}': {e}")
        finally:
            if close_session:
                session.close()

    @log_runtime("SRRManager")
    def register_srr(self, bioproject_id: str, srr_id: str, file_path: str, description: str = "", session: Session = None) -> SRRResource:
        """
        Registers a new SRR entry in the database.

        Args:
            bioproject_id (str): The ID of the associated BioProject.
            srr_id (str): The unique SRR ID.
            file_path (str): The local file path of the SRR file.
            description (str): Description of the BioProject (optional).

        Raises:
            FileNotFoundError: If the file_path does not exist.
            ValueError: If the SRR ID is empty.
        """
        session, close_session = self._get_session(session)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File '{file_path}' not found.")
        if not srr_id:
            raise ValueError("SRR ID cannot be empty.")

        try:
            # Ensure the BioProject exists or create a new one
            bioproject = self.register_bioproject(bioproject_id, description, session)

            existing_srr = session.query(SRRResource).filter_by(srr_id=srr_id).first()
            if existing_srr:
                self.logger.info(f"SRR '{srr_id}' already exists in the database.")
                return existing_srr

            srr_resource = SRRResource(
                bioproject_id=bioproject_id,
                srr_id=srr_id,
                file_path=file_path,
                file_size=os.path.getsize(file_path),
                status="registered"
            )
            session.add(srr_resource)
            session.commit()
            self.logger.info(f"SRR '{srr_id}' registered successfully.")
            
            return srr_resource
        except ValueError as ve:
            session.rollback()
            self.logger.error(f"Invalid value for SRR ID '{srr_id}': {e}")
            raise ve                 
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error registering SRR '{srr_id}': {e}")
            raise e
        finally:
            if close_session:
                session.close()

    @log_runtime("SRRManager")
    def get_srr_path(self, srr_id: str, session: Session = None) -> str:
        """
        Retrieves the file path for a given SRR ID.

        Args:
            srr_id (str): The SRR ID.

        Returns:
            str: The file path if found, otherwise None.
        """
        session, close_session = self._get_session(session)
        
        try:
            srr = session.query(SRRResource).filter_by(srr_id=srr_id).first()
            if srr:
                self.logger.info(f"Retrieved file path for SRR ID '{srr_id}': {srr.file_path}")
                return srr.file_path
            else:
                self.logger.info(f"No file path found for SRR ID '{srr_id}'.")
                return None
            
        except Exception as e:
            self.logger.error(f"Error retrieving file path for SRR ID '{srr_id}': {e}")
            return None
        finally:
            if close_session:
                session.close()

    @log_runtime("SRRManager")
    def list_srrs(self, bioproject_id: str = None, session: Session = None) -> list[SRRResource]:
        """
        Lists all SRR resources, optionally filtered by BioProject ID.

        Args:
            bioproject_id (str, optional): BioProject ID to filter SRRs. Defaults to None.

        Returns:
            list[SRRResource]: List of SRRResource objects.
        """
        session, close_session = self._get_session(session)

        try:
            query = session.query(SRRResource)
            if bioproject_id:
                query = query.filter_by(bioproject_id=bioproject_id)
            srr_list = query.all()
            self.logger.info(f"Listed {len(srr_list)} SRRs for BioProject '{bioproject_id}'" if bioproject_id else f"Listed {len(srr_list)} SRRs.")
            return srr_list
        
        except Exception as e:
            self.logger.error(f"Error listing SRRs for BioProject '{bioproject_id}': {e}")
            return []
        finally:
            if close_session:
                session.close()


    @log_runtime("SRRManager")
    def check_bioproject_completeness(self, bioproject_id: str, srr_list: list[str], session: Session = None) -> dict:
        """
        Checks completeness of SRR entries for a given BioProject.

        Args:
            bioproject_id (str): The ID of the BioProject.
            srr_list (list[str]): List of SRR IDs expected for the BioProject.

        Returns:
            dict: A dictionary containing registered and missing SRR IDs.
                {
                    "registered": [list of registered SRR IDs],
                    "missing": [list of missing SRR IDs]
                }
        """
        session, close_session = self._get_session(session)

        try:
            registered_srrs = {srr.srr_id for srr in self.list_srrs(bioproject_id, session)}
            requested_srrs = set(srr_list)
            missing_srrs = requested_srrs - registered_srrs

            completeness = {
                "registered": list(registered_srrs),
                "missing": list(missing_srrs)
            }
            self.logger.info(f"BioProject '{bioproject_id}': {len(completeness['registered'])} registered, {len(completeness['missing'])} missing.")
            return completeness
        
        except Exception as e:
            self.logger.error(f"Error checking completeness for BioProject '{bioproject_id}': {e}")
            return {"registered": [], "missing": srr_list}
        finally:
            if close_session:
                session.close()

    @log_runtime("SRRManager")
    def delete_srr(self, srr_id: str, session: Session = None) -> bool:
        """
        Deletes an SRR entry from the database and removes the file if it exists.

        Args:
            srr_id (str): The SRR ID to delete.

        Returns:
            bool: True if the deletion was successful, False otherwise.
        """
        session, close_session = self._get_session(session)

        try:
            srr = session.query(SRRResource).filter_by(srr_id=srr_id).first()
            if not srr:
                self.logger.info(f"SRR ID '{srr_id}' not found in the database.")
                return False

            if os.path.exists(srr.file_path):
                os.remove(srr.file_path)
                self.logger.info(f"File '{srr.file_path}' deleted from file system.")

            session.delete(srr)
            session.commit()
            self.logger.info(f"SRR '{srr_id}' deleted successfully.")
            return True
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error deleting SRR '{srr_id}': {e}")
            return False
        finally:
            if close_session:
                session.close()

'''
        entity = ''

        session, close_session = self._get_session(session)

        try:
            # Database Operations (INSERT, UPDATE, DELETE)
            session.add(entity)
            session.commit()
            session.refresh(entity)
            return entity

        except Exception as e:
            session.rollback()
            self.logger.error(f"Error: {e}")
            raise

        finally:
            if close_session:
                session.close()
'''

'''


'''

'''

Enhancements Made:
Exception Handling: Proper use of try/except blocks with session.rollback() for safe database operations.
Detailed Documentation: Added docstrings for each method.
Type Hints: Used Python type hints for function arguments and return types to improve readability.
Validation Checks:
Added validation for empty SRR IDs and missing file paths.
Checked if BioProjects and SRRs already exist before insertion.
New delete_srr Method: Added a method to delete an SRR entry and its associated file from the system.
How to Use SRRManager:
1. Instantiate with a session:
python
Copiar código
from backend.database.base import get_session
from backend.database.srr_manager import SRRManager

# Get a new database session
session = get_session()
srr_manager = SRRManager(session)
2. Register a BioProject:
python
Copiar código
srr_manager.register_bioproject("PRJNA12345", "Example BioProject")
3. Register an SRR:
python
Copiar código
srr_manager.register_srr("PRJNA12345", "SRR123456", "/path/to/SRR123456.fastq.gz")
4. Check completeness:
python
Copiar código
completeness = srr_manager.check_bioproject_completeness("PRJNA12345", ["SRR123456", "SRR654321"])
print(completeness)
This design cleanly separates database logic (SRRManager) from the business logic (service layer), making the application maintainable and easier to expand.

'''