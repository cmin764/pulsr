from uuid import UUID

from fastapi import APIRouter, Depends, BackgroundTasks, status

from pulsr.models.pipeline import PipelineRun, RetrievePipelineRun
from pulsr.services.pipeline_service import PipelineService
from pulsr.services.execution_service import ExecutionService
from pulsr.api.deps import get_pipeline_service, get_execution_service


router = APIRouter(prefix="/pipelines", tags=["pipeline-runs"])


@router.post("/{pipeline_id}/trigger_run", response_model=RetrievePipelineRun, status_code=status.HTTP_201_CREATED)
async def trigger_pipeline_run(
    pipeline_id: UUID,
    background_tasks: BackgroundTasks,
    service: PipelineService = Depends(get_pipeline_service),
    execution_service: ExecutionService = Depends(get_execution_service)
) -> PipelineRun:
    """Start a new pipeline run."""

    # Create the pipeline run
    pipeline_run = service.trigger_pipeline_run(pipeline_id)

    # For now, we just create the run in pending state
    # In the future, this would trigger actual execution via background tasks
    # background_tasks.add_task(execute_pipeline, pipeline_run.id, execution_service)

    return pipeline_run


@router.get("/{pipeline_id}/runs", response_model=list[PipelineRun])
async def list_pipeline_runs(
    pipeline_id: UUID,
    skip: int = 0,
    limit: int = 100,
    service: PipelineService = Depends(get_pipeline_service)
) -> list[PipelineRun]:
    """List all runs of a pipeline."""
    return service.list_pipeline_runs(pipeline_id, skip=skip, limit=limit)


@router.get("/{pipeline_id}/runs/{run_id}", response_model=RetrievePipelineRun)
async def get_pipeline_run(
    pipeline_id: UUID,
    run_id: UUID,
    service: PipelineService = Depends(get_pipeline_service)
) -> PipelineRun:
    """Get run details with step runs and artifacts."""
    return service.get_pipeline_run(pipeline_id, run_id)


# Future background task function for actual execution
# async def execute_pipeline(pipeline_run_id: UUID, execution_service: ExecutionService):
#     """Execute pipeline in background (future implementation)."""
#     try:
#         execution_service.start_pipeline_execution(pipeline_run_id)
#         # Here we would implement actual step execution logic
#         # For now, we just mark it as completed
#         execution_service.complete_pipeline_execution(pipeline_run_id, PipelineRunStatus.COMPLETED)
#     except Exception as e:
#         execution_service.complete_pipeline_execution(pipeline_run_id, PipelineRunStatus.FAILED)
