# circ_toolbox/backend/services/orchestrators/srr_orchestrator.py

import os
import time
import subprocess
import shutil
from typing import Dict
from datetime import datetime

# Import the common base orchestrator and logger utilities.
from circ_toolbox.backend.services.orchestrators.base_orchestrator import BaseStepOrchestrator
# from circ_toolbox.backend.utils.logging_config import get_logger
from circ_toolbox.backend.utils.config_loader import load_default_config

# Import the final SRR service (which remains unchanged).
from circ_toolbox.backend.services.srr_service import SRRService

# Import the synchronous session maker and SRRManager.
from circ_toolbox.backend.database.base_sync import get_sync_session
from circ_toolbox.backend.database.srr_manager import SRRManager

from circ_toolbox.backend.utils.logging_config import log_runtime

class SRROrchestrator(BaseStepOrchestrator):
    """
    Low-level orchestrator for the SRR Data Manager step.
    
    Responsibilities:
      - Prepare SRR input data for each BioProject by checking which SRRs are already registered
        in the database versus which need to be downloaded.
      - Merge default configuration for SRRService with any provided overrides.
      - For each BioProject:
          * Use SRRManager to register the BioProject (if not already registered) and check SRR completeness.
          * Create a temporary file listing the SRR IDs to download.
          * Instantiate SRRService (with merged configuration) and call download_and_compress_srr().
          * After download/compression, check for the expected output files and, if found, register them in the database.
      - Return a dictionary mapping BioProject IDs to the final SRR file paths.
    
    Expected input_data format:
        {
            "bioprojects_input": { 
                "BioProject1": {
                    "srr_ids": ["SRR_ID1", "SRR_ID2", ...], 
                    "description": "Optional description for BioProject1"
                },
                "BioProject2": {
                    "srr_ids": ["SRR_ID3", "SRR_ID4", ...],
                    "description": "Optional description for BioProject2"
                }
            },
            "force_redownload": False  # Optional flag; defaults to False.
        }
    
    The 'parameters' dict may include configuration overrides for the SRRService.
    """
    def __init__(self):
        super().__init__()  # Initializes self.logger with the class name.

    @log_runtime("SRROrchestrator")
    def _execute_core(self, parameters: Dict, input_data: Dict) -> Dict:
        """
        Execute the SRR Data Manager step.
        
        This method performs the following:
        1. For each BioProject in the input, use SRRManager to check which SRRs are already registered.
        2. Determine which SRR IDs need to be downloaded (or re-downloaded if force_redownload is True).
        3. For each BioProject with missing SRRs:
                a. Create a temporary file listing the SRR IDs to download.
                b. Instantiate SRRService with the merged configuration (default + overrides).
                c. Call download_and_compress_srr() to perform the downloads and compression.
                d. For each SRR that was downloaded, check for expected output files.
                e. If the expected output file(s) are found, call SRRManager.register_srr() to register them.
        4. Return a dictionary mapping each BioProject ID to a mapping of SRR IDs and their final file paths.
        
        Args:
            parameters (Dict): Configuration overrides for the SRRService.
            input_data (Dict): Input data for SRR processing, including:
                - "bioprojects_input": { 
                    "BioProject1": {
                        "srr_ids": [srr_id1, srr_id2, ...], 
                        "description": "Optional description for BioProject1"
                    },
                    ...
                },
                - "force_redownload": Optional bool.
                
        Returns:
            Dict: A dictionary of the form { "srr_paths": { "BioProject1": { "SRR_ID1": file_path, ... }, ... } }
        """
        self.logger.info("Starting SRR orchestrator execution.")

        # Extract input data.
        bioprojects_input = input_data.get("bioprojects_input", {})
        force_redownload = input_data.get("force_redownload", False)

        # Obtain a synchronous database session.
        session = get_sync_session()
        try:
            # Instantiate SRRManager with the session.
            srr_manager = SRRManager(session)

            # Prepare SRR data for each BioProject.
            prepared_data = self.prepare_srr_data(bioprojects_input, force_redownload, srr_manager)

            # Load default configuration and merge with any overrides.
            tool_config = load_default_config("SRRService", default_fallback=SRRService.DEFAULT_CONFIG, overrides=parameters)
            self.logger.info(f"Using SRRService configuration: {tool_config}")

            # Initialize dictionary to hold final SRR file paths.
            srr_paths = {}

            # Process each BioProject.
            for bioproject_id, data in prepared_data.items():
                srr_paths[bioproject_id] = {}
                
                # Reuse existing paths.
                for srr_id, path in data.get("existing_paths", {}).items():
                    srr_paths[bioproject_id][srr_id] = path
                    self.logger.info(f"Reusing existing SRR '{srr_id}' for BioProject '{bioproject_id}'.")

                # Process SRRs to download.
                to_download = data.get("to_download", [])
                if to_download:
                    self.logger.info(f"{len(to_download)} SRRs to download for BioProject '{bioproject_id}'.")

                    # Create a temporary file containing the SRR IDs.
                    temp_srr_list_path = os.path.join("/tmp", f"{bioproject_id}_to_download.txt")
                    with open(temp_srr_list_path, "w") as f:
                        f.write("\n".join(to_download))

                    try:
                        # Instantiate SRRService for this BioProject.
                        srr_service = SRRService(project_code=bioproject_id, config={**tool_config})
                        srr_service.download_and_compress_srr(temp_srr_list_path)
                    except Exception as e:
                        self.logger.error(f"Error downloading SRRs for BioProject '{bioproject_id}': {e}")
                        raise RuntimeError(f"SRR download failed for BioProject '{bioproject_id}': {e}")
                    finally:
                        if os.path.exists(temp_srr_list_path):
                            os.remove(temp_srr_list_path)
                            self.logger.info(f"Temporary file '{temp_srr_list_path}' removed.")

                    # For each SRR in the to_download list, determine final file paths.
                    for srr_id in to_download:
                        # Expected paths for single-end or paired-end outputs.
                        single_end_path = os.path.join(srr_service.compact_directory, f"{srr_id}.fastq.gz")
                        paired_end_path_1 = os.path.join(srr_service.compact_directory, f"{srr_id}_1.fastq.gz")
                        paired_end_path_2 = os.path.join(srr_service.compact_directory, f"{srr_id}_2.fastq.gz")

                        final_path = None
                        if os.path.exists(single_end_path):
                            final_path = single_end_path
                        elif os.path.exists(paired_end_path_1) and os.path.exists(paired_end_path_2):
                            final_path = f"{paired_end_path_1}, {paired_end_path_2}"

                        if final_path:
                            # Register the SRR in the database.
                            srr_record = srr_manager.register_srr(bioproject_id=bioproject_id, srr_id=srr_id, file_path=final_path)
                            srr_paths[bioproject_id][srr_id] = final_path
                            self.logger.info(f"SRR '{srr_id}' for BioProject '{bioproject_id}' registered with path '{final_path}'.")
                        else:
                            self.logger.warning(f"Compressed file(s) for SRR '{srr_id}' not found for BioProject '{bioproject_id}'.")

            self.logger.info("SRR orchestrator execution completed.")
            return {"srr_paths": srr_paths}
        
        except Exception as e:
            self.logger.error(f"Error executing SRR orchestrator: {e}")
            raise e
        finally:
            session.close()

    @log_runtime("SRROrchestrator")
    def prepare_srr_data(self, bioprojects_input: Dict, force_redownload: bool, srr_manager: SRRManager) -> Dict:
        """
        Prepares SRR input for the pipeline by determining which SRRs are already registered
        in the database and which need to be downloaded.
        
        Args:
            bioprojects_input (dict): Expected format { 
                "bioproject_id": {
                    "srr_ids": [srr_id1, srr_id2, ...], 
                    "description": "Optional description for BioProject"
                } 
            }.
            force_redownload (bool): If True, force re-download of all SRRs.
            srr_manager (SRRManager): An instance of SRRManager for database operations.
        
        Returns:
            dict: Dictionary with keys per BioProject containing:
                - "existing_paths": Mapping of SRR IDs to file paths (if already registered).
                - "to_download": List of SRR IDs that require downloading.
        """
        prepared_data = {}
        for bioproject_id, project_data in bioprojects_input.items():
            srr_list = project_data.get("srr_ids", [])
            description = project_data.get("description", "")

            # Register the BioProject with description (if not already present).
            bioproject_record = srr_manager.register_bioproject(bioproject_id, description)

            # Check completeness: get registered SRRs and missing SRRs.
            completeness = srr_manager.check_bioproject_completeness(bioproject_id, srr_list)
            registered_srrs = set(completeness["registered"])
            missing_srrs = set(completeness["missing"])

            if force_redownload:
                missing_srrs = set(srr_list)
                registered_srrs = set()

            prepared_data[bioproject_id] = {
                "existing_paths": {srr_id: srr_manager.get_srr_path(srr_id) for srr_id in registered_srrs if srr_manager.get_srr_path(srr_id)},
                "to_download": list(missing_srrs)
            }
            self.logger.info(f"BioProject '{bioproject_id}': {len(registered_srrs)} existing, {len(missing_srrs)} to download.")
        return prepared_data


    def validate_inputs(self):
        # Implementação específica de validação de inputs
        self.logger.info("Validating input data for SRROrchestrator.")
    
    def _pre_execute(self):
        # Lógica específica de pré-execução
        self.logger.info("Preparing resources for SRROrchestrator.")
    
    def _post_execute(self, result: Dict):
        # Lógica específica de pós-execução
        self.logger.info(f"Post-execution logic with result: {result}")


