import pickle
import os
import pandas as pd
from Bio.Blast import NCBIXML
from circ_toolbox.backend.utils import log_runtime, load_default_config, get_logger

# Initialize logger
logger = get_logger("data_handler")

class DataHandler:
    def __init__(self, output_dir):
        self.output_dir = output_dir

    # -----------------------------------------------------------------------------------
    # extract, create, save and load mapping
    # -----------------------------------------------------------------------------------   

    def extract_ids_from_blastp_results(self, blast_results_file, use_evalue_filtering=True, evalue_threshold=1e-10):
        """
        Extracts gene ID to UniProt ID mappings from the BLASTP .xml results file, with optional E-value filtering.

        Args:
            use_evalue_filtering (bool): Whether to apply E-value threshold filtering.
            evalue_threshold (float): The E-value threshold for filtering alignments.

        Returns:
            dict: A dictionary mapping gene IDs to UniProt IDs.
        """
        mapping_file = "blast_mapping.pkl"
        existing_mapping = self.load_mapping_from_file(mapping_file)
        if existing_mapping:
            return existing_mapping
        
        logger.info(f"Extracting gene-to-UniProt ID mappings from BLASTP results: {blast_results_file}")
        gene_uniprot_mapping = {}

        try:
            with open(blast_results_file) as xml_file:
                blast_records = NCBIXML.parse(xml_file)
                for record in blast_records:
                    query_id = record.query  # The original gene ID from the .pep file
                    for alignment in record.alignments:
                        evalue = alignment.hsps[0].expect  # Get the E-value of the best HSP
                        if use_evalue_filtering and evalue >= evalue_threshold:
                            continue

                        uniprot_id = alignment.hit_def.split('|')[1]  # Extract the UniProt accession
                        gene_uniprot_mapping.setdefault(query_id, []).append((uniprot_id, evalue))

            # Log ambiguous mappings if there are multiple UniProt IDs for any gene
            ambiguous_mappings = {k: v for k, v in gene_uniprot_mapping.items() if len(v) > 1}
            if ambiguous_mappings:
                logger.warning(f"Found {len(ambiguous_mappings)} ambiguous mappings (multiple UniProt IDs for a gene ID):")
                for gene_id, uniprot_ids in ambiguous_mappings.items():
                    # Convert tuples to string representations for logger
                    uniprot_str_list = [f"{uid} (E-value: {evalue:.2e})" for uid, evalue in uniprot_ids]
                    logger.warning(f"{gene_id}: {', '.join(uniprot_str_list)}")
                                                    
            logger.info(f"Successfully extracted {len(gene_uniprot_mapping)} gene-to-UniProt mappings from BLASTP results.")
        except FileNotFoundError:
            logger.error(f"BLASTP results file not found: {blast_results_file}")
            raise SystemExit("Exiting due to missing BLASTP results file.")
        except Exception as e:
            logger.error(f"Error during BLASTP gene-to-UniProt ID extraction: {e}")
            raise SystemExit("Exiting due to error in parsing the BLASTP results file.")

        self.save_mapping_to_file(gene_uniprot_mapping, mapping_file)  # Save the mapping
        return gene_uniprot_mapping
 
    def extract_ids_from_diamond_results(self, diamond_results_file, use_evalue_filtering=True, evalue_threshold=1e-10):
        """
        Extracts gene ID to UniProt ID mappings from the DIAMOND .tsv results file, with optional E-value filtering.

        Args:
            use_evalue_filtering (bool): Whether to apply E-value threshold filtering.
            evalue_threshold (float): The E-value threshold for filtering alignments.

        Returns:
            dict: A dictionary mapping gene IDs to UniProt IDs and E-values.
        """
        mapping_file = "diamond_mapping.pkl"
        existing_mapping = self.load_mapping_from_file(mapping_file)
        if existing_mapping:
            return existing_mapping
        
        logger.info(f"Extracting gene-to-UniProt ID mappings from DIAMOND results: {diamond_results_file}")
        gene_uniprot_mapping = {}

        try:
            # Load tabular DIAMOND output with fixed fields
            df = pd.read_csv(diamond_results_file, sep='\t', header=None,
                            names=[
                                'query_id', 'subject_id', 'pident', 'length', 'mismatch', 'gapopen', 
                                'qstart', 'qend', 'sstart', 'send', 'evalue', 'bitscore'
                            ])

            for _, row in df.iterrows():
                query_id = row['query_id']
                uniprot_id = row['subject_id']
                evalue = row['evalue']

                # Apply E-value filtering
                if use_evalue_filtering and evalue >= evalue_threshold:
                    continue

                gene_uniprot_mapping.setdefault(query_id, []).append((uniprot_id, evalue))


            # Log ambiguous mappings if there are multiple UniProt IDs for any gene
            ambiguous_mappings = {k: v for k, v in gene_uniprot_mapping.items() if len(v) > 1}
            if ambiguous_mappings:
                logger.warning(f"Found {len(ambiguous_mappings)} ambiguous mappings (multiple UniProt IDs for a gene ID):")
                for gene_id, uniprot_ids in ambiguous_mappings.items():
                    uniprot_list = ', '.join(f"{uid} (E={evalue})" for uid, evalue in uniprot_ids)
                    logger.warning(f"{gene_id}: {uniprot_list}")

            logger.info(f"Successfully extracted {len(gene_uniprot_mapping)} gene-to-UniProt mappings from DIAMOND results.")
        except FileNotFoundError:
            logger.error(f"DIAMOND results file not found: {diamond_results_file}")
            raise SystemExit("Exiting due to missing DIAMOND results file.")
        except Exception as e:
            logger.error(f"Error during DIAMOND gene-to-UniProt ID extraction: {e}")
            raise SystemExit("Exiting due to error in parsing the DIAMOND results file.")

        self.save_mapping_to_file(gene_uniprot_mapping, mapping_file)  # Save the mapping
        return gene_uniprot_mapping

    def save_mapping_to_file(self, mapping, filename):
        """
        Save the gene-to-UniProt mapping dictionary to a file in the intermediate folder.
        
        Args:
            mapping (dict): The gene-to-UniProt mapping dictionary.
            filename (str): The name of the file to save.
        """
        intermediate_folder = self.create_intermediate_folder()
        output_file = os.path.join(intermediate_folder, filename)
        
        try:
            with open(output_file, 'wb') as f:
                pickle.dump(mapping, f)
            logger.info(f"Gene-UniProt mapping saved to {output_file}.")
        except Exception as e:
            logger.error(f"Failed to save mapping to {output_file}: {e}")

    def load_mapping_from_file(self, filename):
        """
        Load the gene-to-UniProt mapping dictionary from a file in the intermediate folder.
        
        Args:
            filename (str): The name of the file to load.
            
        Returns:
            dict: The loaded gene-to-UniProt mapping dictionary.
        """
        intermediate_folder = self.create_intermediate_folder()
        input_file = os.path.join(intermediate_folder, filename)
        
        if not os.path.exists(input_file):
            logger.warning(f"Mapping file not found: {input_file}")
            return None

        try:
            with open(input_file, 'rb') as f:
                mapping = pickle.load(f)
            logger.info(f"Gene-UniProt mapping loaded from {input_file}.")
            # logger.debug(f"First 10 mappings - GENE TO UNIPROT data handler: {list(mapping.items())[:10]}")
            return mapping
        except Exception as e:
            logger.error(f"Failed to load mapping from {input_file}: {e}")
            return None

    def create_intermediate_folder(self):
        """
        Creates the intermediate data folder if it doesn't exist.
        """
        intermediate_folder = os.path.join(self.output_dir, "intermediate_data")
        os.makedirs(intermediate_folder, exist_ok=True)
        logger.info(f"Intermediate data folder: {intermediate_folder}")
        return intermediate_folder

    # -----------------------------------------------------------------------------------
    # run_blast run_diamond
    # -----------------------------------------------------------------------------------   

    def get_gene_uniprot_mapping_from_file(self, file_type, result_file, use_evalue_filtering=True, evalue_threshold=1e-10):
        """
        Extracts gene-to-UniProt mappings from a given result file (BLASTP or DIAMOND).
        
        Args:
            file_type (str): "blast" or "diamond".
            result_file (str): Path to the result file.
            use_evalue_filtering (bool): Apply E-value filtering.
            evalue_threshold (float): Threshold for filtering.

        Returns:
            dict: Gene-to-UniProt mapping.
        """
        if file_type == "blast":
            return self.extract_ids_from_blastp_results(result_file, use_evalue_filtering, evalue_threshold)
        elif file_type == "diamond":
            return self.extract_ids_from_diamond_results(result_file, use_evalue_filtering, evalue_threshold)
        else:
            raise ValueError(f"Invalid file_type: {file_type}. Choose 'blast' or 'diamond'.")
