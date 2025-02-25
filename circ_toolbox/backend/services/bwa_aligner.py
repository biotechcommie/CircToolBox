# circ_toolbox/backend/services/bwa_aligner.py
import os
import subprocess
import time
from circ_toolbox.backend.utils import BasePipelineTool, log_runtime


class BWAAligner(BasePipelineTool):
    """Performs genome alignment using BWA MEM.

    This class is project-agnostic. The base SAM output directory is defined via configuration.
    Specific project codes or bioproject IDs are provided when invoking the run methods to
    organize outputs into subdirectories.

    Attributes:
        genome_file (str): Path to the genome reference file.
        sam_directory (str): Base directory for SAM outputs.
        num_threads (int): Number of threads to use.
        max_retries (int): Maximum number of retry attempts.
        retry_wait_time (int): Time to wait between retries.
        index_algorithm (str): BWA indexing algorithm.
    """

    DEFAULT_CONFIG = {
        "sam_directory": "BWA_MEM_OUTPUT",
        "num_threads": os.cpu_count(),
        "max_retries": 5,
        "retry_wait_time": 10,
        "log_extension": ".log",
        "index_algorithm": "bwtsw"  # Default algorithm for large genomes
    }

    def __init__(self, genome_file, config=None):
        """
        Initializes the BWAAligner class.

        This constructor is now project agnostic. The base SAM output directory is set according to
        the configuration. Specific project codes are supplied to the run methods to organize outputs.

        Args:
            genome_file (str): Path to the genome reference file.
            config (dict, optional): Configuration overrides. Defaults to None.
        """
        super().__init__("bwa_aligner")
        config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.genome_file = genome_file
        self.sam_directory = config["sam_directory"]
        self.num_threads = config["num_threads"]
        self.max_retries = config["max_retries"]
        self.retry_wait_time = config["retry_wait_time"]
        self.index_algorithm = config["index_algorithm"]
        os.makedirs(self.sam_directory, exist_ok=True)

        self.logger.info(f"BWAAligner initialized with config: {config}")


    @log_runtime("bwa_aligner")
    def ensure_genome_indexed(self, force_run=False):
        """
        Ensures that the genome is indexed. Runs `bwa index` if the index files are missing.

        Args:
            force_run (bool, optional): If True, forces re-indexing even if index files exist.
                                        Defaults to False.

        Raises:
            RuntimeError: If indexing fails after the maximum number of retries.
        """
        index_files = [f"{self.genome_file}.{ext}" for ext in ["bwt", "pac", "ann", "amb", "sa"]]
        if not force_run and all(os.path.exists(f) for f in index_files):
            self.logger.info(f"Genome already indexed: {self.genome_file}")
            return
            
        self.logger.info(f"Indexing genome: {self.genome_file}")
        command = ["bwa", "index", "-a", self.index_algorithm, self.genome_file]

        # Run the index command with retry logic
        for attempt in range(self.max_retries):
            try:
                subprocess.run(command, check=True)
                self.logger.info(f"Genome indexing completed successfully for {self.genome_file}")
                return
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Attempt {attempt + 1} to index genome failed: {e}")
                time.sleep(self.retry_wait_time)

        self.logger.error(f"Failed to index genome after {self.max_retries} attempts.")
        raise RuntimeError(f"Max retries reached for genome indexing: {self.genome_file}")

    @log_runtime("bwa_aligner")
    def run_bwa_mem(self, compact_directory, project_code, force_run=False):
        """
        Runs BWA MEM for paired or single-end FASTQ files from a specified directory,
        organizing outputs by the provided project code.

        Args:
            compact_directory (str): Directory containing compressed FASTQ files.
            project_code (str): Project code used to organize the output SAM files.
            force_run (bool, optional): If True, forces re-processing even if valid output exists.
                                        Defaults to False.

        Raises:
            RuntimeError: If alignment fails for any sample after the maximum number of retries.
        """
        self.log_start("Running BWA MEM for All Files")

        # Ensure the genome is indexed before running BWA MEM
        # self.ensure_genome_indexed() # this logic was transfered to the low-level orchestrator

        # Create project-specific output directory
        project_output_dir = os.path.join(self.sam_directory, project_code)
        os.makedirs(project_output_dir, exist_ok=True)

        file_dict = self._build_file_dictionary(compact_directory)
        for base_name, files in file_dict.items():
            input_files = [os.path.join(compact_directory, file) for file in files]
            output_file = os.path.join(project_output_dir, f"{base_name}.sam")
            log_file = os.path.join(project_output_dir, f"aln-se-{base_name}{self.DEFAULT_CONFIG['log_extension']}")

            # Ensure the output directory exists
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            # Log start of alignment
            self.logger.info(f"Starting BWA MEM for {base_name}")
            self.logger.info(f"Input files: {input_files}")
            self.logger.info(f"Output file: {output_file}")
            self.logger.info(f"Log file: {log_file}")

            # Run BWA MEM with retries
            for attempt in range(self.max_retries):
                try:
                    with open(output_file, 'w') as out, open(log_file, 'w') as err:
                        self.logger.info(f"Attempt {attempt + 1} for {base_name}")
                        subprocess.run(
                            ["bwa", "mem", "-t", str(self.num_threads), self.genome_file, *input_files],
                            stdout=out,
                            stderr=err,
                            check=True
                        )
                    self.logger.info(f"BWA MEM completed successfully for {base_name}")
                    break  # Exit retry loop on success
                except subprocess.CalledProcessError as e:
                    self.logger.warning(f"Attempt {attempt + 1} failed for {base_name}: {e}")
                    time.sleep(self.retry_wait_time)
            else:
                self.logger.error(f"Max retries reached for {base_name}. Aborting BWA MEM.")
                raise RuntimeError(f"Max retries reached for {base_name}. Check the logs for more information.")

            # Validate the output SAM file
            if not self.validate_sam_output(output_file):
                self.logger.error(f"SAM validation failed for {output_file}")
                raise RuntimeError(f"Invalid SAM file: {output_file}")

        self.log_end("Running BWA MEM for All Files")

    def _build_file_dictionary(self, compact_directory):
        """
        Builds a dictionary of sample base names to paired or single-end FASTQ file names from a directory.

        Args:
            compact_directory (str): Directory containing compressed FASTQ files.

        Returns:
            dict: A dictionary mapping sample base names to lists of file names.
        """
        self.logger.info(f"Building file dictionary from {compact_directory}")
        file_dict = {}
        for file in os.listdir(compact_directory):
            if '_' in file and (file.endswith("_1.fastq.gz") or file.endswith("_2.fastq.gz")):
                base_name = file.split('_')[0]
                if (
                    f"{base_name}_1.fastq.gz" in os.listdir(compact_directory)
                    and f"{base_name}_2.fastq.gz" in os.listdir(compact_directory)
                ):
                    file_dict[base_name] = [f"{base_name}_1.fastq.gz", f"{base_name}_2.fastq.gz"]
            elif file.endswith(".fastq.gz"):
                base_name = file.replace('.fastq.gz', '')
                file_dict[base_name] = [file]
        
        self.logger.info(f"File dictionary created with {len(file_dict)} entries.")
        return file_dict

    @log_runtime("bwa_aligner")
    def run_bwa_mem_from_dict(self, bioproject_files, force_run=False) -> Dict[str, Dict[str, str]]:
        """
        Runs BWA MEM for selected FASTQ files organized by bioproject.

        This method accepts a dictionary where each key is a bioproject ID and each value is a list of
        file paths (strings) that the BWA Aligner must process. For each bioproject, an output folder is
        created under the base SAM directory, and the files are grouped by sample before alignment.
        The method builds and returns a dictionary mapping bioproject IDs to a sub-dictionary of sample
        names and their corresponding SAM output file paths.

        Args:
            bioproject_files (dict): Dictionary mapping bioproject IDs to lists of file paths.
            force_run (bool, optional): If True, forces re-processing even if valid output exists.
                                        Defaults to False.

        Returns:
            Dict[str, Dict[str, str]]: A dictionary where each key is a bioproject ID and each value is a
            dictionary mapping sample names to the corresponding SAM output file path.

        Raises:
            RuntimeError: If alignment fails for any sample after the maximum number of retries.
        """
  
        self.log_start("Running BWA MEM for Selected Bioproject Files")
        output_dict = {}  # Final dictionary to be returned

        for bioproject_id, file_list in bioproject_files.items():
            # Create an output subdirectory for this bioproject
            bioproject_output_dir = os.path.join(self.sam_directory, bioproject_id)
            os.makedirs(bioproject_output_dir, exist_ok=True)
            self.logger.info(f"Processing bioproject: {bioproject_id}")
            self.logger.info(f"Total input files received: {len(file_list)}")

            # Group files by sample using the helper method
            sample_dict = self._build_file_dictionary_from_list(file_list)
            self.logger.info(f"Grouped into {len(sample_dict)} sample(s) for bioproject {bioproject_id}")
            
            # Initialize output mapping for this bioproject
            output_dict[bioproject_id] = {}
            
            for sample, files in sample_dict.items():
                # Define output SAM file and corresponding log file for each sample
                output_file = os.path.join(bioproject_output_dir, f"{sample}.sam")
                log_file = os.path.join(bioproject_output_dir, f"aln-se-{sample}{self.DEFAULT_CONFIG['log_extension']}")

                self.logger.info(f"Starting BWA MEM for sample {sample} in bioproject {bioproject_id}")
                self.logger.info(f"Input files: {files}")
                self.logger.info(f"Output file: {output_file}")
                self.logger.info(f"Log file: {log_file}")

                # Execute bwa mem with retries
                for attempt in range(self.max_retries):
                    try:
                        with open(output_file, 'w') as out, open(log_file, 'w') as err:
                            self.logger.info(f"Attempt {attempt + 1} for sample {sample}")
                            subprocess.run(
                                ["bwa", "mem", "-t", str(self.num_threads), self.genome_file, *files],
                                stdout=out,
                                stderr=err,
                                check=True
                            )
                        self.logger.info(f"BWA MEM completed successfully for sample {sample}")
                        break  # Exit retry loop on success
                    except subprocess.CalledProcessError as e:
                        self.logger.warning(f"Attempt {attempt + 1} failed for sample {sample}: {e}")
                        time.sleep(self.retry_wait_time)
                else:
                    self.logger.error(f"Max retries reached for sample {sample} in bioproject {bioproject_id}. Aborting BWA MEM.")
                    raise RuntimeError(f"Max retries reached for sample {sample}. Check the logs for more information.")

                # Validate the output SAM file
                if not self.validate_sam_output(output_file):
                    self.logger.error(f"SAM validation failed for {output_file}")
                    raise RuntimeError(f"Invalid SAM file: {output_file}")
                
                # Record the output file in the dictionary
                output_dict[bioproject_id][sample] = output_file
        
        self.log_end("Running BWA MEM for Selected Bioproject Files")
        return output_dict

    def _build_file_dictionary_from_list(self, file_list):
        """
        Builds a dictionary of sample names to paired or single-end FASTQ file paths from a provided list.
        
        Args:
            file_list (list): A list of file paths (strings) to be grouped by sample.
            
        Returns:
            dict: A dictionary mapping sample names to lists of file paths.
                  The grouping logic assumes that paired-end files contain '_1' and '_2' in their names.
        """
        self.logger.info("Building sample file dictionary from provided file list")
        sample_dict = {}
        for file_path in file_list:
            file_name = os.path.basename(file_path)
            if '_' in file_name and (file_name.endswith("_1.fastq.gz") or file_name.endswith("_2.fastq.gz")):
                sample_name = file_name.split('_')[0]
                sample_dict.setdefault(sample_name, []).append(file_path)
            elif file_name.endswith(".fastq.gz"):
                sample_name = file_name.replace('.fastq.gz', '')
                sample_dict[sample_name] = [file_path]
        self.logger.info(f"Sample file dictionary created with {len(sample_dict)} sample(s).")
        return sample_dict

    def validate_sam_output(self, sam_file):
        """
        Validates that the SAM file exists and is non-empty.
        
        Args:
            sam_file (str): Path to the SAM file.
            
        Returns:
            bool: True if the SAM file is valid; otherwise, False.
        """
        if not os.path.exists(sam_file) or os.path.getsize(sam_file) == 0:
            self.logger.error(f"SAM file {sam_file} is missing or empty.")
            return False
        return True



