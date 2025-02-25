import os
import time
import subprocess
from typing import Dict
from datetime import datetime

from circ_toolbox.backend.services.orchestrators.base_orchestrator import BaseStepOrchestrator
from circ_toolbox.backend.utils.logging_config import get_logger
from circ_toolbox.backend.utils import load_default_config
from circ_toolbox.backend.services.bwa_aligner import BWAAligner

class BWAOrchestrator(BaseStepOrchestrator):
    """
    Low-level orchestrator for the BWAAligner step using the new dictionary-based input logic.

    Responsibilities:
      - Retrieve required inputs (genome_file and bioproject_files) from input_data.
      - Load the default configuration for BWAAligner and merge with any overrides.
      - Instantiate a project-agnostic BWAAligner with the genome file and configuration.
      - Ensure genome indexing and run BWA MEM alignment using the provided bioproject_files.
      - Return a dictionary mapping bioproject IDs to sample SAM file paths.

    Expected input_data format:
        {
            "genome_file": "<path_to_genome_file>",
            "bioproject_files": {
                "<bioproject_id1>": [<file_path1>, <file_path2>, ...],
                "<bioproject_id2>": [<file_path3>, <file_path4>, ...],
                ...
            },
            "output": {"sam_directory": "<path_to_sam_output_dir>"},
            "input_mapping": { ... }  # Optional
        }

    The parameters dict may include configuration overrides.
    """

    def __init__(self):
        """Initializes the BWAOrchestrator."""
        super().__init__()
    
    def execute(self, parameters: Dict, input_data: Dict) -> Dict:
        """
        Executes the BWAAligner step using the new dictionary-based input.

        Args:
            parameters (Dict): Configuration overrides for the BWAAligner.
            input_data (Dict): Dictionary containing input data, including:
                - "genome_file": Path to the genome file.
                - "bioproject_files": Dictionary mapping bioproject IDs to lists of FASTQ file paths.
                - "output": Dictionary with key "sam_directory" for the SAM output directory.
                - Optionally, "input_mapping" for additional data.

        Returns:
            Dict: A dictionary with the key "sam_directory" pointing to the SAM output directory.

        Raises:
            ValueError: If "genome_file", "bioproject_files", or "sam_directory" is missing.
            RuntimeError: If genome indexing or BWA MEM alignment fails.
        """
        
        self.logger.info("Starting BWAOrchestrator execution (dictionary-based input).")

        # Retrieve mandatory inputs.
        genome_file = input_data.get("genome_file")
        bioproject_files = input_data.get("bioproject_files")
        if not genome_file or not bioproject_files:
            self.logger.error("'genome_file' and 'bioproject_files' are required in input_data.")
            raise ValueError("'genome_file' and 'bioproject_files' are required.")


        output_params = input_data.get("output", {})
        sam_directory = output_params.get("sam_directory") # must be set by Celery based on the output folder for the user / pipeline in execution
        if not sam_directory:
            self.logger.error("'sam_directory' must be specified in output parameters.")
            raise ValueError("'sam_directory' is required in output parameters.")


        self.logger.info(f"Input parameters: genome_file={genome_file}; bioproject_files provided.")
        self.logger.info(f"SAM output directory: {sam_directory}")

        # Load default configuration for BWAAligner and merge with overrides.
        tool_config = load_default_config("BWAAligner",
                                          default_fallback=BWAAligner.DEFAULT_CONFIG,
                                          overrides=parameters)
        self.logger.info(f"Final BWAAligner configuration: {tool_config}")

        # Instantiate a project-agnostic BWAAligner.
        aligner = BWAAligner(genome_file=genome_file, config=tool_config)
        self.logger.info("BWAAligner instance created successfully.")

        # Update the SAM output directory with the one provided in output parameters.
        aligner.sam_directory = sam_directory

        try:
            self.logger.info("Ensuring genome is indexed.")
            aligner.ensure_genome_indexed(force_run=tool_config.get("force_run", False))
        except Exception as e:
            self.logger.error(f"Genome indexing failed: {e}")
            raise RuntimeError(f"Genome indexing failed: {e}")

        try:
            self.logger.info("Starting BWA MEM alignment using dictionary-based input.")
            start_time = time.time()
            # Capture the output dictionary from run_bwa_mem_from_dict
            output_dict = aligner.run_bwa_mem_from_dict(bioproject_files, force_run=tool_config.get("force_run", False))
            elapsed_time = time.time() - start_time
            self.logger.info(f"BWAAligner workflow completed successfully in {elapsed_time:.2f} seconds.")
        except Exception as e:
            self.logger.error(f"BWA MEM alignment failed: {e}")
            raise RuntimeError(f"BWA MEM alignment failed: {e}")

        self.logger.info("BWAOrchestrator execution completed successfully.")
        return {"sam_output": output_dict}
    

