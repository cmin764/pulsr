from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlmodel import Field, Relationship
from pydantic import BaseModel

from pulsr.models.base import BaseModel as PulsrBaseModel


class PipelineRunStatus(StrEnum):
    """Pipeline run status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Pipeline(PulsrBaseModel, table=True):
    """Pipeline model representing a workflow definition."""

    name: str = Field(index=True)
    description: str | None = None

    # Relationships
    steps: list["Step"] = Relationship(
        back_populates="pipeline",
        cascade_delete=True
    )
    runs: list["PipelineRun"] = Relationship(
        back_populates="pipeline",
        cascade_delete=False  # Restrict deletion if runs exist
    )


class PipelineRun(PulsrBaseModel, table=True):
    """Pipeline run model representing an execution instance."""

    pipeline_id: UUID = Field(foreign_key="pipeline.id")
    status: PipelineRunStatus = Field(default=PipelineRunStatus.PENDING)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Relationships
    pipeline: Pipeline = Relationship(back_populates="runs")
    step_runs: list["StepRun"] = Relationship(
        back_populates="pipeline_run",
        cascade_delete=True
    )


# Schema models for API
class PipelineCreate(BaseModel):
    """Schema for creating a pipeline."""
    name: str
    description: str | None = None
    steps: list["StepCreate"]
    step_dependencies: list["StepDependencyCreate"] = []


# Import here to avoid circular imports
from pulsr.models.step import Step, StepRun, StepCreate, StepDependencyCreate
