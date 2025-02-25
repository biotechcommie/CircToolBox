# circ_toolbox/backend/utils/config_loader.py
import os
import yaml
from circ_toolbox.backend.utils.logging_config import get_logger
from circ_toolbox.config import BASE_DIR

# Get logger instance
logger = get_logger("config_loader")

CONFIG_DIR = os.path.join(BASE_DIR, "config")

def load_default_config(class_name, default_fallback=None, overrides=None):
    """
    Load default configuration values for a specific class or operation.
    Supports environment-specific configurations and overrides.

    Args:
        class_name (str): The name of the class or operation.
        overrides (dict): Optional overrides for configuration.

    Returns:
        dict: Default configuration values with optional overrides applied.
    """


    env = os.getenv("APP_ENV", "development")
    config_file = os.path.join(CONFIG_DIR, f"{env}_config.yaml")

    if not os.path.exists(config_file):
        logger.warning(f"Environment-specific config {config_file} not found. Using default_config.yaml.")
        config_file = os.path.join(CONFIG_DIR, "default_config.yaml")
        if not os.path.exists(config_file):
            logger.warning(f"Config file {config_file} not found. Using provided defaults.")

    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to load configuration file {config_file}: {e}")
        config = {}

    # Load class-specific configuration from YAML and apply defaults
    yaml_values = config.get(class_name, {})
    final_config = {**(default_fallback or {}), **yaml_values, **(overrides or {})}

    logger.info(f"Loaded configuration for '{class_name}' with fallbacks: {final_config}")
    return final_config


'''

 Ensure Correct YAML Files:
default_config.yaml (used as a fallback if no environment-specific YAML is found):

yaml
Copiar código
SRRService:
  fasterq_dump_threads: 2
  compression_threads: 2
  max_retries: 3
  retry_wait_time: 5
  keep_uncompressed: false
  temp_directory: "temp"
  compact_directory: "COMPACT"
development_config.yaml:

yaml
Copiar código
SRRService:
  fasterq_dump_threads: 4
  compression_threads: 4
  max_retries: 5
  retry_wait_time: 10
  keep_uncompressed: true
  temp_directory: "dev_temp"
  compact_directory: "DEV_COMPACT"
production_config.yaml:

yaml
Copiar código
SRRService:
  fasterq_dump_threads: 8
  compression_threads: 4
  max_retries: 5
  retry_wait_time: 15
  keep_uncompressed: false
  temp_directory: "prod_temp"
  compact_directory: "PROD_COMPACT"

  
export APP_ENV=production  # or development

'''


