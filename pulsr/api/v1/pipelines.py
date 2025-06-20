from uuid import UUID

from fastapi import APIRouter, Depends, status

from pulsr.models.pipeline import Pipeline, CreatePipeline, RetrievePipeline
from pulsr.services.pipeline_service import PipelineService
from pulsr.api.deps import get_pipeline_service


router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.post("/", response_model=RetrievePipeline, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    pipeline_data: CreatePipeline,
    service: PipelineService = Depends(get_pipeline_service)
) -> Pipeline:
    """Register a new pipeline with steps and dependencies."""
    pipeline = service.create_pipeline(
        name=pipeline_data.name,
        description=pipeline_data.description,
        steps=pipeline_data.steps,
        step_dependencies=pipeline_data.step_dependencies
    )

    return pipeline


@router.get("/", response_model=list[Pipeline])
def list_pipelines(
    skip: int = 0,
    limit: int = 100,
    service: PipelineService = Depends(get_pipeline_service)
) -> list[Pipeline]:
    """List all pipelines."""
    return service.list_pipelines(skip=skip, limit=limit)


@router.get("/{pipeline_id}", response_model=RetrievePipeline)
async def get_pipeline(
    pipeline_id: UUID,
    service: PipelineService = Depends(get_pipeline_service)
) -> Pipeline:
    """Get pipeline details with steps."""
    return service.get_pipeline(pipeline_id)
