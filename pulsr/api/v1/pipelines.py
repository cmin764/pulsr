from uuid import UUID

from fastapi import APIRouter, Depends

from pulsr.models.pipeline import Pipeline, PipelineCreate
from pulsr.services.pipeline_service import PipelineService
from pulsr.api.deps import get_pipeline_service


router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.post("/", response_model=Pipeline)
async def create_pipeline(
    pipeline_data: PipelineCreate,
    service: PipelineService = Depends(get_pipeline_service)
) -> Pipeline:
    """Register a new pipeline with steps and dependencies."""

    # Convert step dependencies to the format expected by the service
    step_deps = []
    if pipeline_data.step_dependencies:
        step_deps = [
            {
                "step_id": dep.step_id,
                "depends_on_step_id": dep.depends_on_step_id
            }
            for dep in pipeline_data.step_dependencies
        ]

    # Convert steps to dict format
    steps = [
        {
            "name": step.name,
            "description": step.description,
            "command": step.command
        }
        for step in pipeline_data.steps
    ]

    pipeline = service.create_pipeline(
        name=pipeline_data.name,
        description=pipeline_data.description,
        steps=steps,
        step_dependencies=step_deps
    )

    return pipeline


@router.get("/", response_model=list[Pipeline])
async def list_pipelines(
    skip: int = 0,
    limit: int = 100,
    service: PipelineService = Depends(get_pipeline_service)
) -> list[Pipeline]:
    """List all pipelines."""
    return service.list_pipelines(skip=skip, limit=limit)


@router.get("/{pipeline_id}", response_model=Pipeline)
async def get_pipeline(
    pipeline_id: UUID,
    service: PipelineService = Depends(get_pipeline_service)
) -> Pipeline:
    """Get pipeline details with steps."""
    return service.get_pipeline(pipeline_id)
