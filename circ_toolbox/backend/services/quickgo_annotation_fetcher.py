import requests
import os
import time
import pandas as pd
import random
import json
from Bio.Blast import NCBIXML
from circ_toolbox.backend.utils import BasePipelineTool, log_runtime


class GOAnnotationFetcher(BasePipelineTool):
    """
    A class to fetch GO annotations from the QuickGO API based on BLASTP/DIAMOND output.
    """

    DEFAULT_CONFIG = {
        "batch_size": 3,
        "sleep_time": 1,
        "evalue_threshold": 1e-10,
        "max_retries": 10,
        "api_timeout": (10, 200),
        "quickgo_url": "https://www.ebi.ac.uk/QuickGO/services/annotation/search",
        "geneProductType": "protein",
        "fields_to_include": ["goName", "taxonName", "name", "synonyms"],
        "aspect": ["biological_process", "molecular_function", "cellular_component"],
        "limit": 200,
    }

    def __init__(self, output_dir='processed_annotations', config=None):
        """
        Initialize GOAnnotationFetcher with file paths and settings.

        Args:
            output_dir (str): Directory to save processed annotations.
            config (dict): Finalized configuration dictionary (already merged by orchestration).
        """
        super().__init__("quickgo")  # Automatically injects the "quickgo" logger

        # Assign configuration values to class attributes directly
        self.output_dir = output_dir
        self.batch_size = config["batch_size"]
        self.evalue_threshold = config["evalue_threshold"]
        self.max_retries = config["max_retries"]
        self.sleep_time = config["sleep_time"]
        self.api_timeout = tuple(config["api_timeout"])
        self.quickgo_url = config["quickgo_url"]
        self.gene_product_type = config["geneProductType"]
        self.fields_to_include = config["fields_to_include"]
        self.aspect = config["aspect"]
        self.limit = config["limit"]

        # Create the output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

        self.logger.info(f"GOAnnotationFetcher initialized with config: {config}")


    @log_runtime("quickgo")
    def fetch_annotations(self, gene_uniprot_mapping, annotation_file):
        """
        Fetches annotations from the QuickGO API for all valid UniProt IDs and saves them to a JSONL file.

        Args:
            gene_uniprot_mapping (dict): Dictionary of gene-to-UniProt ID mappings.
            annotation_file (str): Path to the output JSONL file.

        Returns:
            str: Path to the annotation file containing fetched annotations.
        """
        self.log_start("Fetch Annotations")

        # Instance-level attributes are used directly
        evalue_threshold = self.evalue_threshold
        max_retries = self.max_retries
        api_timeout = self.api_timeout

        uniprot_id_to_gene_info = {}  # Mapping UniProt ID → list of (gene_id, evalue) pairs
        no_annotations_uniprot_ids = []  # Track UniProt IDs with no GO terms
        saved_uniprot_ids = set()  # Track already saved UniProt IDs

        # If the annotation file exists, load the saved UniProt IDs to prevent duplicates
        if os.path.exists(annotation_file):
            self.logger.info(f"Resuming annotation fetch from {annotation_file}. Loading existing entries to avoid duplicates...")
            with open(annotation_file, "r") as f:
                for line in f:
                    annotation = json.loads(line)
                    gene_product_id = annotation["geneProductId"].split(":")[-1]
                    saved_uniprot_ids.add(gene_product_id)
            self.logger.info(f"Loaded {len(saved_uniprot_ids)} previously saved UniProt IDs.")

        # GOAL 1: Build the uniprot_id_to_gene_info to hold ALL (gene_id, evalue) pairs
        for gene_id, uni_evalue_pairs in gene_uniprot_mapping.items():
            for uniprot_id, evalue in uni_evalue_pairs:
                if evalue <= evalue_threshold:
                    uniprot_id_to_gene_info.setdefault(uniprot_id, []).append((gene_id, evalue))

        # GOAL 2: Build unique UniProt ID list for batch querying, excluding already saved IDs
        uniprot_ids = list(set(uniprot_id_to_gene_info.keys()) - saved_uniprot_ids)
        self.logger.info(f"Total unique UniProt IDs to process: {len(uniprot_ids)}")
        
        self.logger.info("Starting to fetch GO annotations from the QuickGO API...")

        # GOAL 3: Fetch annotations in batches
        for i in range(0, len(uniprot_ids), self.batch_size):
            batch_ids = uniprot_ids[i:i + self.batch_size]

            # Build query parameters using helper function
            query_params = self._build_query_params(batch_ids)
                                        
            self.logger.info(f"Processing batch {i // self.batch_size + 1} of {len(uniprot_ids) // self.batch_size + 1}")

            retries = 0
            while retries < max_retries:
                try:
                    self.logger.info(f"Sending request for batch {i // self.batch_size + 1}, attempt {retries + 1}...")
                    response = requests.post(self.quickgo_url, params=query_params, headers={"Accept": "application/json"}, timeout=api_timeout)
                    response.raise_for_status()

                    json_data = response.json()
                    results = json_data.get("results", [])

                    self.logger.debug(f"Raw response data: {json_data}")
                    self.logger.info(f"Raw response size: {len(response.content)} bytes.")

                    # GOAL 4: Log results and unannotated UniProt IDs
                    if results:
                        annotated_ids = {result["geneProductId"].split(":")[-1] for result in results}
                        unannotated_ids = set(batch_ids) - annotated_ids

                        self.logger.info(f"Batch {i // self.batch_size + 1} returned {len(results)} annotations for {len(annotated_ids)} unique UniProt IDs.")
                        self.logger.debug(f"Remaining unannotated IDs: {unannotated_ids}")

                        no_annotations_uniprot_ids.extend(unannotated_ids)

                        # GOAL 5: Save all annotations for the batch
                        with open(annotation_file, "a") as f:
                            for annotation in results:
                                json.dump(annotation, f)
                                f.write("\n")
                        self.logger.info(f"Saved {len(results)} new annotations to {annotation_file}")
                    else:
                        self.logger.warning(f"No GO terms found for UniProt IDs in batch: {batch_ids}")
                        no_annotations_uniprot_ids.extend(batch_ids)

                    break  # Exit retry loop after successful request

                except requests.exceptions.RequestException as e:
                    retries += 1
                    wait_time = random.randint(5, 15)
                    self.logger.error(f"HTTP request failed for batch {i // self.batch_size + 1} on attempt {retries}: {e}")
                    self.logger.warning(f"Retrying after {wait_time} seconds...")
                    time.sleep(wait_time)

                    if retries >= max_retries:
                        self.logger.error(f"Max retries reached for batch {i // self.batch_size + 1}. Skipping batch.")
                        break

            time.sleep(self.sleep_time)

        # Final self.logger and save no-annotations IDs
        self.logger.info(f"Total annotations saved to file: {annotation_file}")
        self.logger.info(f"Number of UniProt IDs with no GO terms: {len(no_annotations_uniprot_ids)}")
        self.logger.info(f"Completed fetching annotations for all {len(uniprot_ids)} UniProt IDs.")

        no_annotations_file = os.path.join(os.path.dirname(annotation_file), "no_annotations_uniprot_ids.json")
        with open(no_annotations_file, "w") as f:
            json.dump(no_annotations_uniprot_ids, f)
        self.logger.info(f"Saved UniProt IDs with no GO terms to {no_annotations_file}")

        # GOAL 6: Return annotation file path and uniprot_id_to_gene_info
        self.log_end("Fetch Annotations")
        return annotation_file, uniprot_id_to_gene_info


    def _build_query_params(self, batch_ids, overrides=None):
        """
        Build query parameters for the QuickGO API request.

        Args:
            batch_ids (list): UniProt IDs for the current batch.
            overrides (dict): Optional overrides for additional query parameters.

        Returns:
            dict: The final query parameters.
        """
        default_params = {
            "geneProductType": self.gene_product_type,
            "aspect": self.aspect,
            "includeFields": self.fields_to_include,
            "limit": self.limit,
            "geneProductId": ",".join(batch_ids),
        }
        return {**default_params, **(overrides or {})}


    ### --- ### --- ### VERIFICATIONS ### --- ### --- ###
    def is_annotation_file_complete(self, output_file, expected_uniprot_ids):
        """
        Check if the annotation JSONL file contains all expected UniProt IDs.

        Args:
            output_file (str): Path to the annotation JSONL file.
            expected_uniprot_ids (set): Set of all expected UniProt IDs.

        Returns:
            bool: True if the file contains annotations for all expected UniProt IDs, False otherwise.
        """
        self.log_start("Check Annotation Completeness")

        # Step 1: Verify if the file exists
        if not os.path.exists(output_file):
            self.logger.info(f"Annotation file {output_file} does not exist.")
            self.log_end("Check Annotation Completeness")
            return False

        # Step 2: Extract saved UniProt IDs from the file
        saved_uniprot_ids = set()
        try:
            with open(output_file, "r") as f:
                saved_uniprot_ids = {
                    json.loads(line)["geneProductId"].split(":")[-1] for line in f
                }
        except (IOError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to read or parse {output_file}: {e}")
            self.log_end("Check Annotation Completeness")
            return False

        # Step 3: Identify missing IDs
        missing_ids = expected_uniprot_ids - saved_uniprot_ids
        if not missing_ids:
            self.logger.info(f"Annotation file {output_file} is complete. No missing IDs.")
            self.log_end("Check Annotation Completeness")
            return True

        self.logger.info(f"Annotation file {output_file} is incomplete. Missing {len(missing_ids)} UniProt IDs.")
        self.log_end("Check Annotation Completeness")
        return False





'''

from Bio.Blast import NCBIXML

def extract_ids_from_diamond_results(self, use_evalue_filtering=True, evalue_threshold=1e-10):
    """
    Extracts gene ID to UniProt ID mappings from the DIAMOND .xml results file.
    """
    logging.info(f"Extracting gene-to-UniProt ID mappings from DIAMOND XML results: {self.diamond_results_file}")
    gene_uniprot_mapping = {}

    try:
        with open(self.diamond_results_file) as xml_file:
            diamond_records = NCBIXML.parse(xml_file)
            for record in diamond_records:
                query_id = record.query  # Gene ID
                for alignment in record.alignments:
                    evalue = alignment.hsps[0].expect  # E-value
                    if use_evalue_filtering and evalue >= evalue_threshold:
                        continue

                    uniprot_id = alignment.accession  # UniProt accession ID
                    gene_uniprot_mapping.setdefault(query_id, []).append((uniprot_id, evalue))

        logging.info(f"Successfully extracted {len(gene_uniprot_mapping)} gene-to-UniProt mappings from DIAMOND XML results.")
    except FileNotFoundError:
        logging.error(f"DIAMOND results file not found: {self.diamond_results_file}")
        raise SystemExit("Exiting due to missing DIAMOND results file.")
    except Exception as e:
        logging.error(f"Error during DIAMOND gene-to-UniProt ID extraction: {e}")
        raise SystemExit("Exiting due to error in parsing the DIAMOND XML results file.")

    return gene_uniprot_mapping

'''


'''
###
Why is evalue_threshold Used in Multiple Functions (extract_ids_from_* and fetch_annotations)?
evalue_threshold is used in different functions (extract_ids_from_blastp_results, extract_ids_from_diamond_results, and fetch_annotations) for distinct purposes. Let me explain the reasoning behind each:

1. extract_ids_from_blastp_results and extract_ids_from_diamond_results:
These functions extract only relevant UniProt IDs from the BLASTP or DIAMOND outputs based on the E-value threshold. The logic here is as follows:

E-values quantify the statistical significance of the sequence alignment (lower is better).
Only hits with an E-value below the threshold are included in the mapping.
The purpose is to discard weak matches early so that irrelevant UniProt IDs aren’t sent to the QuickGO API.
Key point: This step narrows down the number of IDs fetched before performing API queries.

2. fetch_annotations:
The fetch_annotations function receives a mapping of UniProt IDs that already passed the initial filtering. However, this function allows a second layer of filtering for additional flexibility. Here’s why:

The annotations might include UniProt IDs from ambiguous mappings or multiple hits.
You may want to filter UniProt-Gene pairs further, especially when handling GO terms associated with weak hits.

###
Why Have Filtering in Both Stages?
Pre-filtering (extract_ids_from_* functions):

Reduces the number of UniProt IDs sent to the API.
Saves API calls, bandwidth, and time by skipping weak hits early.
Post-filtering (fetch_annotations):

Ensures that during processing of API responses, no low-confidence UniProt-Gene pairs sneak in (e.g., due to how ambiguous matches are processed).
Adds a safety net in case some hits were incorrectly processed or if you want finer control at the annotation stage.


'''


'''

for result in uni_results:
    
    
# Iterate over all valid (gene_id, evalue) pairs for this UniProt ID
for gene_id, evalue in uniprot_id_to_gene_info[uniprot_id]:
    
    
    
    go_info = {
        "GeneID": gene_id,
        "UniProtID": uniprot_id,
        "E-value": evalue,
        "GO_ID": result.get("goId"),
        "GO_Name": result.get("goName"),
        "Aspect": result.get("goAspect"),
        "Evidence_Code": result.get("evidenceCode"),
        "Source": result.get("assignedBy"),
        "Qualifier": result.get("qualifier", ""),
        "Extensions": result.get("extensions", []),
        "Taxon_ID": result.get("taxonId", None),
        "Taxon_Name": result.get("taxonName", ""),
    }
    annotations.append(go_info)

'''