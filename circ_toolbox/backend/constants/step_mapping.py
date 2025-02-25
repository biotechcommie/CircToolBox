# circ_toolbox/backend/constants/step_mappings.py

STEP_EXECUTION_ORDER = [
    "SRRDataManager",
    "BWAAligner",
    "CIRI2Processor",
    "UniProtDataPreparer",
    "GOAnnotationFetcher"
]

STEP_ORCHESTRATORS = {
    "SRRDataManager": "circ_toolbox.backend.services.orchestrators.srr_orchestrator.SRROrchestrator",
    "BWAAligner": "circ_toolbox.backend.services.orchestrators.bwa_orchestrator.BWAOrchestrator",
    "CIRI2Processor": "circ_toolbox.backend.services.orchestrators.ciri2_orchestrator.CIRI2Orchestrator",
    "UniProtDataPreparer": "circ_toolbox.backend.services.orchestrators.uniprot_orchestrator.UniProtOrchestrator",
    "GOAnnotationFetcher": "circ_toolbox.backend.services.orchestrators.go_orchestrator.GOOrchestrator",
}

# New global input mapping source-of-truth.
# Each step lists the dependency from which it should fetch a particular input key.
GLOBAL_INPUT_MAPPING = {
    "SRRDataManager": {},  # first step: user input only
    "BWAAligner": {"compact_directory": "SRRDataManager"},
    "CIRI2Processor": {"sam_directory": "BWAAligner"},
    # Additional steps can be added here if needed.
}


def get_step_orchestrator(step_name):
    if step_name not in STEP_ORCHESTRATORS:
        raise ValueError(f"No orchestrator defined for step {step_name}")
    module_path, class_name = STEP_ORCHESTRATORS[step_name].rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)

def ensure_steps_order(steps: list) -> list:
    """
    Ensures that the provided list of pipeline steps is sorted in the correct execution order.
    
    The expected order is defined in STEP_EXECUTION_ORDER. This function will:
      - Sort the steps based on the index in STEP_EXECUTION_ORDER.
      - Verify that the steps form a contiguous block (no missing steps in the sequence).
    
    Args:
        steps (list): List of pipeline step objects. Each must have an attribute 'step_name'.
    
    Returns:
        list: Sorted list of pipeline step objects in the correct execution order.
    
    Raises:
        ValueError: If any step's name is not in STEP_EXECUTION_ORDER or if the steps are not contiguous.
    """
    try:
        steps_with_index = [(step, STEP_EXECUTION_ORDER.index(step.step_name)) for step in steps]
    except ValueError as e:
        raise ValueError(f"One or more steps have invalid names: {e}")

    # Sort steps by index.
    steps_sorted = sorted(steps_with_index, key=lambda x: x[1])
    sorted_steps = [step for step, idx in steps_sorted]

    # Verify that the indices form a contiguous block.
    indices = [idx for step, idx in steps_with_index]
    min_idx, max_idx = min(indices), max(indices)
    expected = list(range(min_idx, max_idx + 1))
    if sorted(indices) != expected:
        raise ValueError("The steps do not form a contiguous execution block.")
    
    return sorted_steps

'''

WE NEED TO BUID A FUNCTION INSIDE PIPELINE MANAGER TO ENFORCE STEPS CORRECT ORDEM IN THE DATABASE INSERTION, AS A FIRST LINE OF DEFENCE. - THIS CAN BE CALLED WHILE REGISTERING A STEP IN DATABASE OR AFTER IT - IT JUST NEED TO BE REUSABLE ENOUGH TO BE USED BY REGISTRATION AND ALSO BY PIPELINE EXECUTION AND ALSO BY CELERY.

WE NEED TO NOT JUST RAISE ERROR IF ORDER IS WRONG IN THE ORCHESTRATOR, BUT TO CALL THIS CORRECTOR FUNCTION IN PIPELINE MANAGER TO ENFORCE CORRECT ORDER.

WE NEED TO ENSURE THAT STEP ORDER IS CORRECT VALIDATING IT AGAIN AFTER CALLING PIPELINE FUNCTION CORRECTOR, AND BEFORE PASSING THE PIPELINE - ID TO THE CELERY TASK.
# REGARDLESS OF BEING TO THE FULL PIPELINE TASK OR THE JUST NEXT STEP TASK. #

WE ALSO CAN EXECUTE THE SAME ENSURE CHECK INSIDE CELERY, USING THE SAME LOGIC, AS THE HIGH - LEVEL ORCHESTRATOR WILL USE - SO MAYBE WE CAN ADD THIS ROUTINE TO THE 'step_mapping' SO IT CAN BE USED IN 'PipelineExecutionOrchestrator' AND ALSO IN 'Celery Task' OR ANY OTHER LOGIC, AS CLI...

WE USE A CENTRALIZED 'circ_toolbox/backend/constants/step_mapping.py' TO DO IT. - THIS ALREADY HAS STEPS MAPPING AND LOW-LEVEL ORCHESTRATORS MAPPING, BUT MUST GAIN THE VERIFICATION, AND DATABASE CORRECTION LOGIC IF NEEDED, AND RE-VERIFICATION AFTER DATABASE CORRECTION.

'''