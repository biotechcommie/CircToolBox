import os
import subprocess
import multiprocessing
import requests
import time
from tqdm import tqdm
from Bio.Blast import NCBIXML
import pandas as pd 
from circ_toolbox.backend.utils import BasePipelineTool, log_runtime


class UniProtDataPreparer(BasePipelineTool):
    """
    A class to download UniProt data, prepare BLAST and DIAMOND databases, and run BLASTP and DIAMOND queries.
    """
    DEFAULT_CONFIG = {
        "uniprot_url": "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.fasta.gz",
        "num_threads": multiprocessing.cpu_count(),
        "force_run": False,
        "blast_output_file": "blast_results.xml",
        "diamond_output_file": "diamond_results.tsv",
        "skip_download": False,
        "skip_blast": False,
        "skip_diamond": False,
        "max_retries": 5,
        "retry_wait_time": 5,
    }
    
    def __init__(self, output_dir="uniprot_data", config=None):
        """
        Initializes the UniProtDataPreparer class.

        Args:
            output_dir (str): Directory to save UniProt data and databases.
            config (dict): Configuration dictionary with optional overrides.
        """
        super().__init__("uniprot")  # Automatically injects the "uniprot" logger

        # Merge default config with any provided config
        final_config = {**self.DEFAULT_CONFIG, **(config or {})}

        # Assign values from the merged config
        self.output_dir = output_dir
        self.uniprot_url = final_config["uniprot_url"]
        self.num_threads = final_config["num_threads"]
        self.force_run = final_config["force_run"]
        self.max_retries = final_config["max_retries"]
        self.retry_wait_time = final_config["retry_wait_time"]
        self.blast_output_file = os.path.join(output_dir, final_config["blast_output_file"])
        self.diamond_output_file = os.path.join(output_dir, final_config["diamond_output_file"])

        # File paths
        self.uniprot_fasta_gz = os.path.join(output_dir, "uniprot_sprot.fasta.gz")
        self.uniprot_fasta = os.path.join(output_dir, "uniprot_sprot.fasta")
        self.blast_db = os.path.join(output_dir, "uniprot_blast_db")
        self.diamond_db = os.path.join(output_dir, "uniprot_diamond_db.dmnd")

        # Create the output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

        self.logger.info(f"UniProtDataPreparer initialized with config: {final_config}")



    @log_runtime("uniprot")
    def download_uniprot_data(self):
        """
        Downloads the UniProtKB data file if it does not already exist and decompresses it.
        """
        self.log_start("Downloading UniProtKB Data")

        if os.path.exists(self.uniprot_fasta) and not self.force_run:
            self.logger.info("UniProtKB FASTA file already exists. Skipping download.")
            self.log_end("Downloading UniProtKB Data")
            return

        for attempt in range(self.max_retries):
            try:
                if not os.path.exists(self.uniprot_fasta_gz) or self.force_run:
                    self.logger.info("Downloading UniProtKB data...")
                    response = requests.get(self.uniprot_url, stream=True)
                    response.raise_for_status()
                    total_size = int(response.headers.get("content-length", 0))

                    with open(self.uniprot_fasta_gz, 'wb') as f, tqdm(total=total_size, unit="B", unit_scale=True) as pbar:
                        for data in response.iter_content(1024):
                            f.write(data)
                            pbar.update(len(data))

                    self.logger.info("Download complete.")
                break

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Download attempt {attempt + 1} failed: {e}")
                time.sleep(self.retry_wait_time)

        # Decompress the downloaded file
        try:
            self.logger.info("Decompressing UniProtKB data...")
            subprocess.run(['gunzip', '-k', self.uniprot_fasta_gz], check=True)
            self.logger.info("Decompression complete. UniProtKB FASTA file is ready.")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to decompress UniProtKB data: {e}")
            raise SystemExit("Exiting due to failed decompression.")
        
        self.log_end("Downloading UniProtKB Data")
    
    @log_runtime("uniprot")
    def prepare_blast_db(self):
        """
        Prepares the BLAST database from the UniProtKB data if it doesn't already exist.
        """
        self.log_start("Preparing BLAST Database")

        if not os.path.exists(self.blast_db) or self.force_run:
            try:
                self.logger.info("Creating BLAST database...")
                subprocess.run(['makeblastdb', '-in', self.uniprot_fasta, '-dbtype', 'prot', '-out', self.blast_db], check=True)
                self.logger.info("BLAST database created successfully.")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to create BLAST database: {e}")
                raise SystemExit("Exiting due to failed BLAST database creation.")
        else:
            self.logger.info("BLAST database already exists. Skipping creation.")

        self.log_end("Preparing BLAST Database")

    @log_runtime("uniprot")
    def prepare_diamond_db(self):
        """
        Prepares the DIAMOND database from the UniProtKB data if it doesn't already exist.
        """
        self.log_start("Preparing DIAMOND Database")

        if not os.path.exists(self.diamond_db) or self.force_run:
            try:
                self.logger.info("Creating DIAMOND database...")
                subprocess.run(['diamond', 'makedb', '--in', self.uniprot_fasta, '-d', self.diamond_db], check=True)
                self.logger.info("DIAMOND database created successfully.")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to create DIAMOND database: {e}")
                raise SystemExit("Exiting due to failed DIAMOND database creation.")
        else:
            self.logger.info("DIAMOND database already exists. Skipping creation.")

        self.log_end("Preparing DIAMOND Database")

    def _retry_request(self, command, desc):
        """
        Helper function to retry subprocess calls.
        """
        for attempt in range(self.max_retries):
            try:
                subprocess.run(command, check=True)
                self.logger.info(f"{desc} completed successfully.")
                return
            except subprocess.CalledProcessError:
                self.logger.warning(f"Attempt {attempt + 1} failed for {desc}. Retrying...")
                time.sleep(self.retry_wait_time)

        raise SystemExit(f"Max retries reached. Exiting {desc} due to failure.")

    @log_runtime("uniprot")
    def run_blastp(self, query_file, output_file, num_threads=None, force_run=False):
        """
        Runs BLASTP using the prepared BLAST database.
        """
        self.log_start("Running BLASTP")

        force_run = self.force_run if force_run is None else force_run
        if os.path.exists(output_file) and not force_run:
            self.logger.info(f"BLASTP results already exist at {output_file}. Skipping BLASTP run.")
            self.log_end("Running BLASTP")
            return

        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        num_threads = num_threads or self.num_threads

        command = [
            'blastp', '-query', query_file, '-db', self.blast_db,
            '-out', output_file, '-outfmt', '5', '-num_threads', str(num_threads)
        ]

        self._retry_subprocess(command, "BLASTP")
        self.logger.info(f"BLASTP completed. Results saved to {output_file}.")
        self.log_end("Running BLASTP")

    @log_runtime("uniprot")
    def run_diamond(self, query_file, output_file, num_threads=None, force_run=False):
        """
        Runs DIAMOND using the prepared DIAMOND database.
        """
        self.log_start("Running DIAMOND")

        force_run = self.force_run if force_run is None else force_run
        if os.path.exists(output_file) and not force_run:
            self.logger.info(f"DIAMOND results already exist at {output_file}. Skipping DIAMOND run.")
            self.log_end("Running DIAMOND")
            return

        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        num_threads = num_threads or self.num_threads

        command = [
            'diamond', 'blastp', '-q', query_file, '-d', self.diamond_db,
            '-o', output_file, '--outfmt', '6', '--max-target-seqs', '5',
            '--evalue', '1e-5', '--threads', str(num_threads)
        ]

        self._retry_subprocess(command, "DIAMOND")
        self.logger.info(f"DIAMOND completed. Results saved to {output_file}.")
        self.log_end("Running DIAMOND")

    @log_runtime("uniprot")
    def run(self, query_file, blast_output_file=None, diamond_output_file=None, force_run=False):
        """
        Full workflow: download UniProtKB, prepare databases, and run both BLASTP and DIAMOND.
        """
        self.log_start("Full UniProt Data Preparation Workflow")

        # Assign default paths if not provided or if invalid (empty string)
        blast_output_file = blast_output_file if blast_output_file else self.blast_output_file
        diamond_output_file = diamond_output_file if diamond_output_file else self.diamond_output_file

        # Download and prepare databases
        self.download_uniprot_data()
        self.prepare_blast_db()
        self.prepare_diamond_db()

        # Run BLASTP
        if not self.is_file_valid(blast_output_file) or force_run:
            self.run_blastp(query_file, blast_output_file, force_run=force_run)
            if not self.validate_blastp_xml(blast_output_file):
                raise SystemExit("BLASTP output validation failed.")
        else:
            self.logger.info(f"Skipping BLASTP as valid results already exist: {blast_output_file}")

        # Run DIAMOND
        if not self.is_file_valid(diamond_output_file) or force_run:
            self.run_diamond(query_file, diamond_output_file, force_run=force_run)
            if not self.validate_diamond_tsv(diamond_output_file):
                raise SystemExit("DIAMOND output validation failed.")
        else:
            self.logger.info(f"Skipping DIAMOND as valid results already exist: {diamond_output_file}")

        self.log_end("Full UniProt Data Preparation Workflow")

    def _retry_subprocess(self, command, desc):
        """
        Helper function to retry subprocess calls with a retry mechanism.

        Args:
            command (list): Command to execute.
            desc (str): Description of the task for logging purposes.
        """
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"{desc} attempt {attempt + 1} of {self.max_retries}...")
                subprocess.run(command, check=True)
                self.logger.info(f"{desc} completed successfully.")
                return  # Exit on success
            except subprocess.CalledProcessError as e:
                self.logger.error(f"{desc} failed on attempt {attempt + 1}: {e}")
                time.sleep(self.retry_wait_time)

        raise SystemExit(f"Max retries reached. Exiting {desc} due to failure.")


    ### --- ### --- ### VERIFICATIONS ### --- ### --- ###
    def is_file_valid(self, file_path):
        """
        Check if the file exists and has a non-zero size.
        
        Args:
            file_path (str): Path to the file.
            
        Returns:
            bool: True if the file exists and is not empty, False otherwise.
        """
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            return False
        if os.path.getsize(file_path) == 0:
            self.logger.error(f"File is empty: {file_path}")
            return False
        return True

    def validate_blastp_xml(self, file_path):
        """
        Validate the BLASTP XML output to ensure it is well-formed and contains data.
        
        Args:
            file_path (str): Path to the BLASTP XML file.
            
        Returns:
            bool: True if the XML is valid and contains data, False otherwise.
        """
        try:
            with open(file_path) as f:
                blast_records = list(NCBIXML.parse(f))
                if not blast_records:
                    self.logger.error(f"No BLAST records found in {file_path}")
                    return False
                self.logger.info(f"BLASTP output file {file_path} is valid.")
                return True
        except Exception as e:
            self.logger.error(f"Error parsing BLASTP XML file {file_path}: {e}")
            return False

    def validate_diamond_tsv(self, file_path):
        """
        Validate the DIAMOND TSV output to ensure it contains valid data.
        
        Args:
            file_path (str): Path to the DIAMOND TSV file.
            
        Returns:
            bool: True if the TSV file is valid and contains data, False otherwise.
        """
        try:
            df = pd.read_csv(file_path, sep='\t', header=None)
            if df.empty:
                self.logger.error(f"No data found in DIAMOND output {file_path}")
                return False
            if len(df.columns) < 2:
                self.logger.error(f"DIAMOND TSV {file_path} does not have the expected columns (len(df.columns) < 2).")
                return False
            self.logger.info(f"DIAMOND output file {file_path} is valid.")
            return True
        except Exception as e:
            self.logger.error(f"Error reading DIAMOND TSV file {file_path}: {e}")
            return False



