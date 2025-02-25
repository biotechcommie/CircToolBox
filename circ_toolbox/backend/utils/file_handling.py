# circ_toolbox/backend/utils/file_handling.py

from circ_toolbox.config import RESOURCE_DIR
import os
import json
import shutil
from uuid import UUID
import aiofiles
from circ_toolbox.config import USER_OUTPUT_DIR
import re
import unicodedata

def sanitize_filename(filename: str) -> str:
    """
    Sanitize the filename by removing unsafe characters and replacing spaces with underscores.

    Args:
        filename (str): The original filename.

    Returns:
        str: A safe version of the filename.
    """
    # Normalize Unicode characters to ASCII
    filename = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")
    # Replace spaces with underscores
    filename = filename.replace(" ", "_")
    # Remove any character that is not alphanumeric, a dot, underscore or hyphen
    filename = re.sub(r"(?u)[^-\w.]", "", filename)
    return filename

def copy_file_to_storage(
    src_file_path: str,
    original_filename: str,
    resource_type: str,
    species: str,
    version: str,
    force_overwrite: bool = False
) -> str:
    """
    Synchronously copies the file from src_file_path to the designated resource directory.
    
    Args:
        src_file_path (str): The source file path.
        original_filename (str): The original file name.
        resource_type (str): The type/category of the resource.
        species (str): The species associated with the resource.
        version (str): The version of the resource.
        force_overwrite (bool): If True, overwrite the file if it exists.
    
    Returns:
        str: The destination file path.
    
    Raises:
        FileNotFoundError: If src_file_path does not exist.
    """
    if not os.path.exists(src_file_path):
        raise FileNotFoundError(f"Source file '{src_file_path}' does not exist.")

    # Create the destination directory
    dest_dir = os.path.join(RESOURCE_DIR, resource_type, species, version)
    os.makedirs(dest_dir, exist_ok=True)

    # Sanitize filename and construct final path
    safe_filename = sanitize_filename(original_filename)
    dest_path = os.path.join(dest_dir, safe_filename)

    # If file exists and overwrite is False, skip
    if os.path.exists(dest_path) and not force_overwrite:
        print(f"File '{dest_path}' already exists. Skipping copy.")
        return dest_path

    # Perform the file copy
    shutil.copy2(src_file_path, dest_path)
    print(f"File copied to '{dest_path}'")
    return dest_path



async def async_copy_file_to_storage(
    src_file_path: str,
    original_filename: str,
    resource_type: str,
    species: str,
    version: str,
    force_overwrite: bool = False
) -> str:
    """
    Asynchronously copies the file from src_file_path to the designated resource directory.
    
    Args:
        src_file_path (str): The source file path.
        original_filename (str): The original file name.
        resource_type (str): The type/category of the resource.
        species (str): The species associated with the resource.
        version (str): The version of the resource.
        force_overwrite (bool): If True, overwrite the file if it exists.
    
    Returns:
        str: The destination file path.
    
    Raises:
        FileNotFoundError: If src_file_path does not exist.
    """
    if not os.path.exists(src_file_path):
        raise FileNotFoundError(f"Source file '{src_file_path}' does not exist.")

    # Create the destination directory structure.
    dest_dir = os.path.join(RESOURCE_DIR, resource_type, species, version)
    os.makedirs(dest_dir, exist_ok=True)

    # Instead of using os.path.basename(src_file_path), we need to get the original filename.
    # Assume that you have access to the original filename (passed via the UploadFile instance)
    # Here, we will simulate that by extracting it from the source file path if available.
    # Ideally, the service should also receive the original filename.
    fallback_name = os.path.basename(src_file_path)  # Fallback; you'll override it below.
    
    # You might pass the original filename separately or extract it earlier.
    # For example, if you modify async_copy_and_save_file to also accept file.filename, then:
    # original_filename = sanitize_filename(file.filename)
    
    # For now, we'll assume that the original filename is stored in a global variable
    # or passed in (this needs to be integrated with your UploadFile handling logic).
    # For demonstration, let's simulate it:
    safe_filename = sanitize_filename(original_filename)
    
    dest_path = os.path.join(dest_dir, safe_filename)

    # If the file already exists and we are not forcing an overwrite, skip copying.
    if os.path.exists(dest_path) and not force_overwrite:
        print(f"File '{dest_path}' already exists. Skipping copy.")
        return dest_path

    # Open the source and destination files asynchronously and copy in chunks.
    async with aiofiles.open(src_file_path, 'rb') as src_file:
        async with aiofiles.open(dest_path, 'wb') as dest_file:
            while True:
                chunk = await src_file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                await dest_file.write(chunk)
    print(f"File copied to '{dest_path}'")
    return dest_path

