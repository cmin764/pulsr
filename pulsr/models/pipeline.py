from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel

from pulsr.models.base import BaseModel as PulsrBaseModel
from pulsr.models.step import Step, StepRun, CreateStep, CreateStepDependency, RetrieveStep, RetrieveStepRun


class PipelineRunStatus(StrEnum):
    """Pipeline run status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Base classes with core fields - inherit from SQLModel (no table creation)
class BasePipeline(SQLModel):
    """Base pipeline model with core fields."""
    name: str = Field(index=True)
    description: str | None = None


class BasePipelineRun(SQLModel):
    """Base pipeline run model with core fields."""
    pipeline_id: UUID = Field(foreign_key="pipeline.id")
    status: PipelineRunStatus = Field(default=PipelineRunStatus.PENDING)
    started_at: datetime | None = None
    completed_at: datetime | None = None


# Table models - only these inherit from SQLModel with table=True
class Pipeline(BasePipeline, PulsrBaseModel, table=True):
    """Pipeline table model representing a workflow definition."""

    # Relationships
    steps: list[Step] = Relationship(
        back_populates="pipeline",
        cascade_delete=True
    )
    runs: list["PipelineRun"] = Relationship(
        back_populates="pipeline",
        cascade_delete=False  # Restrict deletion if runs exist
    )


class PipelineRun(BasePipelineRun, PulsrBaseModel, table=True):
    """Pipeline run table model representing an execution instance."""

    # Relationships
    pipeline: Pipeline = Relationship(back_populates="runs")
    step_runs: list[StepRun] = Relationship(
        back_populates="pipeline_run",
        cascade_delete=True
    )


# API schema models - inherit from base classes (no table creation)
class CreatePipeline(BasePipeline):
    """Schema for creating a pipeline."""
    steps: list[CreateStep]
    step_dependencies: list[CreateStepDependency] = []


class RetrievePipeline(BasePipeline):
    """Schema for retrieving a pipeline with steps."""
    id: UUID
    created_at: datetime
    # updated_at: datetime | None
    steps: list[RetrieveStep]


class CreatePipelineRun(BaseModel):
    """Schema for creating a pipeline run (no additional fields needed)."""
    pass


class RetrievePipelineRun(BasePipelineRun):
    """Schema for retrieving a pipeline run with step runs."""
    id: UUID
    created_at: datetime
    # updated_at: datetime | None
    step_runs: list[RetrieveStepRun]
