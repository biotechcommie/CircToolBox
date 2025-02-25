# circ_toolbox/backend/utils/validation.py
import pathlib
from fastapi import HTTPException

# Allowed file extensions for validation
ALLOWED_EXTENSIONS = [".fasta", ".fa", ".txt"]

def validate_file_path(file_path: str):
    """
    Validates a file path to ensure:
    - The file exists.
    - The file extension is allowed.
    - The path does not contain invalid or malicious characters.

    Args:
        file_path (str): The file path to validate.

    Raises:
        HTTPException: If the file path is invalid or unsupported.
    """
    file_path_obj = pathlib.Path(file_path)

    # Check if the file exists and is a valid file
    if not file_path_obj.exists() or not file_path_obj.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"File path '{file_path}' is invalid or the file does not exist."
        )

    # Validate the file extension
    extension = file_path_obj.suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {extension}. Allowed formats: {ALLOWED_EXTENSIONS}"
        )
