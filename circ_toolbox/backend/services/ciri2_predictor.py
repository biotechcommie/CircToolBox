# circ_toolbox/backend/services/ciri2_predictor.py
import os
import subprocess
import time
from circ_toolbox.backend.utils import BasePipelineTool, log_runtime


class CIRI2Processor(BasePipelineTool):
    """Processes SAM files using CIRI2 for circular RNA prediction.

    This processor is project-agnostic. The output directory is defined by the configuration,
    and specific project (or bioproject) identifiers are provided when invoking the run methods.

    Attributes:
        genome_file (str): Path to the genome reference file.
        ciri_output_directory (str): Base directory for CIRI2 outputs.
        threads (int): Number of threads to use for processing.
        ciri2_path (str): Path to the CIRI2 Perl script.
        max_retries (int): Maximum number of retry attempts for processing.
        retry_wait_time (int): Wait time (in seconds) between retries.
    """
    DEFAULT_CONFIG = {
        "ciri_output_directory": "CIRI2_OUTPUT",
        "threads": 16,
        "max_retries": 5,
        "retry_wait_time": 10,
        "ciri2_path": "/home/hugo/Documents/CIRI_v2.0.6/CIRI2.pl"
    }

    def __init__(self, genome_file, config=None):
        """
        Initializes the CIRI2Processor.

        This constructor is now project-agnostic. It does not bind to a specific project code,
        allowing the same instance to process multiple projects by specifying the project code
        in the run methods.

        Args:
            genome_file (str): Path to the genome reference file.
            config (dict, optional): Configuration overrides. If not provided, defaults are used.
        """
        super().__init__("ciri2_processor")
        config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.genome_file = genome_file
        self.ciri_output_directory = config["ciri_output_directory"]
        self.threads = config["threads"]
        self.ciri2_path = config["ciri2_path"]
        self.max_retries = config["max_retries"]
        self.retry_wait_time = config["retry_wait_time"]
        os.makedirs(self.ciri_output_directory, exist_ok=True)
        
        self.logger.info(f"CIRI2Processor initialized with config: {config}")

    @log_runtime("ciri2_processor")
    def run_ciri2(self, sam_directory, project_code, force_run=False):
        """
        Runs CIRI2 for each SAM file found in the specified directory, organizing outputs by project.

        This method scans the given SAM directory for SAM files. For each SAM file, an output directory is
        created based on the provided project_code, and the CIRI2 command is executed with a retry mechanism.

        Args:
            sam_directory (str): Directory containing SAM files.
            project_code (str): Project code used to organize outputs.
            force_run (bool, optional): If True, processing is forced even if valid output exists. Defaults to False.

        Raises:
            RuntimeError: If processing of any SAM file fails after the maximum number of retries.
        """
        self.log_start("Running CIRI2 for All SAM Files")

        # Create project-specific output directory
        project_output_dir = os.path.join(self.ciri_output_directory, project_code)
        os.makedirs(project_output_dir, exist_ok=True)
        
        sam_files = [
            f for f in os.listdir(sam_directory)
            if f.endswith(".sam") and os.path.isfile(os.path.join(sam_directory, f))
        ]
        
        if not sam_files:
            self.logger.warning("No SAM files found for CIRI2 processing.")
            return

        for sam_file in sam_files:
            sam_file_path = os.path.join(sam_directory, sam_file)
            base_name = os.path.splitext(sam_file)[0]
            output_file = os.path.join(project_output_dir, base_name)

            # Skip processing if output already exists and is valid unless force_run is True
            if not force_run and self._validate_ciri2_output(output_file):
                self.logger.info(f"Skipping {sam_file_path}: valid CIRI2 output already exists.")
                continue

            self.logger.info(f"Starting CIRI2 for {sam_file_path}")

            command = [
                "perl", self.ciri2_path,
                "-I", sam_file_path,
                "-T", str(self.threads),
                "-F", self.genome_file,
                "-O", output_file
            ]

            # Run CIRI2 with retries
            for attempt in range(self.max_retries):
                try:
                    self.logger.info(f"Attempt {attempt + 1} for {sam_file}")
                    subprocess.run(command, check=True)
                    self.logger.info(f"CIRI2 completed successfully for {sam_file}")
                    break  # Exit retry loop on success
                except subprocess.CalledProcessError as e:
                    self.logger.warning(f"Attempt {attempt + 1} failed for {sam_file}: {e}")
                    time.sleep(self.retry_wait_time)
            else:
                self.logger.error(f"Max retries reached for {sam_file}. Skipping CIRI2.")
                raise RuntimeError(f"Max retries reached for {sam_file}. Check the logs for more information.")

        self.log_end("Running CIRI2 for All SAM Files")


    @log_runtime("ciri2_processor")
    def run_ciri2_from_dict(self, bioproject_sam_files, force_run=False) -> dict:
        """
        Runs CIRI2 for selected SAM files organized by bioproject.

        This method accepts a dictionary where each key is a bioproject ID and each value is a list
        of SAM file paths to be processed. For each bioproject, a dedicated output directory is created
        under the base CIRI2 output directory. For each SAM file, the output file is generated, and the
        method returns a dictionary mapping bioproject IDs to dictionaries mapping sample names (derived
        from the SAM file basename) to their corresponding output file paths.

        Args:
            bioproject_sam_files (dict): Dictionary mapping bioproject IDs to lists of SAM file paths.
            force_run (bool, optional): If True, processing is forced even if valid output exists.
                                        Defaults to False.

        Returns:
            dict: A dictionary where each key is a bioproject ID and each value is a dictionary mapping
                  sample names to output SAM file paths.

        Raises:
            RuntimeError: If processing of any SAM file fails after the maximum number of retries.
        """
        self.log_start("Running CIRI2 for Selected SAM Files by Bioproject")
        output_dict = {}

        for bioproject_id, sam_files in bioproject_sam_files.items():
            # Create a dedicated output directory for this bioproject
            bioproject_output_dir = os.path.join(self.ciri_output_directory, bioproject_id)
            os.makedirs(bioproject_output_dir, exist_ok=True)
            self.logger.info(f"Processing bioproject: {bioproject_id} with {len(sam_files)} SAM file(s)")

            output_dict[bioproject_id] = {}

            for sam_file_path in sam_files:
                if not os.path.isfile(sam_file_path):
                    self.logger.warning(f"File not found or not a regular file: {sam_file_path}")
                    continue

                base_name = os.path.splitext(os.path.basename(sam_file_path))[0]
                output_file = os.path.join(bioproject_output_dir, base_name)

                # Skip processing if valid output already exists unless force_run is True
                if not force_run and self._validate_ciri2_output(output_file):
                    self.logger.info(f"Skipping {sam_file_path}: valid CIRI2 output already exists.")
                    continue

                self.logger.info(f"Starting CIRI2 for {sam_file_path}")
                command = [
                    "perl", self.ciri2_path,
                    "-I", sam_file_path,
                    "-T", str(self.threads),
                    "-F", self.genome_file,
                    "-O", output_file
                ]

                # Run CIRI2 with retry mechanism
                for attempt in range(self.max_retries):
                    try:
                        self.logger.info(f"Attempt {attempt + 1} for {sam_file_path}")
                        subprocess.run(command, check=True)
                        self.logger.info(f"CIRI2 completed successfully for {sam_file_path}")
                        break  # Exit retry loop on success
                    except subprocess.CalledProcessError as e:
                        self.logger.warning(f"Attempt {attempt + 1} failed for {sam_file_path}: {e}")
                        time.sleep(self.retry_wait_time)
                else:
                    self.logger.error(f"Max retries reached for {sam_file_path}. Aborting CIRI2 for this file.")
                    raise RuntimeError(f"Max retries reached for {sam_file_path}. Check the logs for more information.")

                # Validate the output SAM file
                if not self._validate_ciri2_output(output_file):
                    self.logger.error(f"SAM validation failed for {output_file}")
                    raise RuntimeError(f"Invalid SAM file: {output_file}")

                # Record the output file in the dictionary
                output_dict[bioproject_id][base_name] = output_file

        self.log_end("Running CIRI2 for Selected SAM Files by Bioproject")
        return output_dict


    def _validate_ciri2_output(self, output_file):
        """
        Validates the CIRI2 output to ensure it was created and is not empty.

        Args:
            output_file (str): Path to the CIRI2 output file.

        Returns:
            bool: True if the file exists and has content; otherwise, False.
        """
        if not os.path.exists(output_file):
            self.logger.error(f"CIRI2 output file not found: {output_file}")
            return False
        if os.path.getsize(output_file) == 0:
            self.logger.error(f"CIRI2 output file is empty: {output_file}")
            return False

        self.logger.info(f"CIRI2 output file validated: {output_file}")
        return True




