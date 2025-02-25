# circ_toolbox/backend/services/orchestrators/uniprot_orchestrator.py

import os
import time
from datetime import datetime
from typing import Dict

from circ_toolbox.backend.services.orchestrators.base_orchestrator import BaseStepOrchestrator
from circ_toolbox.backend.utils.config_loader import load_default_config
from circ_toolbox.backend.services.uniprot_data_preparer import UniProtDataPreparer  # Assume this service exists

class UniProtOrchestrator(BaseStepOrchestrator):
    """
    Low-level orchestrator for the UniProtDataPreparer step.
    
    Responsibilities:
      - Retrieve required inputs from input_data (e.g., query_file).
      - Load default configuration for UniProtDataPreparer and merge with overrides.
      - Instantiate UniProtDataPreparer and execute its workflow.
      - Return a dictionary with output file paths.
    
    Expected input_data format:
        {
            "input": {"query_file": "<path_to_query_file>"},
            "output": {
                "output_dir": "<path_to_output_dir>",
                "blast_output_file": "<path_to_blast_output_file>",
                "diamond_output_file": "<path_to_diamond_output_file>"
            },
            "input_mapping": {}  # Typically not needed.
        }
    
    The 'parameters' dict may include configuration overrides.
    """
    def __init__(self):
        super().__init__()
    
    def execute(self, parameters: Dict, input_data: Dict) -> Dict:
        self.logger.info("Starting UniProtOrchestrator execution.")

        input_params = input_data.get("input", {})
        query_file = input_params.get("query_file")

        if not query_file:
            self.logger.error("'query_file' is required in input parameters.")
            raise ValueError("'query_file' is required.")

        output_params = input_data.get("output", {})
        output_dir = output_params.get("output_dir")
        blast_output_file = output_params.get("blast_output_file")
        diamond_output_file = output_params.get("diamond_output_file")
        if not output_dir or not blast_output_file or not diamond_output_file:
            self.logger.error("Output parameters 'output_dir', 'blast_output_file', and 'diamond_output_file' are required.")
            raise ValueError("Output parameters are required.")

        self.logger.info(f"Input query_file: {query_file}")
        self.logger.info(f"Output directory: {output_dir}")

        tool_config = load_default_config("UniProtDataPreparer", default_fallback=UniProtDataPreparer.DEFAULT_CONFIG, overrides=parameters)
        self.logger.info(f"Final UniProtDataPreparer configuration: {tool_config}")

        preparer = UniProtDataPreparer(output_dir=output_dir, config=tool_config)
        self.logger.info("UniProtDataPreparer instance created successfully.")

        force_run = tool_config.get("force_run", False)
        skip_blastp = not force_run and preparer.is_file_valid(blast_output_file)
        skip_diamond = not force_run and preparer.is_file_valid(diamond_output_file)
        if skip_blastp and skip_diamond:
            self.logger.info("Skipping UniProt data preparation as outputs are complete.")
            return {
                "blast_output_file": blast_output_file,
                "diamond_output_file": diamond_output_file,
            }

        try:
            self.logger.info("Running UniProtDataPreparer workflow...")
            start_time = time.time()
            preparer.run(
                query_file=query_file,
                blast_output_file=blast_output_file,
                diamond_output_file=diamond_output_file,
                force_run=force_run
            )
            elapsed_time = time.time() - start_time
            self.logger.info(f"UniProtDataPreparer completed in {elapsed_time:.2f} seconds.")
        except Exception as e:
            self.logger.error(f"UniProt data preparation failed: {e}")
            raise RuntimeError(f"UniProt data preparation failed: {e}")

        self.logger.info("UniProtOrchestrator execution completed successfully.")
        return {
            "blast_output_file": blast_output_file,
            "diamond_output_file": diamond_output_file,
        }
