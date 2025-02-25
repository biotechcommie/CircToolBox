import json
import os
import pandas as pd
from circ_toolbox.backend.utils import BasePipelineTool, log_runtime, load_default_config, DataHandler

class AnnotationProcessor(BasePipelineTool):
    """
    A class to process GO annotations and produce filtered or processed annotation files.
    """
    def __init__(self, output_dir):
        """
        Initialize AnnotationProcessor with an output directory.

        Args:
            output_dir (str): Path to the output directory.
        """
        super().__init__("annotation")  # Automatically injects the "annotation" logger
        self.output_dir = output_dir
        default_config = load_default_config("AnnotationProcessor")
        self.evalue_threshold = default_config.get("evalue_threshold", 1e-10)
        self.filtered_annotations_file = os.path.join(self.output_dir, default_config.get("filtered_annotations_file", "filtered_annotations.jsonl"))
        self.aggregated_annotations_file = os.path.join(self.output_dir, default_config.get("aggregated_annotations_file", "aggregated_annotations.tsv"))
        self.processed_annotations_file = os.path.join(self.output_dir, default_config.get("processed_annotations_file", "processed_annotations.tsv"))
        self.report_file = os.path.join(self.output_dir, default_config.get("report_file", "gene_report.txt"))
        self.fields_to_extract = default_config.get("fields_to_extract", ["goName", "taxonName", "name", "synonyms"])
        self.filter_criteria = default_config.get("filter_criteria", {})
        self.best_uniprot_only = default_config.get("best_uniprot_only", False)
        self.memory_safety_threshold = default_config.get("memory_safety_threshold", 500)

        self.data_handler = DataHandler(output_dir, logger=self.logger)  # Pass self.logger to DataHandler

    @log_runtime("annotation")
    def load_mappings(self, file_type, result_file, use_evalue_filtering=True, evalue_threshold=None):
        """
        Load gene-to-UniProt mapping using the DataHandler.

        Args:
            file_type (str): "blast" or "diamond".
            result_file (str): Path to the BLASTP or DIAMOND result file.
            use_evalue_filtering (bool): Whether to apply e-value filtering.
            evalue_threshold (float): E-value threshold for filtering.
        """
        evalue_threshold = evalue_threshold or self.evalue_threshold  # Use default if not provided

        self.log_start("Load Mappings")
        self.gene_uniprot_mapping = self.data_handler.get_gene_uniprot_mapping_from_file(
            file_type, result_file, use_evalue_filtering, evalue_threshold
        )
        self.uniprot_id_to_gene_info = {
            uniprot_id: [(gene_id, evalue) for gene_id, evalue in pairs]
            for gene_id, pairs in self.gene_uniprot_mapping.items()
            for uniprot_id, evalue in pairs
        }
        self.log_end("Load Mappings")

    @log_runtime("annotation")
    def export_filtered_annotations_line_by_line(self, annotation_file, filter_criteria=None, output_file=None):
        """
        Export filtered annotations line-by-line to avoid memory overload.

        Args:
            annotation_file (str): Path to the JSONL annotation file.
            filter_criteria (dict): Filtering criteria for annotations.
            output_file (str): Path to save the filtered annotations. If None, use a default path in output_dir.
        """
        filter_criteria = filter_criteria or self.filter_criteria  # Use default if not provided
        output_file = output_file or self.filtered_annotations_file  # Use default if not provided

        self.log_start("Export Filtered Annotations")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        filtered_count = 0
        with open(annotation_file, "r") as f_in, open(output_file, "w") as f_out:
            for line in f_in:
                annotation = json.loads(line)
                if filter_criteria and not all(annotation.get(k) == v for k, v in filter_criteria.items()):
                    continue
                f_out.write(json.dumps(annotation) + "\n")
                filtered_count += 1

        self.logger.info(f"{filtered_count} filtered annotations saved to {output_file}")
        self.log_end("Export Filtered Annotations")

    @log_runtime("annotation")
    def create_aggregated_annotation_file_line_by_line(self, annotation_file, fields_to_extract=None, output_file=None, best_uniprot_only=None, filter_criteria=None, report_file=None):
        """
        Create a gene-centered processed annotation file without loading all data at once.

        Args:
            annotation_file (str): Path to the JSONL annotation file.
            fields_to_extract (list): Fields to extract from annotations.
            output_file (str): Path to save the processed TSV file. If None, use a default path in output_dir.
            best_uniprot_only (bool): Whether to use only the best UniProt match for each gene ID.
            filter_criteria (dict): Filtering criteria for annotations.
            report_file (str): Path to save the report of filtered-out gene IDs. If None, no report is generated.
        """
        fields_to_extract = fields_to_extract or self.fields_to_extract  # Use default if not provided
        output_file = output_file or self.aggregated_annotations_file  # Use default if not provided
        best_uniprot_only = best_uniprot_only if best_uniprot_only is not None else self.best_uniprot_only  # Use default
        filter_criteria = filter_criteria or self.filter_criteria  # Use default if not provided
        report_file = report_file or self.report_file  # Use default if not provided

        self.log_start("Create Aggregated Annotation File")

        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        gene_to_annotations = {}
        all_gene_ids = set(self.uniprot_id_to_gene_info.keys())
        matching_gene_ids = set()  # To track gene IDs that pass the filter

        with open(annotation_file, "r") as f_in:
            for line in f_in:
                annotation = json.loads(line)

                # Apply filtering criteria
                if filter_criteria and not all(annotation.get(k) == v for k, v in filter_criteria.items()):
                    continue

                uniprot_id = annotation["geneProductId"].split(":")[-1]
                gene_info = self.uniprot_id_to_gene_info.get(uniprot_id, [])
                for gene_id, evalue in gene_info:
                    matching_gene_ids.add(gene_id)
                    if best_uniprot_only:
                        current_best_evalue = gene_to_annotations.get(gene_id, {}).get("best_evalue", float("inf"))
                        if evalue < current_best_evalue:
                            gene_to_annotations[gene_id] = {
                                "uniprot_id": uniprot_id,
                                "best_evalue": evalue,
                                "go_terms": set([annotation.get("goId", "N/A")]),
                                **{field: annotation.get(field, "N/A") for field in fields_to_extract}
                            }
                    else:
                        if gene_id not in gene_to_annotations:
                            gene_to_annotations[gene_id] = {"go_terms": set(), "uniprot_ids": {}}
                        gene_to_annotations[gene_id]["go_terms"].add(annotation.get("goId", "N/A"))
                        gene_to_annotations[gene_id]["uniprot_ids"][uniprot_id] = evalue

        # Write the aggregated output to file
        with open(output_file, "w") as f_out:
            if best_uniprot_only:
                f_out.write("gene_id\tbest_uniprot_id\tbest_evalue\tgo_terms\n")
                for gene_id, data in gene_to_annotations.items():
                    go_terms = ", ".join(data["go_terms"])
                    f_out.write(f"{gene_id}\t{data['uniprot_id']}\t{data['best_evalue']}\t{go_terms}\n")
            else:
                f_out.write("gene_id\tuniprot_ids_and_evalues\tgo_terms\n")
                for gene_id, data in gene_to_annotations.items():
                    uniprot_details = ", ".join(f"{uid}:{evalue}" for uid, evalue in data["uniprot_ids"].items())
                    go_terms = ", ".join(data["go_terms"])
                    f_out.write(f"{gene_id}\t{uniprot_details}\t{go_terms}\n")
        self.logger.info(f"Aggregated annotations saved to {output_file}")

        # Generate report of filtered-out gene IDs if requested
        if report_file:
            os.makedirs(os.path.dirname(report_file), exist_ok=True)
            filtered_out_gene_ids = all_gene_ids - matching_gene_ids
            with open(report_file, "w") as f_report:
                f_report.write("\n".join(filtered_out_gene_ids))
            self.logger.info(f"Report of filtered-out gene IDs saved to {report_file}")

        self.log_end("Create Aggregated Annotation File")

    @log_runtime("annotation")
    def process_annotations_line_by_line(self, annotation_file, fields_to_extract=None, output_file=None, filter_criteria=None, report_file=None):
        """
        Process annotations line-by-line to create a processed TSV file.

        Args:
            annotation_file (str): Path to the JSONL annotation file.
            fields_to_extract (list): Fields to extract from annotations.
            output_file (str): Path to save the processed TSV file. If None, use a default path in output_dir.
            filter_criteria (dict): Filtering criteria for annotations.
            report_file (str): Path to save the report of filtered-out gene IDs. If None, no report is generated.
        """
        fields_to_extract = fields_to_extract or self.fields_to_extract  # Use default
        output_file = output_file or self.processed_annotations_file  # Use default
        filter_criteria = filter_criteria or self.filter_criteria  # Use default
        report_file = report_file or self.report_file  # Use default

        self.log_start("Process Annotations")

        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        all_gene_ids = set(self.uniprot_id_to_gene_info.keys())
        matching_gene_ids = set()  # Track gene IDs with at least one matching UniProt annotation

        with open(annotation_file, "r") as f_in, open(output_file, "w") as f_out:
            f_out.write("\t".join(["gene_id", "uniprot_id", "evalue"] + fields_to_extract) + "\n")

            for line in f_in:
                annotation = json.loads(line)
                if filter_criteria and not all(annotation.get(k) == v for k, v in filter_criteria.items()):
                    continue  # Skip non-matching annotations

                uniprot_id = annotation["geneProductId"].split(":")[-1]
                gene_info = self.uniprot_id_to_gene_info.get(uniprot_id, [])
                for gene_id, evalue in gene_info:
                    matching_gene_ids.add(gene_id)
                    record = [gene_id, uniprot_id, str(evalue)] + [annotation.get(field, "N/A") for field in fields_to_extract]
                    f_out.write("\t".join(record) + "\n")

        self.logger.info(f"Processed annotations saved to {output_file}")

        # Generate report of filtered-out gene IDs if requested
        if report_file:
            os.makedirs(os.path.dirname(report_file), exist_ok=True)
            filtered_out_gene_ids = all_gene_ids - matching_gene_ids
            with open(report_file, "w") as f_report:
                f_report.write("\n".join(filtered_out_gene_ids))
            self.logger.info(f"Report of filtered-out gene IDs saved to {report_file}") 

        self.log_end("Process Annotations")
        

    @log_runtime("annotation")
    def process_annotations_in_memory(self, annotation_file, fields_to_extract=None, output_file=None, filter_criteria=None, report_file=None):
        """
        Process annotations in memory using pandas for small files.

        Args:
            annotation_file (str): Path to the JSONL annotation file.
            fields_to_extract (list): Fields to extract from annotations.
            output_file (str): Path to save the processed TSV file.
            filter_criteria (dict): Filtering criteria for annotations.
            report_file (str): Optional path to save a summary report of the processed annotations.
        """
        fields_to_extract = fields_to_extract or self.fields_to_extract  # Use default if not provided
        output_file = output_file or self.processed_annotations_file  # Use default if not provided
        filter_criteria = filter_criteria or self.filter_criteria  # Use default if not provided
        report_file = report_file or self.report_file  # Use default if not provided
        
        self.log_start("Process Annotations In Memory")

        # Memory safety check
        if os.path.getsize(annotation_file) > self.memory_safety_threshold * 1024 * 1024:  # Default 500 MB
            raise MemoryError(f"File size exceeds memory-safe threshold of {self.memory_safety_threshold} MB. Please use a line-by-line function.")

        self.logger.info(f"Loading annotations from {annotation_file} into memory...")
        annotations = []
        invalid_entries = 0

        with open(annotation_file, "r") as f:
            for line in f:
                try:
                    annotation = json.loads(line)
                    if filter_criteria and not all(annotation.get(k) == v for k, v in filter_criteria.items()):
                        continue
                    if "geneProductId" not in annotation or ":" not in annotation["geneProductId"]:
                        raise ValueError("Invalid 'geneProductId' format. Skipping entry.")
                    annotations.append(annotation)
                except (json.JSONDecodeError, ValueError) as e:
                    invalid_entries += 1
                    self.logger.warning(f"Skipping invalid annotation: {e}")

        self.logger.info(f"Total annotations after filtering: {len(annotations)}")
        self.logger.info(f"Invalid or malformed entries skipped: {invalid_entries}")

        records = []
        filtered_out_genes = set()

        for annotation in annotations:
            uniprot_id = annotation["geneProductId"].split(":")[-1]
            gene_info = self.uniprot_id_to_gene_info.get(uniprot_id, [])
            if not gene_info:
                filtered_out_genes.add(uniprot_id)
            for gene_id, evalue in gene_info:
                record = {
                    "gene_id": gene_id,
                    "uniprot_id": uniprot_id,
                    "evalue": evalue,
                    **{field: annotation.get(field, "N/A") for field in fields_to_extract}
                }
                records.append(record)

        if not records:
            self.logger.warning(f"No records found after filtering for fields: {fields_to_extract}. Empty TSV will be saved.")

        # Convert to DataFrame and save to TSV
        df = pd.DataFrame(records)
        df.to_csv(output_file, sep='\t', index=False)
        self.logger.info(f"Processed annotations saved to {output_file}")
        self.logger.info(f"Summary: {len(df)} records written to {output_file}")

        if report_file:
            with open(report_file, "w") as report:
                report.write(f"Total records processed: {len(df)}\n")
                report.write(f"Number of UniProt IDs filtered out: {len(filtered_out_genes)}\n")
                report.write("Filtered out UniProt IDs:\n")
                for uniprot_id in filtered_out_genes:
                    report.write(f"{uniprot_id}\n")
                report.write(f"Invalid annotations skipped: {invalid_entries}\n")
            self.logger.info(f"Summary report saved to {report_file}")

        self.log_end("Process Annotations In Memory")

    @log_runtime("annotation")
    def query_go_terms_for_gene_line_by_line(self, annotation_file, gene_id, best_uniprot_only=None, report_file=None):
        """
        Query GO terms for a specific gene ID without loading the entire file into memory.

        Args:
            annotation_file (str): Path to the JSONL annotation file.
            gene_id (str): The gene ID to query.
            best_uniprot_only (bool): Whether to return only GO terms from the best UniProt match.
            report_file (str): Optional path to save a summary report.
        
        Returns:
            list: List of GO terms associated with the gene ID.
        """
        best_uniprot_only = best_uniprot_only if best_uniprot_only is not None else self.best_uniprot_only  # Use default if not provided
        report_file = report_file or self.report_file  # Use default if not provided

        self.log_start(f"Query GO Terms for Gene {gene_id}")

        uniprot_ids = self.gene_uniprot_mapping.get(gene_id, [])
        if not uniprot_ids:
            self.logger.warning(f"No UniProt IDs found for gene ID: {gene_id}")
            self.log_end(f"Query GO Terms for Gene {gene_id}")
            return ["No UniProt IDs found"]

        if best_uniprot_only:
            best_uniprot_id, _ = min(uniprot_ids, key=lambda x: x[1]) # Select UniProt ID with the best (lowest) e-value
            uniprot_ids = [best_uniprot_id]

        go_terms = set()
        skipped_uniprot_ids = set()
        invalid_entries = 0

        with open(annotation_file, "r") as f:
            for line in f:
                try:
                    annotation = json.loads(line)
                    if "geneProductId" not in annotation or ":" not in annotation["geneProductId"]:
                        skipped_uniprot_ids.add(annotation.get("geneProductId", "N/A"))
                        raise ValueError("Invalid 'geneProductId' format.")
                    
                    uniprot_id = annotation["geneProductId"].split(":")[-1]
                    if uniprot_id in uniprot_ids:
                        go_terms.add(annotation.get("goId", "N/A"))
                except (json.JSONDecodeError, ValueError):
                    invalid_entries += 1

        self.logger.info(f"Found {len(go_terms)} GO terms for gene {gene_id}.")
        self.logger.info(f"Invalid entries skipped: {invalid_entries}")

        if report_file:
            with open(report_file, "w") as report:
                report.write(f"GO Terms for gene ID {gene_id}:\n")
                report.write(f"Total UniProt IDs queried: {len(uniprot_ids)}\n")
                report.write(f"GO terms found: {len(go_terms)}\n")
                report.write(f"Skipped UniProt IDs: {len(skipped_uniprot_ids)}\n")
                report.write(f"Invalid annotations skipped: {invalid_entries}\n")
                if skipped_uniprot_ids:
                    report.write("List of skipped UniProt IDs (invalid format):\n")
                    for skipped_id in skipped_uniprot_ids:
                        report.write(f"{skipped_id}\n")
            self.logger.info(f"Summary report saved to {report_file}")

        self.log_end(f"Query GO Terms for Gene {gene_id}")
        return list(go_terms) if go_terms else ["No GO terms found"]