'''


bwa_aligner = BWAAligner(
    genome_file="/path/to/genome.fasta",
    project_code="PRJEB12420",
    config={
        "num_threads": 8,
        "max_retries": 3,
        "retry_wait_time": 5,
        "index_algorithm": "bwtsw"
    }
)
bwa_aligner.run_bwa_mem("/path/to/compact_directory")


INFO: [bwa_aligner] Indexing genome: /path/to/genome.fasta
INFO: [bwa_aligner] Genome indexing completed successfully for /path/to/genome.fasta
INFO: [bwa_aligner] Starting BWA MEM for SRR123456
INFO: [bwa_aligner] Input files: ['/path/to/compact/SRR123456_1.fastq.gz', '/path/to/compact/SRR123456_2.fastq.gz']
INFO: [bwa_aligner] Output file: /path/to/sam/SRR123456.sam
INFO: [bwa_aligner] Attempt 1 for SRR123456
INFO: [bwa_aligner] BWA MEM completed successfully for SRR123456
INFO: [bwa_aligner] File dictionary created with 10 entries.









Workflow Explanation:
Before Running bwa mem:
The input files are prepared and logged.
After Running bwa mem:
The output SAM file is validated for existence and size.
If the SAM file is valid, the process continues.
If the SAM file is missing or empty, a RuntimeError is raised, stopping further execution.
Benefits of the Validation Step:
Detects issues where bwa mem runs successfully but produces an empty or missing SAM file.
Prevents downstream tools from processing invalid SAM files.
Ensures robust error handling and comprehensive logging.

'''