'''

def download_uniprot_data_wget(self):
    """
    Alternative implementation to download the UniProtKB data file using wget if it does not already exist and decompress it.
    """
    if os.path.exists(self.uniprot_fasta):
        self.logger.info("UniProtKB FASTA file already exists. Skipping download.")
        return

    try:
        if not os.path.exists(self.uniprot_fasta_gz):
            logging.info("Downloading UniProtKB data using wget...")

            # Retry mechanism with wget (manual implementation of retries)
            for attempt in range(3):
                try:
                    # Run wget to download the file
                    subprocess.run(
                        ['wget', '-O', self.uniprot_fasta_gz, self.uniprot_url],
                        check=True
                    )
                    logging.info("Download complete.")
                    break  # Exit the retry loop on successful download
                except subprocess.CalledProcessError as e:
                    logging.warning(f"Download attempt {attempt + 1} with wget failed: {e}")
                    time.sleep(5)  # Wait 5 seconds before retrying
            else:
                # If all attempts fail, exit with an error
                raise SystemExit("Failed to download UniProtKB data after 3 attempts using wget.")

        logging.info("Decompressing UniProtKB data...")
        subprocess.run(['gunzip', '-k', self.uniprot_fasta_gz], check=True)
        logging.info("Decompression complete. UniProtKB FASTA file is ready.")

    except subprocess.CalledProcessError as e:
        logging.error(f"Failed during wget download or decompression: {e}")
        raise SystemExit("Exiting due to failure during wget download or decompression.")

'''


'''
def run_diamond(self, query_file, output_file, num_threads=None):
    """
    Runs DIAMOND using the prepared DIAMOND database with XML output.
    """
    if num_threads is None:
        num_threads = multiprocessing.cpu_count()

    try:
        logging.info(f"Running DIAMOND BLASTP with {num_threads} threads...")
        subprocess.run([
            'diamond', 'blastp', '-q', query_file, '-d', self.diamond_db,
            '-o', output_file, '--outfmt', '5',  # Use XML format (similar to BLASTP)
            '--max-target-seqs', '5',  # Optional: keep top 5 matches for better coverage
            '--evalue', '1e-5', '--threads', str(num_threads)
        ], check=True)
        logging.info(f"DIAMOND completed. Results saved to {output_file}.")

    except subprocess.CalledProcessError as e:
        logging.error(f"DIAMOND failed: {e}")
        raise SystemExit("Exiting due to failed DIAMOND run.")
    
'''