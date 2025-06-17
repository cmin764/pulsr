from fastapi import Depends
from sqlmodel import Session

from pulsr.core.database import get_session
from pulsr.services.pipeline_service import PipelineService
from pulsr.services.execution_service import ExecutionService


def get_pipeline_service(
    session: Session = Depends(get_session)
) -> PipelineService:
    """Dependency to get pipeline service."""
    return PipelineService(session)


def get_execution_service(
    session: Session = Depends(get_session)
) -> ExecutionService:
    """Dependency to get execution service."""
    return ExecutionService(session)
