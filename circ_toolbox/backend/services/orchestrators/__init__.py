# circ_toolbox/backend/services/orchestrators/__init__.py
# Import specific orchestrators so they’re accessible within the package
'''
from pipeline.orchestrators.orchestrator_srrdatamanager import orchestrator_run_srr_data_manager
from pipeline.orchestrators.orchestrator_bwa import orchestrator_run_bwa_alignment
from pipeline.orchestrators.orchestrator_ciri2 import orchestrator_run_ciri2_processing
from pipeline.orchestrators.orchestrator_quickgo import orchestrator_run_fetch_annotations
from pipeline.orchestrators.orchestrator_uniprot import orchestrator_run_uniprot_preparation


__all__ = ["orchestrator_run_srr_data_manager", "orchestrator_run_bwa_alignment", "orchestrator_run_ciri2_processing", "orchestrator_run_fetch_annotations", "orchestrator_run_uniprot_preparation"]

'''
from circ_toolbox.backend.services.orchestrators.resource_orchestrator import ResourceOrchestrator
from circ_toolbox.backend.services.orchestrators.pipeline_registration_orchestrator import PipelineRegistrationOrchestrator
from circ_toolbox.backend.services.orchestrators.pipeline_execution_orchestrator import PipelineExecutionOrchestrator
from circ_toolbox.backend.services.orchestrators.user_orchestrator import UserOrchestrator

__all__ = ["ResourceOrchestrator", "PipelineRegistrationOrchestrator", "PipelineExecutionOrchestrator", "UserOrchestrator"]
