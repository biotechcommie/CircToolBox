# circ_toolbox/backend/services/orchestrators/go_orchestrator.py

import os
import time
from datetime import datetime
from typing import Dict

from circ_toolbox.backend.services.orchestrators.base_orchestrator import BaseStepOrchestrator
from circ_toolbox.backend.utils.logging_config import get_logger
from circ_toolbox.backend.utils import load_default_config
from circ_toolbox.backend.services.quickgo_annotation_fetcher import GOAnnotationFetcher  # Assume this service exists
from circ_toolbox.backend.utils.data_handler import DataHandler  # Assume this service exists

class GOOrchestrator(BaseStepOrchestrator):
    """
    Low-level orchestrator for the GOAnnotationFetcher step.
    
    Responsibilities:
      - Retrieve required inputs from input_data (e.g., result_file, file_type).
      - Load default configuration for GOAnnotationFetcher and merge with overrides.
      - Extract gene-to-UniProt mapping from the input result file.
      - Instantiate GOAnnotationFetcher and run its annotation fetching process.
      - Return a dictionary with the output annotation file path.
    
    Expected input_data format:
        {
            "input": {
                "result_file": "<path_to_input_result_file>",
                "file_type": "blast" or "diamond"
            },
            "output": {
                "output_file": "<path_to_output_annotations_file>",
                "output_dir": "<path_to_intermediate_output_dir>"
            },
            "input_mapping": {}  # Typically not needed.
        }
    
    The 'parameters' dict may include configuration overrides.
    """
    def __init__(self):
        super().__init__()
    
    def execute(self, parameters: Dict, input_data: Dict) -> Dict:
        self.logger.info("Starting GOOrchestrator execution.")

        input_params = input_data.get("input", {})
        result_file = input_params.get("result_file")
        file_type = input_params.get("file_type")
        if not result_file or not file_type:
            self.logger.error("Both 'result_file' and 'file_type' are required in input parameters.")
            raise ValueError("Both 'result_file' and 'file_type' are required.")

        output_params = input_data.get("output", {})
        output_file = output_params.get("output_file")
        output_dir = output_params.get("output_dir")
        if not output_file or not output_dir:
            self.logger.error("Both 'output_file' and 'output_dir' are required in output parameters.")
            raise ValueError("Both 'output_file' and 'output_dir' are required.")

        self.logger.info(f"Input: result_file={result_file}, file_type={file_type}")
        self.logger.info(f"Output: output_file={output_file}, output_dir={output_dir}")

        tool_config = load_default_config("GOAnnotationFetcher", default_fallback=GOAnnotationFetcher.DEFAULT_CONFIG, overrides=parameters)
        self.logger.info(f"Final GOAnnotationFetcher configuration: {tool_config}")

        # Extract gene-to-UniProt mapping from the result file.
        data_handler = DataHandler(output_dir)
        try:
            self.logger.info(f"Extracting gene-to-UniProt mapping from {result_file}...")
            start_time = time.time()
            gene_uniprot_mapping = data_handler.get_gene_uniprot_mapping_from_file(
                file_type=file_type,
                result_file=result_file,
                use_evalue_filtering=tool_config.get("use_evalue_filtering", True),
                evalue_threshold=tool_config.get("evalue_threshold_extract", 1e-10),
            )
            elapsed_time = time.time() - start_time
            self.logger.info(f"Mapping extracted in {elapsed_time:.2f} seconds.")
        except Exception as e:
            self.logger.error(f"Mapping extraction failed: {e}")
            raise RuntimeError(f"Failed to extract mapping from {result_file}: {e}")

        if not gene_uniprot_mapping:
            self.logger.error(f"No valid mappings found in {result_file}.")
            raise RuntimeError(f"No valid mappings found in {result_file}.")

        fetcher = GOAnnotationFetcher(output_dir=output_dir, config=tool_config)
        self.logger.info("GOAnnotationFetcher instance created successfully.")

        if not tool_config.get("force_run", False) and fetcher.is_annotation_file_complete(output_file, set(uniprot_id for pairs in gene_uniprot_mapping.values() for uniprot_id, _ in pairs)):
            self.logger.info(f"Skipping annotation fetch as {output_file} is complete.")
            return {"output_file": output_file}

        try:
            self.logger.info("Running GOAnnotationFetcher for annotation retrieval...")
            start_time = time.time()
            fetcher.fetch_annotations(gene_uniprot_mapping, output_file)
            elapsed_time = time.time() - start_time
            self.logger.info(f"Annotation fetch completed in {elapsed_time:.2f} seconds.")
        except Exception as e:
            self.logger.error(f"Annotation fetch failed: {e}")
            raise RuntimeError(f"Annotation fetch failed: {e}")

        self.logger.info("GOOrchestrator execution completed successfully.")
        return {"output_file": output_file}