'''

ciri2_processor = CIRI2Processor(
    genome_file="/path/to/genome.fasta",
    project_code="PRJEB12420",
    config={
        "threads": 8,
        "max_retries": 3,
        "retry_wait_time": 5,
        "ciri2_path": "/path/to/CIRI2.pl"
    }
)
ciri2_processor.run_ciri2("/path/to/sam_directory")

### --- ### --- ###

This will:

    Run CIRI2 for all SAM files in /path/to/sam_directory.
    Output CIRI2 results to CIRI2_OUTPUT/PRJEB12420/.
    Retry up to 3 times if the process fails, waiting 5 seconds between attempts.


INFO: [ciri2_processor] Starting CIRI2 for /path/to/sam/SRR123456.sam
INFO: [ciri2_processor] Attempt 1 for SRR123456.sam
INFO: [ciri2_processor] CIRI2 completed successfully for SRR123456.sam
INFO: [ciri2_processor] Validated CIRI2 output for /path/to/output/SRR123456





Explanation of Changes:
1. Orchestrator Force Run Logic:
The orchestrator extracts the force_run parameter from the step configuration (step_config["params"]["force_run"]).
Passes force_run to the run_ciri2() method in the CIRI2Processor class.
2. CIRI2Processor Changes:
In run_ciri2(), the force_run parameter dictates whether the tool should run even if valid output files already exist:
If force_run=False, the tool checks for valid output files and skips reprocessing.
If force_run=True, the tool always reprocesses the SAM file.
3. SAM File Validation:
After running CIRI2, the output file is validated using _validate_ciri2_output().
If validation fails, an error is raised and logged.
Benefits of This Implementation:
Avoids Unnecessary Reprocessing: Prevents re-running CIRI2 if outputs are valid unless explicitly requested with force_run=True.
Ensures Valid Output: Adds a safeguard to detect and report invalid or missing CIRI2 output.
Retry Mechanism: Still retains the retry logic for robust execution.

'''