'''
### USAGE CASES ###

# -----------------------------------------------------------------------------
# 1 - Create a subset of annotations (JSONL) with the filtering criteria, e.g:taxonId: 3575
# -----------------------------------------------------------------------------

# Function to use:
# export_filtered_annotations_line_by_line

# Initialize the processor
annotation_processor = AnnotationProcessor(output_dir="output_directory")

# Path to the full annotation file
annotation_file = "path/to/full_annotations.jsonl"

# Filtering criteria
filter_criteria = {"taxonId": 3575}

# Output filtered JSONL file
output_filtered_file = "output_directory/filtered_annotations_taxon_3575.jsonl"

# Create the filtered subset
annotation_processor.export_filtered_annotations_line_by_line(
    annotation_file=annotation_file,
    filter_criteria=filter_criteria,
    output_file=output_filtered_file
)

Explanation:
filter_criteria={"taxonId": 3575} filters only the annotations where the taxonId is 3575.
Result: A filtered JSONL file containing only the annotations that match the specified taxon.

# -----------------------------------------------------------------------------
# 2 - Create a gene-centered processed annotation file with all GO terms from UniProt IDs for each gene ID
# ----------------------------------------------------------------------------- 

# Function to use:
# create_aggregated_annotation_file_line_by_line

# Initialize the processor
annotation_processor = AnnotationProcessor(output_dir="output_directory")

# Path to the full or filtered annotation file
annotation_file = "path/to/full_or_filtered_annotations.jsonl"

# Fields to extract
fields_to_extract = ["goName", "goAspect", "evidenceCode"]

# Output processed annotation file
output_file = "output_directory/gene_centered_annotations.tsv"

# Create gene-centered processed annotation file
annotation_processor.create_aggregated_annotation_file_line_by_line(
    annotation_file=annotation_file,
    fields_to_extract=fields_to_extract,
    output_file=output_file,
    best_uniprot_only=False  # Include all UniProt IDs for each gene ID
)

Explanation:
The file contains one row per gene ID.
The columns include all GO terms associated with all UniProt IDs for the gene.
fields_to_extract: You can customize the fields to include additional data like goName, goAspect, etc.
The "uniprot_ids_and_evalues" column will show a list of UniProt IDs and their E-values for the gene.

# -----------------------------------------------------------------------------
# 3 - Create a non-aggregated processed annotation file with a single UniProt ID per row (gene-UniProt pair)
# ----------------------------------------------------------------------------- 

# Function to use:
# process_annotations_line_by_line

# Initialize the processor
annotation_processor = AnnotationProcessor(output_dir="output_directory")

# Path to the full or filtered annotation file
annotation_file = "path/to/full_or_filtered_annotations.jsonl"

# Fields to extract
fields_to_extract = ["goName", "goAspect", "evidenceCode"]

# Output processed annotation file
output_file = "output_directory/gene_uniprot_pair_annotations.tsv"

# Create non-aggregated processed annotation file
annotation_processor.process_annotations_line_by_line(
    annotation_file=annotation_file,
    fields_to_extract=fields_to_extract,
    output_file=output_file,
    filter_criteria=None  # No additional filtering criteria
)

# -----------------------------------------------------------------------------
# 4 - Create a processed annotation file using only the best UniProt ID match for each gene ID
# ----------------------------------------------------------------------------- 

# Function to use:
# create_aggregated_annotation_file_line_by_line

# Initialize the processor
annotation_processor = AnnotationProcessor(output_dir="output_directory")

# Path to the full or filtered annotation file
annotation_file = "path/to/full_or_filtered_annotations.jsonl"

# Fields to extract
fields_to_extract = ["goName", "goAspect", "evidenceCode"]

# Output processed annotation file
output_file = "output_directory/best_uniprot_annotations.tsv"

# Create processed annotation file using the best UniProt match
annotation_processor.create_aggregated_annotation_file_line_by_line(
    annotation_file=annotation_file,
    fields_to_extract=fields_to_extract,
    output_file=output_file,
    best_uniprot_only=True  # Use only the best UniProt ID for each gene ID
)

Explanation:
This file contains one row per gene ID.
The UniProt ID with the best E-value for the gene ID is used.
The "best_uniprot_id" and "best_evalue" columns show the top UniProt ID and its E-value.
You can include additional fields like "goName" and "evidenceCode".
'''

