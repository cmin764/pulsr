from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlmodel import SQLModel, Field, Relationship, JSON
from pydantic import BaseModel

from pulsr.models.base import BaseModel as PulsrBaseModel
from pulsr.models.artifact import Artifact

class StepRunStatus(StrEnum):
    """Step run status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# Base classes with core fields - inherit from SQLModel (no table creation)
class BaseStep(SQLModel):
    """Base step model with core fields."""
    pipeline_id: UUID = Field(foreign_key="pipeline.id")
    name: str = Field(index=True)
    description: str | None = None
    command: str  # Bash command or script path


class BaseStepRun(SQLModel):
    """Base step run model with core fields."""
    step_id: UUID = Field(foreign_key="step.id")
    pipeline_run_id: UUID = Field(foreign_key="pipelinerun.id")
    status: StepRunStatus = Field(default=StepRunStatus.PENDING)
    logs: str | None = None  # stdout/stderr
    step_metadata: dict[str, Any] | None = Field(default={}, sa_type=JSON, alias="metadata")
    started_at: datetime | None = None
    completed_at: datetime | None = None


# Table models - only these inherit from SQLModel with table=True
class Step(BaseStep, PulsrBaseModel, table=True):
    """Step table model representing an atomic unit of work."""

    # Relationships
    pipeline: "Pipeline" = Relationship(back_populates="steps")
    step_runs: list["StepRun"] = Relationship(
        back_populates="step",
        cascade_delete=True
    )

    # Dependencies handled through StepDependency table


class StepRun(BaseStepRun, PulsrBaseModel, table=True):
    """Step run table model representing a step execution instance."""

    # Relationships
    step: Step = Relationship(back_populates="step_runs")
    pipeline_run: "PipelineRun" = Relationship(back_populates="step_runs")
    created_artifacts: list[Artifact] = Relationship(
        back_populates="created_by_step_run",
        cascade_delete=True
    )


class StepDependency(PulsrBaseModel, table=True):
    """Step dependency table model representing step relationships."""

    step_id: UUID = Field(foreign_key="step.id")
    depends_on_step_id: UUID = Field(foreign_key="step.id")


# API schema models - inherit from base classes (no table creation)
class CreateStep(BaseModel):
    """Schema for creating a step."""
    name: str = Field(..., min_length=1, description="Must not be empty")
    description: str | None = None
    command: str = Field(..., min_length=1, description="Must not be empty")


class RetrieveStep(BaseStep):
    """Schema for retrieving a step."""
    id: UUID
    created_at: datetime
    # updated_at: datetime | None


class CreateStepDependency(BaseModel):
    """Schema for creating a step dependency by passing their names."""
    step_name: str
    depends_on_step_name: str


class CreateStepRun(BaseModel):
    """Schema for creating a step run (no additional fields needed)."""
    pass


class RetrieveStepRun(BaseStepRun):
    """Schema for retrieving a step run."""
    id: UUID
    created_at: datetime
    # updated_at: datetime | None
