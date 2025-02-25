# circ_toolbox/backend/services/orchestrators/ciri2_orchestrator.py

import os
import time
from datetime import datetime
from typing import Dict

from circ_toolbox.backend.services.orchestrators.base_orchestrator import BaseStepOrchestrator
from circ_toolbox.backend.utils.logging_config import get_logger
from circ_toolbox.backend.utils import load_default_config
from circ_toolbox.backend.services.ciri2_predictor import CIRI2Processor 

class CIRI2Orchestrator(BaseStepOrchestrator):
    """
    Low-level orchestrator for the CIRI2Processor step using dictionary-based input.

    Responsibilities:
      - Retrieve required inputs (genome_file and bioproject_sam_files) from input_data.
      - Load default configuration for CIRI2Processor and merge with any overrides.
      - Instantiate a project-agnostic CIRI2Processor with the genome file and configuration.
      - Run the CIRI2 processing on SAM files using run_ciri2_from_dict.
      - Return a dictionary mapping bioproject IDs to dictionaries that map sample names to their
        corresponding CIRI2 output file paths.

    Expected input_data format:
        {
            "genome_file": "<path_to_genome_file>",
            "bioproject_sam_files": {
                "<bioproject_id1>": [<sam_file_path1>, <sam_file_path2>, ...],
                "<bioproject_id2>": [<sam_file_path3>, <sam_file_path4>, ...],
                ...
            },
            "output": {"ciri_output_directory": "<path_to_ciri2_output_dir>"},
            "input_mapping": { ... }  # Optional.
        }

    The parameters dict may include configuration overrides.
    """
    def __init__(self):
        """Initializes the CIRI2Orchestrator."""
        super().__init__()
    
    def execute(self, parameters: Dict, input_data: Dict) -> Dict:
        """
        Executes the CIRI2Processor step using dictionary-based input.

        Args:
            parameters (Dict): Configuration overrides for the CIRI2Processor.
            input_data (Dict): Dictionary containing input data, including:
                - "genome_file": Path to the genome file.
                - "bioproject_sam_files": Dictionary mapping bioproject IDs to lists of SAM file paths.
                - "output": Dictionary with key "ciri_output_directory" for the CIRI2 output directory.
                - Optionally, "input_mapping" for additional data.

        Returns:
            Dict: A dictionary mapping bioproject IDs to dictionaries that map sample names to their
                  corresponding CIRI2 output file paths.

        Raises:
            ValueError: If "genome_file", "bioproject_sam_files", or "ciri_output_directory" is missing.
            RuntimeError: If CIRI2 processing fails.
        """
        self.logger.info("Starting CIRI2Orchestrator execution.")


        # Retrieve mandatory inputs.
        genome_file = input_data.get("genome_file")
        bioproject_sam_files = input_data.get("bioproject_sam_files")
        if not genome_file or not bioproject_sam_files:
            self.logger.error("'genome_file' and 'bioproject_sam_files' are required in input_data.")
            raise ValueError("'genome_file' and 'bioproject_sam_files' are required.")

        output_params = input_data.get("output", {})
        ciri_output_directory = output_params.get("ciri_output_directory")
        if not ciri_output_directory:
            self.logger.error("'ciri_output_directory' must be specified in output parameters.")
            raise ValueError("'ciri_output_directory' is required in output parameters.")

        self.logger.info(f"Input: genome_file={genome_file}; bioproject_sam_files provided.")
        self.logger.info(f"CIRI2 output directory: {ciri_output_directory}")

        # Load default configuration for CIRI2Processor and merge with overrides.
        tool_config = load_default_config("CIRI2Processor",
                                          default_fallback=CIRI2Processor.DEFAULT_CONFIG,
                                          overrides=parameters)
        self.logger.info(f"Final CIRI2Processor configuration: {tool_config}")

        # Instantiate a project-agnostic CIRI2Processor.
        processor = CIRI2Processor(genome_file=genome_file, config=tool_config)
        self.logger.info("CIRI2Processor instance created successfully.")

        # Update the CIRI2 output directory with the one provided in output parameters.
        processor.ciri_output_directory = ciri_output_directory

        try:
            self.logger.info("Starting CIRI2 processing using dictionary-based input.")
            start_time = time.time()
            output_dict = processor.run_ciri2_from_dict(bioproject_sam_files,
                                                        force_run=tool_config.get("force_run", False))
            elapsed_time = time.time() - start_time
            self.logger.info(f"CIRI2Processor workflow completed in {elapsed_time:.2f} seconds.")
        except Exception as e:
            self.logger.error(f"CIRI2 processing failed: {e}")
            raise RuntimeError(f"CIRI2 processing failed: {e}")

        self.logger.info("CIRI2Orchestrator execution completed successfully.")
        return {"ciri_output": output_dict}