'''

# -----------------------------------------------------------------------------
# 'report_file' argument - crete report on gene IDs dropped after filtering annotations
# -----------------------------------------------------------------------------

# report_file default is: None
# When output file path for report is not provided, skip report creation

annotation_processor = AnnotationProcessor(output_dir="output/")

# Example 1: Aggregated file with report
annotation_processor.create_aggregated_annotation_file_line_by_line(
    annotation_file="annotations.jsonl",
    fields_to_extract=["goName", "goAspect"],
    output_file="output/aggregated_annotations.tsv",
    best_uniprot_only=True,
    filter_criteria={"taxonId": 3575},
    report_file="output/filtered_out_gene_ids.txt"
)

# Example 2: Processed file with report
annotation_processor.process_annotations_line_by_line(
    annotation_file="annotations.jsonl",
    fields_to_extract=["goName", "evidenceCode"],
    output_file="output/processed_annotations.tsv",
    filter_criteria={"goAspect": "biological_process"},
    report_file="output/filtered_out_gene_ids.txt"
)

'''

'''


# Usage example:
annotation_processor = AnnotationProcessor(output_dir="/path/to/output")

annotation_processor.process_annotations_in_memory(
    annotation_file="/path/to/annotations.jsonl",
    fields_to_extract=["goId", "goName", "taxonId"],
    output_file="/path/to/output/processed_annotations.tsv",
    filter_criteria={"taxonId": 3575}  # Example: only annotations for a specific species
)

Expected Output:

A TSV file with the following columns:
    gene_id  uniprot_id  evalue  goId  goName  taxonId
Only annotations with 'taxonId' equal to 3575 will be included.


# Query GO terms for a gene ID, using the best UniProt match
go_terms = annotation_processor.query_go_terms_for_gene_line_by_line(
    annotation_file="/path/to/annotations.jsonl",
    gene_id="gene_ABC123",
    best_uniprot_only=True
)
print(f"GO terms for gene_ABC123: {go_terms}")

Expected Output:

A list of GO terms (e.g., ["GO:0008150", "GO:0003674"]), showing the terms for the best UniProt ID associated with the gene.
'''