def get_pipeline_storage_path(user_id: UUID, pipeline_id: UUID) -> str:
    """
    Returns the base storage path for a specific user's pipeline.

    Args:
        user_id (UUID): Unique identifier for the user.
        pipeline_id (UUID): Unique identifier for the pipeline.

    Returns:
        str: The directory path where all pipeline-related files will be stored.
    """
    pipeline_path = os.path.join(USER_OUTPUT_DIR, str(user_id), str(pipeline_id))
    return pipeline_path


def ensure_pipeline_directory_structure(user_id: UUID, pipeline_id: UUID):
    """
    Ensures that the directory structure exists for a user's pipeline files.

    Args:
        user_id (UUID): Unique identifier for the user.
        pipeline_id (UUID): Unique identifier for the pipeline.
    """
    base_path = get_pipeline_storage_path(user_id, pipeline_id)

    # Subdirectories for input files, output files, and configurations
    directories = [
        os.path.join(base_path, "input_files"),
        os.path.join(base_path, "output_files"),
        os.path.join(base_path, "configs")
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)

    return base_path


def save_initial_config_to_file(pipeline_data: dict, user_id: UUID, pipeline_id: UUID) -> str:
    """
    Saves the initial pipeline configuration to a JSON file.

    Args:
        pipeline_data (dict): The pipeline input data to save.
        user_id (UUID): Unique identifier for the user.
        pipeline_id (UUID): Unique identifier for the pipeline.

    Returns:
        str: The file path where the configuration was saved.
    """
    base_path = ensure_pipeline_directory_structure(user_id, pipeline_id)
    config_dir = os.path.join(base_path, "configs")
    config_file_path = os.path.join(config_dir, "initial_config.json")

    with open(config_file_path, "w") as f:
        json.dump(pipeline_data, f, indent=4)

    print(f"Initial pipeline configuration saved to {config_file_path}")
    return config_file_path


def store_output_file(user_id: UUID, pipeline_id: UUID, step_name: str, file_path: str):
    """
    Stores an output file for a specific pipeline step.

    Args:
        user_id (UUID): Unique identifier for the user.
        pipeline_id (UUID): Unique identifier for the pipeline.
        step_name (str): The name of the pipeline step that generated the file.
        file_path (str): The source path of the output file.

    Returns:
        str: The path where the file was stored.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Source file '{file_path}' does not exist.")

    base_path = ensure_pipeline_directory_structure(user_id, pipeline_id)
    output_dir = os.path.join(base_path, "output_files")
    dest_file_path = os.path.join(output_dir, f"{step_name}_{os.path.basename(file_path)}")

    shutil.copy2(file_path, dest_file_path)  # Copy file with metadata
    print(f"Output file saved to '{dest_file_path}'")
    return dest_file_path



def create_pipeline_run_directory(user_id: UUID, pipeline_id: UUID) -> str:
    """
    Creates and returns a dedicated run directory for a specific pipeline.
    This directory will store all execution-related files (e.g., intermediate outputs).

    Args:
        user_id (UUID): The unique identifier for the user.
        pipeline_id (UUID): The unique identifier for the pipeline.

    Returns:
        str: The path to the pipeline run directory.
    """
    # Use the existing function to get the base storage path
    base_path = get_pipeline_storage_path(user_id, pipeline_id)
    # Define a dedicated subdirectory for the pipeline run.
    # For example, you can use a fixed name like "run" or include a timestamp.
    run_directory = os.path.join(base_path, "run")
    os.makedirs(run_directory, exist_ok=True)
    return run_directory
