from abc import ABC
from circ_toolbox.backend.utils import get_logger

class BasePipelineTool(ABC):
    """
    Abstract base class for pipeline tools with built-in logging support.
    """
    def __init__(self, logger_name: str):
        """
        Initialize the base class with a logger instance.
        
        Args:
            logger_name (str): Name of the logger to use.
        """
        self.logger = get_logger(logger_name)

    def log_start(self, operation_name: str):
        """Log the start of an operation."""
        self.logger.info(f"Starting {operation_name}...")

    def log_end(self, operation_name: str):
        """Log the end of an operation."""
        self.logger.info(f"Completed {operation_name}.")
