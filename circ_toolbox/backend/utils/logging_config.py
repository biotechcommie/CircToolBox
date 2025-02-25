# circ_toolbox/backend/utils/logging_config.py
import logging
import logging.config
import yaml
import os
from functools import wraps
from datetime import datetime
from circ_toolbox.config import LOG_DIR, LOG_CONFIG_PATH
import asyncio



def setup_logging(user_id=None, run_id=None):
    """
    Setup logging configuration dynamically.
    If user_id and run_id are provided, logs will be placed in specific folders.
    """

    if not os.path.exists(LOG_CONFIG_PATH):
        raise FileNotFoundError(f"Logging configuration file not found at {LOG_CONFIG_PATH}")

    with open(LOG_CONFIG_PATH, "r") as f:
        logging_config = yaml.safe_load(f)

    # Generate dynamic log directory
    subfolder = f"user_{user_id}/run_{run_id}" if user_id and run_id else "general"
    log_folder = os.path.join(LOG_DIR, subfolder)
    os.makedirs(log_folder, exist_ok=True)

    # Update log file paths dynamically
    for handler_name, handler in logging_config["handlers"].items():
        if "filename" in handler:
            handler["filename"] = os.path.join(log_folder, os.path.basename(handler["filename"]))

    logging.config.dictConfig(logging_config)
    logging.getLogger("app").info(f"Logging configured for subfolder: {subfolder}")
    
    logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)


def get_logger(name):
    """
    Get a logger instance.
    """
    return logging.getLogger(name)


def OLD_log_runtime(logger_name):
    """
    Decorator to log the runtime of functions.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name)
            start_time = datetime.now()
            logger.info(f"Starting {func.__name__}")
            try:
                result = func(*args, **kwargs)
                logger.info(f"Completed {func.__name__} in {datetime.now() - start_time}")
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                raise
        return wrapper
    return decorator


def log_runtime(logger_name):
    def decorator(func):
        logger = get_logger(logger_name)
        is_async_func = asyncio.iscoroutinefunction(func)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = datetime.now()
            logger.info(f"Starting {func.__name__}")
            try:
                result = await func(*args, **kwargs)
                end_time = datetime.now()
                logger.info(f"Completed {func.__name__} in {end_time - start_time}")
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = datetime.now()
            logger.info(f"Starting {func.__name__}")
            try:
                result = func(*args, **kwargs)
                end_time = datetime.now()
                logger.info(f"Completed {func.__name__} in {end_time - start_time}")
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                raise

        return async_wrapper if is_async_func else sync_wrapper
    return decorator

'''

from circ_toolbox.backend.utils.logging_config import get_logger, log_runtime

logger = get_logger("resource_service")

@log_runtime("resource_service")
def process_resource(data):
    try:
        logger.debug("Processing resource data...")
        # Some processing
        logger.info("Resource processed successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to process resource: {e}")
        raise


'''
'''

# Paths for logging
LOG_DIR = os.path.join(BASE_DIR, "log")
LOG_CONFIG_PATH = os.path.join(BASE_DIR, "config", "logging_config.yaml")

# Ensure log directories exist
os.makedirs(LOG_DIR, exist_ok=True)



'''