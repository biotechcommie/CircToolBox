# circ_toolbox_project/circ_toolbox/backend/services/srr_service.py
import os
import subprocess
import time
import shutil
from circ_toolbox.backend.utils.logging_config import log_runtime
from circ_toolbox.backend.utils.base_pipeline_tool import BasePipelineTool
from circ_toolbox.config import SRA_DIR

class SRRService(BasePipelineTool):
    """
    SRRService manages the download and compression of SRR data for bioinformatics pipelines.
    
    This class inherits from BasePipelineTool to integrate common logging and runtime measurement features.
    It uses a default configuration that defines key parameters such as the SRA directory, the number of threads 
    for fasterq-dump, compression settings, maximum retry attempts, and designated directories for temporary and 
    final output files.
    
    The service ensures that SRR data is downloaded using a retry mechanism in case of transient failures, 
    compresses the downloaded files with pigz (using a configurable number of threads), and cleans up temporary 
    files if required.
    """

    DEFAULT_CONFIG = {
        "sra_directory": SRA_DIR,  # Base directory to store SRR files
        "fasterq_dump_threads": 4,  # Number of threads for `fasterq-dump` command
        "compression_threads": None,  # If `None`, pigz uses all available threads
        "max_retries": 5,  # Maximum number of attempts for download and compression
        "retry_wait_time": 10,  # Wait time (in seconds) between attempts
        "temp_directory": "temp",  # Temporary directory for intermediate downloads
        "compact_directory": "COMPACT",  # Directory for storing compressed files
        "keep_uncompressed": False  # If `True`, keep files uncompressed
    }

    def __init__(self, project_code, config=None):
        super().__init__("srr_service")  # Automatically injects the "srr_data_manager" logger
        config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.project_code = project_code

        # Shared global resource directory for final compressed files
        self.global_sra_directory = os.path.join(config["sra_directory"], project_code)
        os.makedirs(self.global_sra_directory, exist_ok=True)

        # Run-specific temp directory for download and decompression | Temp directory inside the project folder
        self.temp_directory = os.path.join(self.global_sra_directory, config["temp_directory"])
        os.makedirs(self.temp_directory, exist_ok=True)

        # Create COMPACT directory inside global_sra_directory per project
        self.compact_directory = os.path.join(self.global_sra_directory, config["compact_directory"])  # Global resource
        os.makedirs(self.compact_directory, exist_ok=True)

        self.max_retries = config["max_retries"]
        self.retry_wait_time = config["retry_wait_time"]
        self.compression_threads = config["compression_threads"]
        self.keep_uncompressed = config["keep_uncompressed"]

        self.logger.info(f"SRRDataManager initialized with config: {config}")

    @log_runtime("srr_data_manager")
    def download_and_compress_srr(self, srr_list_path):
        """
        Downloads and compresses SRR data from a list of SRR IDs.
        
        Reads an input file containing a list of SRR accession IDs and, for each ID, checks whether the 
        corresponding compressed files already exist. If not, the method attempts to download the data using 
        fasterq-dump with a retry mechanism. Upon a successful download, it compresses the downloaded files 
        using pigz, applying retries as needed.
        
        Args:
            srr_list_path (str): Path to the file containing the list of SRR IDs.
        
        Raises:
            FileNotFoundError: If the SRR list file is not found.
            RuntimeError: If the download or compression fails after the maximum number of retries.
        """
        self.log_start("Download and Compress SRR Data")

        if not os.path.exists(srr_list_path):
            self.logger.error(f"SRR list file {srr_list_path} not found.")
            raise FileNotFoundError(f"SRR list file {srr_list_path} not found.")

        with open(srr_list_path, 'r') as file:
            for srr_acc in file:
                srr_acc = srr_acc.strip()
                if not srr_acc:
                    continue

                self.logger.info(f"Starting download for SRR ID: {srr_acc}")

                # Skip if compressed files already exist in global resource
                if self._files_already_compressed(srr_acc):
                    self.logger.info(f"Skipping {srr_acc}: already exists in global resource directory.")
                    continue

                # Retry mechanism for fasterq-dump
                for attempt in range(self.max_retries):
                    try:
                        self.logger.info(f"fasterq-dump attempt {attempt + 1} for {srr_acc}...")
                        subprocess.run(["fasterq-dump", srr_acc, "--outdir", self.temp_directory], check=True)
                        self.logger.info(f"Download completed for {srr_acc}.")
                        break  # Exit retry loop on success
                    except subprocess.CalledProcessError as e:
                        self.logger.warning(f"Attempt {attempt + 1} failed for {srr_acc}: {e}")
                        time.sleep(self.retry_wait_time)
                else:
                    self.logger.error(f"Failed to download {srr_acc} after {self.max_retries} attempts.")
                    raise RuntimeError(f"Max retries reached for SRR ID {srr_acc}. Aborting.")

                # Compress downloaded files and remove originals
                self._compress_files(srr_acc)
        
        # Remove temporary directory after processing all SRRs if uncompressed files aren't kept
        if not self.keep_uncompressed:
            shutil.rmtree(self.temp_directory, ignore_errors=True)
            self.logger.info(f"Temporary directory {self.temp_directory} removed after completion.")

        self.log_end("Download and Compress SRR Data")
    
    def _files_already_compressed(self, srr_acc):
        """
        Checks if the compressed files for a given SRR accession ID already exist.
        
        Args:
            srr_acc (str): The SRR accession ID.
        
        Returns:
            bool: True if all expected compressed files exist; otherwise, False.
        """
        compressed_file_paths = [
            os.path.join(self.compact_directory, f"{srr_acc}_1.fastq.gz"),
            os.path.join(self.compact_directory, f"{srr_acc}_2.fastq.gz"),
            os.path.join(self.compact_directory, f"{srr_acc}.fastq.gz")
        ]
        return all(os.path.exists(path) for path in compressed_file_paths)

    def _compress_files(self, srr_acc):
        """
        Compresses the downloaded files corresponding to a given SRR accession ID using pigz.
        
        For each file produced by fasterq-dump, the method constructs a pigz command to compress the file,
        applying a retry mechanism in case of failure. Optionally, if the configuration is set to not keep
        uncompressed files, the original file is removed after successful compression.
        
        Args:
            srr_acc (str): The SRR accession ID for which the files will be compressed.
        
        Raises:
            RuntimeError: If compression fails after the maximum number of retry attempts.
        """
        for file_name in [f"{srr_acc}_1.fastq", f"{srr_acc}_2.fastq", f"{srr_acc}.fastq"]:
            file_path = os.path.join(self.temp_directory, file_name)
            if os.path.isfile(file_path):
                compressed_file_path = os.path.join(self.compact_directory, f"{file_name}.gz")
                self.logger.info(f"Compressing {file_path} to {compressed_file_path}")


                # Build the pigz command
                pigz_command = ["pigz", "-c", file_path]
                if self.compression_threads:  # Only add `-p` if explicitly set by user
                    pigz_command.insert(1, f"-p{self.compression_threads}")


                # Retry mechanism for pigz compression
                for attempt in range(self.max_retries):
                    try:
                        with open(compressed_file_path, 'w') as out:
                            subprocess.run(pigz_command, stdout=out, check=True)
                        if not self.keep_uncompressed:
                            os.remove(file_path)
                        self.logger.info(f"Compression completed for {file_path}.")
                        break  # Exit retry loop on success
                    except subprocess.CalledProcessError as e:
                        self.logger.warning(f"Compression attempt {attempt + 1} failed for {file_path}: {e}")
                        time.sleep(self.retry_wait_time)
                else:
                    self.logger.error(f"Failed to compress {file_path} after {self.max_retries} attempts.")
                    raise RuntimeError(f"Max retries reached for file {file_path}. Aborting.")


'''
# Configuração para o SRRService
config = {
    "fasterq_dump_threads": 8,
    "compression_threads": 4,
    "max_retries": 3,
    "retry_wait_time": 5,
    "temp_directory": "temp",
    "compact_directory": "COMPACT",
    "keep_uncompressed": False
}

# Instanciar e chamar o serviço
srr_service = SRRService(project_code="PRJNA12345", config=config)
srr_service.download_and_compress_srr(srr_list_path="/path/to/PRJNA12345_to_download.txt")

'''

'''

srr_manager = SRRDataManager("PRJEB12420")
srr_manager.download_and_compress_srr("/path/to/PRJEB12420_SRR_Acc_List.txt")


INFO: [srr_data_manager] Starting download for SRR ID: SRR123456
INFO: [srr_data_manager] fasterq-dump attempt 1 for SRR123456...
INFO: [srr_data_manager] Download completed for SRR123456.
INFO: [srr_data_manager] Compressing /path/to/temp/SRR123456_1.fastq to /path/to/compact/SRR123456_1.fastq.gz
INFO: [srr_data_manager] Compression completed for /path/to/temp/SRR123456_1.fastq.
INFO: [srr_data_manager] Temporary directory removed after completion.

'''