'''
# Usage Example:
# 'process_annotations_in_memory'

annotation_processor.process_annotations_in_memory(
    annotation_file="/path/to/annotations.jsonl",
    fields_to_extract=["goId", "goName", "taxonId"],
    output_file="/path/to/output/processed_annotations.tsv",
    filter_criteria={"taxonId": 9606},
    report_file="/path/to/output/report.txt"
)

# 'query_go_terms_for_gene_line_by_line'

go_terms = annotation_processor.query_go_terms_for_gene_line_by_line(
    annotation_file="/path/to/annotations.jsonl",
    gene_id="gene_ABC123",
    best_uniprot_only=True,
    report_file="/path/to/output/go_terms_report.txt"
)
print(f"GO terms for gene ABC123: {go_terms}")



'process_annotations_in_memory'
    Added validation for "'geneProductId'" format and skipped malformed entries.
    Detailed self.logger for each step of processing.
    If no valid records are found, saves an empty TSV file and logs a warning.
    The optional 'report_file' saves details about filtered-out UniProt IDs and skipped entries.

'query_go_terms_for_gene_line_by_line'
    Validates "'geneProductId'" format.
    Logs the number of skipped UniProt IDs and malformed records.
    Saves the summary report with:
        Number of GO terms found.
        Number of invalid or skipped entries.
        List of skipped UniProt IDs for further debugging.
'''