'''

input_data = {
    "bioprojects_input": {
        "BioProject1": {
            "srr_ids": ["SRR12345", "SRR67890"],
            "description": "Optional description for BioProject1"
        },
        "BioProject2": {
            "srr_ids": ["SRR54321", "SRR98765"],
            "description": "Optional description for BioProject2"
        }
    },
    "force_redownload": False,  # Este parâmetro é tratado apenas no orquestrador
    "srr_service_config": {  # Este dicionário contém os overrides para o SRRService
        "sra_directory": "/path/to/sra_directory",
        "fasterq_dump_threads": 8,
        "compression_threads": 4,
        "max_retries": 10,
        "retry_wait_time": 20,
        "temp_directory": "temp",
        "compact_directory": "COMPACT",
        "keep_uncompressed": False
    }
}

# Parâmetros que serão passados para o load_default_config
parameters = input_data.get("srr_service_config", {})

orchestrator = SRROrchestrator()
result = orchestrator.execute(parameters, input_data)
print(result)

'''


'''
input_data = {
    "bioprojects_input": {
        "PRJNA12345": {
            "srr_ids": ["SRR123456", "SRR654321"],
            "description": "Este é um projeto de exemplo para estudos de RNA-seq."
        },
        "PRJNA67890": {
            "srr_ids": ["SRR987654", "SRR543210"],
            "description": "Projeto relacionado a estudos de metagenômica."
        }
    },
    "force_redownload": False
}

parameters = {
    "fasterq_dump_threads": 8,
    "compression_threads": 4,
    "max_retries": 3,
    "retry_wait_time": 5
}


Descrição:
bioprojects_input: Mapeia cada BioProject ID para um dicionário contendo uma lista de SRR IDs e uma descrição opcional.
force_redownload: Flag booleana para forçar o redownload de todos os SRRs, independentemente de já estarem registrados.
parameters: Configurações opcionais para o SRRService, como número de threads e tentativas de download.



'''


'''

    def validate_inputs(self):
        # Implementação específica de validação de inputs
        self.logger.info("Validating input data for SRROrchestrator.")
    
    def _pre_execute(self):
        # Lógica específica de pré-execução
        self.logger.info("Preparing resources for SRROrchestrator.")
    
    def _execute_core(self, parameters: Dict, input_data: Dict) -> Dict:
        # Implementação específica da lógica principal
        self.logger.info("Executing core logic of SRROrchestrator.")
        # Simulação de retorno
        return {"result": "success"}
    
    def _post_execute(self, result: Dict):
        # Lógica específica de pós-execução
        self.logger.info(f"Post-execution logic with result: {result}")


'''